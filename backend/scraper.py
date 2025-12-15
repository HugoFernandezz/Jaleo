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
    "https://site.fourvenues.com/es/el-club-by-odiseo/events",
    "https://site.fourvenues.com/es/dodo-club/events"
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
            if title and "momento" not in title.lower() and "checking" not in title.lower() and "just" not in title.lower() and "hang" not in title.lower() and "wait" not in title.lower() and "sec" not in title.lower():
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
        # Aumentado para dispositivos lentos (Raspberry Pi)
        print("   Esperando carga de Angular...")
        await asyncio.sleep(20)
        
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
        
        # Esperar carga de Angular (aumentado para Raspberry Pi)
        await asyncio.sleep(5)
        
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
    """
    Busca el ejecutable de Chromium según el sistema operativo.
    
    IMPORTANTE: Si Playwright está instalado o estamos en CI, devuelve None 
    para que nodriver use automáticamente Playwright's Chromium interno.
    """
    import platform
    
    # En CI (GitHub Actions), SIEMPRE devolver None para usar Playwright
    # nodriver usará automáticamente su Playwright interno
    if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
        print("   [INFO] Entorno CI detectado, usando Playwright interno de nodriver")
        return None
    
    # En Linux, verificar si Playwright Chromium está instalado
    if platform.system() == 'Linux':
        try:
            home = os.path.expanduser("~")
            pw_cache = os.path.join(home, ".cache", "ms-playwright")
            if os.path.exists(pw_cache):
                for item in os.listdir(pw_cache):
                    if item.startswith("chromium-"):
                        pw_chrome = os.path.join(pw_cache, item, "chrome-linux", "chrome")
                        if os.path.exists(pw_chrome):
                            print(f"   [INFO] Playwright Chromium encontrado, usando automáticamente")
                            return None  # nodriver usará Playwright automáticamente
        except:
            pass
        
        # Si no hay Playwright, buscar en sistema
        linux_paths = [
            '/usr/bin/chromium-browser',
            '/usr/bin/chromium',
            '/usr/bin/google-chrome',
            '/snap/bin/chromium',
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


async def start_browser_with_retry(chrome_path: Optional[str], max_retries: int = 3) -> tuple:
    """
    Inicia el navegador con reintentos y backoff exponencial.
    Específicamente diseñado para manejar la lentitud de ARM64/Raspberry Pi.
    
    Args:
        chrome_path: Ruta al ejecutable de Chromium
        max_retries: Número máximo de reintentos
    
    Returns:
        tuple: (browser, success)
    """
    import platform
    import tempfile
    import shutil
    
    is_arm = platform.machine().lower() in ('aarch64', 'arm64', 'armv7l')
    
    # Crear directorio dedicado para el perfil de usuario
    user_data_dir = os.path.join(tempfile.gettempdir(), 'nodriver_profile_partyfinder')
    
    # Limpiar directorio de perfil previo si existe (evita conflictos)
    if os.path.exists(user_data_dir):
        try:
            shutil.rmtree(user_data_dir)
        except:
            pass
    
    # Argumentos base para el navegador
    base_args = [
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-setuid-sandbox',
        '--disable-extensions',
        '--disable-plugins',
        '--window-size=1920,1080',
        '--no-first-run',
        '--no-default-browser-check',
    ]
    
    # Argumentos adicionales para ARM64 (Raspberry Pi)
    # NOTA: --single-process causa problemas de conexión, no usar
    if is_arm:
        base_args.extend([
            '--disable-accelerated-2d-canvas',
            '--disable-software-rasterizer',
            '--disable-features=VizDisplayCompositor',
            '--disable-background-networking',
            '--disable-background-timer-throttling',
            '--disable-renderer-backgrounding',
            '--memory-pressure-off',  # Desactiva gestión de memoria agresiva
        ])
        print(f"   [INFO] Detectado ARM64 - usando configuración optimizada para Raspberry Pi")
    
    for attempt in range(max_retries):
        try:
            wait_time = 3 * (attempt + 1)  # 3s, 6s, 9s - más tiempo en ARM
            
            if attempt > 0:
                print(f"   ⏳ Reintento {attempt + 1}/{max_retries} (esperando {wait_time}s)...")
                await asyncio.sleep(wait_time)
                
                # Limpiar procesos zombie de Chrome/Chromium en ARM
                if is_arm:
                    try:
                        os.system("pkill -9 -f 'chrome.*--remote-debugging' 2>/dev/null")
                        await asyncio.sleep(1)
                    except:
                        pass
            
            # Usar puerto fijo para evitar problemas de detección
            debug_port = 9222 + attempt  # 9222, 9223, 9224 por si hay conflictos
            
            print(f"   [INFO] Intentando puerto {debug_port}...")
            
            if chrome_path:
                print(f"   Usando Chromium: {chrome_path}")
                browser = await uc.start(
                    headless=False,  # Con Xvfb, headless=False funciona mejor
                    browser_executable_path=chrome_path,
                    browser_args=base_args,
                    user_data_dir=user_data_dir,
                    port=debug_port,
                    sandbox=False,  # CRÍTICO para Linux/Raspberry Pi
                )
            else:
                print("   Usando Chrome del sistema...")
                browser = await uc.start(
                    headless=True,
                    browser_args=base_args,
                    user_data_dir=user_data_dir,
                    port=debug_port,
                    sandbox=False,  # CRÍTICO para Linux/Raspberry Pi
                )
            
            # Espera adicional en ARM para asegurar que el navegador está listo
            if is_arm:
                print("   [INFO] Esperando estabilización del navegador en ARM (5s)...")
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(1)
            
            print("   ✅ Conexión establecida con el navegador")
            return browser, True
            
        except Exception as e:
            error_msg = str(e)
            print(f"   ⚠️ Intento {attempt + 1} fallido: {type(e).__name__}: {error_msg[:100]}")
            
            # Si es el último intento, lanzar excepción con contexto
            if attempt == max_retries - 1:
                raise Exception(f"No se pudo conectar al navegador después de {max_retries} intentos. Último error: {error_msg}")
    
    return None, False



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
    
    # Debug logging
    import json as _json
    _log_path = os.path.expanduser("~/PartyFinder/debug.log")
    def _debug_log(hyp, msg, data=None):
        try:
            with open(_log_path, "a") as f:
                f.write(_json.dumps({"hypothesisId": hyp, "message": msg, "data": data, "timestamp": __import__('time').time()}) + "\n")
        except: pass
    
    try:
        chrome_path = get_chromium_path()
        _debug_log("INIT", "Starting browser", {"chrome_path": chrome_path})
        
        # Iniciar navegador con reintentos
        browser, success = await start_browser_with_retry(chrome_path, max_retries=3)
        
        if not success or browser is None:
            print("❌ No se pudo iniciar el navegador después de varios intentos")
            return []
        
        _debug_log("SUCCESS", "Browser started successfully!")
        print("   ✅ Navegador iniciado correctamente")
        
        # Scrapear cada URL de venue
        for url in target_urls:
            events = await scrape_single_venue(url, browser)
            all_events.extend(events)
            
            # Pausa entre venues (aumentada para evitar detección)
            if url != target_urls[-1]:
                await asyncio.sleep(5)
        
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
                    
                    # Pausa entre eventos (aumentada para evitar rate limiting)
                    await asyncio.sleep(2)
        
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
        import traceback as _tb
        _full_error = _tb.format_exc()
        _debug_log("ERROR", "Exception caught", {"type": type(e).__name__, "message": str(e), "traceback": _full_error})
        print(f"   [DEBUG] Full traceback:\n{_full_error}")
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
                
                # Extraer descripción de options (FourVenues la guarda ahí)
                options = ticket.get('options', [])
                descripcion = ''
                info_adicional = ''
                if options and len(options) > 0:
                    first_option = options[0]
                    descripcion = first_option.get('content', '')
                    info_adicional = first_option.get('additionalInfo', '')
                
                # Combinar descripción e info adicional si existen
                descripcion_completa = descripcion
                if info_adicional:
                    descripcion_completa = f"{descripcion}\n{info_adicional}".strip() if descripcion else info_adicional
                
                entrada = {
                    "id": ticket.get('id', ''),
                    "tipo": ticket.get('name', 'Entrada General'),
                    "descripcion": descripcion_completa,
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
