#!/usr/bin/env python3
"""
Scraper de eventos para PartyFinder usando Firecrawl
=====================================================
Utiliza Firecrawl para bypass Cloudflare y extrae eventos del HTML.

Este scraper se ejecuta automáticamente mediante GitHub Actions 3 veces al día.
No requiere navegador local ya que utiliza la API de Firecrawl.

Arquitectura:
    - VenueScraperBase: Clase base abstracta con lógica común
    - SiteFourVenuesScraper: Para venues en site.fourvenues.com (Luminata, Odiseo, Dodo)
    - SalaRemScraper: Para Sala Rem en web.fourvenues.com (estrategia separada)

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
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from bs4 import BeautifulSoup


# ==============================================================================
# CONFIGURACIÓN Y UTILIDADES
# ==============================================================================

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

DATA_DIR = Path(__file__).parent / "data"


class DebugLogger:
    """Logger centralizado para debug del scraper."""
    
    LOG_PATH = Path(__file__).parent.parent / ".cursor" / "debug.log"
    
    @classmethod
    def log(cls, hypothesis_id: str, location: str, message: str, data: dict):
        """Escribe un log de debug."""
        try:
            cls.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            log_entry = {
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": hypothesis_id,
                "location": location,
                "message": message,
                "data": data,
                "timestamp": int(datetime.now().timestamp() * 1000)
            }
            with open(cls.LOG_PATH, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
                f.flush()
            print(f"[DEBUG {hypothesis_id}] {location}: {message}", file=sys.stdout)
            if 'precio' in str(data).lower() or 'price' in str(data).lower():
                print(f"  → Precio data: {json.dumps(data, ensure_ascii=False)}", file=sys.stdout)
        except Exception as e:
            print(f"[DEBUG LOG ERROR] {e}", file=sys.stderr)


def normalize_ticket_name(name: str) -> str:
    """Normaliza nombres de tickets para comparación."""
    if not name:
        return ""
    normalized = re.sub(r'\s+', ' ', name.strip().upper())
    normalized = normalized.replace('PROMOCIÓN', 'PROMOCION')
    normalized = normalized.replace('CONSUMICIÓN', 'CONSUMICION')
    normalized = normalized.replace('CONSUMICIONES', 'CONSUMICION')
    return normalized


# ==============================================================================
# CLASE BASE: VenueScraperBase
# ==============================================================================

class VenueScraperBase(ABC):
    """
    Clase base abstracta para scrapers de venues.
    
    Cada venue hereda de esta clase e implementa su propia estrategia de extracción.
    """
    
    # Propiedades que deben definir las subclases
    name: str = ""  # Slug del venue (ej: "luminata-disco")
    base_url: str = "https://site.fourvenues.com"  # Dominio base
    
    def __init__(self, firecrawl: Firecrawl = None):
        self.firecrawl = firecrawl or Firecrawl(api_key=API_KEY)
    
    @property
    def venue_url(self) -> str:
        """URL completa de la página de eventos del venue."""
        return f"{self.base_url}/es/{self.name}/events"
    
    def get_scrape_config(self) -> dict:
        """
        Configuración de Firecrawl para este venue.
        Las subclases pueden override para configuración específica.
        """
        return {
            "formats": ["html"],
            "actions": [
                {"type": "wait", "milliseconds": 8000},
                {"type": "scroll", "direction": "down", "amount": 500},
                {"type": "wait", "milliseconds": 2000}
            ],
            "wait_for": 5000
        }
    
    def get_retry_config(self) -> dict:
        """Configuración para reintentos con scroll más agresivo."""
        return {
            "formats": ["html"],
            "actions": [
                {"type": "wait", "milliseconds": 10000},
                {"type": "scroll", "direction": "down", "amount": 1500},
                {"type": "wait", "milliseconds": 5000},
                {"type": "scroll", "direction": "down", "amount": 1500},
                {"type": "wait", "milliseconds": 5000}
            ],
            "wait_for": 10000
        }
    
    @abstractmethod
    def extract_events_from_html(self, html: str, markdown: str = None, raw_html: str = None) -> List[Dict]:
        """
        Extrae eventos del HTML scrapeado.
        Cada subclase implementa su propia estrategia.
        """
        pass
    
    def scrape_events_list(self) -> List[Dict]:
        """
        Scrapea la lista de eventos del venue.
        Retorna lista de eventos básicos (URL, nombre, código).
        """
        print(f"\n📡 Scrapeando: {self.venue_url}")
        
        try:
            config = self.get_scrape_config()
            result = self.firecrawl.scrape(self.venue_url, **config)
            
            html = result.html or ""
            raw_html = getattr(result, 'raw_html', None) or ""
            markdown = getattr(result, 'markdown', None) or ""
            status = result.metadata.status_code if result.metadata else "N/A"
            
            print(f"   Status: {status}")
            print(f"   HTML: {len(html)} bytes")
            if raw_html:
                print(f"   Raw HTML: {len(raw_html)} bytes")
            if markdown:
                print(f"   Markdown: {len(markdown)} caracteres")
            
            if not html and not raw_html:
                print("   ❌ No se recibió HTML")
                return []
            
            events = self.extract_events_from_html(html, markdown, raw_html)
            
            # Reintento si no se encontraron eventos
            if not events and self.should_retry():
                print("   ⚠️ No detectados en primer intento. Reintentando...")
                events = self._retry_scrape()
            
            print(f"   ✅ {len(events)} eventos encontrados")
            return events
            
        except Exception as e:
            print(f"   ❌ Error: {type(e).__name__}: {e}")
            return []
    
    def should_retry(self) -> bool:
        """Indica si este venue debe reintentar si no encuentra eventos."""
        return False
    
    def _retry_scrape(self) -> List[Dict]:
        """Reintento con configuración más agresiva."""
        config = self.get_retry_config()
        result = self.firecrawl.scrape(self.venue_url, **config)
        html = result.html or ""
        raw_html = getattr(result, 'raw_html', None) or ""
        markdown = getattr(result, 'markdown', None) or ""
        print(f"   HTML segundo intento: {len(html)} bytes")
        return self.extract_events_from_html(html, markdown, raw_html)
    
    def scrape_event_details(self, event: Dict) -> Dict:
        """
        Scrapea detalles completos de un evento específico.
        
        Extrae:
        - Descripción del evento
        - Tickets con precios reales
        - Géneros musicales / tags
        - Información del venue
        """
        event = copy.deepcopy(event)
        event_url = event.get('url', '')
        
        if not event_url:
            return event
        
        # Hacer URL absoluta si es relativa
        if not event_url.startswith('http'):
            event_url = f"{self.base_url}{event_url}"
        
        DebugLogger.log("A", "scrape_event_details:START", "Iniciando scrape de detalles", {
            "event_name": event.get('name', 'N/A'),
            "event_url": event_url[:100]
        })
        
        try:
            result = self.firecrawl.scrape(
                event_url,
                formats=["html", "markdown", "rawHtml"],
                actions=[{"type": "wait", "milliseconds": 8000}]
            )
            
            html = result.html or ""
            raw_html = getattr(result, 'raw_html', None) or html or ""
            markdown = result.markdown or ""
            
            if not html and not markdown:
                print(f"      ⚠️ URL inválida o no accesible: {event_url}")
                event['_invalid'] = True
                return event
            
            soup = BeautifulSoup(html, 'html.parser') if html else None
            
            # Extraer tickets desde markdown
            tickets = self._extract_tickets_from_markdown(markdown, event_url)
            
            # Enriquecer con datos de schema.org
            schema_tickets = self._extract_tickets_from_schema(raw_html)
            if schema_tickets:
                tickets = self._merge_tickets(tickets, schema_tickets)
            
            if tickets:
                event['tickets'] = tickets
            
            # Extraer descripción
            description = self._extract_description(markdown)
            if description:
                event['description'] = description
            
            # Extraer imagen
            image_url = self._extract_image(soup, raw_html)
            if image_url:
                event['image'] = image_url
            
            # Extraer tags/géneros
            tags = self._extract_tags(soup, event.get('name', ''))
            event['tags'] = tags
            
            # Extraer información del venue
            venue_info = self._extract_venue_info(soup)
            if venue_info:
                event['venue_info'] = venue_info
            
            # IMPORTANTE: Extraer fecha desde Schema.org si no tenemos fecha
            if not event.get('date_text') and not event.get('_date_parts'):
                date_info = self._extract_date_from_schema(raw_html)
                if date_info:
                    event.update(date_info)
                    print(f"      📅 Fecha extraída de Schema.org: {event.get('date_text', 'N/A')}")
            
            return event
            
        except Exception as e:
            print(f"      ⚠️ Error detalles: {e}")
            DebugLogger.log("E", "scrape_event_details:ERROR", str(e), {
                "event_url": event_url
            })
            return event
    
    def _extract_tickets_from_markdown(self, markdown: str, event_url: str) -> List[Dict]:
        """Extrae tickets desde el markdown de Firecrawl."""
        tickets = []
        if not markdown:
            return tickets
        
        lines = markdown.split('\n')
        current_ticket = None
        ticket_start_line = -1
        last_ticket_end_line = -1
        MAX_DISTANCE = 50
        MIN_DISTANCE_FROM_PREVIOUS = 2
        
        # Pre-coleccionar líneas de tickets
        ticket_lines = []
        for j, l in enumerate(lines):
            if l.startswith('- ') and any(keyword in l.upper() for keyword in 
                ['ENTRADA', 'ENTRADAS', 'PROMOCIÓN', 'PROMOCION', 'VIP', 'RESERVADO', 'LISTA']):
                ticket_lines.append(j)
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Detectar línea de ticket
            is_ticket_line = line.startswith('- ') and any(keyword in line.upper() for keyword in 
                ['ENTRADA', 'ENTRADAS', 'PROMOCIÓN', 'PROMOCION', 'VIP', 'RESERVADO', 'LISTA'])
            
            if is_ticket_line:
                if current_ticket:
                    if '_candidate_price_line' in current_ticket:
                        del current_ticket['_candidate_price_line']
                    tickets.append(current_ticket)
                    last_ticket_end_line = i - 1
                
                ticket_name = line[2:].strip()
                
                # Extraer precio inline
                inline_price = "0"
                price_match = re.search(r'(\d+(?:[,.]\d+)?)\s*€', ticket_name)
                if price_match:
                    inline_price = price_match.group(1).replace(',', '.')
                
                # Buscar precio en líneas siguientes si tiene "consumición"
                if inline_price == "0" and ('consumicion' in ticket_name.lower() or 'consumición' in ticket_name.lower()):
                    for j in range(i + 1, min(i + 6, len(lines))):
                        next_line = lines[j].strip()
                        pm = re.search(r'(\d+(?:[,.]\d+)?)\s*€', next_line)
                        if pm:
                            inline_price = pm.group(1).replace(',', '.')
                            break
                
                current_ticket = {
                    "tipo": ticket_name,
                    "precio": inline_price,
                    "agotadas": False,
                    "descripcion": "",
                    "url_compra": event_url
                }
                ticket_start_line = i
            
            # Detectar precio separado
            elif current_ticket and re.search(r'^\d+\s*€$', line) and current_ticket['precio'] == "0":
                distance = i - ticket_start_line
                next_ticket = next((tl for tl in ticket_lines if tl > ticket_start_line), None)
                max_dist = min(next_ticket - ticket_start_line, MAX_DISTANCE) if next_ticket else MAX_DISTANCE
                
                if distance <= max_dist and (i - last_ticket_end_line) >= MIN_DISTANCE_FROM_PREVIOUS:
                    pm = re.search(r'(\d+)\s*€', line)
                    if pm:
                        if '_candidate_price_line' not in current_ticket or i < current_ticket['_candidate_price_line']:
                            current_ticket['precio'] = pm.group(1)
                            current_ticket['_candidate_price_line'] = i
            
            # Detectar agotada
            elif current_ticket and 'agotad' in line.lower():
                distance = i - ticket_start_line
                next_ticket = next((tl for tl in ticket_lines if tl > ticket_start_line), None)
                max_dist = min(next_ticket - ticket_start_line, MAX_DISTANCE) if next_ticket else MAX_DISTANCE
                
                if distance <= max_dist and (i - last_ticket_end_line) >= MIN_DISTANCE_FROM_PREVIOUS:
                    current_ticket['agotadas'] = True
            
            # Capturar descripción
            elif current_ticket and ('copa' in line.lower() or 'consumir' in line.lower() or 'alcohol' in line.lower()):
                distance = i - ticket_start_line
                next_ticket = next((tl for tl in ticket_lines if tl > ticket_start_line), None)
                max_dist = min(next_ticket - ticket_start_line, MAX_DISTANCE) if next_ticket else MAX_DISTANCE
                
                if distance <= max_dist and (i - last_ticket_end_line) >= MIN_DISTANCE_FROM_PREVIOUS:
                    if not current_ticket['descripcion'] or len(line) > len(current_ticket['descripcion']):
                        current_ticket['descripcion'] = line
        
        # Añadir último ticket
        if current_ticket:
            if '_candidate_price_line' in current_ticket:
                del current_ticket['_candidate_price_line']
            tickets.append(current_ticket)
        
        # Deduplicar
        unique_tickets = []
        seen = set()
        for t in tickets:
            name_clean = re.sub(r'\s+', ' ', t['tipo']).strip().lower()
            price_clean = str(t['precio']).replace(',', '.')
            ticket_id = f"{name_clean}|{price_clean}"
            if ticket_id not in seen:
                seen.add(ticket_id)
                unique_tickets.append(t)
        
        return unique_tickets
    
    def _extract_tickets_from_schema(self, html: str) -> List[Dict]:
        """Extrae tickets desde bloques JSON-LD (Schema.org)."""
        tickets = []
        if not html:
            return tickets
        
        soup = BeautifulSoup(html, 'html.parser')
        scripts = soup.find_all('script', type='application/ld+json')
        
        for script in scripts:
            try:
                if not script.string:
                    continue
                data = json.loads(script.string.strip())
                
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
                            name = offer.get('name')
                            price = offer.get('price')
                            
                            if url and '/tickets/' in url:
                                availability = str(offer.get('availability', '')).lower()
                                is_sold_out = (
                                    'outofstock' in availability or
                                    'soldout' in availability or
                                    offer.get('availabilityStatus') == 'SoldOut'
                                )
                                
                                tickets.append({
                                    "tipo": name,
                                    "precio": str(price),
                                    "url_compra": url,
                                    "agotadas": is_sold_out
                                })
            except:
                continue
        
        # Fallback: regex
        if not tickets:
            pattern = r'"url"\s*:\s*"(https?://[^"]+/tickets/[a-z0-9]{20,})"'
            matches = re.findall(pattern, html)
            for url in set(matches):
                tickets.append({
                    "url_compra": url,
                    "tipo": "Entrada (Detectada)",
                    "precio": "0",
                    "agotadas": False
                })
        
        return tickets
    
    def _merge_tickets(self, markdown_tickets: List[Dict], schema_tickets: List[Dict]) -> List[Dict]:
        """Combina tickets de markdown y schema.org."""
        if not markdown_tickets:
            return schema_tickets
        if not schema_tickets:
            return markdown_tickets
        
        schema_has_prices = any(
            st.get('precio') and str(st.get('precio')).strip() not in ['0', 'None', '']
            for st in schema_tickets
        )
        markdown_has_prices = any(
            t.get('precio') and str(t.get('precio')).strip() not in ['0', 'None', '']
            for t in markdown_tickets
        )
        
        # Si schema tiene precios y markdown no, priorizar schema
        if schema_has_prices and not markdown_has_prices:
            schema_dict = {normalize_ticket_name(st['tipo']): st for st in schema_tickets}
            enriched = []
            
            for t in markdown_tickets:
                t_norm = normalize_ticket_name(t['tipo'])
                if t_norm in schema_dict:
                    st = schema_dict[t_norm]
                    enriched_ticket = copy.deepcopy(st)
                    enriched_ticket['tipo'] = t['tipo']
                    if t.get('agotadas'):
                        enriched_ticket['agotadas'] = True
                    enriched.append(enriched_ticket)
                else:
                    # Buscar match parcial
                    best_partial = None
                    best_score = 0
                    for st in schema_tickets:
                        st_norm = normalize_ticket_name(st['tipo'])
                        common = len(set(t_norm.split()) & set(st_norm.split()))
                        if common > best_score and common >= 2:
                            best_score = common
                            best_partial = st
                    
                    if best_partial:
                        enriched_ticket = copy.deepcopy(best_partial)
                        enriched_ticket['tipo'] = t['tipo']
                        if t.get('agotadas'):
                            enriched_ticket['agotadas'] = True
                        enriched.append(enriched_ticket)
                    else:
                        enriched.append(copy.deepcopy(t))
            
            # Añadir tickets del schema no usados
            used_names = {normalize_ticket_name(t['tipo']) for t in enriched}
            for st in schema_tickets:
                if normalize_ticket_name(st['tipo']) not in used_names:
                    enriched.append(copy.deepcopy(st))
            
            return enriched
        
        # Si ambos tienen tickets, hacer matching
        used_schema = set()
        for t in markdown_tickets:
            t_norm = normalize_ticket_name(t['tipo'])
            
            # Buscar match exacto
            for idx, st in enumerate(schema_tickets):
                if idx in used_schema:
                    continue
                if st['tipo'] == t['tipo'] or normalize_ticket_name(st['tipo']) == t_norm:
                    used_schema.add(idx)
                    t['url_compra'] = st['url_compra']
                    if st['precio'] and st['precio'] not in ['0', 'None']:
                        t['precio'] = str(st['precio']).strip()
                    if st.get('agotadas') and not t.get('agotadas'):
                        t['agotadas'] = st['agotadas']
                    break
        
        return markdown_tickets
    
    def _extract_description(self, markdown: str) -> str:
        """Extrae descripción del evento desde markdown."""
        if not markdown:
            return ""
        
        lines = markdown.split('\n')
        for line in lines[:20]:
            line = line.strip()
            if (line and not line.startswith('!') and not line.startswith('#')
                and not line.startswith('-') and not line.startswith('[')
                and len(line) > 50
                and 'RESERVA' not in line.upper() and 'DERECHO' not in line.upper()
                and 'google.com/maps' not in line.lower()):
                return line
        
        return ""
    
    def _extract_image(self, soup: BeautifulSoup, raw_html: str) -> str:
        """Extrae URL de imagen del evento."""
        # 1. Meta og:image
        if soup:
            og_image = soup.find('meta', {'property': 'og:image'})
            if og_image:
                img_url = og_image.get('content', '')
                if img_url and 'fourvenues.com' in img_url:
                    return img_url
        
        # 2. Schema.org
        if raw_html:
            soup_temp = BeautifulSoup(raw_html, 'html.parser')
            for script in soup_temp.find_all('script', type='application/ld+json'):
                try:
                    if not script.string:
                        continue
                    data = json.loads(script.string.strip())
                    items = data.get('@graph', [data]) if isinstance(data, dict) else data
                    
                    for item in items:
                        if item.get('@type') == 'Event' or 'Event' in str(item.get('@type', '')):
                            event_image = item.get('image')
                            if event_image:
                                if isinstance(event_image, str):
                                    img_url = event_image
                                elif isinstance(event_image, dict):
                                    img_url = event_image.get('url', '')
                                elif isinstance(event_image, list) and event_image:
                                    img_url = event_image[0] if isinstance(event_image[0], str) else event_image[0].get('url', '')
                                else:
                                    continue
                                
                                if img_url and 'fourvenues.com' in img_url:
                                    return img_url
                except:
                    continue
            
            # Fallback regex
            match = re.search(r'"image"\s*:\s*"([^"]+)"', raw_html)
            if match and 'fourvenues.com' in match.group(1):
                return match.group(1)
        
        # 3. HTML img tag
        if soup:
            main_image = soup.find('img', {'class': lambda x: x and ('hero' in str(x).lower() or 'main' in str(x).lower() or 'event' in str(x).lower())})
            if not main_image:
                main_image = soup.find('img', src=lambda x: x and 'fourvenues.com' in x and ('cdn-cgi' in x or 'imagedelivery' in x))
            if main_image:
                img_url = main_image.get('src', '')
                if img_url and not img_url.startswith('http'):
                    img_url = f"{self.base_url}{img_url}" if img_url.startswith('/') else f"{self.base_url}/{img_url}"
                return img_url
        
        return ""
    
    def _extract_tags(self, soup: BeautifulSoup, event_name: str) -> List[str]:
        """Extrae géneros musicales / tags del evento."""
        tags = []
        genre_keywords = ['reggaeton', 'comercial', 'latin', 'techno', 'house', 'electro',
                         'hip hop', 'trap', 'remember', 'indie', 'pop', 'rock', 'r&b']
        
        # Buscar en aria-labels
        if soup:
            for elem in soup.find_all(attrs={'aria-label': True}):
                label = elem.get('aria-label', '').lower()
                for genre in genre_keywords:
                    if genre in label and genre.title() not in tags:
                        tags.append(genre.title())
        
        # Analizar nombre del evento
        event_name_lower = event_name.lower()
        for genre in genre_keywords:
            if genre in event_name_lower and genre.title() not in tags:
                tags.append(genre.title())
        
        if not tags:
            if 'viernes' in event_name_lower:
                tags = ['Fiesta', 'Viernes']
            elif 'sabado' in event_name_lower or 'sábado' in event_name_lower:
                tags = ['Fiesta', 'Sábado']
            else:
                tags = ['Fiesta']
        
        return tags
    
    def _extract_venue_info(self, soup: BeautifulSoup) -> Dict:
        """Extrae información del venue desde el HTML."""
        venue_info = {}
        
        if not soup:
            return venue_info
        
        # Buscar dirección
        address_elem = soup.find(attrs={'class': lambda x: x and 'address' in str(x).lower()})
        if address_elem:
            venue_info['direccion'] = address_elem.get_text(strip=True)
        
        # Buscar en schema.org
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
        
        return venue_info
    
    def _extract_date_from_schema(self, html: str) -> Optional[Dict]:
        """
        Extrae fecha del evento desde Schema.org JSON-LD.
        
        Schema.org Event tiene campos startDate y endDate en formato ISO 8601.
        Ejemplo: "2025-01-10T23:59:00+01:00"
        """
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                if not script.string:
                    continue
                data = json.loads(script.string.strip())
                
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    items = data.get('@graph', [data])
                
                for item in items:
                    if item.get('@type') == 'Event' or 'Event' in str(item.get('@type', '')):
                        start_date = item.get('startDate')
                        end_date = item.get('endDate')
                        
                        if start_date:
                            # Parsear fecha ISO 8601: "2025-01-10T23:59:00+01:00"
                            date_match = re.match(r'(\d{4})-(\d{2})-(\d{2})T?(\d{2})?:?(\d{2})?', start_date)
                            if date_match:
                                year = date_match.group(1)
                                month = date_match.group(2)
                                day = date_match.group(3)
                                hora = date_match.group(4) or '23'
                                minuto = date_match.group(5) or '00'
                                
                                # Mapear mes a nombre en español
                                month_names = {
                                    '01': 'enero', '02': 'febrero', '03': 'marzo', '04': 'abril',
                                    '05': 'mayo', '06': 'junio', '07': 'julio', '08': 'agosto',
                                    '09': 'septiembre', '10': 'octubre', '11': 'noviembre', '12': 'diciembre'
                                }
                                
                                result = {
                                    'date_text': f"{int(day)} {month_names.get(month, 'enero')}",
                                    '_date_parts': {'day': day, 'month': month, 'year': year},
                                    'hora_inicio': f"{hora}:{minuto}"
                                }
                                
                                # Extraer hora de fin si existe
                                if end_date:
                                    end_match = re.match(r'\d{4}-\d{2}-\d{2}T?(\d{2})?:?(\d{2})?', end_date)
                                    if end_match and end_match.group(1):
                                        result['hora_fin'] = f"{end_match.group(1)}:{end_match.group(2) or '00'}"
                                
                                return result
            except:
                continue
        
        return None


# ==============================================================================
# SCRAPERS site.fourvenues.com (Luminata, Odiseo, Dodo)
# ==============================================================================

class SiteFourVenuesScraper(VenueScraperBase):
    """
    Scraper para venues en site.fourvenues.com.
    
    Estrategia principal: ARIA-LABEL
    Los eventos tienen enlaces con aria-label estructurado:
    "Evento: NOMBRE. Edad mínima: X años. Fecha: DD de mes. Horario: de HH:MM a HH:MM"
    """
    
    base_url = "https://site.fourvenues.com"
    
    def extract_event_code(self, href: str) -> Optional[str]:
        """Extrae el código del evento de la URL. Formato: /events/CODIGO"""
        match = re.search(r'/events/([A-Z0-9-]+)$', href)
        return match.group(1) if match else None
    
    def parse_aria_label(self, aria_label: str) -> Dict:
        """Parsea el aria-label estructurado de FourVenues."""
        result = {}
        
        # Nombre del evento
        name_match = re.search(r'Evento\s*:\s*(.+?)(?:\.\s*Edad|\s*$)', aria_label)
        if name_match:
            result['name'] = name_match.group(1).strip()
        
        # Edad mínima
        age_match = re.search(r'Edad mínima:\s*(.+?)(?:\.\s*Fecha|\s*$)', aria_label)
        if age_match:
            result['age_info'] = age_match.group(1).strip()
            num_match = re.search(r'(\d+)', age_match.group(1))
            if num_match:
                result['age_min'] = int(num_match.group(1))
        
        # Fecha
        fecha_match = re.search(r'Fecha:\s*(.+?)(?:\.\s*Horario|\s*$)', aria_label)
        if fecha_match:
            result['date_text'] = fecha_match.group(1).strip()
        
        # Horario
        horario_match = re.search(r'Horario:\s*de\s*(\d{1,2}:\d{2})\s*a\s*(\d{1,2}:\d{2})', aria_label)
        if horario_match:
            result['hora_inicio'] = horario_match.group(1)
            result['hora_fin'] = horario_match.group(2)
        
        return result
    
    def extract_events_from_html(self, html: str, markdown: str = None, raw_html: str = None) -> List[Dict]:
        """
        Extrae eventos usando la ESTRATEGIA 1: aria-label.
        """
        events = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # Debug
        all_event_links = soup.find_all('a', href=lambda x: x and '/events/' in x)
        print(f"   🔍 Debug: {len(all_event_links)} enlaces con '/events/' encontrados")
        
        # Buscar enlaces con aria-label que contenga "Evento"
        event_links = soup.find_all('a', href=lambda x: x and '/events/' in x and x.count('/') >= 4)
        print(f"   🔍 Debug Estrategia ARIA-LABEL: {len(event_links)} enlaces candidatos")
        
        for link in event_links:
            try:
                href = link.get('href', '')
                aria_label = link.get('aria-label', '')
                
                if not aria_label or 'Evento' not in aria_label:
                    continue
                
                # Extraer código
                code = self.extract_event_code(href)
                if not code:
                    continue
                
                # Parsear aria-label
                parsed = self.parse_aria_label(aria_label)
                if not parsed.get('name'):
                    continue
                
                event = {
                    'url': href,
                    'venue_slug': self.name,
                    'code': code,
                    'image': link.find('img').get('src', '') if link.find('img') else '',
                    **parsed
                }
                
                events.append(event)
                
            except Exception:
                continue
        
        # ESTRATEGIA 2: data-testid (fallback)
        if not events:
            events = self._extract_via_data_testid(soup)
        
        # ESTRATEGIA 3: Fallback simple
        if not events:
            events = self._extract_via_fallback(soup)
        
        return events
    
    def _extract_via_data_testid(self, soup: BeautifulSoup) -> List[Dict]:
        """ESTRATEGIA 2: Buscar por data-testid (usado por Dodo Club)."""
        events = []
        
        event_cards = soup.find_all(attrs={"data-testid": ["event-card", "event-card-name"]})
        print(f"   🔍 Debug Estrategia DATA-TESTID: {len(event_cards)} elementos encontrados")
        
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
                
                code = href.split('/')[-1] if '/' in href else href
                
                # Obtener nombre del card
                name = card.get_text(strip=True) if card.name != 'a' else 'Evento'
                
                event = {
                    'url': href,
                    'venue_slug': self.name,
                    'name': name,
                    'code': code
                }
                
                # IMPORTANTE: Buscar aria-label en el enlace para extraer fecha
                # El enlace padre suele tener aria-label con toda la información
                aria_label = link_elem.get('aria-label', '')
                if aria_label and 'Evento' in aria_label:
                    parsed = self.parse_aria_label(aria_label)
                    # Solo actualizar nombre si el actual es genérico
                    if name in ['Evento', ''] and parsed.get('name'):
                        event['name'] = parsed['name']
                    # Añadir fecha, horario, edad
                    if parsed.get('date_text'):
                        event['date_text'] = parsed['date_text']
                    if parsed.get('hora_inicio'):
                        event['hora_inicio'] = parsed['hora_inicio']
                    if parsed.get('hora_fin'):
                        event['hora_fin'] = parsed['hora_fin']
                    if parsed.get('age_info'):
                        event['age_info'] = parsed['age_info']
                    if parsed.get('age_min'):
                        event['age_min'] = parsed['age_min']
                
                events.append(event)
                
            except Exception:
                continue
        
        return events
    
    def _extract_via_fallback(self, soup: BeautifulSoup) -> List[Dict]:
        """ESTRATEGIA 3: Fallback simple - cualquier enlace con /events/."""
        events = []
        print(f"   🔍 Debug Estrategia FALLBACK...")
        
        for link in soup.find_all('a', href=lambda x: x and '/events/' in x):
            href = link.get('href', '')
            code = href.split('/')[-1] if '/' in href else href
            name = link.get('aria-label', '') or link.get_text(strip=True) or 'Evento'
            
            if name == 'Evento' or not name:
                parent_text = link.find_parent().get_text(strip=True) if link.find_parent() else ''
                if parent_text and len(parent_text) > 5:
                    name = parent_text[:100]
            
            events.append({
                'url': href,
                'venue_slug': self.name,
                'name': name,
                'code': code
            })
        
        print(f"   🔍 Debug Estrategia FALLBACK: {len(events)} eventos encontrados")
        return events


class LuminataScraper(SiteFourVenuesScraper):
    """Scraper para Luminata Disco."""
    name = "luminata-disco"


class OdiseoScraper(SiteFourVenuesScraper):
    """Scraper para El Club by Odiseo."""
    name = "el-club-by-odiseo"


class DodoScraper(SiteFourVenuesScraper):
    """
    Scraper para Dodo Club.
    
    Usa la misma base pero puede necesitar reintentos por Queue-Fair.
    """
    name = "dodo-club"
    
    def should_retry(self) -> bool:
        return True
    
    def extract_events_from_html(self, html: str, markdown: str = None, raw_html: str = None) -> List[Dict]:
        """
        Dodo Club usa principalmente data-testid.
        Intentar primero con data-testid, luego fallback a aria-label.
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Primero intentar data-testid (más común en Dodo)
        events = self._extract_via_data_testid(soup)
        
        # Si no funciona, intentar aria-label
        if not events:
            events = super().extract_events_from_html(html, markdown, raw_html)
        
        return events


# ==============================================================================
# SCRAPER site.fourvenues.com (Sala Rem)
# ==============================================================================

class SalaRemScraper(SiteFourVenuesScraper):
    """
    Scraper para Sala Rem.
    
    Sala Rem está disponible tanto en:
    - https://site.fourvenues.com/es/sala-rem/events (preferido - misma estructura que otros venues)
    - https://web.fourvenues.com/es/sala-rem/events (alternativa)
    
    Hereda de SiteFourVenuesScraper para usar la misma estrategia de aria-label
    que funciona para Luminata, Odiseo y Dodo.
    """
    
    name = "sala-rem"
    # Usar site.fourvenues.com que tiene la misma estructura que los otros venues
    base_url = "https://site.fourvenues.com"
    
    def should_retry(self) -> bool:
        """Sala Rem puede necesitar reintentos."""
        return True
    
    def get_scrape_config(self) -> dict:
        """Sala Rem puede necesitar más tiempo de espera."""
        return {
            "formats": ["html"],
            "actions": [
                {"type": "wait", "milliseconds": 10000},
                {"type": "scroll", "direction": "down", "amount": 1000},
                {"type": "wait", "milliseconds": 3000},
                {"type": "scroll", "direction": "down", "amount": 1000},
                {"type": "wait", "milliseconds": 3000}
            ],
            "wait_for": 8000
        }


# ==============================================================================
# FUNCIONES DE TRANSFORMACIÓN Y DEDUPLICACIÓN
# ==============================================================================

def deduplicate_events(events: List[Dict]) -> List[Dict]:
    """Elimina eventos duplicados de la lista."""
    seen_urls = set()
    seen_codes = set()
    seen_name_date = set()
    unique_events = []
    
    print(f"\n🔍 Deduplicando {len(events)} eventos...")
    
    for event in events:
        event_url = event.get('url', '')
        event_code = event.get('code', '')
        event_name = event.get('name', '')
        venue_slug = event.get('venue_slug', '')
        is_sala_rem = 'sala-rem' in venue_slug.lower()
        
        # Para Sala Rem: deduplicar por nombre + fecha
        if is_sala_rem:
            name_normalized = re.sub(r'[^\w\s]', '', event_name.lower()).strip()
            name_normalized = re.sub(r'\s+', ' ', name_normalized)
            
            event_date = None
            if event.get('_date_parts'):
                dp = event['_date_parts']
                event_date = f"{dp['day']}-{dp['month']}-{dp['year']}"
            elif event.get('date_text'):
                date_match = re.search(r'(\d{1,2})\s+\w+', event.get('date_text', ''))
                if date_match:
                    day = date_match.group(1)
                    month_map = {
                        'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
                        'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
                        'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
                    }
                    for month_name, month_num in month_map.items():
                        if month_name in event.get('date_text', '').lower():
                            event_date = f"{day}-{month_num}-2025"
                            break
            
            if event_date:
                name_date_key = (name_normalized, event_date)
                if name_date_key in seen_name_date:
                    print(f"   ⚠️ Duplicado (nombre+fecha): {event_name}")
                    continue
                seen_name_date.add(name_date_key)
        
        # Deduplicar por URL
        if event_url in seen_urls:
            print(f"   ⚠️ Duplicado (URL): {event_name}")
            continue
        
        # Deduplicar por código (excepto Sala Rem)
        if not is_sala_rem and event_code and event_code in seen_codes:
            print(f"   ⚠️ Duplicado (código): {event_name}")
            continue
        
        seen_urls.add(event_url)
        if event_code:
            seen_codes.add(event_code)
        unique_events.append(event)
    
    if len(unique_events) < len(events):
        print(f"   ✅ Deduplicados: {len(events)} → {len(unique_events)}")
    
    return unique_events


def transform_to_app_format(events: List[Dict]) -> List[Dict]:
    """Transforma los eventos al formato de la app PartyFinder."""
    transformed = []
    
    for event in events:
        # Parsear fecha
        fecha = datetime.now().strftime('%Y-%m-%d')
        
        if event.get('_date_parts'):
            dp = event['_date_parts']
            day = dp['day'].zfill(2)
            month = dp['month']
            year = dp['year']
            fecha = f"{year}-{month}-{day}"
        else:
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
                if int(month) < datetime.now().month:
                    year += 1
                fecha = f"{year}-{month}-{day}"
            
            # Intentar extraer de URL
            if fecha == datetime.now().strftime('%Y-%m-%d') and event.get('url'):
                url = event.get('url', '')
                date_match = re.search(r'-{1,2}(\d{1,2})-(\d{2})-(\d{4})\d*-', url)
                if date_match:
                    day = date_match.group(1).zfill(2)
                    month = date_match.group(2)
                    year = date_match.group(3)
                    fecha = f"{year}-{month}-{day}"
        
        # Construir entradas
        entradas = []
        if event.get('tickets'):
            entradas = [copy.deepcopy(t) for t in event['tickets']]
        else:
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
        
        # Ajustar fecha si hora es 00:00
        hora_inicio = event.get('hora_inicio', '23:00')
        if hora_inicio in ['00:00', '0:00']:
            try:
                from datetime import timedelta
                fecha_obj = datetime.strptime(fecha, '%Y-%m-%d')
                fecha_obj = fecha_obj - timedelta(days=1)
                fecha = fecha_obj.strftime('%Y-%m-%d')
            except Exception:
                pass
        
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
                "tags": event.get('tags', ['Fiesta']),
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


# ==============================================================================
# PUNTO DE ENTRADA
# ==============================================================================

# Registro de scrapers disponibles
# =============================================================================
# TEMPORAL: Solo Sala Rem para desarrollo
# Cambiar DEV_MODE_SALA_REM_ONLY = False cuando termine el desarrollo
# =============================================================================
DEV_MODE_SALA_REM_ONLY = True


def get_venue_scrapers(firecrawl: Firecrawl = None) -> List[VenueScraperBase]:
    """Retorna lista de scrapers para todos los venues."""
    fc = firecrawl or Firecrawl(api_key=API_KEY)
    
    # TEMPORAL: Solo Sala Rem para desarrollo rápido
    if DEV_MODE_SALA_REM_ONLY:
        print("⚠️  MODO DESARROLLO: Solo scrapeando Sala Rem")
        return [SalaRemScraper(fc)]
    
    return [
        LuminataScraper(fc),
        OdiseoScraper(fc),
        DodoScraper(fc),
        SalaRemScraper(fc),
    ]


def scrape_all_events(urls: List[str] = None, get_details: bool = True) -> List[Dict]:
    """
    Scrapea eventos de todos los venues.
    
    Args:
        urls: Lista de URLs específicas (opcional, si no se usa todos los venues)
        get_details: Si obtener detalles completos de cada evento
    
    Returns:
        Lista de eventos scrapeados
    """
    print("=" * 60)
    print("PartyFinder - Firecrawl Scraper")
    print("=" * 60)
    
    firecrawl = Firecrawl(api_key=API_KEY)
    all_events = []
    
    # Si hay URLs específicas, filtrar scrapers
    if urls:
        scrapers = get_venue_scrapers(firecrawl)
        for scraper in scrapers:
            if any(scraper.name in url for url in urls):
                events = scraper.scrape_events_list()
                all_events.extend(events)
    else:
        # Usar todos los scrapers
        for scraper in get_venue_scrapers(firecrawl):
            events = scraper.scrape_events_list()
            all_events.extend(events)
    
    # Obtener detalles si se solicita
    if get_details and all_events:
        # Deduplicar antes de obtener detalles
        all_events = deduplicate_events(all_events)
        
        print(f"\n🎫 Obteniendo detalles de {len(all_events)} eventos...")
        
        # Agrupar eventos por venue para usar el scraper correcto
        scrapers_by_name = {s.name: s for s in get_venue_scrapers(firecrawl)}
        
        for i, event in enumerate(all_events):
            print(f"   [{i+1}/{len(all_events)}] {event.get('name', 'N/A')[:40]}...")
            
            venue_slug = event.get('venue_slug', '')
            scraper = scrapers_by_name.get(venue_slug)
            
            if scraper:
                result = scraper.scrape_event_details(event)
            else:
                # Fallback: usar scraper base
                result = VenueScraperBase.scrape_event_details(
                    SiteFourVenuesScraper(firecrawl), event
                )
            
            # Filtrar eventos inválidos
            if result.get('_invalid'):
                print(f"   ⚠️ Evento inválido descartado: {result.get('name', 'N/A')}")
                all_events[i] = None
            else:
                # Validar contenido para Sala Rem
                if 'sala-rem' in venue_slug.lower():
                    tickets = result.get('tickets', [])
                    has_content = (
                        bool(result.get('description', '').strip()) or
                        bool(result.get('image', '').strip()) or
                        len(tickets) > 0
                    )
                    if not has_content:
                        print(f"   ⚠️ Sin contenido válido: {result.get('name', 'N/A')}")
                        all_events[i] = None
                        continue
                
                all_events[i] = result
    
    # Filtrar eventos inválidos
    all_events = [e for e in all_events if e is not None and not e.get('_invalid')]
    
    print(f"\n🎉 Total: {len(all_events)} eventos scrapeados")
    return all_events


def test_connection() -> bool:
    """Test básico de conexión."""
    print("=" * 60)
    print("PartyFinder - Test de Firecrawl")
    print("=" * 60)
    
    firecrawl = Firecrawl(api_key=API_KEY)
    scraper = LuminataScraper(firecrawl)
    
    print(f"\n🔗 URL: {scraper.venue_url}")
    print("📡 Probando conexión...")
    
    try:
        config = scraper.get_scrape_config()
        result = firecrawl.scrape(scraper.venue_url, **config)
        
        status = result.metadata.status_code if result.metadata else "N/A"
        html_len = len(result.html) if result.html else 0
        
        print(f"\n✅ Conexión exitosa!")
        print(f"   Status: {status}")
        print(f"   HTML: {html_len} bytes")
        
        events = scraper.extract_events_from_html(result.html or "")
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
    parser.add_argument('--urls', nargs='+', help='URLs específicas a scrapear')
    
    args = parser.parse_args()
    
    # Crear directorio data
    DATA_DIR.mkdir(exist_ok=True)
    
    if args.test:
        success = test_connection()
        return 0 if success else 1
    
    # Scraping completo
    raw_events = scrape_all_events(urls=args.urls, get_details=not args.no_details)
    
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
        print("\n📤 Subiendo a Firebase (colección: 'eventos-dev')...")
        try:
            from firebase_config import upload_events_to_firestore, delete_old_events
            delete_old_events(collection_name='eventos-dev')
            upload_events_to_firestore(transformed, collection_name='eventos-dev')
            print("✅ Datos subidos a Firebase en 'eventos-dev'")
            
            # Enviar push notifications
            print("\n📬 Verificando y enviando notificaciones push...")
            try:
                from push_notifications import check_and_send_notifications
                check_and_send_notifications()
            except Exception as e:
                print(f"⚠️ Error enviando notificaciones: {e}")
        except Exception as e:
            print(f"❌ Error subiendo a Firebase: {e}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
