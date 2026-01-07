#!/usr/bin/env python3
"""
Scraper de eventos para PartyFinder usando Firecrawl - VERSIÓN DESARROLLO
=========================================================================
Esta versión es INDEPENDIENTE del scraper de producción (scraper_firecrawl.py).
Envía los datos a la colección 'eventos-dev' en Firebase.

Utiliza Firecrawl para bypass Cloudflare y extrae eventos del HTML.

Este scraper se usa para probar cambios antes de migrarlos a producción.
No requiere navegador local ya que utiliza la API de Firecrawl.

Uso:
    python3 scraper_firecrawl_dev.py                    # Scraping completo
    python3 scraper_firecrawl_dev.py --test             # Solo test de conexión
    python3 scraper_firecrawl_dev.py --upload           # Scraping + Firebase (eventos-dev)
"""

import json
import os
import re
import sys
import copy
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from bs4 import BeautifulSoup

# #region agent log
# Configuración de logging para debug
LOG_PATH = Path(__file__).parent.parent / ".cursor" / "debug.log"
def debug_log(session_id, run_id, hypothesis_id, location, message, data):
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        log_entry = {
            "sessionId": session_id,
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
        # Escribir a archivo
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            f.flush()  # Forzar escritura inmediata
        # También imprimir en stdout para GitHub Actions
        print(f"[DEBUG {hypothesis_id}] {location}: {message}", file=sys.stdout)
        if 'precio' in str(data).lower() or 'price' in str(data).lower():
            print(f"  → Precio data: {json.dumps(data, ensure_ascii=False)}", file=sys.stdout)
    except Exception as e:
        # Imprimir error para debugging si falla el logging
        print(f"[DEBUG LOG ERROR] {e}", file=sys.stderr)
# #endregion

# Intentar importar firecrawl
try:
    from firecrawl import Firecrawl
except ImportError:
    print("❌ Error: firecrawl-py no está instalado")
    print("   Instalar con: pip install firecrawl-py")
    sys.exit(1)

# Configuración
API_KEY = os.environ.get("FIRECRAWL_API_KEY")
if not API_KEY:
    print("WARNING: Faltan credenciales: FIRECRAWL_API_KEY")
    # No fallar inmediatamente, permitir que el script intente otras cosas o falle más adelante si es crítico

DATA_DIR = Path(__file__).parent / "data"

# URLs de las discotecas a scrapear
# TEMPORAL: Solo Sala REM para debugging. Cuando funcione, volver a añadir las otras discotecas.
VENUE_URLS = [
    "https://web.fourvenues.com/es/sala-rem/events"
]

# ============================================================================
# FUNCIONES DE UTILIDAD CENTRALIZADAS
# ============================================================================

# Patrones de URLs inválidas (plantillas de JavaScript, código, etc.)
INVALID_URL_PATTERNS = [
    r'\$\*\*\*',           # Plantillas de template $***
    r'Message\.',          # Código JavaScript Message.
    r'evento_slug',        # Variables de template
    r'evento_codigo',       # Variables de template
    r'function\s*\(',      # Código JavaScript
    r'window\.',            # Código JavaScript
    r'var\s+\w+\s*=',       # Declaraciones de variables
    r'createelement',       # Código JavaScript
]


def is_valid_event_url(url: str, code: str = None) -> bool:
    """
    Valida que una URL de evento sea real y no una plantilla de JS.
    
    Checks:
    1. No contiene patrones de código JS
    2. Tiene código alfanumérico de 4+ caracteres (si se proporciona)
    3. Contiene '/events/' en el path
    4. No está vacía
    5. No contiene caracteres inválidos en el slug
    
    Args:
        url: URL a validar
        code: Código extraído (opcional, para validación adicional)
    
    Returns:
        True si la URL es válida, False en caso contrario
    """
    if not url or len(url) < 10:
        return False
    
    # Verificar que contiene /events/
    if '/events/' not in url:
        return False
    
    # Verificar patrones inválidos
    for pattern in INVALID_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return False
    
    # Extraer slug y validar
    if '/events/' in url:
        url_slug = url.split('/events/')[-1].split('?')[0].split('#')[0].strip()
        if not url_slug:
            return False
        
        # Validar que el slug no contiene caracteres inválidos
        invalid_chars = ['$***', 'Message.', 'evento_', 'function', 'window']
        if any(invalid_char in url_slug for invalid_char in invalid_chars):
            return False
    
    # Si se proporciona código, validar que es alfanumérico y tiene 4+ caracteres
    if code:
        if not code.replace('-', '').isalnum() or len(code.replace('-', '')) < 4:
            return False
    
    return True


def extract_code_from_url(url: str, venue_slug: str) -> Optional[str]:
    """
    Extrae el código de evento de una URL de forma centralizada.
    
    Maneja múltiples formatos:
    - Sala REM: /events/slug--fecha-CODIGO o slug-fecha-CODIGO
      Ejemplos: friday-session--sala-rem--09-01-2026-HZOY
                jueves-universitario-08-01-20261-5YTV
    - Otros venues: /events/CODIGO
      Ejemplo: /events/LKB5
    
    Args:
        url: URL del evento
        venue_slug: Slug del venue (ej: 'sala-rem', 'luminata-disco')
    
    Returns:
        Código del evento o None si no se puede extraer
    """
    if not url or '/events/' not in url:
        return None
    
    is_sala_rem = 'sala-rem' in venue_slug.lower()
    
    if is_sala_rem:
        # PATRÓN 1: Código después de fecha (DD-MM-YYYY seguido de posibles dígitos y luego el código)
        # Ejemplos: -08-01-20261-5YTV, --09-01-2026-HZOY, -10-01-2026-XTNE
        match = re.search(r'/(?:-{1,2})?\d{1,2}-\d{2}-\d{4}\d*-([A-Z0-9]{4,})(?:/|$)', url)
        if match:
            return match.group(1)
        
        # PATRÓN 2: Fallback - extraer del final de la URL
        slug_match = re.search(r'/events/([^/]+)(?:/|$)', url)
        if slug_match:
            slug = slug_match.group(1)
            parts = slug.split('-')
            
            if len(parts) > 0:
                # Intentar con el último segmento
                last_part = parts[-1]
                if last_part.isalnum() and len(last_part) >= 4:
                    return last_part
                
                # Intentar con los últimos 2 segmentos (por si hay dígitos extra)
                if len(parts) >= 2:
                    potential_code = '-'.join(parts[-2:])
                    if potential_code.replace('-', '').isalnum() and len(potential_code.replace('-', '')) >= 4:
                        return potential_code
    else:
        # Formato estándar: /events/CODIGO
        match = re.search(r'/events/([A-Z0-9-]+)(?:/|$)', url)
        if match:
            return match.group(1)
    
    return None


def extract_from_html_links(soup: BeautifulSoup, venue_slug: str) -> List[Dict]:
    """
    Extrae eventos desde enlaces <a> con aria-label o href.
    ESTRATEGIA 1: Para Luminata, Odiseo y Sala REM.
    """
    events = []
    is_sala_rem = 'sala-rem' in venue_slug.lower()
    
    if is_sala_rem:
        event_links = soup.find_all('a', href=lambda x: x and '/events/' in x)
    else:
        event_links = soup.find_all('a', href=lambda x: x and '/events/' in x and x.count('/') >= 4)
    
    for link in event_links:
        try:
            href = link.get('href', '')
            aria_label = link.get('aria-label', '')
            
            if not is_sala_rem and (not aria_label or 'Evento' not in aria_label):
                continue
            
            event = {
                'url': href,
                'venue_slug': venue_slug,
                'image': link.find('img').get('src', '') if link.find('img') else ''
            }
            
            event['code'] = extract_code_from_url(href, venue_slug)
            if not event['code']:
                continue
            
            if aria_label:
                name_match = re.search(r'Evento\s*:\s*(.+?)(?:\.\s*Edad|\s*$)', aria_label)
                if name_match:
                    event['name'] = name_match.group(1).strip()
                
                age_match = re.search(r'Edad mínima:\s*(.+?)(?:\.\s*Fecha|\s*$)', aria_label)
                if age_match:
                    event['age_info'] = age_match.group(1).strip()
                    num_match = re.search(r'(\d+)', age_match.group(1))
                    if num_match:
                        event['age_min'] = int(num_match.group(1))
                
                fecha_match = re.search(r'Fecha:\s*(.+?)(?:\.\s*Horario|\s*$)', aria_label)
                if fecha_match:
                    event['date_text'] = fecha_match.group(1).strip()
                
                horario_match = re.search(r'Horario:\s*de\s*(\d{1,2}:\d{2})\s*a\s*(\d{1,2}:\d{2})', aria_label)
                if horario_match:
                    event['hora_inicio'] = horario_match.group(1)
                    event['hora_fin'] = horario_match.group(2)
            
            if is_sala_rem and not event.get('name'):
                link_text = link.get_text(strip=True)
                if link_text and len(link_text) > 5:
                    event['name'] = link_text[:100]
                else:
                    parent = link.find_parent()
                    if parent:
                        parent_text = parent.get_text(strip=True)
                        if parent_text and len(parent_text) > 5:
                            event['name'] = parent_text[:100]
            
            if event.get('name') and event.get('code'):
                events.append(event)
        except:
            continue
    
    return events


def extract_from_custom_components(soup: BeautifulSoup, venue_slug: str) -> List[Dict]:
    """
    Busca data-testid y componentes custom (Dodo Club style).
    ESTRATEGIA 2: Para venues con componentes personalizados.
    """
    events = []
    event_cards = soup.find_all(attrs={"data-testid": ["event-card", "event-card-name"]})
    if not event_cards:
        event_cards = soup.find_all('div', class_=lambda x: x and 'event' in x and 'card' in x)
    
    for card in event_cards:
        try:
            link_elem = card.find_parent('a') or card.find('a') or (card if card.name == 'a' else None)
            if not link_elem:
                continue
            
            href = link_elem.get('href', '')
            if not href or '/events/' not in href:
                continue
            
            code = extract_code_from_url(href, venue_slug)
            if not code:
                continue
            
            event = {
                'url': href,
                'venue_slug': venue_slug,
                'name': card.get_text(strip=True) if card.name != 'a' else link_elem.get('aria-label', 'Evento'),
                'code': code
            }
            events.append(event)
        except:
            continue
    
    return events


def extract_from_raw_html(html: str, venue_slug: str) -> List[Dict]:
    """
    Busca URLs directamente en el HTML raw/renderizado.
    ESTRATEGIA: Extracción de URLs reales del HTML/rawHtml.
    """
    events = []
    soup = BeautifulSoup(html, 'html.parser')
    
    # Buscar enlaces <a> reales
    soup_links = soup.find_all('a', href=True)
    soup_event_urls = []
    for link in soup_links:
        href = link.get('href', '')
        if href and 'sala-rem' in href.lower() and '/events/' in href:
            soup_event_urls.append(href)
    
    # Buscar URLs con regex
    html_event_urls = []
    html_event_urls += re.findall(r'https?://[^\s"\'<>\)]+sala-rem/events/[^\s"\'<>\)]+', html, re.IGNORECASE)
    html_event_urls += re.findall(r'/es/sala-rem/events/[^\s"\'<>\)]+', html, re.IGNORECASE)
    html_event_urls += re.findall(r'/sala-rem/events/[^\s"\'<>\)]+', html, re.IGNORECASE)
    html_event_urls += re.findall(r'(?:href|data-href|data-url|url|link|to|path)["\']?\s*[:=]\s*["\']?([^"\']*sala-rem/events/[^"\']+)', html, re.IGNORECASE)
    html_event_urls += re.findall(r'["\']([^"\']*sala-rem/events/[^"\']+)["\']', html, re.IGNORECASE)
    html_event_urls += re.findall(r'(?:data-|aria-)\w+["\']?\s*[:=]\s*["\']?([^"\']*sala-rem/events/[^"\']+)', html, re.IGNORECASE)
    html_event_urls += re.findall(r'(?:url|href|link|path)\s*[:=]\s*([^\s,;\)]+sala-rem/events/[^\s,;\)]+)', html, re.IGNORECASE)
    html_event_urls += re.findall(r'sala-rem/events/[a-zA-Z0-9\-_/]+', html, re.IGNORECASE)
    
    html_event_urls = list(set(html_event_urls + soup_event_urls))
    
    unique_urls = []
    seen_slugs = set()
    for event_url in html_event_urls:
        event_url = event_url.strip().strip('"').strip("'").strip()
        if not event_url or len(event_url) < 10:
            continue
        
        if not is_valid_event_url(event_url):
            continue
        
        if not event_url.startswith('http'):
            if event_url.startswith('/'):
                event_url = f"https://web.fourvenues.com{event_url}"
            else:
                event_url = f"https://web.fourvenues.com/{event_url}"
        
        if '/events/' not in event_url:
            continue
        
        url_slug = event_url.split('/events/')[-1].split('?')[0].split('#')[0].strip()
        if not url_slug or url_slug in seen_slugs:
            continue
        
        seen_slugs.add(url_slug)
        code = extract_code_from_url(event_url, venue_slug)
        
        if not code or not is_valid_event_url(event_url, code):
            continue
        
        code_index = url_slug.rfind(code) if code and code in url_slug else -1
        if code_index > 0:
            name_part = url_slug[:code_index].rstrip('-')
            name_from_slug = name_part.replace('-', ' ').title() if name_part else f"Evento {code}"
        else:
            name_from_slug = url_slug.replace('-', ' ').title() if url_slug else f"Evento {code}"
        
        unique_urls.append((event_url, code, name_from_slug))
    
    for event_url, code, name_from_slug in unique_urls:
        events.append({
            'url': event_url,
            'venue_slug': venue_slug,
            'name': name_from_slug,
            'code': code
        })
    
    return events


def extract_from_markdown(markdown: str, venue_slug: str) -> List[Dict]:
    """
    Extrae desde enlaces markdown [texto](url).
    ESTRATEGIA 4: Para cuando no se encuentran eventos en HTML.
    """
    events = []
    markdown_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', markdown)
    
    for link_text, link_url in markdown_links:
        if '/events/' not in link_url:
            continue
        
        code = extract_code_from_url(link_url, venue_slug)
        if not code:
            continue
        
        if not is_valid_event_url(link_url, code):
            continue
        
        # Hacer URL absoluta si es relativa
        if not link_url.startswith('http'):
            if link_url.startswith('/'):
                link_url = f"https://web.fourvenues.com{link_url}"
            else:
                link_url = f"https://web.fourvenues.com/{link_url}"
        
        events.append({
            'url': link_url,
            'venue_slug': venue_slug,
            'name': link_text.strip(),
            'code': code
        })
    
    return events


def deduplicate_events(events: List[Dict]) -> List[Dict]:
    """
    Deduplica eventos usando múltiples criterios:
    1. Por código único (prioridad alta)
    2. Por URL exacta
    3. Para Sala REM: por (nombre_normalizado + fecha)
    
    Mantiene el evento con más información (más fields completos)
    
    Args:
        events: Lista de eventos a deduplicar
    
    Returns:
        Lista de eventos únicos
    """
    if not events:
        return []
    
    seen_urls = set()
    seen_codes = set()
    seen_name_date = set()  # Para Sala Rem: (nombre_normalizado, fecha)
    unique_events = []
    
    for event in events:
        event_url = event.get('url', '').strip()
        event_code = event.get('code', '').strip().upper() if event.get('code') else None
        event_name = event.get('name', '').strip()
        venue_slug = event.get('venue_slug', '').lower()
        is_sala_rem = 'sala-rem' in venue_slug
        
        # Normalizar URL
        if event_url:
            event_url = event_url.split('?')[0].split('#')[0]
        
        # Criterio 1: URL exacta (más confiable)
        if event_url and event_url in seen_urls:
            continue
        
        # Criterio 2: Para Sala REM, usar (nombre + fecha) como clave única
        if is_sala_rem and event_name:
            # Normalizar nombre (eliminar emojis, espacios extra, etc.)
            name_normalized = re.sub(r'[^\w\s]', '', event_name.lower()).strip()
            name_normalized = re.sub(r'\s+', ' ', name_normalized)
            
            # Obtener fecha de _date_parts, date_text o URL
            event_date = None
            if event.get('_date_parts'):
                date_parts = event['_date_parts']
                event_date = f"{date_parts['day']}-{date_parts['month']}-{date_parts['year']}"
            elif event.get('date_text'):
                # Intentar extraer fecha de date_text
                date_match = re.search(r'(\d{1,2})\s+\w+', event.get('date_text', ''))
                if date_match:
                    day = date_match.group(1)
                    month_map = {'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
                               'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
                               'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'}
                    for month_name, month_num in month_map.items():
                        if month_name in event.get('date_text', '').lower():
                            event_date = f"{day}-{month_num}-2026"  # Año correcto
                            break
            elif event_url:
                # Extraer fecha de la URL como último recurso
                date_match = re.search(r'-{1,2}(\d{1,2})-(\d{2})-(\d{4})\d*-', event_url)
                if date_match:
                    event_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
            
            if event_date:
                name_date_key = (name_normalized, event_date)
                if name_date_key in seen_name_date:
                    continue
                seen_name_date.add(name_date_key)
        
        # Criterio 3: Para otros venues, usar código único
        if not is_sala_rem and event_code and event_code in seen_codes:
            continue
        
        # Añadir a sets de control
        if event_url:
            seen_urls.add(event_url)
        if event_code:
            seen_codes.add(event_code)
        
        unique_events.append(event)
    
    return unique_events


def extract_events_from_html(html: str, venue_url: str, markdown: str = None, raw_html: str = None) -> List[Dict]:
    """
    Extrae eventos del HTML de FourVenues de forma robusta.
    Usa múltiples estrategias de extracción en orden de prioridad.
    """
    debug_log("debug-session", "run1", "A", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "extract_events_from_html START", {
        "venue_url": venue_url,
        "html_length": len(html) if html else 0,
        "markdown_length": len(markdown) if markdown else 0,
        "raw_html_length": len(raw_html) if raw_html else 0
    })
    
    soup = BeautifulSoup(html, 'html.parser')
    venue_slug = venue_url.split('/')[-2] if '/events' in venue_url else ''
    
    all_events = []
    
    # ESTRATEGIA 1: Enlaces HTML con aria-label
    all_events.extend(extract_from_html_links(soup, venue_slug))
    
    # ESTRATEGIA 2: Componentes personalizados (data-testid)
    if not all_events:
        all_events.extend(extract_from_custom_components(soup, venue_slug))
    
    # ESTRATEGIA 3: URLs reales del rawHtml (más información después del JS)
    if not all_events:
        html_to_search = raw_html if raw_html and len(raw_html) > len(html) else html
        if html_to_search:
            all_events.extend(extract_from_raw_html(html_to_search, venue_slug))
    
    # ESTRATEGIA 4: Enlaces markdown
    if not all_events and markdown:
        all_events.extend(extract_from_markdown(markdown, venue_slug))
    
    print(f"   ✅ {len(all_events)} eventos encontrados")
    return all_events


def scrape_venue(firecrawl: Firecrawl, url: str) -> List[Dict]:
    """
    Scrapea eventos de una URL de venue con lógica agresiva de bypass.
    """
    print(f"\n📡 Scrapeando: {url}")
    
    try:
        # Para Sala Rem, usar más tiempo y formatos adicionales ya que el contenido se carga dinámicamente
        is_sala_rem = "sala-rem" in url.lower()
        
        if is_sala_rem:
            # Sala Rem necesita más tiempo y formato markdown para mejor extracción
            # Usar rawHtml también para obtener más información antes del procesamiento
            result = firecrawl.scrape(
                url,
                formats=["html", "markdown", "rawHtml"],  # rawHtml puede tener más información
                actions=[
                    {"type": "wait", "milliseconds": 20000},  # Más tiempo inicial para que cargue JS
                    {"type": "scroll", "direction": "down", "amount": 1500},
                    {"type": "wait", "milliseconds": 8000},
                    {"type": "scroll", "direction": "down", "amount": 1500},
                    {"type": "wait", "milliseconds": 8000},
                    {"type": "scroll", "direction": "down", "amount": 1500},
                    {"type": "wait", "milliseconds": 8000}
                ],
                wait_for=20000  # Esperar más tiempo para que cargue el contenido dinámico
            )
        else:
            # Para Dodo Club y otros que puedan tener Queue-Fair, subimos el tiempo
            # y añadimos un wait_for para asegurar que el contenido esté ahí.
            result = firecrawl.scrape(
                url,
                formats=["html"],
                actions=[
                    {"type": "wait", "milliseconds": 8000},
                    {"type": "scroll", "direction": "down", "amount": 500},
                    {"type": "wait", "milliseconds": 2000}
                ],
                # Si vemos que falla por Queue-Fair, Firecrawl suele esperar automáticamente
                # pero podemos forzar que espere a que aparezca un card de evento
                wait_for=5000 
            )
        
        html = result.html or ""
        raw_html = getattr(result, 'raw_html', None) or ""
        markdown = result.markdown or "" if hasattr(result, 'markdown') else ""
        status = result.metadata.status_code if result.metadata else "N/A"
        
        print(f"   Status: {status}")
        print(f"   HTML: {len(html)} bytes")
        if raw_html:
            print(f"   Raw HTML: {len(raw_html)} bytes")
        if markdown:
            print(f"   Markdown: {len(markdown)} caracteres")
        
        # #region agent log
        debug_log("debug-session", "run1", "D", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "Datos recibidos de Firecrawl", {
            "url": url,
            "is_sala_rem": is_sala_rem,
            "status": status,
            "html_length": len(html),
            "raw_html_length": len(raw_html) if raw_html else 0,
            "markdown_length": len(markdown) if markdown else 0,
            "has_html": bool(html),
            "has_raw_html": bool(raw_html),
            "has_markdown": bool(markdown)
        })
        # #endregion
        
        if not html and not raw_html:
            print("   ❌ No se recibió HTML")
            # #region agent log
            debug_log("debug-session", "run1", "D", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "ERROR: No se recibió HTML", {
                "url": url
            })
            # #endregion
            return []
        
        # Para Sala Rem, usar raw_html si está disponible (puede tener más información después del JS)
        html_to_use = raw_html if is_sala_rem and raw_html and len(raw_html) > len(html) else html
        
        # #region agent log
        debug_log("debug-session", "run1", "D", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "HTML seleccionado para extracción", {
            "html_to_use_length": len(html_to_use),
            "using_raw_html": html_to_use == raw_html,
            "using_html": html_to_use == html
        })
        # #endregion
        
        events = extract_events_from_html(html_to_use, url, markdown, raw_html=raw_html)
        
        # #region agent log
        debug_log("debug-session", "run1", "D", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "Eventos extraídos después de extract_events_from_html", {
            "events_count": len(events),
            "events": [{"name": e.get('name', ''), "code": e.get('code', '')} for e in events[:5]]
        })
        # #endregion
        
        # Si sigue sin pillar nada, intentar un segundo intento con JS más agresivo
        # Aplicar a Dodo Club y Sala Rem (ambos pueden tener estructuras similares o necesitar más tiempo)
        if not events and ("dodo" in url.lower() or "sala-rem" in url.lower()):
            print("   ⚠️ No detectados en primer intento. Reintentando con scroll profundo...")
            # Para Sala Rem, usar también markdown en el segundo intento
            is_sala_rem_retry = "sala-rem" in url.lower()
            result = firecrawl.scrape(
                url,
                formats=["html", "markdown", "rawHtml"] if is_sala_rem_retry else ["html"],
                actions=[
                    {"type": "wait", "milliseconds": 20000},  # Más tiempo para Sala Rem
                    {"type": "scroll", "direction": "down", "amount": 1500},
                    {"type": "wait", "milliseconds": 8000},
                    {"type": "scroll", "direction": "down", "amount": 1500},
                    {"type": "wait", "milliseconds": 8000},
                    {"type": "scroll", "direction": "down", "amount": 1500},
                    {"type": "wait", "milliseconds": 8000}
                ],
                wait_for=20000 if is_sala_rem_retry else 10000
            )
            html = result.html or ""
            raw_html = getattr(result, 'raw_html', None) or ""
            markdown = result.markdown or "" if hasattr(result, 'markdown') else ""
            print(f"   HTML segundo intento: {len(html)} bytes")
            if raw_html:
                print(f"   Raw HTML segundo intento: {len(raw_html)} bytes")
            if markdown:
                print(f"   Markdown segundo intento: {len(markdown)} caracteres")
            # Usar raw_html si está disponible y es más grande
            html_to_use = raw_html if is_sala_rem_retry and raw_html and len(raw_html) > len(html) else html
            events = extract_events_from_html(html_to_use, url, markdown, raw_html=raw_html)

        print(f"   ✅ {len(events)} eventos encontrados")
        
        return events
        
    except Exception as e:
        print(f"   ❌ Error: {type(e).__name__}: {e}")
        return []


def match_tickets_with_schema(markdown_tickets: List[Dict], schema_tickets: List[Dict]) -> List[Dict]:
    """
    Combina tickets del markdown con tickets del schema.org de forma inteligente.
    Prioriza schema cuando tiene precios válidos, pero preserva nombres del markdown.
    
    Args:
        markdown_tickets: Tickets extraídos del markdown
        schema_tickets: Tickets extraídos del schema.org
    
    Returns:
        Lista de tickets combinados y enriquecidos
    """
    if not schema_tickets:
        return markdown_tickets
    
    if not markdown_tickets:
        return schema_tickets
    
    def normalize_name(name: str) -> str:
        """Normaliza nombres para matching flexible"""
        if not name:
            return ""
        normalized = re.sub(r'\s+', ' ', name.strip().upper())
        normalized = normalized.replace('PROMOCIÓN', 'PROMOCION')
        normalized = normalized.replace('CONSUMICIÓN', 'CONSUMICION')
        normalized = normalized.replace('CONSUMICIONES', 'CONSUMICION')
        return normalized
    
    schema_has_prices = any(st.get('precio') and str(st.get('precio')).strip() not in ['0', 'None', ''] for st in schema_tickets)
    markdown_has_prices = any(t.get('precio') and str(t.get('precio')).strip() not in ['0', 'None', ''] for t in markdown_tickets)
    
    # Si schema tiene precios y markdown no, priorizar schema
    if schema_has_prices and not markdown_has_prices:
        schema_dict = {normalize_name(st['tipo']): st for st in schema_tickets}
        enriched = []
        
        for t in markdown_tickets:
            ticket_norm = normalize_name(t['tipo'])
            if ticket_norm in schema_dict:
                st = schema_dict[ticket_norm]
                enriched_ticket = copy.deepcopy(st)
                enriched_ticket['tipo'] = t['tipo']  # Preferir nombre del markdown
                if t.get('agotadas') is True:
                    enriched_ticket['agotadas'] = True
                enriched.append(enriched_ticket)
            else:
                # Intentar match parcial por palabras comunes
                best_partial = None
                best_score = 0
                for st in schema_tickets:
                    schema_norm = normalize_name(st['tipo'])
                    common = len(set(ticket_norm.split()) & set(schema_norm.split()))
                    if common > best_score and common >= 2:
                        best_score = common
                        best_partial = st
                
                if best_partial:
                    enriched_ticket = copy.deepcopy(best_partial)
                    enriched_ticket['tipo'] = t['tipo']
                    if t.get('agotadas') is True:
                        enriched_ticket['agotadas'] = True
                    enriched.append(enriched_ticket)
                else:
                    enriched.append(copy.deepcopy(t))
        
        # Añadir tickets del schema no usados
        used_names = {normalize_name(t['tipo']) for t in enriched}
        for st in schema_tickets:
            if normalize_name(st['tipo']) not in used_names:
                enriched.append(copy.deepcopy(st))
        
        return enriched
    
    # Si ambos tienen tickets, hacer matching inteligente
    used_schema_indices = set()
    result = []
    
    for t in markdown_tickets:
        ticket_norm = normalize_name(t['tipo'])
        matched = False
        best_match = None
        
        # Estrategia 1: Match exacto por nombre
        for idx, st in enumerate(schema_tickets):
            if idx in used_schema_indices:
                continue
            if st['tipo'] == t['tipo']:
                best_match = (idx, st)
                matched = True
                break
        
        # Estrategia 2: Match normalizado
        if not matched:
            for idx, st in enumerate(schema_tickets):
                if idx in used_schema_indices:
                    continue
                schema_norm = normalize_name(st['tipo'])
                if schema_norm == ticket_norm:
                    best_match = (idx, st)
                    matched = True
                    break
        
        # Estrategia 3: Match parcial por palabras clave
        if not matched:
            ticket_keywords = set(re.findall(r'\b(ENTRADA|VIP|COPA|COPAS|CONSUMICION|PROMOCION|RESERVADO|REDUCIDA|ANTICIPADA)\b', ticket_norm))
            best_partial = None
            best_score = 0
            
            for idx, st in enumerate(schema_tickets):
                if idx in used_schema_indices:
                    continue
                schema_norm = normalize_name(st['tipo'])
                schema_keywords = set(re.findall(r'\b(ENTRADA|VIP|COPA|COPAS|CONSUMICION|PROMOCION|RESERVADO|REDUCIDA|ANTICIPADA)\b', schema_norm))
                common_keywords = ticket_keywords & schema_keywords
                score = len(common_keywords)
                
                # Bonus por números similares
                ticket_numbers = set(re.findall(r'\b(\d+)\b', ticket_norm))
                schema_numbers = set(re.findall(r'\b(\d+)\b', schema_norm))
                if ticket_numbers and schema_numbers and ticket_numbers == schema_numbers:
                    score += 2
                
                if score > best_score and score >= 2:
                    best_partial = (idx, st)
                    best_score = score
            
            if best_partial:
                best_match = best_partial
                matched = True
        
        # Estrategia 4: Match por precio (solo si es único)
        if not matched and t.get('precio') and t['precio'] != "0":
            price_matches = [st for idx, st in enumerate(schema_tickets) 
                           if idx not in used_schema_indices 
                           and st.get('precio') == t['precio'] 
                           and st.get('precio') not in ['0', 'None', '']]
            
            if len(price_matches) == 1:
                for idx, st in enumerate(schema_tickets):
                    if idx in used_schema_indices:
                        continue
                    if st.get('precio') == t['precio'] and st.get('precio') not in ['0', 'None', '']:
                        best_match = (idx, st)
                        matched = True
                        break
        
        # Aplicar match si se encontró
        if matched and best_match:
            idx, st = best_match
            used_schema_indices.add(idx)
            old_url = t.get('url_compra')
            old_price = t.get('precio')
            
            t['url_compra'] = st['url_compra']
            if st.get('precio') and st['precio'] not in ['0', 'None', '']:
                t['precio'] = str(st['precio']).strip()
            
            # Preservar estado "agotadas" del markdown si está disponible (más confiable)
            if t.get('agotadas') is not True and 'agotadas' in st:
                if st['agotadas'] is True:
                    t['agotadas'] = True
                elif t.get('agotadas') is None:
                    t['agotadas'] = st['agotadas']
        
        result.append(t)
    
    # Añadir tickets del schema no usados
    for idx, st in enumerate(schema_tickets):
        if idx not in used_schema_indices:
            result.append(copy.deepcopy(st))
    
    return result


def extract_tickets_from_schema(html: str) -> List[Dict]:
    """
    Extrae URLs precisas de tickets desde los bloques JSON-LD (Schema.org) en el HTML.
    """
    tickets_from_schema = []
    
    if not html:
        return tickets_from_schema
    
    # Buscar bloques script con application/ld+json
    soup = BeautifulSoup(html, 'html.parser')
    scripts = soup.find_all('script', type='application/ld+json')
    
    
    for script in scripts:
        try:
            if not script.string:
                continue
            
            # Limpiar posibles comentarios o espacios extra
            content = script.string.strip()
            data = json.loads(content)
            
            # Schema.org suele tener una lista o un objeto @graph
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                if '@graph' in data:
                    items = data['@graph']
                else:
                    items = [data]
            
            for item in items:
                # El evento suele tener un campo 'offers' que es una lista de tickets
                offers = item.get('offers', [])
                if isinstance(offers, dict):
                    offers = [offers]
                
                for offer in offers:
                    if offer.get('@type') == 'Offer':
                        url = offer.get('url')
                        name = offer.get('name')
                        price = offer.get('price')
                        
                        if url and '/tickets/' in url:
                            # Detectar estado "agotadas" desde múltiples fuentes en el schema
                            availability = offer.get('availability', '')
                            availability_str = str(availability).lower() if availability else ''
                            
                            # Múltiples formas de detectar "agotadas" en schema.org
                            is_sold_out = (
                                availability == 'http://schema.org/OutOfStock' or
                                availability == 'https://schema.org/OutOfStock' or
                                'outofstock' in availability_str or
                                'soldout' in availability_str or
                                offer.get('availabilityStatus') == 'SoldOut' or
                                offer.get('inventoryLevel', {}).get('value', 0) == 0 if isinstance(offer.get('inventoryLevel'), dict) else False
                            )
                            
                            tickets_from_schema.append({
                                "tipo": name,
                                "precio": str(price),
                                "url_compra": url,
                                "agotadas": is_sold_out
                            })
        except:
            continue
            
    # Si no se encontró vía BeautifulSoup (a veces el JS lo inyecta), usar Regex sobre el raw
    if not tickets_from_schema:
        # Buscar patrones "url": "..." junto a "@type": "Offer"
        # Este regex es más agresivo para pillar URLs de tickets en JSONs inyectados
        pattern = r'"url"\s*:\s*"(https?://[^"]+/tickets/[a-z0-9]{20,})"'
        matches = re.findall(pattern, html)
        if matches:
            for url in set(matches):
                tickets_from_schema.append({
                    "url_compra": url,
                    "tipo": "Entrada (Detectada)", # Intentar pillar el nombre es más difícil con regex
                    "precio": "0",
                    "agotadas": False
                })
                
    return tickets_from_schema


def scrape_event_details(firecrawl: Firecrawl, event: Dict) -> Dict:
    """
    Scrapea detalles completos de un evento específico.
    
    Extrae:
    - Descripción del evento (desde markdown de Firecrawl)
    - Tickets con precios reales y descripciones
    - Géneros musicales / tags
    - Información del venue (dirección, coordenadas, etc.)
    """
    # #region agent log
    session_id = "debug-session"
    run_id = "run1"
    debug_log(session_id, run_id, "A", "scraper_firecrawl.py:269", "scrape_event_details START", {
        "event_name": event.get('name', 'N/A'),
        "event_url": event.get('url', 'N/A'),
        "event_code": event.get('code', 'N/A')
    })
    # #endregion
    
    # Crear una copia profunda del evento para evitar mutaciones del original
    event = copy.deepcopy(event)
    
    event_url = event.get('url', '')
    if not event_url:
        return event
    
    # Hacer URL absoluta si es relativa
    # Detectar el dominio correcto basándose en el venue_slug o la URL original
    if not event_url.startswith('http'):
        venue_slug = event.get('venue_slug', '')
        # Si el evento es de Sala Rem (web.fourvenues.com), usar ese dominio
        if 'sala-rem' in venue_slug.lower() or 'sala-rem' in event_url.lower():
            base_url = "https://web.fourvenues.com"
        else:
            base_url = "https://site.fourvenues.com"
        
        event_url = f"{base_url}{event_url}"
    
    # Extraer fecha de la URL si está disponible
    # Formatos para Sala Rem:
    # - --DD-MM-YYYY- (ej: --09-01-2026-)
    # - -DD-MM-YYYY- (ej: -08-01-2026-)
    # - -DD-MM-YYYYD- (ej: -08-01-20261- donde D es un dígito extra)
    # Esto es especialmente útil para Sala Rem donde la fecha está en la URL
    if not event.get('date_text') and 'sala-rem' in event.get('venue_slug', '').lower():
        # Patrón flexible: puede tener 1 o 2 guiones antes, y puede tener dígitos extra después del año
        date_match = re.search(r'-{1,2}(\d{1,2})-(\d{2})-(\d{4})\d*-', event_url)
        if date_match:
            day, month, year = date_match.group(1), date_match.group(2), date_match.group(3)
            month_names = {'01': 'enero', '02': 'febrero', '03': 'marzo', '04': 'abril',
                          '05': 'mayo', '06': 'junio', '07': 'julio', '08': 'agosto',
                          '09': 'septiembre', '10': 'octubre', '11': 'noviembre', '12': 'diciembre'}
            event['date_text'] = f"{day} {month_names.get(month, 'diciembre')}"
            event['_date_parts'] = {'day': day, 'month': month, 'year': year}
            print(f"      📅 Fecha extraída de URL: {event['date_text']} ({year})")
    
    try:
        # Solicitar HTML, MARKDOWN y RAWHTML
        # - markdown: descripciones legibles
        # - raw_html: metadatos JSON-LD con URLs exactas de tickets
        result = firecrawl.scrape(
            event_url,
            formats=["html", "markdown", "rawHtml"],
            actions=[{"type": "wait", "milliseconds": 8000}]
        )
        
        html = result.html or ""
        raw_html = getattr(result, 'raw_html', None) or html or ""
        markdown = result.markdown or ""
        
        # #region agent log
        debug_log(session_id, run_id, "A", "scraper_firecrawl.py:297", "Markdown recibido", {
            "markdown_length": len(markdown),
            "html_length": len(html),
            "raw_html_length": len(raw_html),
            "markdown_preview": markdown[:500] if markdown else ""
        })
        # #endregion
        
        # Validar que la URL es válida: si no hay HTML ni markdown, la URL probablemente es inválida
        # Esto es especialmente importante para Sala Rem donde construimos múltiples combinaciones
        if not html and not markdown:
            print(f"      ⚠️ URL inválida o no accesible: {event_url}")
            # Marcar el evento como inválido para que se filtre después
            event['_invalid'] = True
            return event
        
        soup = BeautifulSoup(html, 'html.parser') if html else None
        
        # ===== EXTRAER DESCRIPCIÓN Y TICKETS DESDE MARKDOWN =====
        # El markdown de Firecrawl contiene descripciones legibles de tickets
        tickets = []
        event_description = ""
        
        if markdown:
            lines = markdown.split('\n')
            current_ticket = None
            ticket_descriptions = []
            ticket_start_line = -1  # Línea donde empezó el ticket actual
            last_ticket_end_line = -1  # Línea donde terminó el último ticket guardado
            MAX_DISTANCE = 50  # Máxima distancia en líneas para asignar precio/descripción (fallback)
            MIN_DISTANCE_FROM_PREVIOUS = 2  # Distancia mínima desde el último ticket guardado
            
            # Pre-coleccionar todas las líneas de tickets para saber dónde terminan
            ticket_lines = []
            for j, l in enumerate(lines):
                if l.startswith('- ') and any(keyword in l.upper() for keyword in 
                    ['ENTRADA', 'ENTRADAS', 'PROMOCIÓN', 'PROMOCION', 'VIP', 'RESERVADO', 'LISTA']):
                    ticket_lines.append(j)
            
            # #region agent log
            debug_log(session_id, run_id, "A", "scraper_firecrawl.py:312", "Iniciando parsing markdown", {
                "total_lines": len(lines),
                "lines_preview": lines[:10]
            })
            # #endregion
            
            for i, line in enumerate(lines):
                line = line.strip()
                
                # #region agent log
                debug_log(session_id, run_id, "A", f"scraper_firecrawl.py:316", f"Procesando línea {i}", {
                    "line_number": i,
                    "line_content": line,
                    "current_ticket_before": current_ticket.copy() if current_ticket else None,
                    "ticket_start_line": ticket_start_line,
                    "last_ticket_end_line": last_ticket_end_line
                })
                # #endregion
                
                # Buscar tickets (formato: "- ENTRADA(S) ..." o "- PROMOCIÓN ..." o "- VIP")
                # Incluimos ENTRADAS (plural) y verificamos variaciones comunes
                is_ticket_line = line.startswith('- ') and any(keyword in line.upper() for keyword in 
                    ['ENTRADA', 'ENTRADAS', 'PROMOCIÓN', 'PROMOCION', 'VIP', 'RESERVADO', 'LISTA'])
                
                if is_ticket_line:
                    if current_ticket:
                        # #region agent log
                        debug_log(session_id, run_id, "A", f"scraper_firecrawl.py:325", "Guardando ticket anterior", {
                            "ticket_guardado": current_ticket.copy()
                        })
                        # #endregion
                        tickets.append(current_ticket)
                        last_ticket_end_line = i - 1  # Marcar dónde terminó el ticket anterior
                    
                    ticket_name = line[2:].strip()  # Quitar "- "
                    
                    # Intentar extraer precio inline (ej: "PRIMERAS ENTRADAS 8€" o "ENTRADA 10€")
                    inline_price = "0"
                    price_inline_match = re.search(r'(\d+(?:[,.]\d+)?)\s*€', ticket_name)
                    if price_inline_match:
                        inline_price = price_inline_match.group(1).replace(',', '.')
                    
                    # Detectar descripción común como "1 CONSUMICION" que suele tener precio asociado
                    # Buscar en las líneas siguientes si hay un precio
                    if inline_price == "0" and ('consumicion' in ticket_name.lower() or 'consumición' in ticket_name.lower()):
                        # Buscar precio en las siguientes 5 líneas
                        for j in range(i + 1, min(i + 6, len(lines))):
                            next_line = lines[j].strip()
                            price_match = re.search(r'(\d+(?:[,.]\d+)?)\s*€', next_line)
                            if price_match:
                                inline_price = price_match.group(1).replace(',', '.')
                                print(f"      💰 Precio encontrado para '{ticket_name}' en línea siguiente: {inline_price}€")
                                break
                    
                    current_ticket = {
                        "tipo": ticket_name,
                        "precio": inline_price,
                        "agotadas": False,
                        "descripcion": "",
                        "url_compra": event_url
                    }
                    ticket_start_line = i  # Marcar dónde empezó este ticket
                    
                    # #region agent log
                    debug_log(session_id, run_id, "A", f"scraper_firecrawl.py:336", "Nuevo ticket creado", {
                        "ticket_nuevo": current_ticket.copy(),
                        "precio_inline": inline_price,
                        "ticket_start_line": ticket_start_line,
                        "last_ticket_end_line": last_ticket_end_line
                    })
                    # #endregion
                
                # Detectar precio (formato: "X €") - Solo si no tiene precio inline
                elif current_ticket and re.search(r'^\d+\s*€$', line):
                    # Solo procesar si no tiene precio inline válido
                    if current_ticket['precio'] == "0":
                        distance_from_current = i - ticket_start_line
                        distance_from_previous = i - last_ticket_end_line if last_ticket_end_line >= 0 else float('inf')
                        
                        # Encontrar el siguiente ticket (si existe)
                        next_ticket_line = None
                        for tl in ticket_lines:
                            if tl > ticket_start_line:
                                next_ticket_line = tl
                                break
                        
                        # Calcular distancia máxima: hasta el siguiente ticket o MAX_DISTANCE, lo que sea menor
                        max_allowed_distance = MAX_DISTANCE
                        if next_ticket_line is not None:
                            max_allowed_distance = min(next_ticket_line - ticket_start_line, MAX_DISTANCE)
                        
                        # Validar proximidad: debe estar dentro del rango permitido
                        # Y no estar demasiado cerca del último ticket guardado
                        if distance_from_current <= max_allowed_distance and distance_from_previous >= MIN_DISTANCE_FROM_PREVIOUS:
                            price_match = re.search(r'(\d+)\s*€', line)
                            if price_match:
                                # Si ya hay un precio candidato, solo actualizar si este está más cerca
                                if '_candidate_price_line' not in current_ticket or i < current_ticket['_candidate_price_line']:
                                    old_price = current_ticket['precio']
                                    current_ticket['precio'] = price_match.group(1)
                                    current_ticket['_candidate_price_line'] = i  # Marcar línea del precio asignado
                                    # #region agent log
                                    debug_log(session_id, run_id, "B", f"scraper_firecrawl.py:345", "Precio asignado desde línea", {
                                        "line_number": i,
                                        "line_content": line,
                                        "ticket_tipo": current_ticket['tipo'],
                                        "precio_anterior": old_price,
                                        "precio_nuevo": current_ticket['precio'],
                                        "distance_from_current": distance_from_current,
                                        "distance_from_previous": distance_from_previous,
                                        "next_ticket_line": next_ticket_line,
                                        "max_allowed_distance": max_allowed_distance
                                    })
                                    # #endregion
                        else:
                            # #region agent log
                            debug_log(session_id, run_id, "B", f"scraper_firecrawl.py:345", "Precio IGNORADO (validación de proximidad falló)", {
                                "line_number": i,
                                "line_content": line,
                                "ticket_tipo": current_ticket['tipo'],
                                "distance_from_current": distance_from_current,
                                "distance_from_previous": distance_from_previous,
                                "next_ticket_line": next_ticket_line,
                                "max_allowed_distance": max_allowed_distance,
                                "max_distance": MAX_DISTANCE
                            })
                            # #endregion
                    else:
                        # #region agent log
                        debug_log(session_id, run_id, "B", f"scraper_firecrawl.py:345", "Precio IGNORADO (ya tiene precio inline)", {
                            "line_number": i,
                            "line_content": line,
                            "ticket_tipo": current_ticket['tipo'],
                            "precio_actual": current_ticket['precio']
                        })
                        # #endregion
                
                # Detectar si está agotada - solo si está cerca del ticket
                elif current_ticket and 'agotad' in line.lower():
                    distance_from_current = i - ticket_start_line
                    distance_from_previous = i - last_ticket_end_line if last_ticket_end_line >= 0 else float('inf')
                    
                    # Encontrar el siguiente ticket (si existe)
                    next_ticket_line = None
                    for tl in ticket_lines:
                        if tl > ticket_start_line:
                            next_ticket_line = tl
                            break
                    
                    # Calcular distancia máxima: hasta el siguiente ticket o MAX_DISTANCE
                    max_allowed_distance = MAX_DISTANCE
                    if next_ticket_line is not None:
                        max_allowed_distance = min(next_ticket_line - ticket_start_line, MAX_DISTANCE)
                    
                    if distance_from_current <= max_allowed_distance and distance_from_previous >= MIN_DISTANCE_FROM_PREVIOUS:
                        current_ticket['agotadas'] = True
                        # #region agent log
                        debug_log(session_id, run_id, "C", f"scraper_firecrawl.py:353", "Estado agotado asignado", {
                            "line_number": i,
                            "line_content": line,
                            "ticket_tipo": current_ticket['tipo'],
                            "distance_from_current": distance_from_current,
                            "distance_from_previous": distance_from_previous,
                            "next_ticket_line": next_ticket_line,
                            "max_allowed_distance": max_allowed_distance
                        })
                        # #endregion
                
                # Capturar descripción del ticket (texto con info de consumición) - solo si está cerca
                elif current_ticket and ('copa' in line.lower() or 'consumir' in line.lower() or 'alcohol' in line.lower()):
                    distance_from_current = i - ticket_start_line
                    distance_from_previous = i - last_ticket_end_line if last_ticket_end_line >= 0 else float('inf')
                    
                    # Encontrar el siguiente ticket (si existe)
                    next_ticket_line = None
                    for tl in ticket_lines:
                        if tl > ticket_start_line:
                            next_ticket_line = tl
                            break
                    
                    # Calcular distancia máxima: hasta el siguiente ticket o MAX_DISTANCE
                    max_allowed_distance = MAX_DISTANCE
                    if next_ticket_line is not None:
                        max_allowed_distance = min(next_ticket_line - ticket_start_line, MAX_DISTANCE)
                    
                    if distance_from_current <= max_allowed_distance and distance_from_previous >= MIN_DISTANCE_FROM_PREVIOUS:
                        # Solo asignar si no tiene descripción o si la nueva es más específica
                        if not current_ticket['descripcion'] or len(line) > len(current_ticket['descripcion']):
                            old_desc = current_ticket['descripcion']
                            current_ticket['descripcion'] = line
                            ticket_descriptions.append(line)
                            # #region agent log
                            debug_log(session_id, run_id, "C", f"scraper_firecrawl.py:357", "Descripción asignada", {
                                "line_number": i,
                                "line_content": line,
                                "ticket_tipo": current_ticket['tipo'],
                                "descripcion_anterior": old_desc,
                                "descripcion_nueva": current_ticket['descripcion'],
                                "distance_from_current": distance_from_current,
                                "distance_from_previous": distance_from_previous,
                                "next_ticket_line": next_ticket_line,
                                "max_allowed_distance": max_allowed_distance
                            })
                            # #endregion
            
            # Añadir último ticket
            if current_ticket:
                # Limpiar atributos temporales antes de guardar
                if '_candidate_price_line' in current_ticket:
                    del current_ticket['_candidate_price_line']
                tickets.append(current_ticket)
            
            # #region agent log
            debug_log(session_id, run_id, "A", "scraper_firecrawl.py:361", "Tickets antes de deduplicación", {
                "total_tickets": len(tickets),
                "tickets": [t.copy() for t in tickets]
            })
            # #endregion
            
            # --- DEDUPLICACIÓN DE TICKETS ---
            # Eliminar duplicados exactos (mismo nombre y precio)
            unique_tickets = []
            seen_tickets = set()
            
            for t in tickets:
                # Normalizar nombre para comparación
                name_clean = re.sub(r'\s+', ' ', t['tipo']).strip().lower()
                price_clean = str(t['precio']).replace(',', '.')
                ticket_id = f"{name_clean}|{price_clean}"
                
                if ticket_id not in seen_tickets:
                    seen_tickets.add(ticket_id)
                    unique_tickets.append(t)
                else:
                    # #region agent log
                    debug_log(session_id, run_id, "D", "scraper_firecrawl.py:370", "Ticket DUPLICADO eliminado", {
                        "ticket_duplicado": t.copy(),
                        "ticket_id": ticket_id
                    })
                    # #endregion
            
            tickets = unique_tickets
            # --------------------------------
            
            # #region agent log
            debug_log(session_id, run_id, "A", "scraper_firecrawl.py:380", "Tickets después de deduplicación", {
                "total_tickets": len(tickets),
                "tickets": [t.copy() for t in tickets]
            })
            # #endregion
            
            # Usar la primera descripción de ticket como descripción general del evento
            if ticket_descriptions:
                event_description = ". ".join(set(ticket_descriptions))
            
            # Buscar descripción general del evento en las primeras líneas
            # (suele estar después de la imagen y antes de los tickets)
            for line in lines[:20]:
                line = line.strip()
                # Descripción si empieza con texto, no es imagen, y tiene longitud razonable
                # Excluir también líneas con enlaces de Google Maps
                if (line and not line.startswith('!') and not line.startswith('#') 
                    and not line.startswith('-') and not line.startswith('[')
                    and len(line) > 50
                    and 'RESERVA' not in line.upper() and 'DERECHO' not in line.upper()
                    and 'google.com/maps' not in line.lower() and 'google maps' not in line.lower()):
                    event_description = line
                    break
        
        if tickets:
            event['tickets'] = tickets
        
        if event_description:
            event['description'] = event_description
        
        # ===== IMAGEN DE ALTA CALIDAD =====
        # Buscar imagen en múltiples fuentes para Sala Rem
        image_found = False
        
        # 1. Meta og:image (más confiable)
        og_image = soup.find('meta', {'property': 'og:image'}) if soup else None
        if og_image:
            img_url = og_image.get('content', '')
            if img_url and 'fourvenues.com' in img_url:
                event['image'] = img_url
                image_found = True
                print(f"      📷 Imagen encontrada (og:image): {img_url[:80]}...")
        
        # 2. Buscar en schema.org JSON-LD específicamente en el objeto Event (más preciso)
        if not image_found and raw_html:
            # Buscar bloques script con application/ld+json
            soup_temp = BeautifulSoup(raw_html, 'html.parser')
            scripts = soup_temp.find_all('script', type='application/ld+json')
            
            for script in scripts:
                try:
                    if not script.string:
                        continue
                    content = script.string.strip()
                    data = json.loads(content)
                    
                    # Schema.org suele tener una lista o un objeto @graph
                    items = []
                    if isinstance(data, list):
                        items = data
                    elif isinstance(data, dict):
                        if '@graph' in data:
                            items = data['@graph']
                        else:
                            items = [data]
                    
                    # Buscar específicamente en objetos de tipo Event
                    for item in items:
                        if item.get('@type') == 'Event' or 'Event' in str(item.get('@type', '')):
                            # El evento puede tener una imagen directamente
                            event_image = item.get('image')
                            if event_image:
                                # Puede ser un string o un objeto con url
                                if isinstance(event_image, str):
                                    img_url = event_image
                                elif isinstance(event_image, dict):
                                    img_url = event_image.get('url', '')
                                elif isinstance(event_image, list) and len(event_image) > 0:
                                    img_url = event_image[0] if isinstance(event_image[0], str) else event_image[0].get('url', '')
                                else:
                                    continue
                                
                                if img_url and 'fourvenues.com' in img_url:
                                    event['image'] = img_url
                                    image_found = True
                                    print(f"      📷 Imagen encontrada (schema Event): {img_url[:80]}...")
                                    break
                    
                    if image_found:
                        break
                except:
                    continue
            
            # Fallback: buscar cualquier imagen en schema.org (método anterior)
            if not image_found:
                schema_image_match = re.search(r'"image"\s*:\s*"([^"]+)"', raw_html)
                if schema_image_match:
                    img_url = schema_image_match.group(1)
                    if 'fourvenues.com' in img_url:
                        event['image'] = img_url
                        image_found = True
                        print(f"      📷 Imagen encontrada (schema fallback): {img_url[:80]}...")
        
        # 3. Buscar imagen principal en el HTML (fallback)
        if not image_found and soup:
            main_image = soup.find('img', {'class': lambda x: x and ('hero' in str(x).lower() or 'main' in str(x).lower() or 'event' in str(x).lower())})
            if not main_image:
                # Buscar cualquier imagen grande en el contenido principal
                main_image = soup.find('img', src=lambda x: x and 'fourvenues.com' in x and ('cdn-cgi' in x or 'imagedelivery' in x))
            if main_image:
                img_url = main_image.get('src', '')
                if img_url:
                    # Hacer URL absoluta si es relativa
                    if not img_url.startswith('http'):
                        if 'sala-rem' in event.get('venue_slug', '').lower():
                            img_url = f"https://web.fourvenues.com{img_url}" if img_url.startswith('/') else f"https://web.fourvenues.com/{img_url}"
                        else:
                            img_url = f"https://site.fourvenues.com{img_url}" if img_url.startswith('/') else f"https://site.fourvenues.com/{img_url}"
                    event['image'] = img_url
                    image_found = True
                    print(f"      📷 Imagen encontrada (HTML): {img_url[:80]}...")
        
        if not image_found:
            print(f"      ⚠️ No se encontró imagen para el evento")
        
        # ===== INTEGRAR URLs EXACTAS DESDE SCHEMA/RAW =====
        schema_tickets = extract_tickets_from_schema(raw_html)
        
        
        # Combinar tickets del markdown con tickets del schema usando función centralizada
        if schema_tickets:
            tickets = match_tickets_with_schema(tickets, schema_tickets)

        if tickets:
            # Crear copias profundas de los tickets para evitar referencias compartidas
            event['tickets'] = [copy.deepcopy(t) for t in tickets]
        
        # #region agent log
        debug_log(session_id, run_id, "A", "scraper_firecrawl.py:428", "Tickets finales", {
            "total_tickets": len(event.get('tickets', [])),
            "tickets_finales": [copy.deepcopy(t) for t in event.get('tickets', [])],
            "event_name": event.get('name', 'N/A'),
            "event_code": event.get('code', 'N/A')
        })
        # #endregion
        
        # ===== GÉNEROS MUSICALES / TAGS =====
        tags = []
        
        # Buscar en aria-labels que mencionen géneros
        all_labels = soup.find_all(attrs={'aria-label': True})
        genre_keywords = ['reggaeton', 'comercial', 'latin', 'techno', 'house', 'electro', 
                         'hip hop', 'trap', 'remember', 'indie', 'pop', 'rock', 'r&b']
        
        for elem in all_labels:
            label = elem.get('aria-label', '').lower()
            for genre in genre_keywords:
                if genre in label and genre.title() not in tags:
                    tags.append(genre.title())
        
        # Analizar el nombre del evento para tags
        event_name = event.get('name', '').lower()
        for genre in genre_keywords:
            if genre in event_name and genre.title() not in tags:
                tags.append(genre.title())
        
        if tags:
            event['tags'] = tags
        else:
            # Inferir del nombre
            if 'viernes' in event_name:
                event['tags'] = ['Fiesta', 'Viernes']
            elif 'sabado' in event_name or 'sábado' in event_name:
                event['tags'] = ['Fiesta', 'Sábado']
            else:
                event['tags'] = ['Fiesta']
        
        # ===== INFORMACIÓN DEL VENUE =====
        venue_info = {}
        
        # Buscar dirección (suele estar en elementos con address o location)
        address_elem = soup.find(attrs={'class': lambda x: x and 'address' in str(x).lower()})
        if address_elem:
            venue_info['direccion'] = address_elem.get_text(strip=True)
        
        # Buscar en schema.org o meta tags
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                ld_data = json.loads(script.string)
                if isinstance(ld_data, dict):
                    location = ld_data.get('location', {})
                    if isinstance(location, dict):
                        address = location.get('address', {})
                        if isinstance(address, dict):
                            venue_info['direccion'] = address.get('streetAddress', '')
                            venue_info['ciudad'] = address.get('addressLocality', '')
                            venue_info['codigo_postal'] = address.get('postalCode', '')
                        elif isinstance(address, str):
                            venue_info['direccion'] = address
                        
                        geo = location.get('geo', {})
                        if geo:
                            venue_info['latitud'] = geo.get('latitude')
                            venue_info['longitud'] = geo.get('longitude')
            except:
                continue
        
        if venue_info:
            event['venue_info'] = venue_info
        
        # #region agent log
        debug_log(session_id, run_id, "A", "scraper_firecrawl.py:494", "scrape_event_details END", {
            "event_name": event.get('name', 'N/A'),
            "tickets_count": len(event.get('tickets', [])),
            "tickets": [t.copy() for t in event.get('tickets', [])],
            "description": event.get('description', '')[:100]
        })
        # #endregion
        
        return event
        
    except Exception as e:
        print(f"      ⚠️ Error detalles: {e}")
        # #region agent log
        debug_log(session_id, run_id, "E", "scraper_firecrawl.py:496", "ERROR en scrape_event_details", {
            "error": str(e),
            "error_type": type(e).__name__,
            "event_url": event_url
        })
        # #endregion
        return event


def transform_to_app_format(events: List[Dict]) -> List[Dict]:
    """
    Transforma los eventos al formato de la app PartyFinder.
    """
    transformed = []
    
    for event in events:
        # Parsear fecha - priorizar _date_parts si está disponible (más confiable)
        fecha = datetime.now().strftime('%Y-%m-%d')
        
        # Si tenemos las partes de la fecha directamente (de la URL o markdown), usarlas
        if event.get('_date_parts'):
            date_parts = event['_date_parts']
            day = date_parts['day'].zfill(2)
            month = date_parts['month']
            year = date_parts['year']
            fecha = f"{year}-{month}-{day}"
        else:
            # Intentar parsear desde date_text
            date_text = event.get('date_text', '')
            months = {
                'ene': '01', 'feb': '02', 'mar': '03', 'abr': '04',
                'may': '05', 'jun': '06', 'jul': '07', 'ago': '08',
                'sep': '09', 'oct': '10', 'nov': '11', 'dic': '12',
                'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
                'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
                'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
            }
            
            match = re.search(r'(\d{1,2})\s+(\w+)', date_text, re.IGNORECASE)
            if match:
                day = match.group(1).zfill(2)
                month_str = match.group(2).lower()[:3]
                month = months.get(month_str, '12')
                year = datetime.now().year
                # Si el mes ya pasó, es del año siguiente
                if int(month) < datetime.now().month:
                    year += 1
                fecha = f"{year}-{month}-{day}"
            
            # Si aún no tenemos fecha, intentar extraer de la URL
            # Patrón flexible para Sala Rem: puede tener 1 o 2 guiones antes, y puede tener dígitos extra después del año
            if fecha == datetime.now().strftime('%Y-%m-%d') and event.get('url'):
                url = event.get('url', '')
                date_match = re.search(r'-{1,2}(\d{1,2})-(\d{2})-(\d{4})\d*-', url)
                if date_match:
                    day = date_match.group(1).zfill(2)
                    month = date_match.group(2)
                    year = date_match.group(3)
                    fecha = f"{year}-{month}-{day}"
        
        # Construir entradas desde tickets extraídos
        entradas = []
        
        # #region agent log
        session_id = "debug-session"
        run_id = "run1"
        debug_log(session_id, run_id, "B", "scraper_firecrawl.py:804", "ANTES de transformar entradas", {
            "event_name": event.get('name', 'N/A'),
            "event_code": event.get('code', 'N/A'),
            "tickets_from_event": [copy.deepcopy(t) for t in event.get('tickets', [])] if event.get('tickets') else None,
            "prices_from_event": event.get('prices', [])
        })
        # #endregion
        
        # Usar tickets extraídos si existen (hacer copia profunda para evitar mutaciones)
        if event.get('tickets'):
            entradas = [copy.deepcopy(t) for t in event['tickets']]
        else:
            # Fallback a precios individuales
            for price in event.get('prices', []):
                entradas.append({
                    "tipo": "Entrada General",
                    "precio": str(price).replace(',', '.'),
                    "agotadas": False,
                    "url_compra": event.get('url', '')
                })
        
        if not entradas:
            entradas = [{
                "tipo": "Entrada General",
                "precio": "0",
                "agotadas": False,
                "url_compra": event.get('url', '')
            }]
        
        # #region agent log
        debug_log(session_id, run_id, "B", "scraper_firecrawl.py:832", "DESPUÉS de transformar entradas", {
            "event_name": event.get('name', 'N/A'),
            "event_code": event.get('code', 'N/A'),
            "entradas_finales": [copy.deepcopy(e) for e in entradas]
        })
        # #endregion
        
        # Ajustar fecha si la hora de inicio es 00:00
        # Un evento que empieza a las 00:00 pertenece al día anterior
        # Ejemplo: Si la URL dice --28-12-2025- y el evento empieza a las 00:00,
        # el evento realmente es del 27 (sábado 27 a las 00:00 = inicio del sábado 27)
        hora_inicio = event.get('hora_inicio', '23:00')
        if hora_inicio == '00:00' or hora_inicio == '0:00':
            try:
                from datetime import timedelta
                fecha_obj = datetime.strptime(fecha, '%Y-%m-%d')
                fecha_obj = fecha_obj - timedelta(days=1)
                fecha = fecha_obj.strftime('%Y-%m-%d')
                print(f"      🔧 Ajuste de fecha por hora 00:00: {event.get('name', 'Evento')} -> {fecha}")
            except Exception as e:
                print(f"      ⚠️ Error ajustando fecha para hora 00:00: {e}")
        
        # Usar tags extraídos o inferidos
        tags = event.get('tags', ['Fiesta'])
        
        # Información del venue
        venue_info = event.get('venue_info', {})
        
        transformed_event = {
            "evento": {
                "nombreEvento": event.get('name', 'Evento'),
                "descripcion": event.get('description', ''),
                "fecha": fecha,
                "hora_inicio": hora_inicio,
                "hora_fin": event.get('hora_fin', '06:00'),
                "imagen_url": event.get('image', ''),
                "url_evento": event.get('url', ''),
                "code": event.get('code', ''),
                "entradas": entradas,
                "tags": tags,
                "edad_minima": event.get('age_min', 18),
                "lugar": {
                    "nombre": event.get('venue_slug', '').replace('-', ' ').title(),
                    "direccion": venue_info.get('direccion', ''),
                    "ciudad": venue_info.get('ciudad', 'Murcia'),
                    "codigo_postal": venue_info.get('codigo_postal', ''),
                    "latitud": venue_info.get('latitud'),
                    "longitud": venue_info.get('longitud'),
                    "categoria": "Discoteca"
                }
            }
        }
        
        transformed.append(transformed_event)
    
    return transformed


def scrape_all_events(urls: List[str] = None, get_details: bool = True) -> List[Dict]:
    """
    Scrapea eventos de todas las URLs.
    """
    target_urls = urls or VENUE_URLS
    all_events = []
    
    print("=" * 60)
    print("PartyFinder - Firecrawl Scraper")
    print("=" * 60)
    
    firecrawl = Firecrawl(api_key=API_KEY)
    
    for url in target_urls:
        events = scrape_venue(firecrawl, url)
        all_events.extend(events)
    
    # Obtener detalles de eventos si se solicita
    if get_details and all_events:
        # Deduplicar eventos antes de scrapear detalles
        print(f"\n🔍 Deduplicando {len(all_events)} eventos...")
        original_count = len(all_events)
        all_events = deduplicate_events(all_events)
        if len(all_events) < original_count:
            print(f"   ✅ Eventos deduplicados: {original_count} → {len(all_events)}")
        
        print(f"\n🎫 Obteniendo detalles de {len(all_events)} eventos...")
        for i, event in enumerate(all_events):
            print(f"   [{i+1}/{len(all_events)}] {event.get('name', 'N/A')[:40]}...")
            # #region agent log
            session_id = "debug-session"
            run_id = "run1"
            debug_log(session_id, run_id, "F", "scraper_firecrawl.py:878", "Procesando evento en scrape_all_events", {
                "event_index": i,
                "event_name": event.get('name', 'N/A'),
                "event_code": event.get('code', 'N/A'),
                "event_url": event.get('url', 'N/A'),
                "tickets_before": [t.copy() if isinstance(t, dict) else str(t) for t in event.get('tickets', [])]
            })
            # #endregion
            result = scrape_event_details(firecrawl, event)
            
            # Filtrar eventos inválidos (URLs que no retornaron contenido)
            if result.get('_invalid'):
                print(f"   ⚠️ Evento inválido descartado: {result.get('name', 'N/A')} - {result.get('url', 'N/A')}")
                all_events[i] = None  # Marcar para filtrar después
            else:
                # Verificar que el evento tiene contenido válido (tickets o precios)
                # Si no tiene tickets y todos los precios son 0, probablemente es inválido
                tickets = result.get('tickets', [])
                prices = result.get('prices', [])
                has_valid_tickets = any(t.get('precio', '0') != '0' for t in tickets) if tickets else False
                has_valid_prices = any(str(p) != '0' and str(p) != '0.0' for p in prices) if prices else False
                
                # #region agent log
                debug_log(session_id, run_id, "G", f"scraper_firecrawl.py:{sys._getframe().f_lineno}", "Validando contenido del evento", {
                    "event_name": result.get('name', 'N/A'),
                    "tickets_count": len(tickets),
                    "tickets": [t.copy() if isinstance(t, dict) else str(t) for t in tickets],
                    "prices": prices,
                    "has_valid_tickets": has_valid_tickets,
                    "has_valid_prices": has_valid_prices,
                    "has_description": bool(result.get('description', '').strip()),
                    "has_image": bool(result.get('image', '').strip()),
                    "description": result.get('description', '')[:100],
                    "image": result.get('image', '')[:100]
                })
                # #endregion
                
                # Si no tiene tickets válidos ni precios válidos, y es de Sala Rem, puede ser una URL inválida
                if not has_valid_tickets and not has_valid_prices and 'sala-rem' in result.get('venue_slug', '').lower():
                    # Verificar si tiene descripción o imagen (signos de que la URL es válida)
                    has_description = bool(result.get('description', '').strip())
                    has_image = bool(result.get('image', '').strip())
                    
                    # RELAJAR VALIDACIÓN: Si tiene al menos tickets (aunque sean precio 0), mantenerlo
                    # Esto es importante para eventos que pueden tener tickets gratuitos o con "consumicion"
                    has_any_tickets = len(tickets) > 0
                    
                    if not has_description and not has_image and not has_any_tickets:
                        print(f"   ⚠️ Evento sin contenido válido descartado: {result.get('name', 'N/A')} - {result.get('url', 'N/A')[:80]}...")
                        # #region agent log
                        debug_log(session_id, run_id, "H", f"scraper_firecrawl.py:{sys._getframe().f_lineno}", "Evento descartado por falta de contenido", {
                            "event_name": result.get('name', 'N/A'),
                            "reason": "no_description_no_image_no_tickets"
                        })
                        # #endregion
                        all_events[i] = None  # Marcar para filtrar después
                    else:
                        # Mantener el evento aunque no tenga precios válidos si tiene tickets o descripción/imagen
                        print(f"   ✅ Evento mantenido (tiene tickets/descripción/imagen): {result.get('name', 'N/A')}")
                        all_events[i] = result
                else:
                    all_events[i] = result
                # #region agent log
                debug_log(session_id, run_id, "F", "scraper_firecrawl.py:880", "Evento procesado en scrape_all_events", {
                    "event_index": i,
                    "event_name": result.get('name', 'N/A'),
                    "event_code": result.get('code', 'N/A'),
                    "tickets_after": [t.copy() if isinstance(t, dict) else str(t) for t in result.get('tickets', [])]
                })
                # #endregion
    
    # Filtrar eventos inválidos (None o marcados como inválidos)
    all_events = [e for e in all_events if e is not None and not e.get('_invalid')]
    
    print(f"\n🎉 Total: {len(all_events)} eventos scrapeados (eventos inválidos filtrados)")
    return all_events


def test_connection() -> bool:
    """
    Test básico de conexión.
    """
    print("=" * 60)
    print("PartyFinder - Test de Firecrawl")
    print("=" * 60)
    
    firecrawl = Firecrawl(api_key=API_KEY)
    test_url = VENUE_URLS[0]
    
    print(f"\n🔗 URL: {test_url}")
    print("📡 Probando conexión...")
    
    try:
        # Usar actions para obtener HTML completo con aria-labels
        result = firecrawl.scrape(
            test_url, 
            formats=["html"],
            actions=[{"type": "wait", "milliseconds": 5000}]
        )
        status = result.metadata.status_code if result.metadata else "N/A"
        html_len = len(result.html) if result.html else 0
        
        print(f"\n✅ Conexión exitosa!")
        print(f"   Status: {status}")
        print(f"   HTML: {html_len} bytes")
        
        events = extract_events_from_html(result.html, test_url)
        print(f"   Eventos detectados: {len(events)}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Scraper FourVenues con Firecrawl - VERSIÓN DESARROLLO (eventos-dev)')
    parser.add_argument('--test', '-t', action='store_true', help='Solo test de conexión')
    parser.add_argument('--upload', '-u', action='store_true', help='Subir a Firebase (colección eventos-dev)')
    parser.add_argument('--no-details', action='store_true', help='No obtener detalles de eventos')
    parser.add_argument('--urls', nargs='+', help='URLs específicas a scrapear (ej: --urls https://web.fourvenues.com/es/sala-rem/events)')
    
    args = parser.parse_args()
    
    # Crear directorio data
    DATA_DIR.mkdir(exist_ok=True)
    
    if args.test:
        success = test_connection()
        return 0 if success else 1
    
    # Scraping completo - usar URLs específicas si se proporcionan
    target_urls = args.urls if args.urls else None
    raw_events = scrape_all_events(urls=target_urls, get_details=not args.no_details)
    
    if not raw_events:
        print("\n❌ No se encontraron eventos")
        return 1
    
    # Transformar
    transformed = transform_to_app_format(raw_events)
    
    # Guardar
    with open(DATA_DIR / 'raw_events.json', 'w', encoding='utf-8') as f:
        json.dump(raw_events, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Datos crudos: {DATA_DIR / 'raw_events.json'}")
    
    with open(DATA_DIR / 'events.json', 'w', encoding='utf-8') as f:
        json.dump(transformed, f, indent=2, ensure_ascii=False)
    print(f"💾 Datos transformados: {DATA_DIR / 'events.json'}")
    
    # Subir a Firebase - VERSIÓN DESARROLLO: usar colección 'eventos-dev'
    if args.upload:
        print("\n📤 Subiendo a Firebase (colección: eventos-dev)...")
        try:
            from firebase_config import upload_events_to_firestore, delete_old_events
            
            # Usar colección 'eventos-dev' para desarrollo
            DEV_COLLECTION = 'eventos-dev'
            delete_old_events(collection_name=DEV_COLLECTION)
            upload_events_to_firestore(transformed, collection_name=DEV_COLLECTION)
            print(f"✅ Datos subidos a Firebase (colección: {DEV_COLLECTION})")
            
            # NOTA: Las notificaciones push normalmente se envían solo desde producción
            # Si quieres habilitarlas también en desarrollo, descomenta lo siguiente:
            # print("\n📬 Verificando y enviando notificaciones push...")
            # try:
            #     from push_notifications import check_and_send_notifications
            #     check_and_send_notifications()
            # except Exception as e:
            #     print(f"⚠️ Error enviando notificaciones: {e}")
        except Exception as e:
            print(f"❌ Error subiendo a Firebase: {e}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
