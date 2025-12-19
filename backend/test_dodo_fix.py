#!/usr/bin/env python3
"""
Test específico para Dodo Club con el scraper actualizado.
"""

from scraper_firecrawl import scrape_venue, Firecrawl
import os

API_KEY = os.environ.get("FIRECRAWL_API_KEY")
DODO_URL = "https://site.fourvenues.com/es/dodo-club/events"

def test_dodo():
    firecrawl = Firecrawl(api_key=API_KEY)
    events = scrape_venue(firecrawl, DODO_URL)
    
    print("\n" + "="*40)
    print(f"RESULTADOS DODO CLUB ({len(events)}):")
    print("="*40)
    for e in events:
        print(f"- {e.get('name')} | URL: {e.get('url')}")
    print("="*40)

if __name__ == "__main__":
    test_dodo()
