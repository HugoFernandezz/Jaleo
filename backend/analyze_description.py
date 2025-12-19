#!/usr/bin/env python3
"""
Análisis de página de detalle de evento FourVenues
Para encontrar dónde está la descripción
"""

from firecrawl import Firecrawl
from bs4 import BeautifulSoup
import re
import json

import os
API_KEY = os.environ.get("FIRECRAWL_API_KEY")

# URL de un evento específico
EVENT_URL = "https://site.fourvenues.com/es/luminata-disco/events/59QH"

def analyze_event_page():
    print("=" * 60)
    print("Analizando página de evento FourVenues")
    print("=" * 60)
    
    firecrawl = Firecrawl(api_key=API_KEY)
    
    print(f"\n🔗 URL: {EVENT_URL}")
    print("📡 Obteniendo HTML con actions wait...")
    
    result = firecrawl.scrape(
        EVENT_URL,
        formats=["html", "markdown"],
        actions=[{"type": "wait", "milliseconds": 5000}]
    )
    
    html = result.html or ""
    markdown = result.markdown or ""
    
    print(f"\n📄 HTML: {len(html)} bytes")
    print(f"📝 Markdown: {len(markdown)} bytes")
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # 1. Buscar meta description
    print("\n\n=== 1. META TAGS ===")
    meta_desc = soup.find('meta', {'name': 'description'})
    og_desc = soup.find('meta', {'property': 'og:description'})
    
    print(f"meta[name=description]: {meta_desc.get('content', 'N/A')[:200] if meta_desc else 'NO ENCONTRADO'}")
    print(f"meta[property=og:description]: {og_desc.get('content', 'N/A')[:200] if og_desc else 'NO ENCONTRADO'}")
    
    # 2. Buscar JSON-LD (schema.org)
    print("\n\n=== 2. JSON-LD (Schema.org) ===")
    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    print(f"Scripts JSON-LD encontrados: {len(json_ld_scripts)}")
    for i, script in enumerate(json_ld_scripts):
        try:
            data = json.loads(script.string)
            print(f"\nJSON-LD #{i}:")
            print(f"  @type: {data.get('@type', 'N/A')}")
            if 'description' in data:
                print(f"  description: {data['description'][:200]}")
            print(f"  Keys: {list(data.keys())[:10]}")
        except:
            pass
    
    # 3. Buscar aria-labels con descripción
    print("\n\n=== 3. ARIA-LABELS ===")
    elems_with_aria = soup.find_all(attrs={'aria-label': True})
    for elem in elems_with_aria[:10]:
        label = elem.get('aria-label', '')
        if len(label) > 50:  # Solo los largos
            print(f"  {label[:150]}...")
    
    # 4. Buscar elementos que parezcan descripción (párrafos largos)
    print("\n\n=== 4. PÁRRAFOS/TEXTO LARGO ===")
    # Buscar cualquier texto largo
    all_text = soup.get_text(separator='\n')
    lines = [l.strip() for l in all_text.split('\n') if len(l.strip()) > 100]
    print(f"Líneas largas (>100 chars): {len(lines)}")
    for line in lines[:5]:
        print(f"  - {line[:150]}...")
    
    # 5. Buscar en clases que sugieran descripción
    print("\n\n=== 5. CLASES CON 'DESCRIPTION' O 'INFO' ===")
    desc_elems = soup.find_all(class_=re.compile(r'desc|info|detail|about', re.I))
    print(f"Elementos encontrados: {len(desc_elems)}")
    for elem in desc_elems[:5]:
        text = elem.get_text(strip=True)
        if text:
            print(f"  [{elem.get('class')}]: {text[:100]}...")
    
    # 6. Buscar JSON embebido con datos del evento
    print("\n\n=== 6. SCRIPTS JSON EMBEBIDOS ===")
    all_scripts = soup.find_all('script')
    print(f"Total scripts: {len(all_scripts)}")
    for script in all_scripts:
        content = script.string or ""
        if 'description' in content.lower() and len(content) > 100:
            print(f"  Script con 'description' (tipo: {script.get('type', 'text/javascript')})")
            # Intentar extraer JSON
            try:
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = content[start:end]
                    data = json.loads(json_str)
                    print(f"    Parsed JSON keys: {list(data.keys())[:10]}")
            except:
                print(f"    (contenido parcial: {content[100:300]}...)")
    
    # 7. Analizar Markdown (Firecrawl lo extrae limpio)
    print("\n\n=== 7. MARKDOWN DE FIRECRAWL ===")
    print("Primeros 1000 caracteres del markdown:")
    print(markdown[:1000])
    
    # Guardar para análisis manual
    with open('data/event_analysis.html', 'w', encoding='utf-8') as f:
        f.write(html)
    with open('data/event_analysis.md', 'w', encoding='utf-8') as f:
        f.write(markdown)
    
    print("\n\n💾 HTML guardado en data/event_analysis.html")
    print("💾 Markdown guardado en data/event_analysis.md")

if __name__ == "__main__":
    import os
    os.makedirs('data', exist_ok=True)
    analyze_event_page()
