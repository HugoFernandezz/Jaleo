#!/usr/bin/env python3
"""
Investigación de Dodo Club
==========================
Extrae el HTML de Dodo Club para ver por qué no se detectan eventos.
"""

from firecrawl import Firecrawl
import os

API_KEY = os.environ.get("FIRECRAWL_API_KEY")
DODO_URL = "https://site.fourvenues.com/es/dodo-club/events"

def investigate_dodo():
    print(f"📡 Cargando Dodo Club: {DODO_URL}")
    firecrawl = Firecrawl(api_key=API_KEY)
    
    try:
        result = firecrawl.scrape(
            DODO_URL,
            formats=["html"],
            actions=[{"type": "wait", "milliseconds": 8000}]
        )
        
        html = result.html or ""
        print(f"✅ HTML recibido: {len(html)} bytes")
        
        # Guardar para inspección
        os.makedirs('data', exist_ok=True)
        with open("data/debug_dodo.html", "w", encoding='utf-8') as f:
            f.write(html)
        print("💾 Dump guardado en data/debug_dodo.html")
        
        # Análisis rápido de enlaces
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        links = soup.find_all('a')
        print(f"🔍 Total enlaces: {len(links)}")
        
        event_links = [l for l in links if '/events/' in str(l.get('href', ''))]
        print(f"🎫 Enlaces con '/events/': {len(event_links)}")
        
        for i, l in enumerate(event_links[:5]):
            print(f"  [{i}] Href: {l.get('href')}")
            print(f"      Aria-label: {l.get('aria-label')}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    investigate_dodo()
