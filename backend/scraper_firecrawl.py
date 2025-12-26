#!/usr/bin/env python3
"""
Scraper de eventos para PartyFinder usando Firecrawl
=====================================================
Utiliza Firecrawl para bypass Cloudflare y extrae eventos del HTML.

Este scraper se ejecuta automáticamente mediante GitHub Actions 3 veces al día.
No requiere navegador local ya que utiliza la API de Firecrawl.

Uso:
    python3 scraper_firecrawl.py                    # Scraping completo
    python3 scraper_firecrawl.py --test             # Solo test de conexión
    python3 scraper_firecrawl.py --upload           # Scraping + Firebase
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
VENUE_URLS = [
    "https://site.fourvenues.com/es/luminata-disco/events",
    "https://site.fourvenues.com/es/el-club-by-odiseo/events",
    "https://site.fourvenues.com/es/dodo-club/events"
]


def extract_events_from_html(html: str, venue_url: str) -> List[Dict]:
    """
    Extrae eventos del HTML de FourVenues de forma robusta.
    """
    events = []
    soup = BeautifulSoup(html, 'html.parser')
    venue_slug = venue_url.split('/')[-2] if '/events' in venue_url else ''
    
    # ESTRATEGIA 1: Enlaces con aria-label (Luminata, Odiseo)
    event_links = soup.find_all('a', href=lambda x: x and '/events/' in x and x.count('/') >= 4)
    
    for link in event_links:
        try:
            href = link.get('href', '')
            aria_label = link.get('aria-label', '')
            
            if not aria_label or 'Evento' not in aria_label:
                continue
            
            event = {
                'url': href,
                'venue_slug': venue_slug,
                'image': link.find('img').get('src', '') if link.find('img') else ''
            }
            
            # Código del evento
            match = re.search(r'/events/([A-Z0-9-]+)$', href)
            if match:
                event['code'] = match.group(1)
            
            # Parsear aria-label
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
            if horario_match:
                event['hora_inicio'] = horario_match.group(1)
                event['hora_fin'] = horario_match.group(2)
            
            if event.get('name') and event.get('code'):
                events.append(event)
        except:
            continue

    # ESTRATEGIA 2: Componentes personalizados / data-testid (Dodo Club)
    if not events:
        event_cards = soup.find_all(attrs={"data-testid": ["event-card", "event-card-name"]})
        if not event_cards:
            event_cards = soup.find_all('div', class_=lambda x: x and 'event' in x and 'card' in x)

        for card in event_cards:
            try:
                link_elem = card.find_parent('a') or card.find('a') or (card if card.name == 'a' else None)
                if not link_elem: continue
                
                href = link_elem.get('href', '')
                if not href or '/events/' not in href: continue
                if any(e['url'] == href for e in events): continue

                event = {
                    'url': href,
                    'venue_slug': venue_slug,
                    'name': card.get_text(strip=True) if card.name != 'a' else link_elem.get('aria-label', 'Evento'),
                    'code': href.split('/')[-1]
                }
                events.append(event)
            except:
                continue

    # ESTRATEGIA 3: Fallback Simple
    if not events:
        for link in soup.find_all('a', href=lambda x: x and '/events/' in x and x.count('/') >= 4):
            href = link.get('href', '')
            if any(e['url'] == href for e in events): continue
            
            events.append({
                'url': href,
                'venue_slug': venue_slug,
                'name': link.get('aria-label', link.get_text(strip=True) or 'Evento'),
                'code': href.split('/')[-1]
            })

    return events


def scrape_venue(firecrawl: Firecrawl, url: str) -> List[Dict]:
    """
    Scrapea eventos de una URL de venue con lógica agresiva de bypass.
    """
    print(f"\n📡 Scrapeando: {url}")
    
    try:
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
        status = result.metadata.status_code if result.metadata else "N/A"
        
        print(f"   Status: {status}")
        print(f"   HTML: {len(html)} bytes")
        
        if not html:
            print("   ❌ No se recibió HTML")
            return []
        
        events = extract_events_from_html(html, url)
        
        # Si sigue sin pillar nada, intentar un segundo intento con JS más agresivo
        if not events and "dodo" in url.lower():
            print("   ⚠️ No detectados en primer intento. Reintentando con scroll profundo...")
            result = firecrawl.scrape(
                url,
                formats=["html"],
                actions=[
                    {"type": "scroll", "direction": "down", "amount": 1000},
                    {"type": "wait", "milliseconds": 5000}
                ]
            )
            html = result.html or ""
            events = extract_events_from_html(html, url)

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
    if not event_url.startswith('http'):
        event_url = f"https://site.fourvenues.com{event_url}"
    
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
        
        if not html and not markdown:
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
                    
                    # Intentar extraer precio inline (ej: "PRIMERAS ENTRADAS 8€")
                    inline_price = "0"
                    price_inline_match = re.search(r'(\d+(?:[,.]\d+)?)\s*€', ticket_name)
                    if price_inline_match:
                        inline_price = price_inline_match.group(1).replace(',', '.')
                    
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
        og_image = soup.find('meta', {'property': 'og:image'})
        if og_image:
            event['image'] = og_image.get('content', event.get('image', ''))
        
        # ===== INTEGRAR URLs EXACTAS DESDE SCHEMA/RAW =====
        schema_tickets = extract_tickets_from_schema(raw_html)
        
        # #region agent log
        debug_log(session_id, run_id, "B", "scraper_firecrawl.py:413", "Schema tickets extraídos", {
            "schema_tickets_count": len(schema_tickets),
            "schema_tickets": [st.copy() for st in schema_tickets]
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
        # Parsear fecha
        fecha = datetime.now().strftime('%Y-%m-%d')
        date_text = event.get('date_text', '')
        
        # Intentar parsear la fecha
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
        
        # Usar tags extraídos o inferidos
        tags = event.get('tags', ['Fiesta'])
        
        # Información del venue
        venue_info = event.get('venue_info', {})
        
        transformed_event = {
            "evento": {
                "nombreEvento": event.get('name', 'Evento'),
                "descripcion": event.get('description', ''),
                "fecha": fecha,
                "hora_inicio": event.get('hora_inicio', '23:00'),
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
            all_events[i] = result
            # #region agent log
            debug_log(session_id, run_id, "F", "scraper_firecrawl.py:880", "Evento procesado en scrape_all_events", {
                "event_index": i,
                "event_name": result.get('name', 'N/A'),
                "event_code": result.get('code', 'N/A'),
                "tickets_after": [t.copy() if isinstance(t, dict) else str(t) for t in result.get('tickets', [])]
            })
            # #endregion
    
    print(f"\n🎉 Total: {len(all_events)} eventos scrapeados")
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
    
    parser = argparse.ArgumentParser(description='Scraper FourVenues con Firecrawl')
    parser.add_argument('--test', '-t', action='store_true', help='Solo test de conexión')
    parser.add_argument('--upload', '-u', action='store_true', help='Subir a Firebase')
    parser.add_argument('--no-details', action='store_true', help='No obtener detalles de eventos')
    
    args = parser.parse_args()
    
    # Crear directorio data
    DATA_DIR.mkdir(exist_ok=True)
    
    if args.test:
        success = test_connection()
        return 0 if success else 1
    
    # Scraping completo
    raw_events = scrape_all_events(get_details=not args.no_details)
    
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
    
    # Subir a Firebase
    if args.upload:
        print("\n📤 Subiendo a Firebase...")
        try:
            from firebase_config import upload_events_to_firestore, delete_old_events
            delete_old_events()
            upload_events_to_firestore(transformed)
            print("✅ Datos subidos a Firebase")
            
            # Enviar push notifications para nuevos eventos
            print("\n📬 Verificando y enviando notificaciones push...")
            try:
                from push_notifications import check_and_send_notifications
                check_and_send_notifications()
            except Exception as e:
                print(f"⚠️ Error enviando notificaciones: {e}")
                # No fallar el scraper si las notificaciones fallan
        except Exception as e:
            print(f"❌ Error subiendo a Firebase: {e}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
