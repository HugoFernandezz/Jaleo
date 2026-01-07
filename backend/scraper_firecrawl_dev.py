#!/usr/bin/env python3
"""
Scraper de eventos para PartyFinder usando Firecrawl - VERSIÓN DESARROLLO REFACTORIZADA
=======================================================================================
Versión mejorada con código más limpio y estrategias de extracción más robustas.
"""

import json
import os
import re
import sys
import copy
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple
from pathlib import Path
from bs4 import BeautifulSoup
from dataclasses import dataclass, field

try:
    from firecrawl import Firecrawl
except ImportError:
    print("❌ Error: firecrawl-py no está instalado")
    print("   Instalar con: pip install firecrawl-py")
    sys.exit(1)

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

API_KEY = os.environ.get("FIRECRAWL_API_KEY")
if not API_KEY:
    print("WARNING: Faltan credenciales: FIRECRAWL_API_KEY")

DATA_DIR = Path(__file__).parent / "data"
LOG_PATH = Path(__file__).parent.parent / ".cursor" / "debug.log"

VENUE_URLS = [
    "https://web.fourvenues.com/es/sala-rem/events"
]

# Patrones de URLs inválidas (plantillas de JS, código, etc.)
INVALID_URL_PATTERNS = [
    r'\$\*\*\*',
    r'Message\.',
    r'evento_slug',
    r'evento_codigo',
    r'function\s*\(',
    r'window\.',
    r'var\s+\w+\s*=',
    r'createelement',
]

# ============================================================================
# UTILIDADES DE LOGGING
# ============================================================================

def debug_log(session_id: str, run_id: str, hypothesis_id: str, 
              location: str, message: str, data: dict):
    """Logging simplificado para debugging"""
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
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            f.flush()
        
        # Log crítico a stdout
        if 'error' in message.lower() or 'warning' in message.lower():
            print(f"[{hypothesis_id}] {location}: {message}")
    except Exception as e:
        print(f"[LOG ERROR] {e}", file=sys.stderr)


# ============================================================================
# MODELOS DE DATOS
# ============================================================================

@dataclass
class EventURL:
    """Representa una URL de evento extraída"""
    url: str
    code: str
    name: str = ""
    date_parts: Optional[Dict[str, str]] = None
    source: str = "unknown"  # html, markdown, schema, etc.
    
    def __hash__(self):
        return hash(self.url)
    
    def is_valid(self) -> bool:
        """Valida que la URL no sea una plantilla de JS"""
        for pattern in INVALID_URL_PATTERNS:
            if re.search(pattern, self.url, re.IGNORECASE):
                return False
        return bool(self.code and len(self.code) >= 4)


@dataclass
class Event:
    """Modelo de evento con toda su información"""
    url: str
    code: str
    venue_slug: str
    name: str = ""
    image: str = ""
    description: str = ""
    date_text: str = ""
    date_parts: Optional[Dict[str, str]] = None
    hora_inicio: str = "23:00"
    hora_fin: str = "06:00"
    age_min: int = 18
    age_info: str = ""
    tickets: List[Dict] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    venue_info: Dict = field(default_factory=dict)
    is_invalid: bool = False


# ============================================================================
# EXTRACTORES DE URLs
# ============================================================================

class URLExtractor:
    """Clase base para extractores de URLs de eventos"""
    
    def __init__(self, venue_slug: str):
        self.venue_slug = venue_slug
        self.is_sala_rem = 'sala-rem' in venue_slug.lower()
    
    def extract(self, html: str, markdown: str = "", raw_html: str = "") -> Set[EventURL]:
        """Método a implementar por subclases"""
        raise NotImplementedError
    
    def extract_code_from_url(self, url: str) -> Optional[str]:
        """Extrae el código de evento de una URL de forma adaptativa"""
        if not url or '/events/' not in url:
            return None
        
        if self.is_sala_rem:
            # Patrón principal: fecha seguida de código
            # Ejemplos: -08-01-20261-5YTV, --09-01-2026-HZOY
            match = re.search(r'-{1,2}\d{1,2}-\d{2}-\d{4}\d*-([A-Z0-9]{4,})(?:/|$)', url)
            if match:
                return match.group(1)
            
            # Fallback: último segmento alfanumérico de 4+ caracteres
            slug = url.split('/events/')[-1].split('/')[0].split('?')[0].split('#')[0]
            parts = slug.split('-')
            
            # Buscar desde el final
            for i in range(len(parts) - 1, -1, -1):
                part = parts[i]
                if part.isalnum() and len(part) >= 4:
                    return part
            
            return None
        else:
            # Formato estándar: /events/CODIGO
            match = re.search(r'/events/([A-Z0-9-]{4,})(?:/|$)', url)
            return match.group(1) if match else None
    
    def make_absolute_url(self, url: str) -> str:
        """Convierte URL relativa en absoluta"""
        if url.startswith('http'):
            return url
        
        base = "https://web.fourvenues.com" if self.is_sala_rem else "https://site.fourvenues.com"
        return f"{base}{url}" if url.startswith('/') else f"{base}/{url}"


class HTMLLinkExtractor(URLExtractor):
    """Extrae URLs desde enlaces HTML (<a> tags)"""
    
    def extract(self, html: str, markdown: str = "", raw_html: str = "") -> Set[EventURL]:
        if not html:
            return set()
        
        soup = BeautifulSoup(html, 'html.parser')
        event_urls = set()
        
        # Buscar todos los enlaces con /events/
        links = soup.find_all('a', href=lambda x: x and '/events/' in x)
        
        for link in links:
            href = link.get('href', '')
            if not href:
                continue
            
            # Hacer URL absoluta
            url = self.make_absolute_url(href)
            
            # Extraer código
            code = self.extract_code_from_url(url)
            if not code:
                continue
            
            # Extraer nombre del aria-label o texto
            name = link.get('aria-label', '') or link.get_text(strip=True)
            
            # Limpiar nombre (quitar "Evento: " prefix)
            if name.startswith('Evento'):
                name = re.sub(r'^Evento\s*:\s*', '', name)
            
            event_url = EventURL(
                url=url,
                code=code,
                name=name,
                source="html_link"
            )
            
            if event_url.is_valid():
                event_urls.add(event_url)
        
        return event_urls


class RawHTMLExtractor(URLExtractor):
    """Extrae URLs directamente del HTML raw (después de JS)"""
    
    def extract(self, html: str, markdown: str = "", raw_html: str = "") -> Set[EventURL]:
        # Priorizar raw_html si disponible (más info después del JS)
        source_html = raw_html if raw_html and len(raw_html) > len(html) else html
        
        if not source_html:
            return set()
        
        event_urls = set()
        
        # Patrones para encontrar URLs de eventos
        patterns = [
            # URLs completas
            r'https?://[^\s"\'<>\)]+/events/[^\s"\'<>\)]+',
            # URLs relativas
            r'/es/[^/]+/events/[^\s"\'<>\)]+',
            r'/[^/]+/events/[^\s"\'<>\)]+',
            # En atributos
            r'(?:href|data-href|data-url|url|link|to|path)["\']?\s*[:=]\s*["\']?([^"\']*events/[^"\']+)',
            # En JSON/JS
            r'["\']([^"\']*events/[^"\']+)["\']',
        ]
        
        found_urls = set()
        for pattern in patterns:
            matches = re.findall(pattern, source_html, re.IGNORECASE)
            for match in matches:
                # El match puede ser una tupla si hay grupos de captura
                url = match if isinstance(match, str) else match[0] if match else ""
                if url and 'events/' in url:
                    found_urls.add(url.strip().strip('"').strip("'"))
        
        # Procesar URLs encontradas
        for url in found_urls:
            # Limpiar y validar
            url = url.split('?')[0].split('#')[0]
            
            if not url or len(url) < 10:
                continue
            
            # Validar que no sea plantilla de JS
            is_invalid = any(re.search(p, url, re.IGNORECASE) for p in INVALID_URL_PATTERNS)
            if is_invalid:
                continue
            
            # Hacer absoluta
            url = self.make_absolute_url(url)
            
            # Extraer código
            code = self.extract_code_from_url(url)
            if not code:
                continue
            
            # Inferir nombre del slug
            slug = url.split('/events/')[-1].split('?')[0].split('#')[0]
            # Quitar el código y convertir a título
            name_part = slug[:slug.rfind(code)] if code in slug else slug
            name = name_part.replace('-', ' ').strip().title()
            
            event_url = EventURL(
                url=url,
                code=code,
                name=name or f"Evento {code}",
                source="raw_html"
            )
            
            if event_url.is_valid():
                event_urls.add(event_url)
        
        return event_urls


class MarkdownExtractor(URLExtractor):
    """Extrae información de eventos desde markdown"""
    
    def extract(self, html: str, markdown: str = "", raw_html: str = "") -> Set[EventURL]:
        if not markdown:
            return set()
        
        event_urls = set()
        
        # Buscar enlaces markdown: [texto](url)
        markdown_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', markdown)
        
        for text, url in markdown_links:
            if '/events/' not in url:
                continue
            
            url = self.make_absolute_url(url)
            code = self.extract_code_from_url(url)
            
            if not code:
                continue
            
            event_url = EventURL(
                url=url,
                code=code,
                name=text.strip(),
                source="markdown"
            )
            
            if event_url.is_valid():
                event_urls.add(event_url)
        
        return event_urls


# ============================================================================
# EXTRACCIÓN DE EVENTOS
# ============================================================================

def extract_events_from_sources(html: str, venue_url: str, 
                                markdown: str = "", raw_html: str = "") -> List[Event]:
    """
    Estrategia principal de extracción: usar múltiples extractores y combinar resultados
    """
    venue_slug = venue_url.split('/')[-2] if '/events' in venue_url else ''
    
    # Inicializar extractores
    extractors = [
        HTMLLinkExtractor(venue_slug),
        RawHTMLExtractor(venue_slug),
        MarkdownExtractor(venue_slug),
    ]
    
    # Recolectar URLs de todas las fuentes
    all_event_urls: Set[EventURL] = set()
    
    for extractor in extractors:
        try:
            urls = extractor.extract(html, markdown, raw_html)
            all_event_urls.update(urls)
            print(f"   📍 {extractor.__class__.__name__}: {len(urls)} URLs encontradas")
        except Exception as e:
            print(f"   ⚠️ Error en {extractor.__class__.__name__}: {e}")
    
    # Deduplicar por código (mantener la mejor fuente)
    unique_events: Dict[str, EventURL] = {}
    source_priority = {"html_link": 3, "raw_html": 2, "markdown": 1}
    
    for event_url in all_event_urls:
        code = event_url.code
        
        if code not in unique_events:
            unique_events[code] = event_url
        else:
            # Mantener la fuente de mayor prioridad
            existing = unique_events[code]
            if source_priority.get(event_url.source, 0) > source_priority.get(existing.source, 0):
                unique_events[code] = event_url
    
    # Convertir a objetos Event
    events = []
    for event_url in unique_events.values():
        event = Event(
            url=event_url.url,
            code=event_url.code,
            venue_slug=venue_slug,
            name=event_url.name or f"Evento {event_url.code}",
            date_parts=event_url.date_parts
        )
        
        # Extraer fecha de la URL si es Sala REM
        if 'sala-rem' in venue_slug.lower():
            date_match = re.search(r'-{1,2}(\d{1,2})-(\d{2})-(\d{4})\d*-', event_url.url)
            if date_match:
                event.date_parts = {
                    'day': date_match.group(1).zfill(2),
                    'month': date_match.group(2),
                    'year': date_match.group(3)
                }
                
                month_names = {
                    '01': 'enero', '02': 'febrero', '03': 'marzo', '04': 'abril',
                    '05': 'mayo', '06': 'junio', '07': 'julio', '08': 'agosto',
                    '09': 'septiembre', '10': 'octubre', '11': 'noviembre', '12': 'diciembre'
                }
                event.date_text = f"{event.date_parts['day']} {month_names.get(event.date_parts['month'], 'diciembre')}"
        
        events.append(event)
    
    print(f"   ✅ Total eventos únicos: {len(events)}")
    return events


# ============================================================================
# SCRAPING DE DETALLES
# ============================================================================

def extract_tickets_from_markdown(markdown: str) -> List[Dict]:
    """Extrae información de tickets desde markdown de forma robusta"""
    if not markdown:
        return []
    
    tickets = []
    lines = markdown.split('\n')
    current_ticket = None
    ticket_start_line = -1
    
    # Identificar líneas de tickets
    ticket_lines = []
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith('- ') and any(kw in line.upper() for kw in 
            ['ENTRADA', 'ENTRADAS', 'PROMOCIÓN', 'PROMOCION', 'VIP', 'RESERVADO', 'LISTA']):
            ticket_lines.append(i)
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Detectar nuevo ticket
        if i in ticket_lines:
            if current_ticket:
                tickets.append(current_ticket)
            
            ticket_name = line[2:].strip()
            
            # Extraer precio inline
            inline_price = "0"
            price_match = re.search(r'(\d+(?:[,.]\d+)?)\s*€', ticket_name)
            if price_match:
                inline_price = price_match.group(1).replace(',', '.')
            
            current_ticket = {
                "tipo": ticket_name,
                "precio": inline_price,
                "agotadas": False,
                "descripcion": ""
            }
            ticket_start_line = i
        
        # Detectar precio en línea siguiente (solo si no tiene precio inline)
        elif current_ticket and current_ticket['precio'] == "0":
            if re.search(r'^\d+\s*€$', line):
                # Calcular distancia al siguiente ticket
                next_ticket_line = None
                for tl in ticket_lines:
                    if tl > ticket_start_line:
                        next_ticket_line = tl
                        break
                
                distance = i - ticket_start_line
                max_distance = (next_ticket_line - ticket_start_line) if next_ticket_line else 50
                
                if distance <= max_distance:
                    price_match = re.search(r'(\d+)\s*€', line)
                    if price_match:
                        current_ticket['precio'] = price_match.group(1)
        
        # Detectar estado agotado
        elif current_ticket and 'agotad' in line.lower():
            current_ticket['agotadas'] = True
        
        # Detectar descripción
        elif current_ticket and any(kw in line.lower() for kw in ['copa', 'consumir', 'alcohol']):
            if not current_ticket['descripcion']:
                current_ticket['descripcion'] = line
    
    # Añadir último ticket
    if current_ticket:
        tickets.append(current_ticket)
    
    # Deduplicar
    unique_tickets = []
    seen = set()
    for t in tickets:
        key = f"{t['tipo'].lower().strip()}|{t['precio']}"
        if key not in seen:
            seen.add(key)
            unique_tickets.append(t)
    
    return unique_tickets


def extract_tickets_from_schema(html: str) -> List[Dict]:
    """Extrae URLs precisas de tickets desde Schema.org (JSON-LD)"""
    if not html:
        return []
    
    tickets = []
    soup = BeautifulSoup(html, 'html.parser')
    scripts = soup.find_all('script', type='application/ld+json')
    
    for script in scripts:
        try:
            if not script.string:
                continue
            
            data = json.loads(script.string.strip())
            
            # Manejar @graph o lista
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get('@graph', [data])
            
            for item in items:
                offers = item.get('offers', [])
                if isinstance(offers, dict):
                    offers = [offers]
                
                for offer in offers:
                    if offer.get('@type') == 'Offer':
                        url = offer.get('url')
                        if url and '/tickets/' in url:
                            availability = str(offer.get('availability', '')).lower()
                            is_sold_out = 'outofstock' in availability or 'soldout' in availability
                            
                            tickets.append({
                                "tipo": offer.get('name', 'Entrada'),
                                "precio": str(offer.get('price', '0')),
                                "url_compra": url,
                                "agotadas": is_sold_out
                            })
        except:
            continue
    
    return tickets


def scrape_event_details(firecrawl: Firecrawl, event: Event) -> Event:
    """Obtiene detalles completos de un evento"""
    event = copy.deepcopy(event)
    
    if not event.url:
        return event
    
    try:
        # Scrape con múltiples formatos
        result = firecrawl.scrape(
            event.url,
            formats=["html", "markdown", "rawHtml"],
            actions=[{"type": "wait", "milliseconds": 8000}]
        )
        
        html = result.html or ""
        raw_html = getattr(result, 'raw_html', None) or html
        markdown = result.markdown or ""
        
        # Validar contenido
        if not html and not markdown:
            event.is_invalid = True
            return event
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # === TICKETS ===
        tickets_markdown = extract_tickets_from_markdown(markdown)
        tickets_schema = extract_tickets_from_schema(raw_html)
        
        # Combinar tickets: priorizar schema para URLs, markdown para nombres
        if tickets_schema and tickets_markdown:
            # Matching inteligente
            for md_ticket in tickets_markdown:
                best_match = None
                for schema_ticket in tickets_schema:
                    if md_ticket['tipo'].upper() in schema_ticket['tipo'].upper():
                        best_match = schema_ticket
                        break
                
                if best_match:
                    md_ticket['url_compra'] = best_match['url_compra']
                    if best_match['precio'] != '0':
                        md_ticket['precio'] = best_match['precio']
                else:
                    md_ticket['url_compra'] = event.url
        elif tickets_schema:
            tickets_markdown = tickets_schema
        
        # Asignar URL por defecto si falta
        for ticket in tickets_markdown:
            if 'url_compra' not in ticket:
                ticket['url_compra'] = event.url
        
        event.tickets = tickets_markdown
        
        # === IMAGEN ===
        og_image = soup.find('meta', {'property': 'og:image'})
        if og_image:
            event.image = og_image.get('content', '')
        else:
            # Buscar en schema
            match = re.search(r'"image"\s*:\s*"([^"]+)"', raw_html)
            if match:
                event.image = match.group(1)
        
        # === DESCRIPCIÓN ===
        if markdown:
            lines = [l.strip() for l in markdown.split('\n')[:20]]
            for line in lines:
                if (line and not line.startswith(('!', '#', '-', '[')) 
                    and len(line) > 50 
                    and 'google.com/maps' not in line.lower()):
                    event.description = line
                    break
        
        # === TAGS ===
        event_name_lower = event.name.lower()
        if 'reggaeton' in event_name_lower or 'latino' in event_name_lower:
            event.tags = ['Reggaeton', 'Latino']
        elif 'viernes' in event_name_lower:
            event.tags = ['Fiesta', 'Viernes']
        elif 'sabado' in event_name_lower or 'sábado' in event_name_lower:
            event.tags = ['Fiesta', 'Sábado']
        else:
            event.tags = ['Fiesta']
        
        return event
        
    except Exception as e:
        print(f"      ⚠️ Error scraping detalles: {e}")
        return event


# ============================================================================
# SCRAPING PRINCIPAL
# ============================================================================

def scrape_venue(firecrawl: Firecrawl, url: str) -> List[Event]:
    """Scrapea eventos de una URL de venue"""
    print(f"\n🔗 Scrapeando: {url}")
    
    try:
        is_sala_rem = "sala-rem" in url.lower()
        
        # Configuración adaptada al venue
        if is_sala_rem:
            result = firecrawl.scrape(
                url,
                formats=["html", "markdown", "rawHtml"],
                actions=[
                    {"type": "wait", "milliseconds": 15000},
                    {"type": "scroll", "direction": "down", "amount": 1500},
                    {"type": "wait", "milliseconds": 5000},
                ],
                wait_for=15000
            )
        else:
            result = firecrawl.scrape(
                url,
                formats=["html"],
                actions=[
                    {"type": "wait", "milliseconds": 8000},
                    {"type": "scroll", "direction": "down", "amount": 500},
                    {"type": "wait", "milliseconds": 2000}
                ],
                wait_for=5000
            )
        
        html = result.html or ""
        raw_html = getattr(result, 'raw_html', None) or ""
        markdown = result.markdown or ""
        
        print(f"   HTML: {len(html)} bytes")
        print(f"   Raw HTML: {len(raw_html)} bytes")
        print(f"   Markdown: {len(markdown)} caracteres")
        
        if not html and not raw_html:
            print("   ❌ No se recibió HTML")
            return []
        
        # Extraer eventos
        events = extract_events_from_sources(html, url, markdown, raw_html)
        
        print(f"   ✅ {len(events)} eventos encontrados")
        return events
        
    except Exception as e:
        print(f"   ❌ Error: {type(e).__name__}: {e}")
        return []


def scrape_all_events(urls: List[str] = None, get_details: bool = True) -> List[Event]:
    """Scrapea eventos de todas las URLs"""
    target_urls = urls or VENUE_URLS
    all_events = []
    
    print("=" * 60)
    print("PartyFinder - Firecrawl Scraper (Refactorizado)")
    print("=" * 60)
    
    firecrawl = Firecrawl(api_key=API_KEY)
    
    # Scrape inicial
    for url in target_urls:
        events = scrape_venue(firecrawl, url)
        all_events.extend(events)
    
    # Deduplicar
    unique_events = []
    seen_codes = set()
    
    for event in all_events:
        if event.code not in seen_codes:
            seen_codes.add(event.code)
            unique_events.append(event)
    
    print(f"\n📋 Eventos únicos después de deduplicación: {len(unique_events)}")
    all_events = unique_events
    
    # Obtener detalles
    if get_details and all_events:
        print(f"\n🎫 Obteniendo detalles de {len(all_events)} eventos...")
        
        detailed_events = []
        for i, event in enumerate(all_events):
            print(f"   [{i+1}/{len(all_events)}] {event.name[:40]}...")
            detailed = scrape_event_details(firecrawl, event)
            
            if not detailed.is_invalid:
                detailed_events.append(detailed)
        
        all_events = detailed_events
    
    print(f"\n🎉 Total: {len(all_events)} eventos válidos")
    return all_events


# ============================================================================
# TRANSFORMACIÓN Y GUARDADO
# ============================================================================

def transform_to_app_format(events: List[Event]) -> List[Dict]:
    """Transforma eventos al formato de la app"""
    transformed = []
    
    for event in events:
        # Calcular fecha
        fecha = datetime.now().strftime('%Y-%m-%d')
        
        if event.date_parts:
            fecha = f"{event.date_parts['year']}-{event.date_parts['month']}-{event.date_parts['day']}"
        
        # Ajustar si hora_inicio es 00:00 (evento es del día anterior)
        if event.hora_inicio in ('00:00', '0:00'):
            try:
                fecha_obj = datetime.strptime(fecha, '%Y-%m-%d')
                fecha_obj = fecha_obj - timedelta(days=1)
                fecha = fecha_obj.strftime('%Y-%m-%d')
            except:
                pass
        
        # Preparar entradas
        entradas = [copy.deepcopy(t) for t in event.tickets] if event.tickets else [{
            "tipo": "Entrada General",
            "precio": "0",
            "agotadas": False,
            "url_compra": event.url
        }]
        
        transformed_event = {
            "evento": {
                "nombreEvento": event.name,
                "descripcion": event.description,
                "fecha": fecha,
                "hora_inicio": event.hora_inicio,
                "hora_fin": event.hora_fin,
                "imagen_url": event.image,
                "url_evento": event.url,
                "code": event.code,
                "entradas": entradas,
                "tags": event.tags,
                "edad_minima": event.age_min,
                "lugar": {
                    "nombre": event.venue_slug.replace('-', ' ').title(),
                    "