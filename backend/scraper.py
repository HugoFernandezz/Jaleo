"""
Scraper de eventos para PartyFinder
===================================
Extrae eventos de discotecas FourVenues usando nodriver para bypassear Cloudflare.

URLs soportadas:
- https://site.fourvenues.com/es/luminata-disco/events
- https://site.fourvenues.com/es/el-club-by-odiseo

Requisitos:
    pip install nodriver beautifulsoup4
    playwright install chromium
"""

import asyncio
import nodriver as uc
import json
import sys
import re
import os
import warnings
from datetime import datetime
from typing import List, Dict, Optional

# Suprimir warnings de asyncio en Windows
warnings.filterwarnings("ignore", category=ResourceWarning)

# Forzar UTF-8 en Windows
if sys.platform == 'win32':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

# URLs de las discotecas a scrapear
VENUE_URLS = [
    "https://site.fourvenues.com/es/luminata-disco/events",
    "https://site.fourvenues.com/es/el-club-by-odiseo/events"
]


async def scrape_single_venue(url: str, browser) -> List[Dict]:
    """
    Scrapea los eventos de una única URL de FourVenues.
    
    Args:
        url: URL de la página de eventos
        browser: Instancia del navegador ya iniciada
    
    Returns:
        list: Lista de eventos encontrados
    """
    print(f"📡 Scrapeando: {url}")
    
    try:
        page = await browser.get(url)
        
        print("⏳ Resolviendo challenge de Cloudflare...")
        
        # Esperar hasta que pase el challenge
        challenge_resolved = False
        for i in range(60):
            await asyncio.sleep(1)
            try:
                title = await page.evaluate("document.title")
            except:
                title = ""
            
            # Verificar si pasó el challenge (título válido y no es página de espera)
            if title and "momento" not in title.lower() and "checking" not in title.lower() and "just" not in title.lower():
                # Verificar que no sea una página vacía
                try:
                    body_length = await page.evaluate("document.body.innerHTML.length")
                    if body_length > 1000:  # La página debe tener contenido sustancial
                        print(f"✅ Challenge resuelto! ({i}s) - Título: {title[:50]}")
                        challenge_resolved = True
                        break
                except:
                    pass
            
            if i % 15 == 0 and i > 0:
                print(f"   Esperando... ({i}s) - Título actual: {title[:30] if title else 'N/A'}")
        
        if not challenge_resolved:
            print("⚠️ Timeout esperando Cloudflare")
            return []
        
        # Esperar más tiempo para que Angular cargue completamente
        print("   Esperando carga de Angular...")
        await asyncio.sleep(8)
        
        # Obtener HTML
        html = await page.get_content()
        
        # Debug: mostrar tamaño del HTML
        print(f"   HTML recibido: {len(html)} bytes")
        
        # Extraer eventos del JSON embebido
        events = extract_events_from_html(html)
        
        if events:
            print(f"✅ {len(events)} eventos encontrados en {url}")
        else:
            print(f"⚠️ No se encontraron eventos en {url}")
            # Guardar HTML para debugging
            venue_name = url.split('/')[-2]
            debug_file = f"data/debug_{venue_name}.html"
            try:
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(html)
                print(f"   Debug: HTML guardado en {debug_file}")
            except Exception as e:
                print(f"   No se pudo guardar debug: {e}")
            
        return events
        
    except Exception as e:
        print(f"💥 Error scrapeando {url}: {type(e).__name__}: {e}")
        return []


async def scrape_event_details(event_url: str, org_slug: str, event_slug: str, event_code: str, browser) -> Dict:
    """
    Scrapea los detalles completos de un evento: info del evento + tickets.
    
    Args:
        event_url: URL completa del evento
        org_slug: Slug de la organización (ej: luminata-disco)
        event_slug: Slug del evento
        event_code: Código del evento
        browser: Instancia del navegador
    
    Returns:
        dict: Diccionario con 'event_info' y 'tickets'
    """
    print(f"   🎫 Obteniendo detalles de: {event_url}")
    
    result = {
        'event_info': None,
        'tickets': []
    }
    
    try:
        page = await browser.get(event_url)
        
        # Esperar carga (el challenge ya debería estar resuelto)
        for i in range(30):
            await asyncio.sleep(1)
            try:
                title = await page.evaluate("document.title")
            except:
                title = ""
            
            if title and "momento" not in title.lower() and "checking" not in title.lower():
                break
        
        # Esperar carga de Angular
        await asyncio.sleep(3)
        
        # Obtener HTML
        html = await page.get_content()
        
        # Extraer tickets y datos del evento
        tickets, event_info = extract_event_data_from_html(html)
        
        # Añadir url_compra a cada ticket
        for ticket in tickets:
            ticket_id = ticket.get('id', '')
            if ticket_id:
                ticket['url_compra'] = f"https://web.fourvenues.com/es/{org_slug}/events/{event_slug}-{event_code}/tickets/{ticket_id}"
            else:
                ticket['url_compra'] = ''
        
        result['tickets'] = tickets
        result['event_info'] = event_info
        
        if tickets:
            print(f"      ✅ {len(tickets)} entradas + info del evento")
        else:
            print(f"      ⚠️ No se encontraron tickets")
            
        return result
        
    except Exception as e:
        print(f"      💥 Error obteniendo detalles: {type(e).__name__}: {e}")
        return result


def extract_event_data_from_html(html: str) -> tuple:
    """
    Extrae los tickets y la información del evento del JSON embebido en el HTML.
    
    Returns:
        tuple: (tickets_list, event_info_dict)
    """
    json_pattern = r'<script[^>]*type=["\']application/json["\'][^>]*>([^<]+)</script>'
    json_matches = re.findall(json_pattern, html, re.DOTALL)
    
    tickets = []
    event_info = None
    
    for json_str in json_matches:
        try:
            data = json.loads(json_str)
            
            if isinstance(data, dict):
                for key in data.keys():
                    value = data[key]
                    
                    if not isinstance(value, dict):
                        continue
                    
                    # Buscar la clave de tickets
                    if 'tickets' in key.lower() and 'data' in value:
                        if isinstance(value['data'], list):
                            tickets = value['data']
                    
                    # Buscar datos del evento (clave que contiene 'event' pero no 'tickets')
                    if 'event' in key.lower() and 'tickets' not in key.lower() and 'lists' not in key.lower():
                        event_info = value.get('data', value)
                        
        except json.JSONDecodeError:
            continue
    
    return tickets, event_info


def extract_events_from_html(html: str) -> List[Dict]:
    """
    Extrae los eventos del JSON embebido en el HTML de Angular.
    
    FourVenues usa Angular con Server State Transfer, los datos están en
    un tag <script type="application/json"> con claves como:
    'transfer-state-events-luminata-disco-1'
    """
    json_pattern = r'<script[^>]*type=["\']application/json["\'][^>]*>([^<]+)</script>'
    json_matches = re.findall(json_pattern, html, re.DOTALL)
    
    for json_str in json_matches:
        try:
            data = json.loads(json_str)
            
            # Buscar claves que contengan 'events'
            for key in data.keys():
                if 'events' in key.lower() and isinstance(data[key], dict):
                    if 'data' in data[key] and isinstance(data[key]['data'], list):
                        return data[key]['data']
                        
        except json.JSONDecodeError:
            continue
    
    return []


def get_chromium_path() -> Optional[str]:
    """Busca el ejecutable de Chromium según el sistema operativo."""
    import platform
    
    if platform.system() == 'Linux':
        # Raspberry Pi / Linux - buscar Chromium del sistema
        linux_paths = [
            '/usr/bin/chromium-browser',  # Raspberry Pi OS / Debian
            '/usr/bin/chromium',           # Algunas distros
            '/usr/bin/google-chrome',      # Chrome instalado
            '/snap/bin/chromium',          # Snap
        ]
        for path in linux_paths:
            if os.path.exists(path):
                return path
                
    elif platform.system() == 'Windows':
        # Windows - buscar Playwright Chromium o Chrome
        localappdata = os.environ.get('LOCALAPPDATA', '')
        
        # Primero buscar Playwright Chromium
        pw_dir = os.path.join(localappdata, 'ms-playwright')
        if os.path.exists(pw_dir):
            for item in os.listdir(pw_dir):
                if item.startswith('chromium-'):
                    potential_path = os.path.join(pw_dir, item, 'chrome-win64', 'chrome.exe')
                    if os.path.exists(potential_path):
                        return potential_path
        
        # Luego buscar Chrome del sistema
        chrome_paths = [
            os.path.join(localappdata, 'Google', 'Chrome', 'Application', 'chrome.exe'),
            r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        ]
        for path in chrome_paths:
            if os.path.exists(path):
                return path
                
    elif platform.system() == 'Darwin':
        # macOS
        mac_paths = [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
        ]
        for path in mac_paths:
            if os.path.exists(path):
                return path
    
    return None


async def scrape_all_events(urls: List[str] = None, scrape_tickets: bool = True) -> List[Dict]:
    """
    Scrapea eventos de todas las URLs configuradas.
    
    Args:
        urls: Lista de URLs a scrapear (usa VENUE_URLS por defecto)
        scrape_tickets: Si True, también scrapea los tickets de cada evento
    
    Returns:
        list: Lista combinada de todos los eventos con tickets
    """
    target_urls = urls or VENUE_URLS
    all_events = []
    
    print("🚀 Iniciando navegador...")
    
    try:
        chrome_path = get_chromium_path()
        
        if chrome_path:
            print(f"   Usando Chromium: {chrome_path}")
            browser = await uc.start(
                headless=False,
                browser_executable_path=chrome_path,
                browser_args=['--no-sandbox', '--disable-dev-shm-usage']
            )
        else:
            print("   Usando Chrome del sistema...")
            browser = await uc.start(
                headless=False,
                browser_args=['--no-sandbox', '--disable-dev-shm-usage']
            )
        
        # Scrapear cada URL de venue
        for url in target_urls:
            events = await scrape_single_venue(url, browser)
            all_events.extend(events)
            
            # Pequeña pausa entre venues
            if url != target_urls[-1]:
                await asyncio.sleep(2)
        
        # Si se solicita, scrapear detalles de cada evento (tickets + info)
        if scrape_tickets and all_events:
            print(f"\n🎫 Scrapeando detalles de {len(all_events)} eventos...")
            
            for event in all_events:
                org = event.get('organization', {})
                org_slug = org.get('slug', '')
                event_slug = event.get('slug', '')
                event_code = event.get('code', '')
                
                if org_slug and event_slug:
                    event_url = f"https://site.fourvenues.com/es/{org_slug}/events/{event_slug}-{event_code}"
                    
                    details = await scrape_event_details(
                        event_url, org_slug, event_slug, event_code, browser
                    )
                    
                    # Guardar los tickets y la info del evento
                    event['_scraped_tickets'] = details.get('tickets', [])
                    event['_scraped_event_info'] = details.get('event_info')
                    
                    # Pequeña pausa entre eventos
                    await asyncio.sleep(1)
        
        browser.stop()
        
    except FileNotFoundError:
        print("""
❌ Error: No se encontró el navegador Chrome/Chromium.

Soluciones:
1. Instalar Chromium de Playwright:
   > pip install playwright
   > playwright install chromium

2. O instalar Google Chrome:
   > Descargar de https://www.google.com/chrome/
""")
        return []
    except Exception as e:
        print(f"💥 Error general: {type(e).__name__}: {e}")
        return []
    
    print(f"\n🎉 Total: {len(all_events)} eventos scrapeados de {len(target_urls)} venues")
    return all_events


def transform_to_app_format(events: List[Dict]) -> List[Dict]:
    """
    Transforma los eventos scrapeados al formato que espera la app PartyFinder.
    
    Args:
        events: Lista de eventos en formato FourVenues
    
    Returns:
        list: Lista de eventos en formato de la app
    """
    transformed = []
    
    for event in events:
        # Extraer datos del venue/organización
        org = event.get('organization', {})
        location = event.get('location', {})
        
        # Obtener información scrapeada del evento (si existe)
        scraped_info = event.get('_scraped_event_info', {}) or {}
        
        # Extraer fecha y horas - Priorizar datos scrapeados (más precisos)
        # Los datos scrapeados tienen 'start' y 'end' directamente, no en 'dates'
        start_timestamp = scraped_info.get('start') or event.get('dates', {}).get('start')
        end_timestamp = scraped_info.get('end') or event.get('dates', {}).get('end')
        date_timestamp = scraped_info.get('date') or event.get('dates', {}).get('date') or start_timestamp
        
        fecha = datetime.now().strftime('%Y-%m-%d')
        hora_inicio = "23:00"
        hora_fin = "06:00"
        
        if date_timestamp:
            try:
                dt = datetime.fromtimestamp(date_timestamp)
                fecha = dt.strftime('%Y-%m-%d')
            except:
                pass
        
        if start_timestamp:
            try:
                dt = datetime.fromtimestamp(start_timestamp)
                hora_inicio = dt.strftime('%H:%M')
            except:
                pass
        
        if end_timestamp:
            try:
                dt = datetime.fromtimestamp(end_timestamp)
                hora_fin = dt.strftime('%H:%M')
            except:
                pass
        
        # Extraer imagen - Priorizar la imagen scrapeada del evento
        scraped_images = scraped_info.get('images', {})
        image_url = (
            scraped_info.get('image') or 
            event.get('image') or 
            scraped_images.get('medium') or 
            scraped_images.get('small') or 
            event.get('images', {}).get('main') or 
            org.get('images', {}).get('main', '')
        )
        
        # Extraer información adicional del evento scrapeado
        dress_code = scraped_info.get('dressCode', '')
        age_min = scraped_info.get('age') or event.get('age', 18)
        
        # Extraer ubicación detallada
        scraped_location = scraped_info.get('location', {}) or {}
        full_address = (
            scraped_location.get('fullAddress') or 
            location.get('addressComplete') or 
            location.get('address', '')
        )
        latitude = scraped_location.get('latitude')
        longitude = scraped_location.get('longitude')
        
        # Extraer tickets - Usar los scrapeados si existen, si no los del listado
        scraped_tickets = event.get('_scraped_tickets', [])
        listing_tickets = event.get('ticketing', {}).get('tickets', [])
        
        entradas = []
        
        # Priorizar tickets scrapeados (tienen url_compra)
        if scraped_tickets:
            for ticket in scraped_tickets:
                # Extraer precio (puede venir como string con € o como número)
                price_raw = ticket.get('price', 0)
                if isinstance(price_raw, str):
                    price_raw = price_raw.replace('€', '').replace(',', '.').strip()
                try:
                    price = float(price_raw)
                except:
                    price = 0
                
                entrada = {
                    "id": ticket.get('id', ''),
                    "tipo": ticket.get('name', 'Entrada General'),
                    "descripcion": ticket.get('description', ''),
                    "precio": str(price),
                    "precio_completo": ticket.get('priceComplete', ''),
                    "agotadas": ticket.get('isSoldOut', False),
                    "quedan_pocas": ticket.get('areFewLeft', False),
                    "url_compra": ticket.get('url_compra', ''),
                    "tipo_entrada": ticket.get('type', 'publica'),
                    "cashless": ticket.get('isCashlessActive', False)
                }
                entradas.append(entrada)
        
        # Si no hay tickets scrapeados, usar los del listado
        elif listing_tickets:
            for ticket in listing_tickets:
                entrada = {
                    "tipo": ticket.get('name', 'Entrada General'),
                    "descripcion": ticket.get('description', ''),
                    "precio": str(ticket.get('price', 0)),
                    "agotadas": ticket.get('soldOut', False) or ticket.get('status') == 'soldout',
                    "quedan_pocas": ticket.get('fewLeft', False),
                    "url_compra": ticket.get('purchaseUrl', '')
                }
                entradas.append(entrada)
        
        # Si no hay tickets, crear uno genérico
        if not entradas:
            entradas = [{
                "tipo": "Entrada General",
                "descripcion": "",
                "precio": "0",
                "agotadas": False,
                "quedan_pocas": False,
                "url_compra": event.get('purchaseUrl', '')
            }]
        
        # Extraer tags/géneros
        tags = []
        if event.get('musicGenres'):
            for g in event.get('musicGenres', []):
                if isinstance(g, dict) and g.get('name'):
                    tags.append(g.get('name'))
                elif isinstance(g, str) and g:
                    tags.append(g)
        if event.get('styles'):
            for s in event.get('styles', []):
                if isinstance(s, dict) and s.get('name'):
                    tags.append(s.get('name'))
                elif isinstance(s, str) and s:
                    tags.append(s)
        if event.get('genres'):
            for g in event.get('genres', []):
                if isinstance(g, dict) and g.get('name'):
                    tags.append(g.get('name'))
                elif isinstance(g, str) and g:
                    tags.append(g)
        if not tags:
            tags = ['Fiesta']
        
        # Construir URL del evento
        org_slug = org.get('slug', '')
        event_slug = event.get('slug', '')
        event_code = event.get('code', '')
        url_evento = f"https://site.fourvenues.com/es/{org_slug}/events/{event_slug}-{event_code}" if org_slug and event_slug else ""
        
        # Construir objeto transformado con TODA la información
        transformed_event = {
            "evento": {
                "nombreEvento": event.get('name', 'Evento'),
                "descripcion": scraped_info.get('description') or event.get('description', ''),
                "fecha": fecha,
                "hora_inicio": hora_inicio,
                "hora_fin": hora_fin,
                "imagen_url": image_url,
                "url_evento": url_evento,
                "url_entradas": event.get('purchaseUrl', ''),
                "code": event_code,
                "entradas": entradas,
                "tags": tags,
                "aforo": event.get('capacity', 500),
                "entradas_vendidas": event.get('soldTickets', 0),
                "edad_minima": age_min,
                "codigo_vestimenta": dress_code,
                "lugar": {
                    "nombre": org.get('name', 'Venue'),
                    "descripcion": org.get('description', ''),
                    "direccion": full_address,
                    "direccion_corta": scraped_location.get('address', '') or location.get('address', ''),
                    "ciudad": scraped_location.get('city') or location.get('city', ''),
                    "codigo_postal": scraped_location.get('postalCode', ''),
                    "latitud": latitude,
                    "longitud": longitude,
                    "imagen_url": org.get('image', '') or org.get('images', {}).get('main', ''),
                    "imagen_portada": org.get('cover') or org.get('coverImage', ''),
                    "sitio_web": org.get('website', ''),
                    "telefono": org.get('phone', ''),
                    "categoria": "Discoteca"
                }
            }
        }
        
        transformed.append(transformed_event)
    
    return transformed


async def scrape_and_save(upload_to_firebase: bool = False):
    """
    Ejecuta el scraping completo y guarda los resultados.
    
    Args:
        upload_to_firebase: Si True, sube los datos a Firebase Firestore
    """
    print("=" * 60)
    print("PartyFinder - Scraper de Eventos")
    print("=" * 60)
    
    # Scrapear eventos
    raw_events = await scrape_all_events()
    
    if not raw_events:
        print("No se encontraron eventos")
        return []
    
    # Transformar al formato de la app
    transformed_events = transform_to_app_format(raw_events)
    
    # Guardar datos crudos
    with open('data/raw_events.json', 'w', encoding='utf-8') as f:
        json.dump(raw_events, f, indent=2, ensure_ascii=False)
    print(f"Datos crudos guardados en data/raw_events.json")
    
    # Guardar datos transformados
    with open('data/events.json', 'w', encoding='utf-8') as f:
        json.dump(transformed_events, f, indent=2, ensure_ascii=False)
    print(f"Datos transformados guardados en data/events.json")
    
    # Subir a Firebase si se solicita
    if upload_to_firebase:
        print("\nSubiendo datos a Firebase...")
        try:
            from firebase_config import upload_events_to_firestore, delete_old_events
            
            # Eliminar eventos antiguos primero
            delete_old_events()
            
            # Subir nuevos eventos
            if upload_events_to_firestore(transformed_events):
                print("Datos subidos a Firebase correctamente")
            else:
                print("Error subiendo a Firebase (datos guardados localmente)")
        except ImportError:
            print("Firebase no configurado (firebase_config.py no encontrado)")
        except Exception as e:
            print(f"Error con Firebase: {e}")
    
    return transformed_events


def main():
    """Punto de entrada principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Scraper de eventos PartyFinder',
        epilog='Scrapea eventos de Luminata Disco y El Club by Odiseo'
    )
    parser.add_argument(
        '--urls', 
        nargs='+',
        default=VENUE_URLS,
        help='URLs de venues a scrapear'
    )
    parser.add_argument(
        '--firebase',
        action='store_true',
        help='Subir datos a Firebase Firestore'
    )
    
    args = parser.parse_args()
    
    # Crear directorio data si no existe
    os.makedirs('data', exist_ok=True)
    
    try:
        events = asyncio.run(scrape_and_save(upload_to_firebase=args.firebase))
        if events:
            print(f"\nScraping completado: {len(events)} eventos")
        return events
    except KeyboardInterrupt:
        print("\nCancelado por el usuario")
        return []


if __name__ == "__main__":
    main()
