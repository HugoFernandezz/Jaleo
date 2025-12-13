"""
Servidor API para PartyFinder
=============================
Sirve los datos de eventos scrapeados a la aplicación móvil.

Endpoints:
- GET /api/events - Obtener todos los eventos
- POST /api/scrape - Ejecutar scraping manualmente (protegido)
- GET /api/status - Estado del servidor y última actualización

Uso:
    python server.py
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os
import asyncio
from datetime import datetime
from threading import Thread
import time

app = Flask(__name__)
CORS(app)  # Permitir peticiones desde la app móvil

# Configuración
DATA_FILE = 'data/events.json'
UPDATE_HOUR = 20  # Hora de actualización automática (20:30)
UPDATE_MINUTE = 30

# Estado del servidor
server_status = {
    "last_scrape": None,
    "total_events": 0,
    "is_scraping": False,
    "last_error": None
}


def get_cached_events():
    """Lee los eventos del archivo de caché."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error leyendo caché: {e}")
    return []


def run_scraper():
    """Ejecuta el scraper en un thread separado."""
    global server_status
    
    if server_status["is_scraping"]:
        return False, "Ya hay un scraping en proceso"
    
    server_status["is_scraping"] = True
    server_status["last_error"] = None
    
    try:
        # Importar y ejecutar el scraper
        from scraper import scrape_and_save
        
        # Ejecutar el scraper async
        events = asyncio.run(scrape_and_save())
        
        server_status["last_scrape"] = datetime.now().isoformat()
        server_status["total_events"] = len(events)
        server_status["is_scraping"] = False
        
        return True, f"Scraping completado: {len(events)} eventos"
        
    except Exception as e:
        server_status["is_scraping"] = False
        server_status["last_error"] = str(e)
        return False, str(e)


def scheduled_scraper():
    """Ejecuta el scraper automáticamente a las 20:30."""
    while True:
        now = datetime.now()
        
        # Verificar si es hora de scrapear
        if now.hour == UPDATE_HOUR and now.minute == UPDATE_MINUTE:
            print(f"[SCHEDULER] Ejecutando scraping programado...")
            success, message = run_scraper()
            if success:
                print(f"[OK] {message}")
            else:
                print(f"[ERROR] {message}")
            
            # Esperar 1 hora para no re-ejecutar
            time.sleep(3600)
        else:
            # Revisar cada minuto
            time.sleep(60)


@app.route('/api/events', methods=['GET'])
def get_events():
    """
    Obtiene todos los eventos disponibles.
    
    Returns:
        JSON con los eventos en formato de la app.
    """
    events = get_cached_events()
    
    return jsonify({
        "success": True,
        "data": events,
        "meta": {
            "total": len(events),
            "last_update": server_status["last_scrape"]
        }
    })


@app.route('/api/scrape', methods=['POST'])
def trigger_scrape():
    """
    Ejecuta el scraping manualmente.
    Requiere header 'X-Admin-Key' para autorización.
    """
    # Verificación simple de autorización
    admin_key = request.headers.get('X-Admin-Key')
    if admin_key != 'partyfinder-admin-2024':
        return jsonify({
            "success": False,
            "error": "No autorizado"
        }), 401
    
    # Ejecutar scraper en background
    def async_scrape():
        run_scraper()
    
    thread = Thread(target=async_scrape)
    thread.start()
    
    return jsonify({
        "success": True,
        "message": "Scraping iniciado en background"
    })


@app.route('/api/status', methods=['GET'])
def get_status():
    """
    Obtiene el estado del servidor.
    """
    events = get_cached_events()
    
    return jsonify({
        "status": "online",
        "version": "1.0.0",
        "last_scrape": server_status["last_scrape"],
        "total_events": len(events),
        "is_scraping": server_status["is_scraping"],
        "last_error": server_status["last_error"],
        "scheduled_update": f"{UPDATE_HOUR:02d}:{UPDATE_MINUTE:02d}"
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check para monitoreo."""
    return jsonify({"status": "healthy"})


@app.route('/', methods=['GET'])
def index():
    """Página de inicio."""
    return jsonify({
        "name": "PartyFinder API",
        "version": "1.0.0",
        "endpoints": {
            "/api/events": "GET - Obtener eventos",
            "/api/scrape": "POST - Ejecutar scraping (requiere auth)",
            "/api/status": "GET - Estado del servidor",
            "/api/health": "GET - Health check"
        }
    })


if __name__ == '__main__':
    import sys
    # Forzar UTF-8 en Windows para evitar errores de codificación
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'replace')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'replace')
    
    # Crear directorio data si no existe
    os.makedirs('data', exist_ok=True)
    
    # Verificar si hay datos existentes
    events = get_cached_events()
    if events:
        server_status["total_events"] = len(events)
        print(f"[OK] {len(events)} eventos cargados desde cache")
    else:
        print("[!] No hay eventos en cache. Ejecuta el scraper primero.")
    
    # Iniciar scheduler en background
    scheduler_thread = Thread(target=scheduled_scraper, daemon=True)
    scheduler_thread.start()
    print(f"[SCHEDULER] Scraping automatico programado para las {UPDATE_HOUR:02d}:{UPDATE_MINUTE:02d}")
    
    # Iniciar servidor
    print("\n[SERVER] Iniciando en http://localhost:5000")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=False)

