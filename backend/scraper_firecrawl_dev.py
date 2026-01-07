#!/usr/bin/env python3
"""
Scraper de eventos para PartyFinder usando Firecrawl - VERSIÓN DESARROLLO
=========================================================================
Esta versión envía los datos a la colección 'eventos-dev' en Firebase.

Utiliza Firecrawl para bypass Cloudflare y extrae eventos del HTML.

Uso:
    python3 scraper_firecrawl_dev.py                    # Scraping completo
    python3 scraper_firecrawl_dev.py --test             # Solo test de conexión
    python3 scraper_firecrawl_dev.py --upload           # Scraping + Firebase (eventos-dev)
"""

import sys
import os
import json
from pathlib import Path

# Importar funciones del scraper original
# Añadir el directorio actual al path para importar
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Importar todas las funciones necesarias del scraper original
try:
    # Importar el módulo completo y acceder a sus funciones
    import scraper_firecrawl as scraper
    
    # Extraer las funciones y constantes que necesitamos
    extract_events_from_html = scraper.extract_events_from_html
    scrape_venue = scraper.scrape_venue
    scrape_event_details = scraper.scrape_event_details
    transform_to_app_format = scraper.transform_to_app_format
    scrape_all_events = scraper.scrape_all_events
    test_connection = scraper.test_connection
    VENUE_URLS = scraper.VENUE_URLS
    DATA_DIR = scraper.DATA_DIR
except ImportError as e:
    print(f"❌ Error importando scraper original: {e}")
    print("   Asegúrate de que scraper_firecrawl.py esté en el mismo directorio")
    sys.exit(1)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Scraper FourVenues con Firecrawl - VERSIÓN DESARROLLO (eventos-dev)')
    parser.add_argument('--test', '-t', action='store_true', help='Solo test de conexión')
    parser.add_argument('--upload', '-u', action='store_true', help='Subir a Firebase (colección eventos-dev)')
    parser.add_argument('--no-details', action='store_true', help='No obtener detalles de eventos')
    parser.add_argument('--urls', nargs='+', help='URLs específicas a scrapear (ej: --urls https://web.fourvenues.com/es/sala-rem/events)')
    
    args = parser.parse_args()
    
    # Crear directorio data
    DATA_DIR.mkdir(exist_ok=True)
    
    if args.test:
        success = test_connection()
        return 0 if success else 1
    
    # Scraping completo - usar URLs específicas si se proporcionan
    target_urls = args.urls if args.urls else None
    raw_events = scrape_all_events(urls=target_urls, get_details=not args.no_details)
    
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
    
    # Subir a Firebase - VERSIÓN DESARROLLO: usar colección 'eventos-dev'
    if args.upload:
        print("\n📤 Subiendo a Firebase (colección: eventos-dev)...")
        try:
            from firebase_config import upload_events_to_firestore, delete_old_events
            
            # Usar colección 'eventos-dev' para desarrollo
            DEV_COLLECTION = 'eventos-dev'
            delete_old_events(collection_name=DEV_COLLECTION)
            upload_events_to_firestore(transformed, collection_name=DEV_COLLECTION)
            print(f"✅ Datos subidos a Firebase (colección: {DEV_COLLECTION})")
            
            # NOTA: Las notificaciones push normalmente se envían solo desde producción
            # Si quieres habilitarlas también en desarrollo, descomenta lo siguiente:
            # print("\n📬 Verificando y enviando notificaciones push...")
            # try:
            #     from push_notifications import check_and_send_notifications
            #     check_and_send_notifications()
            # except Exception as e:
            #     print(f"⚠️ Error enviando notificaciones: {e}")
        except Exception as e:
            print(f"❌ Error subiendo a Firebase: {e}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

