#!/usr/bin/env python3
"""
Test Firecrawl con Actions para JavaScript
==========================================
Las actions permiten esperar a que JavaScript/Angular cargue completamente.
"""

from firecrawl import Firecrawl
import json

import os
API_KEY = os.getenv("FIRECRAWL_API_KEY")
TEST_URL = "https://site.fourvenues.com/es/luminata-disco/events"

def test_with_actions():
    print("=" * 60)
    print("Test Firecrawl con Actions para JavaScript")
    print("=" * 60)
    
    firecrawl = Firecrawl(api_key=API_KEY)
    
    print(f"\n🔗 URL: {TEST_URL}")
    print("📡 Scraping con wait actions...")
    
    try:
        # Usamos actions para esperar JavaScript
        result = firecrawl.scrape(
            TEST_URL,
            formats=["html"],
            actions=[
                {"type": "wait", "milliseconds": 8000},  # Esperar 8s para Angular 
            ]
        )
        
        print("\n✅ Scrape exitoso!")
        
        status = result.metadata.status_code if result.metadata else "N/A"
        print(f"   Status: {status}")
        
        html = result.html or ""
        print(f"   HTML: {len(html)} bytes")
        
        # Buscar scripts JSON
        import re
        json_pattern = r'<script[^>]*type=["\']application/json["\'][^>]*>([^<]+)</script>'
        json_matches = re.findall(json_pattern, html, re.DOTALL)
        
        print(f"   Scripts JSON: {len(json_matches)}")
        
        # Buscar eventos en el HTML
        events_count = html.lower().count("events")
        print(f"   Menciones de 'events': {events_count}")
        
        # Si hay scripts JSON, procesar
        if json_matches:
            for i, js in enumerate(json_matches):
                try:
                    data = json.loads(js)
                    for key in data.keys():
                        if "events" in key.lower():
                            events = data[key].get("data", [])
                            print(f"\n🎉 Eventos encontrados: {len(events)}")
                            for e in events[:3]:
                                print(f"   - {e.get('name', 'N/A')}")
                            return True
                except:
                    continue
        
        # Guardar para debug
        with open("data/firecrawl_actions.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("\n⚠️ No se encontraron eventos")
        print("   HTML guardado en data/firecrawl_actions.html")
        
        return False
        
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import os
    os.makedirs("data", exist_ok=True)
    success = test_with_actions()
    print("\n" + "=" * 60)
    print("RESULTADO:", "✅ ÉXITO" if success else "❌ FALLO")
    print("=" * 60)
