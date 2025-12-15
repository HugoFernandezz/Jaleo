#!/usr/bin/env python3
"""
Scraper para CI (GitHub Actions) usando Playwright directamente.
Este script está optimizado para ejecutarse en entornos CI donde nodriver
tiene problemas de conexión.
"""

import asyncio
import json
import os
import sys
import re
from datetime import datetime
from typing import List, Dict

# Forzar UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

VENUE_URLS = [
    "https://site.fourvenues.com/es/luminata-disco/events",
    "https://site.fourvenues.com/es/el-club-by-odiseo/events",
    "https://site.fourvenues.com/es/dodo-club/events"
]

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

async def scrape_with_playwright():
    """Scraping usando Playwright directamente."""
    from playwright.async_api import async_playwright
    
    all_events = []
    
    print("🚀 Iniciando Playwright...")
    
    async with async_playwright() as p:
        # headless=False con Xvfb puede bypass Cloudflare
        browser = await p.chromium.launch(
            headless=False,  # IMPORTANTE: False para evitar detección
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
            ]
        )
        
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='es-ES',
        )
        
        for url in VENUE_URLS:
            print(f"\n📡 Scrapeando: {url}")
            
            try:
                page = await context.new_page()
                await page.goto(url, timeout=60000, wait_until='domcontentloaded')
                
                # Esperar Cloudflare
                print("   ⏳ Esperando Cloudflare...")
                challenge_passed = False
                for i in range(60):
                    await asyncio.sleep(1)
                    title = await page.title()
                    
                    # Debug: mostrar título actual
                    if i % 10 == 0:
                        print(f"      [{i}s] Título: {title[:40] if title else 'N/A'}")
                    
                    if title and 'moment' not in title.lower() and 'wait' not in title.lower() and 'checking' not in title.lower():
                        body_len = await page.evaluate("document.body.innerHTML.length")
                        if body_len > 1000:
                            print(f"   ✅ Challenge pasado en {i}s - Título: {title[:30]}")
                            challenge_passed = True
                            break
                
                if not challenge_passed:
                    print(f"   ⚠️ Timeout Cloudflare - Título final: {title[:40] if title else 'N/A'}")
                
                # Esperar Angular
                await asyncio.sleep(15)
                
                html = await page.content()
                events = extract_events_from_html(html)
                print(f"   📦 Encontrados {len(events)} eventos")
                all_events.extend(events)
                
                await page.close()
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        await browser.close()
    
    return all_events

def upload_to_firebase(events: List[Dict]):
    """Sube eventos a Firebase."""
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        
        # Inicializar Firebase si no está inicializado
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
        print(f"❌ Error subiendo a Firebase: {e}")
        return False

async def main():
    print("=" * 60)
    print("PartyFinder - Scraper CI (Playwright)")
    print("=" * 60)
    
    events = await scrape_with_playwright()
    
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
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
