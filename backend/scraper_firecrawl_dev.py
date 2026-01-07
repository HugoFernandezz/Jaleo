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


def extract_events_from_html(html: str, venue_url: str, markdown: str = None, raw_html: str = None) -> List[Dict]:
    """
    Extrae eventos del HTML de FourVenues de forma robusta.
    Si se proporciona markdown, también se usa para extraer información.
    raw_html puede contener más información después de que el JavaScript se ejecuta.
    """
    # #region agent log
    debug_log("debug-session", "run1", "A", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "extract_events_from_html START", {
        "venue_url": venue_url,
        "html_length": len(html) if html else 0,
        "markdown_length": len(markdown) if markdown else 0,
        "raw_html_length": len(raw_html) if raw_html else 0
    })
    # #endregion
    
    events = []
    soup = BeautifulSoup(html, 'html.parser')
    venue_slug = venue_url.split('/')[-2] if '/events' in venue_url else ''
    
    # Debug: contar enlaces potenciales
    all_event_links = soup.find_all('a', href=lambda x: x and '/events/' in x)
    print(f"   🔍 Debug: {len(all_event_links)} enlaces con '/events/' encontrados")
    
    # #region agent log
    debug_log("debug-session", "run1", "A", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "Enlaces encontrados", {
        "total_event_links": len(all_event_links),
        "venue_slug": venue_slug,
        "sample_hrefs": [link.get('href', '')[:100] for link in all_event_links[:5]] if all_event_links else []
    })
    # #endregion
    
    # ESTRATEGIA 1: Enlaces con aria-label (Luminata, Odiseo)
    # Para Sala Rem, también buscar sin aria-label ya que puede tener estructura diferente
    is_sala_rem = 'sala-rem' in venue_slug.lower()
    
    if is_sala_rem:
        # Para Sala Rem, buscar cualquier enlace con /events/ (más permisivo)
        event_links = soup.find_all('a', href=lambda x: x and '/events/' in x)
        print(f"   🔍 Debug Estrategia 1 (Sala Rem): {len(event_links)} enlaces con '/events/' encontrados")
        
        # #region agent log
        debug_log("debug-session", "run1", "A", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "Sala REM detectada - enlaces encontrados", {
            "is_sala_rem": is_sala_rem,
            "event_links_count": len(event_links),
            "sample_hrefs": [link.get('href', '') for link in event_links[:10]]
        })
        # #endregion
    else:
        # Para otras discotecas, buscar con aria-label
        event_links = soup.find_all('a', href=lambda x: x and '/events/' in x and x.count('/') >= 4)
        print(f"   🔍 Debug Estrategia 1: {len(event_links)} enlaces con 4+ '/' encontrados")
    
    for link in event_links:
        try:
            href = link.get('href', '')
            aria_label = link.get('aria-label', '')
            
            # Para Sala Rem, no requerir aria-label
            if not is_sala_rem and (not aria_label or 'Evento' not in aria_label):
                continue
            
            event = {
                'url': href,
                'venue_slug': venue_slug,
                'image': link.find('img').get('src', '') if link.find('img') else ''
            }
            
            # Código del evento
            # Para Sala Rem: formato es /events/slug--fecha-CODIGO (ej: friday-session--sala-rem--26-12-2025-EI7Q)
            # También puede ser: slug-fecha-CODIGO (ej: jueves-universitario-08-01-20261-5YTV)
            # Para otros: formato es /events/CODIGO (ej: LKB5)
            if 'sala-rem' in venue_slug.lower():
                # #region agent log
                debug_log("debug-session", "run1", "B", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "Intentando extraer código Sala REM", {
                    "href": href,
                    "href_length": len(href)
                })
                # #endregion
                
                # Patrón mejorado: extraer código después de la fecha (DD-MM-YYYY seguido de posibles dígitos y luego el código)
                # El código puede tener 4 o más caracteres alfanuméricos
                # Ejemplos: -08-01-20261-5YTV, --09-01-2026-HZOY, -10-01-2026-XTNE
                match = re.search(r'/(?:-{1,2})?\d{1,2}-\d{2}-\d{4}\d*-([A-Z0-9]{4,})(?:/|$)', href)
                if match:
                    event['code'] = match.group(1)
                    # #region agent log
                    debug_log("debug-session", "run1", "B", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "Código extraído con patrón principal", {
                        "code": event['code'],
                        "href": href
                    })
                    # #endregion
                else:
                    # #region agent log
                    debug_log("debug-session", "run1", "B", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "Patrón principal falló, intentando fallback", {
                        "href": href,
                        "pattern_tried": r'/(?:-{1,2})?\d{1,2}-\d{2}-\d{4}\d*-([A-Z0-9]{4,})(?:/|$)'
                    })
                    # #endregion
                    
                    # Fallback: extraer del final de la URL (última parte después del último guion)
                    match = re.search(r'/events/([^/]+)$', href)
                    if match:
                        slug = match.group(1)
                        # #region agent log
                        debug_log("debug-session", "run1", "B", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "Slug extraído para fallback", {
                            "slug": slug,
                            "slug_parts": slug.split('-')
                        })
                        # #endregion
                        
                        # El código está al final, después del último guion
                        # Puede tener 4 o más caracteres
                        parts = slug.split('-')
                        if len(parts) > 0:
                            last_part = parts[-1]
                            # Si la última parte es alfanumérica y tiene al menos 4 caracteres, es el código
                            if last_part.isalnum() and len(last_part) >= 4:
                                event['code'] = last_part
                                # #region agent log
                                debug_log("debug-session", "run1", "B", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "Código extraído del último segmento", {
                                    "code": event['code'],
                                    "last_part": last_part
                                })
                                # #endregion
                            # Si no, intentar con las últimas 2 partes (por si hay dígitos extra)
                            elif len(parts) >= 2:
                                potential_code = parts[-2] + '-' + parts[-1]
                                if potential_code.replace('-', '').isalnum() and len(potential_code.replace('-', '')) >= 4:
                                    event['code'] = potential_code
                                    # #region agent log
                                    debug_log("debug-session", "run1", "B", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "Código extraído de últimos 2 segmentos", {
                                        "code": event['code'],
                                        "potential_code": potential_code
                                    })
                                    # #endregion
                            else:
                                # #region agent log
                                debug_log("debug-session", "run1", "B", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "NO se pudo extraer código", {
                                    "href": href,
                                    "parts": parts,
                                    "last_part": last_part if len(parts) > 0 else None
                                })
                                # #endregion
            else:
                # Formato estándar: /events/CODIGO
                match = re.search(r'/events/([A-Z0-9-]+)$', href)
                if match:
                    event['code'] = match.group(1)
            
            # Parsear aria-label (solo si existe)
            if aria_label:
                name_match = re.search(r'Evento\s*:\s*(.+?)(?:\.\s*Edad|\s*$)', aria_label)
                if name_match: event['name'] = name_match.group(1).strip()
                
                age_match = re.search(r'Edad mínima:\s*(.+?)(?:\.\s*Fecha|\s*$)', aria_label)
                if age_match:
                    event['age_info'] = age_match.group(1).strip()
                    num_match = re.search(r'(\d+)', age_match.group(1))
                    if num_match: event['age_min'] = int(num_match.group(1))
                
                fecha_match = re.search(r'Fecha:\s*(.+?)(?:\.\s*Horario|\s*$)', aria_label)
                if fecha_match: event['date_text'] = fecha_match.group(1).strip()
                
                horario_match = re.search(r'Horario:\s*de\s*(\d{1,2}:\d{2})\s*a\s*(\d{1,2}:\d{2})', aria_label)
            else:
                horario_match = None
            
            # Para Sala Rem, si no hay nombre, intentar obtenerlo del texto del enlace o elementos cercanos
            if is_sala_rem and not event.get('name'):
                link_text = link.get_text(strip=True)
                if link_text and len(link_text) > 5:
                    event['name'] = link_text[:100]  # Limitar longitud
                else:
                    # Buscar en elementos padre
                    parent = link.find_parent()
                    if parent:
                        parent_text = parent.get_text(strip=True)
                        if parent_text and len(parent_text) > 5:
                            event['name'] = parent_text[:100]
            
            if horario_match:
                event['hora_inicio'] = horario_match.group(1)
                event['hora_fin'] = horario_match.group(2)
            
            # #region agent log
            debug_log("debug-session", "run1", "C", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "Evento procesado - validación", {
                "has_name": bool(event.get('name')),
                "has_code": bool(event.get('code')),
                "name": event.get('name', ''),
                "code": event.get('code', ''),
                "href": href,
                "will_be_added": bool(event.get('name') and event.get('code'))
            })
            # #endregion
            
            if event.get('name') and event.get('code'):
                events.append(event)
                # #region agent log
                debug_log("debug-session", "run1", "C", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "Evento añadido", {
                    "event_name": event.get('name'),
                    "event_code": event.get('code'),
                    "total_events": len(events)
                })
                # #endregion
            else:
                # #region agent log
                debug_log("debug-session", "run1", "C", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "Evento DESCARTADO (falta nombre o código)", {
                    "has_name": bool(event.get('name')),
                    "has_code": bool(event.get('code')),
                    "href": href
                })
                # #endregion
        except:
            continue

    # ESTRATEGIA 2: Componentes personalizados / data-testid (Dodo Club)
    if not events:
        event_cards = soup.find_all(attrs={"data-testid": ["event-card", "event-card-name"]})
        print(f"   🔍 Debug Estrategia 2a: {len(event_cards)} elementos con data-testid encontrados")
        if not event_cards:
            event_cards = soup.find_all('div', class_=lambda x: x and 'event' in x and 'card' in x)
            print(f"   🔍 Debug Estrategia 2b: {len(event_cards)} divs con 'event' y 'card' encontrados")

        for card in event_cards:
            try:
                link_elem = card.find_parent('a') or card.find('a') or (card if card.name == 'a' else None)
                if not link_elem: continue
                
                href = link_elem.get('href', '')
                if not href or '/events/' not in href: continue
                if any(e['url'] == href for e in events): continue

                # Extraer código del evento
                if 'sala-rem' in venue_slug.lower():
                    # Para Sala Rem: formato es /events/slug--fecha-CODIGO o slug-fecha-CODIGO
                    # El código puede tener 4 o más caracteres alfanuméricos
                    code_match = re.search(r'/(?:-{1,2})?\d{1,2}-\d{2}-\d{4}\d*-([A-Z0-9]{4,})(?:/|$)', href)
                    if code_match:
                        code = code_match.group(1)
                    else:
                        # Fallback: extraer del final
                        slug = href.split('/')[-1] if '/' in href else href
                        parts = slug.split('-')
                        if len(parts) > 0:
                            last_part = parts[-1]
                            if last_part.isalnum() and len(last_part) >= 4:
                                code = last_part
                            elif len(parts) >= 2:
                                potential_code = parts[-2] + '-' + parts[-1]
                                if potential_code.replace('-', '').isalnum() and len(potential_code.replace('-', '')) >= 4:
                                    code = potential_code
                            else:
                                code = slug  # Fallback final
                        else:
                            code = slug  # Fallback final
                else:
                    code = href.split('/')[-1] if '/' in href else href
                
                event = {
                    'url': href,
                    'venue_slug': venue_slug,
                    'name': card.get_text(strip=True) if card.name != 'a' else link_elem.get('aria-label', 'Evento'),
                    'code': code
                }
                events.append(event)
            except:
                continue

    # ESTRATEGIA 3: Fallback Simple (más permisivo - cualquier enlace con /events/)
    if not events:
        print(f"   🔍 Debug Estrategia 3: Intentando fallback simple...")
        for link in soup.find_all('a', href=lambda x: x and '/events/' in x):
            href = link.get('href', '')
            if any(e['url'] == href for e in events): continue
            
            # Extraer código del evento de la URL
            code = href.split('/')[-1] if '/' in href else href
            # Obtener nombre del enlace o del texto
            name = link.get('aria-label', '') or link.get_text(strip=True) or 'Evento'
            
            # Si no tiene nombre útil, intentar obtenerlo del href o elementos cercanos
            if name == 'Evento' or not name:
                # Buscar en el texto del enlace o elementos padre
                parent_text = link.find_parent().get_text(strip=True) if link.find_parent() else ''
                if parent_text and len(parent_text) > 5:
                    name = parent_text[:100]  # Limitar longitud
            
            events.append({
                'url': href,
                'venue_slug': venue_slug,
                'name': name,
                'code': code
            })
        print(f"   🔍 Debug Estrategia 3: {len(events)} eventos encontrados con fallback")
    
    # ESTRATEGIA 4: Extraer desde markdown si está disponible y no encontramos eventos
    if not events and markdown:
        print(f"   🔍 Intentando extraer desde markdown ({len(markdown)} caracteres)...")
        # Debug: mostrar preview del markdown
        if len(markdown) > 0:
            preview = markdown[:500] if len(markdown) > 500 else markdown
            print(f"   🔍 Markdown preview: {preview[:200]}...")
        
        # Buscar enlaces en markdown (formato: [texto](url))
        markdown_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', markdown)
        print(f"   🔍 Markdown links encontrados: {len(markdown_links)}")
        # Debug: mostrar los primeros enlaces encontrados
        if markdown_links:
            for i, (text, url) in enumerate(markdown_links[:5]):
                print(f"   🔍 Link {i+1}: [{text}]({url})")
        
        for link_text, link_url in markdown_links:
            if '/events/' in link_url:
                # Extraer código del evento
                code = None
                if 'sala-rem' in venue_slug.lower():
                    # Para Sala Rem: formato es /events/slug--fecha-CODIGO o slug-fecha-CODIGO
                    # El código puede tener 4 o más caracteres alfanuméricos
                    # Ejemplos: -08-01-20261-5YTV, --09-01-2026-HZOY, -10-01-2026-XTNE
                    code_match = re.search(r'/(?:-{1,2})?\d{1,2}-\d{2}-\d{4}\d*-([A-Z0-9]{4,})(?:/|$)', link_url)
                    if code_match:
                        code = code_match.group(1)
                    else:
                        # Fallback: extraer del final de la URL
                        slug_match = re.search(r'/events/([^/]+)(?:/|$)', link_url)
                        if slug_match:
                            slug = slug_match.group(1)
                            parts = slug.split('-')
                            if len(parts) > 0:
                                last_part = parts[-1]
                                # Si la última parte es alfanumérica y tiene al menos 4 caracteres, es el código
                                if last_part.isalnum() and len(last_part) >= 4:
                                    code = last_part
                                # Si no, intentar con las últimas 2 partes (por si hay dígitos extra)
                                elif len(parts) >= 2:
                                    potential_code = parts[-2] + '-' + parts[-1]
                                    if potential_code.replace('-', '').isalnum() and len(potential_code.replace('-', '')) >= 4:
                                        code = potential_code
                else:
                    # Formato estándar: /events/CODIGO
                    code_match = re.search(r'/events/([A-Z0-9-]+)(?:/|$)', link_url)
                    if code_match:
                        code = code_match.group(1)
                
                if code:
                    # Hacer URL absoluta si es relativa
                    if not link_url.startswith('http'):
                        if 'sala-rem' in venue_slug.lower():
                            link_url = f"https://web.fourvenues.com{link_url}"
                        else:
                            link_url = f"https://site.fourvenues.com{link_url}"
                    
                    events.append({
                        'url': link_url,
                        'venue_slug': venue_slug,
                        'name': link_text.strip(),
                        'code': code
                    })
        
        # Si aún no hay eventos, buscar URLs de eventos directamente en el texto markdown y HTML
        if not events:
            print(f"   🔍 Buscando URLs de eventos directamente en markdown y HTML...")
            if 'sala-rem' in venue_slug.lower():
                # Buscar en markdown primero
                event_urls_md = re.findall(r'/es/sala-rem/events/([^/\s\)]+)', markdown)
                print(f"   🔍 URLs encontradas en markdown: {len(event_urls_md)}")
                
                # También buscar en HTML (puede tener más información)
                if html:
                    # Buscar enlaces <a> con href que contenga /events/
                    html_links = re.findall(r'href=["\']([^"\']*sala-rem/events/[^"\']+)["\']', html, re.IGNORECASE)
                    print(f"   🔍 URLs encontradas en HTML: {len(html_links)}")
                    # Combinar ambas fuentes
                    all_urls = set(event_urls_md + [url.split('/events/')[-1] if '/events/' in url else url for url in html_links])
                else:
                    all_urls = set(event_urls_md)
                
                codes_found = set()
                for url_slug in all_urls:
                    # Limpiar la URL (puede tener parámetros o fragmentos)
                    url_slug = url_slug.split('?')[0].split('#')[0]
                    # Extraer código del final
                    parts = url_slug.split('-')
                    if len(parts) > 0 and len(parts[-1]) == 4 and parts[-1].isalnum():
                        code = parts[-1]
                        codes_found.add(code)
                        event_url = f"https://web.fourvenues.com/es/sala-rem/events/{url_slug}"
                        events.append({
                            'url': event_url,
                            'venue_slug': venue_slug,
                            'name': f"Evento {code}",  # Nombre genérico, se actualizará al scrapear detalles
                            'code': code
                        })
                    else:
                        print(f"   🔍 URL slug no válido: {url_slug}")
                print(f"   🔍 URLs directas encontradas (Sala Rem): {len(codes_found)} códigos únicos")
                
                # ESTRATEGIA: Buscar URLs completas en rawHtml primero (más información después del JS)
                # PRIORIDAD: Extraer URLs reales del HTML/rawHtml en lugar de construirlas
                # Esto hace el scraper adaptable a cualquier formato futuro
                if not events:
                    html_to_search = raw_html if raw_html and len(raw_html) > len(html) else html
                    if html_to_search:
                        print(f"   🔍 Buscando URLs reales de eventos en {'rawHtml' if raw_html and len(raw_html) > len(html) else 'HTML'}...")
                        
                        # #region agent log
                        debug_log("debug-session", "run1", "E", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "Buscando URLs reales en HTML/rawHtml", {
                            "html_length": len(html),
                            "raw_html_length": len(raw_html) if raw_html else 0,
                            "using_raw_html": html_to_search == raw_html
                        })
                        # #endregion
                        
                        # Buscar todas las URLs que contengan sala-rem/events con múltiples patrones flexibles
                        # ADAPTATIVO: Usar patrones amplios para capturar cualquier formato de URL
                        # Patrón 1: URLs completas con https:// o http:// (más flexible)
                        html_event_urls = re.findall(r'https?://[^\s"\'<>\)]+sala-rem/events/[^\s"\'<>\)]+', html_to_search, re.IGNORECASE)
                        # Patrón 2: URLs relativas /es/sala-rem/events/ o /sala-rem/events/ (más flexible)
                        html_event_urls += re.findall(r'/es/sala-rem/events/[^\s"\'<>\)]+', html_to_search, re.IGNORECASE)
                        html_event_urls += re.findall(r'/sala-rem/events/[^\s"\'<>\)]+', html_to_search, re.IGNORECASE)
                        # Patrón 3: URLs en atributos href, data-href, data-url, url, etc. (más flexible)
                        html_event_urls += re.findall(r'(?:href|data-href|data-url|url|link|to|path)["\']?\s*[:=]\s*["\']?([^"\']*sala-rem/events/[^"\']+)', html_to_search, re.IGNORECASE)
                        # Patrón 4: URLs en JSON/JavaScript (más común en rawHtml después del JS) - más flexible
                        html_event_urls += re.findall(r'["\']([^"\']*sala-rem/events/[^"\']+)["\']', html_to_search, re.IGNORECASE)
                        # Patrón 5: URLs en atributos de elementos (data-*, aria-*, etc.)
                        html_event_urls += re.findall(r'(?:data-|aria-)\w+["\']?\s*[:=]\s*["\']?([^"\']*sala-rem/events/[^"\']+)', html_to_search, re.IGNORECASE)
                        # Patrón 6: URLs en strings de JavaScript (sin comillas específicas)
                        html_event_urls += re.findall(r'(?:url|href|link|path)\s*[:=]\s*([^\s,;\)]+sala-rem/events/[^\s,;\)]+)', html_to_search, re.IGNORECASE)
                        # Patrón 7: Buscar cualquier ocurrencia de "sala-rem/events/" seguida de caracteres válidos para URL
                        html_event_urls += re.findall(r'sala-rem/events/[a-zA-Z0-9\-_/]+', html_to_search, re.IGNORECASE)
                        
                        print(f"   🔍 URLs de eventos encontradas en HTML: {len(html_event_urls)}")
                        
                        # #region agent log
                        debug_log("debug-session", "run1", "E", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "URLs encontradas (antes de filtrar)", {
                            "total_urls": len(html_event_urls),
                            "sample_urls": html_event_urls[:5]
                        })
                        # #endregion
                        
                        # Si encontramos URLs completas, usarlas directamente (más confiable)
                        # Filtrar y normalizar URLs - ADAPTATIVO: no asumir formato específico
                        unique_urls = []
                        seen_slugs = set()
                        for event_url in html_event_urls:
                            # Limpiar URL (puede tener espacios, caracteres especiales, etc.)
                            event_url = event_url.strip().strip('"').strip("'").strip()
                            if not event_url or len(event_url) < 10:
                                continue
                            
                            # Hacer URL absoluta si es relativa
                            if not event_url.startswith('http'):
                                if event_url.startswith('/'):
                                    event_url = f"https://web.fourvenues.com{event_url}"
                                else:
                                    event_url = f"https://web.fourvenues.com/{event_url}"
                            
                            # Extraer slug único para deduplicar (todo después de /events/)
                            if '/events/' not in event_url:
                                continue
                            
                            url_slug = event_url.split('/events/')[-1].split('?')[0].split('#')[0].strip()
                            if not url_slug or url_slug in seen_slugs:
                                continue
                            
                            # ADAPTATIVO: Aceptar CUALQUIER URL que contenga /events/ sin validaciones estrictas
                            # No asumir formatos específicos - el scraper debe ser adaptable a cualquier formato futuro
                            seen_slugs.add(url_slug)
                            
                            # Extraer código de forma flexible: buscar alfanuméricos al final (4+ caracteres)
                            # No asumir formato específico, solo que el código probablemente está al final
                            code = None
                            slug_parts = url_slug.split('-')
                            
                            # Buscar desde el final hacia atrás un segmento alfanumérico de 4+ caracteres
                            for i in range(len(slug_parts) - 1, -1, -1):
                                part = slug_parts[i]
                                if part.isalnum() and len(part) >= 4:
                                    code = part
                                    break
                                elif part.replace('-', '').isalnum() and len(part.replace('-', '')) >= 4:
                                    code = part
                                    break
                            
                            # Si no encontramos código, intentar con los últimos 2 segmentos combinados
                            if not code and len(slug_parts) >= 2:
                                potential_code = '-'.join(slug_parts[-2:])
                                if potential_code.replace('-', '').isalnum() and len(potential_code.replace('-', '')) >= 4:
                                    code = potential_code
                            
                            # ADAPTATIVO: Si aún no hay código, generar uno desde el slug
                            # Esto permite que el scraper funcione incluso si el formato cambia
                            if not code:
                                # Usar los últimos caracteres del slug como código temporal
                                code = url_slug[-8:] if len(url_slug) >= 8 else url_slug
                            
                            # Extraer nombre del slug de forma flexible
                            # Intentar inferir nombre desde el slug, pero no asumir formato específico
                            code_index = url_slug.rfind(code) if code and code in url_slug else -1
                            if code_index > 0:
                                name_part = url_slug[:code_index].rstrip('-')
                                name_from_slug = name_part.replace('-', ' ').title() if name_part else f"Evento {code}"
                            else:
                                # Si no podemos encontrar el código, usar todo el slug como nombre
                                name_from_slug = url_slug.replace('-', ' ').title() if url_slug else f"Evento {code}"
                            
                            unique_urls.append((event_url, code, name_from_slug))
                            
                            # #region agent log
                            debug_log("debug-session", "run1", "E", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "URL procesada y añadida", {
                                "url": event_url,
                                "code": code,
                                "name": name_from_slug,
                                "url_slug": url_slug
                            })
                            # #endregion
                        
                        print(f"   🔍 Procesando {len(unique_urls)} URLs únicas de eventos...")
                        
                        for event_url, code, name_from_slug in unique_urls:
                            events.append({
                                'url': event_url,
                                'venue_slug': venue_slug,
                                'name': name_from_slug,
                                'code': code
                            })
                            print(f"   🔍 Evento encontrado en HTML: {name_from_slug} - {code} - {event_url[:80]}...")
                        
                        # #region agent log
                        debug_log("debug-session", "run1", "E", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "URLs reales extraídas", {
                            "total_events_from_urls": len(unique_urls),
                            "events": [{"name": n, "code": c, "url": u[:100]} for u, c, n in unique_urls[:5]]
                        })
                        # #endregion
                
                # ESTRATEGIA FINAL (ÚLTIMO RECURSO ABSOLUTO): Solo si NO encontramos URLs reales
                # ⚠️ ADVERTENCIA CRÍTICA: Esta estrategia construye URLs desde markdown, lo cual NO es ideal
                # porque asume formatos que pueden cambiar. Esta estrategia debería eliminarse en el futuro
                # y reemplazarse por una mejor extracción de URLs reales del HTML/rawHtml.
                # 
                # PROBLEMA: Si Sala REM cambia el formato de sus URLs, esta estrategia fallará.
                # SOLUCIÓN IDEAL: Mejorar la extracción de URLs reales del rawHtml para que siempre
                # encontremos las URLs reales y nunca necesitemos construir URLs.
                if not events and markdown and html:
                    print(f"   ⚠️ ADVERTENCIA: No se encontraron URLs reales, usando construcción desde markdown (NO IDEAL)")
                    print(f"   🔍 Esta estrategia puede fallar si Sala REM cambia el formato de sus URLs")
                    print(f"   🔍 Estrategia final: Construir URLs desde markdown y buscar códigos en HTML...")
                    
                    # #region agent log
                    debug_log("debug-session", "run1", "F", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "ADVERTENCIA: Usando construcción de URLs (no ideal)", {
                        "reason": "no_real_urls_found",
                        "html_length": len(html),
                        "raw_html_length": len(raw_html) if raw_html else 0,
                        "markdown_length": len(markdown)
                    })
                    # #endregion
                    print(f"   🔍 Estrategia final: Construir URLs desde markdown y buscar códigos en HTML...")
                    # Extraer nombres de eventos y fechas del markdown
                    # Formato: ## Fri26Dec ... FRIDAY SESSION | SALA REM
                    event_info = []
                    lines = markdown.split('\n')
                    current_date = None
                    for i, line in enumerate(lines):
                        # Detectar fechas (## Fri26Dec)
                        date_match = re.search(r'##\s*(\w{3})(\d{1,2})(\w{3})', line)
                        if date_match:
                            day_name = date_match.group(1)  # Fri, Sat, Wed
                            day_num = date_match.group(2)   # 26, 27, 31
                            month = date_match.group(3)     # Dec
                            # Convertir a formato fecha
                            month_map = {'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06',
                                       'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'}
                            month_num = month_map.get(month, '12')
                            # Corregir año: si estamos en enero 2026, usar 2026, no 2025
                            # El markdown muestra "January 2026" al inicio
                            current_year = 2026  # Año correcto según los eventos del usuario
                            current_date = f"{day_num}-{month_num}-{current_year}"
                        
                        # Detectar nombres de eventos (líneas que no son fechas ni horas)
                        if current_date and line.strip() and not line.startswith('##') and not re.match(r'^\d{1,2}:\d{2}', line.strip()):
                            event_name = line.strip()
                            # Limpiar emojis y caracteres especiales para el slug
                            # Reemplazar caracteres especiales comunes primero
                            slug_name = event_name.lower()
                            # Reemplazar "|" con espacio, luego limpiar
                            slug_name = slug_name.replace('|', ' ')
                            slug_name = slug_name.replace('/', ' ')
                            # Eliminar emojis y caracteres especiales, mantener solo letras, números, espacios y guiones
                            slug_name = re.sub(r'[^\w\s-]', '', slug_name)
                            # Reemplazar múltiples espacios con un solo guion
                            slug_name = re.sub(r'\s+', '-', slug_name)
                            # Eliminar guiones múltiples consecutivos
                            slug_name = re.sub(r'-+', '-', slug_name)
                            slug_name = slug_name.strip('-')
                            event_info.append({
                                'name': event_name,
                                'slug': slug_name,
                                'date': current_date
                            })
                    
                    print(f"   🔍 Eventos detectados en markdown: {len(event_info)}")
                    for evt in event_info:
                        print(f"   🔍   - {evt['name']} ({evt['date']})")
                    
                    # Buscar códigos de 4 caracteres en el HTML que puedan ser códigos de eventos
                    # PRIORIDAD 1: Buscar códigos cerca de "sala-rem/events" (más confiable)
                    event_code_patterns = [
                        r'sala-rem/events/[^"\s<>\)]+-([A-Z0-9]{4})',  # En URLs de eventos
                        r'/events/[^"\s<>\)]+-([A-Z0-9]{4})',  # En URLs de eventos (sin sala-rem)
                        r'data-code["\']?\s*[:=]\s*["\']?([A-Z0-9]{4})',  # En atributos data-code
                        r'code["\']?\s*[:=]\s*["\']?([A-Z0-9]{4})',  # En atributos code
                    ]
                    
                    valid_codes = []
                    for pattern in event_code_patterns:
                        matches = re.findall(pattern, html, re.IGNORECASE)
                        for code in matches:
                            # Validar que el código tiene letras Y números (más probable que sea un código de evento)
                            if any(x.isalpha() for x in code) and any(x.isdigit() for x in code):
                                if code.upper() not in valid_codes:
                                    valid_codes.append(code.upper())
                    
                    # PRIORIDAD 2: Si no encontramos códigos cerca de eventos, buscar en todo el HTML
                    if not valid_codes:
                        potential_codes = re.findall(r'[^a-zA-Z0-9]([A-Z0-9]{4})[^a-zA-Z0-9]', html)
                        # Filtrar códigos que parezcan válidos (tienen letras y números)
                        valid_codes = [c for c in set(potential_codes) if any(x.isalpha() for x in c) and any(x.isdigit() for x in c)]
                    
                    print(f"   🔍 Códigos potenciales encontrados: {len(valid_codes)} (mostrando primeros 10: {valid_codes[:10]})")
                    
                    # Filtrar eventos válidos (excluir texto de cookies, avisos legales, etc.)
                    valid_events = []
                    for evt in event_info:
                        # Filtrar eventos que parezcan válidos (tienen más de 5 caracteres, no son enlaces, etc.)
                        evt_name = evt['name'].strip()
                        # Excluir: enlaces markdown, texto de cookies, avisos legales, fechas solas, etc.
                        if (len(evt_name) > 5 and 
                            not evt_name.startswith('[') and 
                            not evt_name.lower() in ['december 2025', 'cookies', 'configurar', 'rechazar cookies', 'aceptar cookies', 
                                                      'essencial', 'analytics', 'guardar configuración'] and
                            not 'cookie' in evt_name.lower() and
                            not 'política' in evt_name.lower() and
                            not 'aviso' in evt_name.lower() and
                            not 'usamos cookies' in evt_name.lower() and
                            not 'este sitio utiliza' in evt_name.lower()):
                            valid_events.append(evt)
                    
                    print(f"   🔍 Eventos válidos filtrados: {len(valid_events)}")
                    for evt in valid_events:
                        print(f"   🔍   - {evt['name']} ({evt['date']})")
                    
                    # ESTRATEGIA ESCALABLE: Emparejar eventos con códigos por orden de aparición
                    # En lugar de construir todas las combinaciones (N×M), emparejamos por posición
                    # Esto es más eficiente y escalable
                    if valid_events and valid_codes:
                        print(f"   🔍 Emparejando {len(valid_events)} eventos con {len(valid_codes)} códigos por orden de aparición...")
                        
                        # Emparejar por posición: primer evento con primer código, segundo con segundo, etc.
                        # Si hay más eventos que códigos, los eventos extra no se procesan
                        # Si hay más códigos que eventos, los códigos extra se ignoran
                        max_pairs = min(len(valid_events), len(valid_codes))
                        
                        for i in range(max_pairs):
                            evt = valid_events[i]
                            code = valid_codes[i]
                            
                            date_parts = evt['date'].split('-')
                            date_str = f"{date_parts[0]}-{date_parts[1]}-{date_parts[2]}"
                            
                            # Mejorar generación del slug para Sala Rem
                            # El formato es: primera-parte--segunda-parte--fecha-codigo
                            # Ejemplo: friday-session--sala-rem--26-12-2025-EI7Q
                            slug = evt['slug']
                            event_name_lower = evt['name'].lower()
                            
                            # Detectar patrón común: "SESSION | SALA REM" o "SESSION / REM CLUB"
                            # Dividir en dos partes: antes y después de "|" o "/"
                            if '|' in evt['name'] or '/' in evt['name']:
                                # Dividir por "|" o "/"
                                parts = re.split(r'[|/]', evt['name'], 1)
                                if len(parts) == 2:
                                    part1 = parts[0].strip().lower()
                                    part2 = parts[1].strip().lower()
                                    # Limpiar y generar slugs
                                    slug1 = re.sub(r'[^\w\s-]', '', part1)
                                    slug1 = re.sub(r'\s+', '-', slug1).strip('-')
                                    slug2 = re.sub(r'[^\w\s-]', '', part2)
                                    slug2 = re.sub(r'\s+', '-', slug2).strip('-')
                                    # Combinar con doble guion
                                    slug = f"{slug1}--{slug2}"
                            
                            # Formato correcto según ejemplos del usuario:
                            # - Eventos simples: slug-fecha-codigo (ej: jueves-universitario-08-01-20261-5YTV)
                            # - Eventos con | o /: parte1--parte2--fecha-codigo (ej: friday-session--sala-rem--09-01-2026-HZOY)
                            # Nota: algunos eventos tienen un dígito extra después del año (20261), pero por ahora usamos formato estándar
                            if '|' in evt['name'] or '/' in evt['name']:
                                # Eventos con dos partes: usar doble guion antes de la fecha
                                url_slug = f"{slug}--{date_str}-{code}"
                            else:
                                # Eventos simples: usar un solo guion antes de la fecha
                                url_slug = f"{slug}-{date_str}-{code}"
                            test_url = f"https://web.fourvenues.com/es/sala-rem/events/{url_slug}"
                            
                            # Guardar la fecha en el evento para usarla después
                            day, month, year = date_parts[0], date_parts[1], date_parts[2]
                            month_names = {'01': 'enero', '02': 'febrero', '03': 'marzo', '04': 'abril',
                                         '05': 'mayo', '06': 'junio', '07': 'julio', '08': 'agosto',
                                         '09': 'septiembre', '10': 'octubre', '11': 'noviembre', '12': 'diciembre'}
                            date_text = f"{day} {month_names.get(month, 'diciembre')}"
                            
                            events.append({
                                'url': test_url,
                                'venue_slug': venue_slug,
                                'name': evt['name'],
                                'code': code,
                                'date_text': date_text,
                                '_date_parts': {'day': day, 'month': month, 'year': year}
                            })
                            print(f"   🔍 URL construida (orden {i+1}): {evt['name']} - {code} - fecha: {date_text} - {test_url[:100]}...")
                        
                        if len(valid_events) > len(valid_codes):
                            print(f"   ⚠️ {len(valid_events) - len(valid_codes)} eventos sin código (más eventos que códigos)")
                        elif len(valid_codes) > len(valid_events):
                            print(f"   ⚠️ {len(valid_codes) - len(valid_events)} códigos sin evento (más códigos que eventos)")
                        
                        print(f"   🔍 Total URLs construidas: {len(events)} (1 URL por evento, emparejado por orden)")
                    
            else:
                # Para otras discotecas: buscar /events/CODIGO
                event_url_patterns = re.findall(r'/events/([A-Z0-9-]{4,})', markdown)
                for code in set(event_url_patterns):
                    event_url = f"https://site.fourvenues.com/es/{venue_slug}/events/{code}"
                    events.append({
                        'url': event_url,
                        'venue_slug': venue_slug,
                        'name': f"Evento {code}",
                        'code': code
                    })
                print(f"   🔍 URLs directas encontradas: {len(event_url_patterns)}")
        
        print(f"   🔍 Markdown: {len(events)} eventos encontrados")

    # #region agent log
    debug_log("debug-session", "run1", "A", f"scraper_firecrawl_dev.py:{sys._getframe().f_lineno}", "extract_events_from_html END", {
        "total_events": len(events),
        "events_summary": [{"name": e.get('name', ''), "code": e.get('code', ''), "url": e.get('url', '')[:100]} for e in events[:10]]
    })
    # #endregion

    return events


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
    
    # #region agent log
    debug_log("debug-session", "run1", "I", f"scraper_firecrawl.py:{sys._getframe().f_lineno}", "Buscando tickets en schema.org", {
        "html_length": len(html),
        "scripts_found": len(scripts)
    })
    # #endregion
    
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
                        
                        # #region agent log
                        debug_log("debug-session", "run1", "J", f"scraper_firecrawl.py:{sys._getframe().f_lineno}", "Offer encontrado en schema", {
                            "url": url[:100] if url else None,
                            "name": name,
                            "price": price,
                            "has_tickets_url": url and '/tickets/' in url if url else False
                        })
                        # #endregion
                        
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
                        item_type = item.get('@type', '')
                        # #region agent log
                        debug_log("debug-session", "run1", "G", f"scraper_firecrawl.py:{sys._getframe().f_lineno}", "Buscando imagen en schema.org", {
                            "item_type": item_type,
                            "has_image": 'image' in item,
                            "image_value": str(item.get('image', ''))[:100] if item.get('image') else None
                        })
                        # #endregion
                        
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
                                
                                # #region agent log
                                debug_log("debug-session", "run1", "H", f"scraper_firecrawl.py:{sys._getframe().f_lineno}", "Imagen encontrada en schema Event", {
                                    "img_url": img_url[:150],
                                    "is_fourvenues": 'fourvenues.com' in img_url if img_url else False
                                })
                                # #endregion
                                
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
        
        # #region agent log
        debug_log(session_id, run_id, "B", "scraper_firecrawl.py:413", "Schema tickets extraídos", {
            "schema_tickets_count": len(schema_tickets),
            "schema_tickets": [t.copy() if isinstance(t, dict) else str(t) for t in schema_tickets],
            "raw_html_length": len(raw_html),
            "event_url": event_url[:100]
        })
        # #endregion
        
        # Función para normalizar nombres para matching flexible (definir antes de usar)
        def normalize_name(name: str) -> str:
            if not name:
                return ""
            normalized = re.sub(r'\s+', ' ', name.strip().upper())
            normalized = normalized.replace('PROMOCIÓN', 'PROMOCION')
            normalized = normalized.replace('CONSUMICIÓN', 'CONSUMICION')
            normalized = normalized.replace('CONSUMICIONES', 'CONSUMICION')
            return normalized
        
        if schema_tickets:
            # ESTRATEGIA ADAPTATIVA: Priorizar schema cuando tenga precios válidos
            # Si el schema tiene precios y los tickets del markdown no, usar schema como fuente principal
            schema_has_prices = any(st.get('precio') and str(st.get('precio')).strip() not in ['0', 'None', ''] for st in schema_tickets)
            markdown_has_prices = any(t.get('precio') and str(t.get('precio')).strip() not in ['0', 'None', ''] for t in tickets)
            
            # #region agent log
            debug_log(session_id, run_id, "B", "scraper_firecrawl.py:657", "Evaluando estrategia de matching", {
                "schema_tickets_count": len(schema_tickets),
                "markdown_tickets_count": len(tickets),
                "schema_has_prices": schema_has_prices,
                "markdown_has_prices": markdown_has_prices
            })
            # #endregion
            
            # Si el schema tiene precios y el markdown no, priorizar schema
            if schema_has_prices and not markdown_has_prices:
                # #region agent log
                debug_log(session_id, run_id, "B", "scraper_firecrawl.py:670", "Schema tiene precios, markdown no - priorizando schema", {
                    "schema_tickets": [st.copy() for st in schema_tickets[:3]]
                })
                # #endregion
                # Usar schema como base y enriquecer con nombres del markdown si coinciden
                schema_tickets_dict = {normalize_name(st['tipo']): st for st in schema_tickets}
                enriched_tickets = []
                
                for t in tickets:
                    ticket_normalized = normalize_name(t['tipo'])
                    if ticket_normalized in schema_tickets_dict:
                        st = schema_tickets_dict[ticket_normalized]
                        # Combinar: nombre del markdown, precio del schema, estado agotadas del markdown (más confiable)
                        enriched_ticket = copy.deepcopy(st)
                        enriched_ticket['tipo'] = t['tipo']  # Preferir nombre del markdown
                        # Priorizar estado "agotadas" del markdown si está disponible (más confiable que schema)
                        # El markdown detecta "Agotada" en el texto, el schema puede no tener esta info
                        if t.get('agotadas') is True:
                            enriched_ticket['agotadas'] = True
                        # #region agent log
                        debug_log(session_id, run_id, "B", "scraper_firecrawl.py:695", "Enriqueciendo ticket desde schema", {
                            "ticket_markdown": t.copy(),
                            "ticket_schema": st.copy(),
                            "enriched_ticket": enriched_ticket.copy(),
                            "agotadas_preservada": enriched_ticket.get('agotadas', False)
                        })
                        # #endregion
                        enriched_tickets.append(enriched_ticket)
                    else:
                        # Si no hay match, intentar encontrar el mejor match parcial
                        best_partial = None
                        best_score = 0
                        for st in schema_tickets:
                            schema_normalized = normalize_name(st['tipo'])
                            common = len(set(ticket_normalized.split()) & set(schema_normalized.split()))
                            if common > best_score and common >= 2:
                                best_score = common
                                best_partial = st
                        
                        if best_partial:
                            enriched_ticket = copy.deepcopy(best_partial)
                            enriched_ticket['tipo'] = t['tipo']
                            # Priorizar estado "agotadas" del markdown si está disponible
                            if t.get('agotadas') is True:
                                enriched_ticket['agotadas'] = True
                            enriched_tickets.append(enriched_ticket)
                        else:
                            # Si no hay match, usar ticket del markdown pero intentar encontrar precio
                            enriched_tickets.append(copy.deepcopy(t))
                
                # Si hay tickets del schema que no se usaron, añadirlos
                used_schema_names = {normalize_name(t['tipo']) for t in enriched_tickets}
                for st in schema_tickets:
                    if normalize_name(st['tipo']) not in used_schema_names:
                        enriched_tickets.append(copy.deepcopy(st))
                
                tickets = enriched_tickets
            elif tickets:
                # Si ambos tienen tickets, hacer matching inteligente
                # Crear un conjunto de schema_tickets usados para evitar asignaciones duplicadas
                used_schema_tickets = set()
                
                for t in tickets:
                    # #region agent log
                    debug_log(session_id, run_id, "B", "scraper_firecrawl.py:418", "Buscando match para ticket", {
                        "ticket": t.copy(),
                        "schema_tickets_disponibles": [st.copy() for st in schema_tickets]
                    })
                    # #endregion
                    
                    # Buscar coincidencia: PRIORIZAR match por nombre (flexible), luego por precio
                    # Solo usar match por precio si NO hay match por nombre y el precio es único
                    matched = False
                    best_match = None
                    match_type = None
                    
                    # Función para normalizar nombres para matching flexible
                    def normalize_name(name: str) -> str:
                        if not name:
                            return ""
                        # Normalizar: quitar espacios extra, convertir a mayúsculas, quitar acentos básicos
                        normalized = re.sub(r'\s+', ' ', name.strip().upper())
                        # Reemplazar variaciones comunes
                        normalized = normalized.replace('PROMOCIÓN', 'PROMOCION')
                        normalized = normalized.replace('CONSUMICIÓN', 'CONSUMICION')
                        normalized = normalized.replace('CONSUMICIONES', 'CONSUMICION')
                        return normalized
                    
                    ticket_name_normalized = normalize_name(t['tipo'])
                    
                    # Primero buscar match exacto por nombre
                    for idx, st in enumerate(schema_tickets):
                        if idx in used_schema_tickets:
                            continue
                        if st['tipo'] == t['tipo']:
                            best_match = (idx, st)
                            match_type = "name_exact"
                            matched = True
                            break
                    
                    # Si no hay match exacto, buscar match normalizado (flexible)
                    if not matched:
                        for idx, st in enumerate(schema_tickets):
                            if idx in used_schema_tickets:
                                continue
                            schema_name_normalized = normalize_name(st['tipo'])
                            if schema_name_normalized == ticket_name_normalized:
                                best_match = (idx, st)
                                match_type = "name_normalized"
                                matched = True
                                break
                    
                    # Si aún no hay match, buscar match parcial (contiene palabras clave importantes)
                    if not matched:
                        # Extraer palabras clave del ticket (ENTRADA, VIP, COPA, etc.)
                        ticket_keywords = set(re.findall(r'\b(ENTRADA|VIP|COPA|COPAS|CONSUMICION|PROMOCION|RESERVADO|REDUCIDA|ANTICIPADA)\b', ticket_name_normalized))
                        best_partial_match = None
                        best_partial_score = 0
                        
                        for idx, st in enumerate(schema_tickets):
                            if idx in used_schema_tickets:
                                continue
                            schema_name_normalized = normalize_name(st['tipo'])
                            schema_keywords = set(re.findall(r'\b(ENTRADA|VIP|COPA|COPAS|CONSUMICION|PROMOCION|RESERVADO|REDUCIDA|ANTICIPADA)\b', schema_name_normalized))
                            
                            # Calcular score: palabras clave en común
                            common_keywords = ticket_keywords & schema_keywords
                            score = len(common_keywords)
                            
                            # Bonus si el nombre contiene números similares (ej: "1 COPA" vs "1 CONSUMICION")
                            ticket_numbers = set(re.findall(r'\b(\d+)\b', ticket_name_normalized))
                            schema_numbers = set(re.findall(r'\b(\d+)\b', schema_name_normalized))
                            if ticket_numbers and schema_numbers and ticket_numbers == schema_numbers:
                                score += 2
                            
                            if score > best_partial_score and score >= 2:  # Mínimo 2 palabras clave en común
                                best_partial_match = (idx, st)
                                best_partial_score = score
                        
                        if best_partial_match:
                            best_match = best_partial_match
                            match_type = "name_partial"
                            matched = True
                    
                    # Si no hay match por nombre, buscar por precio (solo si el precio es único)
                    if not matched and t['precio'] != "0":
                        # Contar cuántos schema_tickets tienen el mismo precio
                        price_matches = [st for idx, st in enumerate(schema_tickets) 
                                       if idx not in used_schema_tickets 
                                       and st['precio'] == t['precio'] 
                                       and st['precio'] != "0"]
                        
                        # Solo usar match por precio si hay exactamente UN match (evitar ambigüedad)
                        if len(price_matches) == 1:
                            for idx, st in enumerate(schema_tickets):
                                if idx in used_schema_tickets:
                                    continue
                                if st['precio'] == t['precio'] and st['precio'] != "0":
                                    best_match = (idx, st)
                                    match_type = "price_unique"
                                    matched = True
                                    break
                    
                    if matched and best_match:
                        idx, st = best_match
                        used_schema_tickets.add(idx)  # Marcar como usado
                        old_url = t['url_compra']
                        old_price = t['precio']
                        t['url_compra'] = st['url_compra']
                        
                        # SIEMPRE ACTUALIZAR PRECIO desde schema si está disponible
                        # El schema es la fuente de verdad más confiable para precios
                        if st['precio'] and st['precio'] != "0" and st['precio'] != "None":
                            t['precio'] = str(st['precio']).strip()
                        
                        # Actualizar estado "agotadas" desde schema SOLO si el markdown no tiene información
                        # El markdown es más confiable para detectar "agotadas" (detecta "Agotada" en el texto)
                        # Solo usar schema si el markdown no tiene el estado definido o es False
                        if 'agotadas' in st:
                            # Si el markdown ya detectó "agotadas" como True, mantenerlo (más confiable)
                            if t.get('agotadas') is not True:
                                # Si el schema dice que está agotada, actualizar
                                if st['agotadas'] is True:
                                    t['agotadas'] = True
                                # Si el schema dice que NO está agotada pero el markdown no tenía info, usar schema
                                elif t.get('agotadas') is None:
                                    t['agotadas'] = st['agotadas']
                        
                        # #region agent log
                        debug_log(session_id, run_id, "B", "scraper_firecrawl.py:421", "MATCH encontrado", {
                            "ticket_tipo": t['tipo'],
                            "ticket_precio_antes": old_price,
                            "ticket_precio_despues": t['precio'],
                            "schema_tipo": st['tipo'],
                            "schema_precio": st['precio'],
                            "match_type": match_type,
                            "url_anterior": old_url,
                            "url_nueva": t['url_compra'],
                            "precio_actualizado": old_price != t['precio'],
                            "agotadas_actualizada": t.get('agotadas', False)
                        })
                        # #endregion
                    else:
                        # #region agent log
                        debug_log(session_id, run_id, "B", "scraper_firecrawl.py:421", "NO se encontró match", {
                            "ticket": t.copy(),
                            "reason": "no_match" if not matched else "ambiguous_price"
                        })
                        # #endregion
            else:
                # Si no hay tickets del markdown, usar directamente los del schema
                tickets = schema_tickets
                # #region agent log
                debug_log(session_id, run_id, "B", "scraper_firecrawl.py:674", "Usando tickets directamente del schema (sin markdown)", {
                    "schema_tickets_count": len(schema_tickets),
                    "schema_tickets": [st.copy() for st in schema_tickets]
                })
                # #endregion

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
        # Para Sala Rem: deduplicar por nombre + fecha (ya que tenemos múltiples códigos para el mismo evento)
        # Para otros: deduplicar por URL o código
        seen_urls = set()
        seen_codes = set()
        seen_name_date = set()  # Para Sala Rem: (nombre_normalizado, fecha)
        unique_events = []
        
        print(f"\n🔍 Deduplicando {len(all_events)} eventos...")
        
        for event in all_events:
            event_url = event.get('url', '')
            event_code = event.get('code', '')
            event_name = event.get('name', '')
            venue_slug = event.get('venue_slug', '')
            is_sala_rem = 'sala-rem' in venue_slug.lower()
            
            # #region agent log
            debug_log("debug-session", "run1", "A", f"scraper_firecrawl.py:{sys._getframe().f_lineno}", "Procesando evento para deduplicación", {
                "event_name": event_name,
                "event_url": event_url[:100],
                "event_code": event_code,
                "is_sala_rem": is_sala_rem,
                "_date_parts": event.get('_date_parts'),
                "date_text": event.get('date_text')
            })
            # #endregion
            
            # Para Sala Rem: deduplicar por nombre + fecha
            if is_sala_rem:
                # Normalizar nombre (eliminar emojis, espacios extra, etc.)
                name_normalized = re.sub(r'[^\w\s]', '', event_name.lower()).strip()
                name_normalized = re.sub(r'\s+', ' ', name_normalized)
                # Obtener fecha de _date_parts o date_text
                event_date = None
                if event.get('_date_parts'):
                    date_parts = event['_date_parts']
                    event_date = f"{date_parts['day']}-{date_parts['month']}-{date_parts['year']}"
                elif event.get('date_text'):
                    # Intentar extraer fecha de date_text
                    date_match = re.search(r'(\d{1,2})\s+\w+', event.get('date_text', ''))
                    if date_match:
                        day = date_match.group(1)
                        # Buscar mes en date_text
                        month_map = {'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
                                   'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
                                   'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'}
                        for month_name, month_num in month_map.items():
                            if month_name in event.get('date_text', '').lower():
                                event_date = f"{day}-{month_num}-2025"
                                break
                
                # #region agent log
                debug_log("debug-session", "run1", "B", f"scraper_firecrawl.py:{sys._getframe().f_lineno}", "Deduplicación Sala Rem", {
                    "name_normalized": name_normalized,
                    "event_date": event_date,
                    "name_date_key": (name_normalized, event_date) if event_date else None,
                    "seen_name_date": list(seen_name_date)
                })
                # #endregion
                
                if event_date:
                    name_date_key = (name_normalized, event_date)
                    if name_date_key in seen_name_date:
                        print(f"   ⚠️ Evento duplicado (nombre+fecha): {event_name} - {event_date} - código: {event_code}")
                        # #region agent log
                        debug_log("debug-session", "run1", "C", f"scraper_firecrawl.py:{sys._getframe().f_lineno}", "Evento duplicado detectado (Sala Rem)", {
                            "event_name": event_name,
                            "event_date": event_date,
                            "name_date_key": name_date_key
                        })
                        # #endregion
                        continue
                    seen_name_date.add(name_date_key)
                    print(f"   ✅ Evento único (Sala Rem): {event_name} - {event_date} - código: {event_code}")
                else:
                    print(f"   ⚠️ No se pudo extraer fecha para {event_name}, usando URL para deduplicación")
            
            # Si ya vimos esta URL, saltar
            if event_url in seen_urls:
                print(f"   ⚠️ Evento duplicado (URL): {event.get('name', 'N/A')} - {event_url[:80]}...")
                # #region agent log
                debug_log("debug-session", "run1", "D", f"scraper_firecrawl.py:{sys._getframe().f_lineno}", "Evento duplicado detectado (URL)", {
                    "event_name": event_name,
                    "event_url": event_url[:100]
                })
                # #endregion
                continue
            
            # Para otros venues: deduplicar por código
            if not is_sala_rem and event_code and event_code in seen_codes:
                print(f"   ⚠️ Evento duplicado (código): {event.get('name', 'N/A')} - código: {event_code}")
                # #region agent log
                debug_log("debug-session", "run1", "E", f"scraper_firecrawl.py:{sys._getframe().f_lineno}", "Evento duplicado detectado (código)", {
                    "event_name": event_name,
                    "event_code": event_code
                })
                # #endregion
                continue
            
            seen_urls.add(event_url)
            if event_code:
                seen_codes.add(event_code)
            unique_events.append(event)
            print(f"   ✅ Evento único añadido: {event_name} - {event_code}")
            # #region agent log
            debug_log("debug-session", "run1", "F", f"scraper_firecrawl.py:{sys._getframe().f_lineno}", "Evento único añadido", {
                "event_name": event_name,
                "event_code": event_code,
                "event_url": event_url[:100],
                "total_unique": len(unique_events)
            })
            # #endregion
        
        if len(unique_events) < len(all_events):
            print(f"   ✅ Eventos deduplicados: {len(all_events)} → {len(unique_events)}")
        
        all_events = unique_events  # Usar eventos únicos
        
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
