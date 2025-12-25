#!/usr/bin/env python3
"""
Servicio de Push Notifications para PartyFinder
===============================================
Detecta nuevos eventos y envía notificaciones push a usuarios con alertas activas.

Uso:
    python3 push_notifications.py
"""

import os
import sys
import json
import requests
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

# Importar configuración de Firebase
try:
    from firebase_config import get_db
except ImportError:
    print("❌ Error: No se puede importar firebase_config")
    sys.exit(1)

# Configuración de Expo Push Notification API
EXPO_PUSH_API_URL = "https://exp.host/--/api/v2/push/send"

# Clave para almacenar snapshot de eventos
EVENTS_SNAPSHOT_KEY = "events_snapshot"


def get_previous_events_snapshot(db) -> set:
    """Obtiene el snapshot anterior de eventos desde Firestore."""
    try:
        snapshot_ref = db.collection('_metadata').document(EVENTS_SNAPSHOT_KEY)
        doc = snapshot_ref.get()
        if doc.exists:
            data = doc.to_dict()
            return set(data.get('event_ids', []))
        return set()
    except Exception as e:
        print(f"⚠️ Error obteniendo snapshot: {e}")
        return set()


def save_events_snapshot(db, event_ids: List[str]):
    """Guarda el snapshot actual de eventos en Firestore."""
    try:
        snapshot_ref = db.collection('_metadata').document(EVENTS_SNAPSHOT_KEY)
        snapshot_ref.set({
            'event_ids': event_ids,
            'last_updated': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"⚠️ Error guardando snapshot: {e}")


def get_current_events(db) -> List[Dict]:
    """Obtiene todos los eventos actuales de Firestore."""
    try:
        events_ref = db.collection('eventos')
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Obtener eventos con fecha >= hoy
        events = []
        for doc in events_ref.stream():
            event_data = doc.to_dict()
            if event_data.get('fecha', '') >= today:
                events.append({
                    'id': doc.id,
                    **event_data
                })
        return events
    except Exception as e:
        print(f"❌ Error obteniendo eventos: {e}")
        return []


def get_alert_tokens(db, date: str, venue_name: Optional[str] = None) -> List[str]:
    """Obtiene todos los tokens FCM para alertas que coinciden con la fecha y venue."""
    try:
        alerts_ref = db.collection('alert_tokens')
        
        # Buscar alertas que coincidan con la fecha
        tokens = []
        for doc in alerts_ref.stream():
            alert_data = doc.to_dict()
            alert_id = alert_data.get('alertId', '')
            
            # Parsear alert_id para extraer fecha y venue
            # Formato: {date}_{venueName || 'all'}_{timestamp}
            # Ejemplo: "2024-12-25_Dodo Club_1735123456789" o "2024-12-25_all_1735123456789"
            parts = alert_id.rsplit('_', 1)  # Dividir desde la derecha para separar timestamp
            if len(parts) == 2:
                prefix = parts[0]  # Todo antes del último _
                timestamp = parts[1]  # Último elemento (timestamp)
                
                # Verificar que el timestamp sea numérico
                if not timestamp.isdigit():
                    continue
                
                # Dividir el prefix para obtener fecha y venue
                prefix_parts = prefix.split('_', 1)
                if len(prefix_parts) >= 1:
                    alert_date = prefix_parts[0]
                    alert_venue = prefix_parts[1] if len(prefix_parts) > 1 else 'all'
                    
                    # Verificar coincidencia de fecha
                    date_matches = alert_date == date
                    
                    if date_matches:
                        # Verificar coincidencia de venue
                        # Normalizar nombres para comparación (quitar espacios, convertir a minúsculas)
                        normalized_event_venue = venue_name.lower().replace(' ', '').replace('-', '') if venue_name else ''
                        normalized_alert_venue = alert_venue.lower().replace(' ', '').replace('-', '') if alert_venue else ''
                        
                        venue_matches = (
                            not venue_name or 
                            alert_venue == 'all' or
                            normalized_event_venue in normalized_alert_venue or
                            normalized_alert_venue in normalized_event_venue or
                            venue_name.lower() in alert_venue.lower() or
                            alert_venue.lower() in venue_name.lower()
                        )
                        
                        if venue_matches:
                            token = alert_data.get('token')
                            if token:
                                tokens.append(token)
        
        return list(set(tokens))  # Eliminar duplicados
    except Exception as e:
        print(f"❌ Error obteniendo tokens de alertas: {e}")
        import traceback
        traceback.print_exc()
        return []


def send_push_notification(token: str, title: str, body: str, data: Optional[Dict] = None) -> bool:
    """Envía una notificación push usando Expo Push Notification API."""
    try:
        payload = {
            "to": token,
            "title": title,
            "body": body,
            "sound": "default",
            "priority": "high",
            "data": data or {}
        }
        
        response = requests.post(EXPO_PUSH_API_URL, json=payload, headers={
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        
        if response.status_code == 200:
            result = response.json()
            if result.get('data', {}).get('status') == 'ok':
                return True
            else:
                print(f"⚠️ Error en respuesta: {result}")
                return False
        else:
            print(f"⚠️ Error HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error enviando notificación: {e}")
        return False


def format_date(date_str: str) -> str:
    """Formatea una fecha en formato español."""
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
        months = {
            1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
            5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
            9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
        }
        weekdays = {
            0: 'lunes', 1: 'martes', 2: 'miércoles', 3: 'jueves',
            4: 'viernes', 5: 'sábado', 6: 'domingo'
        }
        weekday = weekdays[date.weekday()]
        return f"{weekday}, {date.day} de {months[date.month]}"
    except:
        return date_str


def check_and_send_notifications():
    """Función principal: detecta nuevos eventos y envía notificaciones."""
    print("=" * 60)
    print("PartyFinder - Push Notifications Service")
    print("=" * 60)
    
    db = get_db()
    if not db:
        print("❌ No se pudo conectar a Firestore")
        return
    
    # Obtener eventos actuales
    print("\n📡 Obteniendo eventos actuales...")
    current_events = get_current_events(db)
    print(f"   ✅ {len(current_events)} eventos encontrados")
    
    # Obtener snapshot anterior
    previous_ids = get_previous_events_snapshot(db)
    print(f"   📸 Snapshot anterior: {len(previous_ids)} eventos")
    
    # Detectar nuevos eventos
    current_ids = {e['id'] for e in current_events}
    new_event_ids = current_ids - previous_ids
    new_events = [e for e in current_events if e['id'] in new_event_ids]
    
    if not new_events:
        print("\n✅ No hay eventos nuevos. Actualizando snapshot...")
        save_events_snapshot(db, list(current_ids))
        return
    
    print(f"\n🎉 {len(new_events)} evento(s) nuevo(s) detectado(s)")
    
    # Para cada nuevo evento, buscar alertas y enviar notificaciones
    notifications_sent = 0
    for event in new_events:
        event_date = event.get('fecha', '')
        # El venue puede estar en lugar.nombre o directamente en el evento
        event_venue = ''
        if isinstance(event.get('lugar'), dict):
            event_venue = event.get('lugar', {}).get('nombre', '')
        elif isinstance(event.get('lugar'), str):
            event_venue = event.get('lugar', '')
        # Normalizar el nombre del venue (quitar espacios extra, convertir a formato consistente)
        event_venue = event_venue.strip() if event_venue else ''
        event_title = event.get('nombreEvento', 'Evento')
        
        if not event_date:
            continue
        
        # Obtener tokens de alertas que coinciden
        tokens = get_alert_tokens(db, event_date, event_venue)
        
        if not tokens:
            print(f"   ⚠️ No hay alertas para: {event_title} ({event_date})")
            continue
        
        print(f"\n   📬 Enviando notificaciones para: {event_title}")
        print(f"      Fecha: {event_date}, Venue: {event_venue}")
        print(f"      Tokens: {len(tokens)}")
        
        # Formatear fecha
        formatted_date = format_date(event_date)
        
        # Enviar notificación a cada token
        for token in tokens:
            success = send_push_notification(
                token=token,
                title="🎉 ¡Nuevas entradas disponibles!",
                body=f"{event_title} en {event_venue} - {formatted_date}",
                data={
                    "eventId": event['id'],
                    "date": event_date,
                    "type": "new_event"
                }
            )
            
            if success:
                notifications_sent += 1
                print(f"      ✅ Notificación enviada")
            else:
                print(f"      ❌ Error enviando notificación")
    
    # Actualizar snapshot
    save_events_snapshot(db, list(current_ids))
    
    print(f"\n✅ Proceso completado: {notifications_sent} notificación(es) enviada(s)")


def main():
    """Punto de entrada principal."""
    try:
        check_and_send_notifications()
        return 0
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

