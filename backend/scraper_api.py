#!/usr/bin/env python3
"""
Scraper usando ScrapingBee API para bypass de Cloudflare.
Este script no requiere navegador - usa la API de ScrapingBee.
"""

import json
import os
import sys
import re
import requests
from typing import List, Dict
from urllib.parse import urlencode

# Forzar UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

VENUE_URLS = [
    "https://site.fourvenues.com/es/luminata-disco/events",
    "https://site.fourvenues.com/es/el-club-by-odiseo/events",
    "https://site.fourvenues.com/es/dodo-club/events"
]

def get_api_key() -> str:
    """Obtiene la API key de ScrapingBee desde variable de entorno."""
    api_key = os.environ.get('SCRAPINGBEE_API_KEY')
    if not api_key:
        print("❌ Error: SCRAPINGBEE_API_KEY no configurada")
        print("   Configúrala como secret en GitHub o como variable de entorno")
        sys.exit(1)
    return api_key

def fetch_with_scrapingbee(url: str, api_key: str) -> str:
    """Obtiene el HTML de una URL usando ScrapingBee."""
    params = {
        'api_key': api_key,
        'url': url,
        'render_js': 'true',  # Renderizar JavaScript (Angular)
        'block_resources': 'false',  # NO bloquear recursos
        'wait': '15000',  # Esperar 15s para Angular
        'wait_for': '#app',  # Esperar elemento Angular
    }
    
    response = requests.get(
        'https://app.scrapingbee.com/api/v1/',
        params=params,
        timeout=90
    )
    
    if response.status_code == 200:
        return response.text
    else:
        print(f"   ❌ ScrapingBee error: {response.status_code}")
        print(f"      {response.text[:200]}")
        return ""

def extract_events_from_html(html: str) -> List[Dict]:
    """Extrae eventos del JSON embebido en el HTML."""
    events = []
    
    # Buscar scripts con type="application/json"
    json_pattern = r'<script[^>]*type=["\']application/json["\'][^>]*>([^<]+)</script>'
    matches = re.findall(json_pattern, html, re.DOTALL)
    
    for match in matches:
        try:
            data = json.loads(match)
            if isinstance(data, dict):
                for key in data.keys():
                    if 'events' in key.lower() and isinstance(data[key], dict):
                        if 'data' in data[key] and isinstance(data[key]['data'], list):
                            raw_events = data[key]['data']
                            for e in raw_events:
                                event = {
                                    'id': e.get('id', ''),
                                    'name': e.get('name', ''),
                                    'description': e.get('description', ''),
                                    'date': e.get('date', ''),
                                    'imageUrl': e.get('flyer', {}).get('image', '') if isinstance(e.get('flyer'), dict) else '',
                                    'venueId': e.get('place', {}).get('id', '') if isinstance(e.get('place'), dict) else '',
                                    'venueName': e.get('place', {}).get('name', '') if isinstance(e.get('place'), dict) else '',
                                }
                                events.append(event)
        except:
            continue
    
    return events

def scrape_all_venues() -> List[Dict]:
    """Scrapea todos los venues usando ScrapingBee."""
    api_key = get_api_key()
    all_events = []
    
    for url in VENUE_URLS:
        print(f"\n📡 Scrapeando: {url}")
        
        html = fetch_with_scrapingbee(url, api_key)
        
        if html:
            print(f"   📥 HTML recibido: {len(html)} bytes")
            events = extract_events_from_html(html)
            print(f"   📦 Encontrados {len(events)} eventos")
            all_events.extend(events)
        else:
            print(f"   ⚠️ No se pudo obtener HTML")
    
    return all_events

def upload_to_firebase(events: List[Dict]):
    """Sube eventos a Firebase."""
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        
        if not firebase_admin._apps:
            cred_path = os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json')
            if os.path.exists(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
            else:
                print("❌ serviceAccountKey.json no encontrado")
                return False
        
        db = firestore.client()
        events_ref = db.collection('events')
        
        # Limpiar eventos existentes
        existing = events_ref.stream()
        for doc in existing:
            doc.reference.delete()
        
        # Subir nuevos eventos
        for event in events:
            events_ref.add(event)
        
        print(f"✅ Subidos {len(events)} eventos a Firebase")
        return True
        
    except Exception as e:
        print(f"❌ Error Firebase: {e}")
        return False

def main():
    print("=" * 60)
    print("PartyFinder - Scraper API (ScrapingBee)")
    print("=" * 60)
    
    events = scrape_all_venues()
    
    if events:
        # Guardar localmente
        os.makedirs('data', exist_ok=True)
        with open('data/events.json', 'w', encoding='utf-8') as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Guardados {len(events)} eventos en data/events.json")
        
        # Subir a Firebase si se solicita
        if '--firebase' in sys.argv:
            upload_to_firebase(events)
    else:
        print("\n⚠️ No se encontraron eventos")
    
    return len(events) > 0

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
