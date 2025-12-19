#!/usr/bin/env python3
"""
Análisis de URLs de compra de tickets en FourVenues
Buscando: https://web.fourvenues.com/.../tickets/{ticket_id}
"""

from firecrawl import Firecrawl
from bs4 import BeautifulSoup
import re

import os
API_KEY = os.getenv("FIRECRAWL_API_KEY")

# URL de evento con entradas disponibles
EVENT_URL = "https://site.fourvenues.com/es/luminata-disco/events/sabado-reggaetoncomercial-20-12-2025-IULK"

def analyze_ticket_urls():
    print("=" * 60)
    print("Analizando URLs de compra de tickets")
    print("=" * 60)
    
    firecrawl = Firecrawl(api_key=API_KEY)
    
    print(f"\n🔗 URL: {EVENT_URL}")
    print("📡 Obteniendo HTML y Markdown...")
    
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
    
    # Buscar URLs que contengan /tickets/
    print("\n\n=== URLs CON /tickets/ ===")
    ticket_urls = []
    
    # Buscar en todos los enlaces
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        if '/tickets/' in href:
            text = link.get_text(strip=True)[:50]
            ticket_urls.append((href, text))
            print(f"  {href}")
            print(f"    Texto: {text}")
    
    print(f"\nTotal URLs de tickets encontradas: {len(ticket_urls)}")
    
    # Buscar en el markdown
    print("\n\n=== URLs EN MARKDOWN ===")
    md_ticket_urls = re.findall(r'https?://[^\s\)]+/tickets/[^\s\)]+', markdown)
    for url in md_ticket_urls[:10]:
        print(f"  {url}")
    
    # Buscar patrón web.fourvenues.com
    print("\n\n=== URLs web.fourvenues.com ===")
    web_urls = re.findall(r'https?://web\.fourvenues\.com[^\s\"\'>]+', html)
    for url in web_urls[:10]:
        print(f"  {url}")
    
    # Buscar cualquier URL con ticket ID (alfanumérico largo)
    print("\n\n=== URLs CON IDs ALFANUMÉRICOS ===")
    id_pattern = re.compile(r'href=["\']([^"\']*[a-z0-9]{20,}[^"\']*)["\']', re.I)
    id_urls = id_pattern.findall(html)
    for url in id_urls[:10]:
        print(f"  {url}")
    
    # Guardar para análisis
    with open('data/ticket_urls_analysis.html', 'w', encoding='utf-8') as f:
        f.write(html)
    with open('data/ticket_urls_analysis.md', 'w', encoding='utf-8') as f:
        f.write(markdown)
    
    print("\n💾 Guardado en data/ticket_urls_analysis.*")

if __name__ == "__main__":
    import os
    os.makedirs('data', exist_ok=True)
    analyze_ticket_urls()
