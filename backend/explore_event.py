"""
Script para explorar la información disponible en una página de evento específico.
"""

import asyncio
import nodriver as uc
import json
import sys
import re
import os

# Forzar UTF-8 en Windows
if sys.platform == 'win32':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

# URL del evento a explorar
EVENT_URL = "https://site.fourvenues.com/es/luminata-disco/events/nochevieja-universitaria-18-12-20253-K7HZ"


def get_chromium_path():
    """Busca el ejecutable de Chromium instalado por Playwright."""
    if sys.platform == 'win32':
        localappdata = os.environ.get('LOCALAPPDATA', '')
        pw_dir = os.path.join(localappdata, 'ms-playwright')
        if os.path.exists(pw_dir):
            for item in os.listdir(pw_dir):
                if item.startswith('chromium-'):
                    potential_path = os.path.join(pw_dir, item, 'chrome-win64', 'chrome.exe')
                    if os.path.exists(potential_path):
                        return potential_path
    return None


async def explore_event_page():
    """Explora la página de un evento y extrae toda la información disponible."""
    
    print("=" * 70)
    print("🔍 EXPLORANDO PÁGINA DE EVENTO")
    print("=" * 70)
    print(f"\n📡 URL: {EVENT_URL}\n")
    
    chrome_path = get_chromium_path()
    
    if chrome_path:
        browser = await uc.start(
            headless=False,
            browser_executable_path=chrome_path,
            browser_args=['--no-sandbox', '--disable-dev-shm-usage']
        )
    else:
        browser = await uc.start(
            headless=False,
            browser_args=['--no-sandbox', '--disable-dev-shm-usage']
        )
    
    page = await browser.get(EVENT_URL)
    
    print("⏳ Esperando que cargue la página...")
    
    # Esperar challenge de Cloudflare
    for i in range(60):
        await asyncio.sleep(1)
        try:
            title = await page.evaluate("document.title")
        except:
            title = ""
        
        if title and "momento" not in title.lower() and "checking" not in title.lower():
            print(f"✅ Página cargada! ({i}s)")
            break
    
    # Esperar carga completa de Angular
    await asyncio.sleep(5)
    
    # Obtener HTML completo
    html = await page.get_content()
    
    # Guardar HTML para análisis
    with open('data/event_page.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("💾 HTML guardado en data/event_page.html")
    
    # Buscar JSONs embebidos
    json_pattern = r'<script[^>]*type=["\']application/json["\'][^>]*>([^<]+)</script>'
    json_matches = re.findall(json_pattern, html, re.DOTALL)
    
    print(f"\n📦 Encontrados {len(json_matches)} bloques JSON embebidos\n")
    
    all_data = {}
    tickets_data = None
    event_data = None
    lists_data = None
    
    for idx, json_str in enumerate(json_matches):
        try:
            data = json.loads(json_str)
            
            if isinstance(data, dict):
                for key in data.keys():
                    value = data[key]
                    
                    if isinstance(value, dict):
                        all_data[key] = value
                        
                        # Buscar tickets
                        if 'tickets' in key.lower() and 'data' in value:
                            tickets_data = value['data']
                        
                        # Buscar datos del evento (clave que contiene 'event' pero no 'tickets')
                        if 'event' in key.lower() and 'tickets' not in key.lower() and 'lists' not in key.lower():
                            event_data = value.get('data', value)
                        
                        # Buscar listas (reservas, etc)
                        if 'lists' in key.lower() and 'data' in value:
                            lists_data = value['data']
                        
        except json.JSONDecodeError:
            continue
    
    # Mostrar todas las claves encontradas
    print(f"\n📋 Claves encontradas en los JSONs:")
    for key in all_data.keys():
        print(f"   • {key}")
    
    # Guardar todos los datos encontrados
    with open('data/all_event_data.json', 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)
    print("💾 Todos los datos guardados en data/all_event_data.json")
    
    # ========================================
    # MOSTRAR INFORMACIÓN DEL EVENTO
    # ========================================
    if event_data:
        print(f"\n{'=' * 70}")
        print("🎉 INFORMACIÓN DEL EVENTO")
        print(f"{'=' * 70}")
        
        # Guardar datos del evento
        with open('data/event_info.json', 'w', encoding='utf-8') as f:
            json.dump(event_data, f, indent=2, ensure_ascii=False)
        print("💾 Datos del evento guardados en data/event_info.json")
        
        # Mostrar campos disponibles
        print(f"\n📋 Campos disponibles en el evento:")
        
        def print_dict_structure(d, prefix=""):
            if isinstance(d, dict):
                for key, value in d.items():
                    if isinstance(value, dict):
                        print(f"{prefix}📁 {key}:")
                        print_dict_structure(value, prefix + "   ")
                    elif isinstance(value, list):
                        print(f"{prefix}📋 {key}: [lista con {len(value)} elementos]")
                    else:
                        val_str = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
                        print(f"{prefix}• {key}: {val_str}")
        
        print_dict_structure(event_data)
        
        # Extraer información específica
        print(f"\n{'=' * 70}")
        print("🎯 INFORMACIÓN CLAVE DEL EVENTO")
        print(f"{'=' * 70}")
        
        # Nombre
        print(f"\n📌 Nombre: {event_data.get('name', 'N/A')}")
        
        # Imagen
        images = event_data.get('images', {})
        if isinstance(images, dict):
            main_image = images.get('main', '')
            print(f"🖼️  Imagen principal: {main_image}")
        elif event_data.get('image'):
            print(f"🖼️  Imagen: {event_data.get('image')}")
        
        # Fechas
        dates = event_data.get('dates', {})
        if dates:
            print(f"\n📅 Fechas:")
            print(f"   • date (timestamp): {dates.get('date')}")
            print(f"   • start (timestamp): {dates.get('start')}")
            print(f"   • end (timestamp): {dates.get('end')}")
            
            # Convertir timestamps a fechas legibles
            from datetime import datetime
            if dates.get('start'):
                try:
                    start_dt = datetime.fromtimestamp(dates.get('start'))
                    print(f"   • Hora inicio: {start_dt.strftime('%H:%M')}")
                except: pass
            if dates.get('end'):
                try:
                    end_dt = datetime.fromtimestamp(dates.get('end'))
                    print(f"   • Hora fin: {end_dt.strftime('%H:%M')}")
                except: pass
        
        # Edad mínima
        age = event_data.get('age')
        if age:
            print(f"\n👤 Edad mínima: +{age}")
        
        # Código de vestimenta / Dress code
        dress_code = event_data.get('dressCode') or event_data.get('dress_code') or event_data.get('dresscode')
        if dress_code:
            print(f"👔 Código de vestimenta: {dress_code}")
        
        # Buscar en otros campos posibles
        for key in ['attire', 'outfit', 'style', 'clothing']:
            if event_data.get(key):
                print(f"👔 {key}: {event_data.get(key)}")
        
        # Ubicación
        location = event_data.get('location', {})
        if location:
            print(f"\n📍 Ubicación:")
            if isinstance(location, dict):
                print(f"   • Dirección: {location.get('addressComplete', location.get('address', 'N/A'))}")
                if location.get('timezone'):
                    print(f"   • Zona horaria: {location.get('timezone', {}).get('id', 'N/A')}")
            else:
                print(f"   • {location}")
        
        # Organización
        org = event_data.get('organization', {})
        if org:
            print(f"\n🏢 Organización:")
            print(f"   • Nombre: {org.get('name', 'N/A')}")
            print(f"   • Imagen: {org.get('image', 'N/A')}")
    else:
        print("\n⚠️ No se encontraron datos específicos del evento")
    
    # ========================================
    # MOSTRAR INFORMACIÓN DE TICKETS
    # ========================================
    if tickets_data:
        print(f"\n{'=' * 70}")
        print("🎫 INFORMACIÓN DE ENTRADAS/TICKETS")
        print(f"{'=' * 70}")
        print(f"\n✅ Encontrados {len(tickets_data)} tipos de entradas:\n")
        
        for i, ticket in enumerate(tickets_data):
            print(f"  {'─' * 60}")
            print(f"  🎟️  ENTRADA #{i+1}: {ticket.get('name', 'Sin nombre')}")
            print(f"  {'─' * 60}")
            print(f"     • ID: {ticket.get('id')}")
            print(f"     • Tipo: {ticket.get('type')}")
            print(f"     • Precio: {ticket.get('price')}€")
            print(f"     • Precio completo: {ticket.get('priceComplete')}")
            print(f"     • Agotadas: {ticket.get('isSoldOut')}")
            print(f"     • Quedan pocas: {ticket.get('areFewLeft')}")
            print(f"     • Disponibilidad: {ticket.get('disponibility')}")
            print(f"     • Cashless activo: {ticket.get('isCashlessActive')}")
            
            # Fechas de venta
            dates = ticket.get('dates', {})
            if dates:
                print(f"     • Fechas de venta:")
                print(f"       - Inicio: {dates.get('start')}")
                print(f"       - Fin: {dates.get('end')}")
            
            # Opciones (variantes)
            options = ticket.get('options', [])
            if options:
                print(f"     • Opciones ({len(options)}):")
                for opt in options[:3]:  # Mostrar máximo 3
                    print(f"       - {opt.get('name', 'N/A')}: {opt.get('price', 0)}€ (Stock: {opt.get('stock', 'N/A')})")
        
        # Guardar datos de tickets
        with open('data/tickets_detail.json', 'w', encoding='utf-8') as f:
            json.dump(tickets_data, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Datos de tickets guardados en data/tickets_detail.json")
    
    # ========================================
    # MOSTRAR INFORMACIÓN DE LISTAS/RESERVAS
    # ========================================
    if lists_data:
        print(f"\n{'=' * 70}")
        print("📋 INFORMACIÓN DE LISTAS/RESERVAS")
        print(f"{'=' * 70}")
        
        if isinstance(lists_data, list):
            print(f"\n✅ Encontradas {len(lists_data)} listas:\n")
            for i, lista in enumerate(lists_data):
                print(f"  🗒️  Lista #{i+1}: {lista.get('name', 'Sin nombre')}")
                print(f"     • Tipo: {lista.get('type')}")
                print(f"     • Precio: {lista.get('price', 0)}€")
        elif isinstance(lists_data, dict):
            print(f"\n  Campos: {list(lists_data.keys())}")
    
    # ========================================
    # RESUMEN DE CAMPOS EXTRAÍBLES
    # ========================================
    print(f"\n{'=' * 70}")
    print("📊 RESUMEN: INFORMACIÓN EXTRAÍBLE DE ESTA PÁGINA")
    print(f"{'=' * 70}\n")
    
    print("De cada ENTRADA/TICKET se puede extraer:")
    print("  ✓ id - Identificador único")
    print("  ✓ name - Nombre de la entrada")
    print("  ✓ type - Tipo (normal, vip, reserva, etc)")
    print("  ✓ price - Precio")
    print("  ✓ priceComplete - Precio con comisiones")
    print("  ✓ isSoldOut - Si está agotada")
    print("  ✓ areFewLeft - Si quedan pocas")
    print("  ✓ disponibility - Disponibilidad")
    print("  ✓ dates.start - Inicio de venta")
    print("  ✓ dates.end - Fin de venta")
    print("  ✓ options[] - Variantes/opciones de la entrada")
    print("  ✓ isCashlessActive - Si acepta cashless")
    
    browser.stop()
    print(f"\n{'=' * 70}")
    print("✅ EXPLORACIÓN COMPLETADA")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(explore_event_page())

