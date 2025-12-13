"""
Configuración de Firebase para el scraper de PartyFinder.

Para configurar:
1. Ve a https://console.firebase.google.com
2. Crea un nuevo proyecto o usa uno existente
3. Ve a Configuración del proyecto > Cuentas de servicio
4. Genera una nueva clave privada (JSON)
5. Guarda el archivo como 'serviceAccountKey.json' en esta carpeta
   O configura la variable de entorno FIREBASE_SERVICE_ACCOUNT con el JSON
"""

import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from typing import Optional

# Inicialización global
_db: Optional[firestore.Client] = None


def init_firebase() -> bool:
    """
    Inicializa Firebase Admin SDK.
    
    Busca credenciales en este orden:
    1. Variable de entorno FIREBASE_SERVICE_ACCOUNT (JSON string)
    2. Archivo serviceAccountKey.json en el directorio backend/
    
    Returns:
        bool: True si se inicializó correctamente, False si falló
    """
    global _db
    
    if _db is not None:
        return True  # Ya inicializado
    
    try:
        cred = None
        
        # Opción 1: Variable de entorno (para CI/CD)
        service_account_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
        if service_account_json:
            try:
                service_account_info = json.loads(service_account_json)
                cred = credentials.Certificate(service_account_info)
                print("[Firebase] Credenciales cargadas desde variable de entorno")
            except json.JSONDecodeError:
                print("[Firebase] Error: Variable FIREBASE_SERVICE_ACCOUNT no es JSON válido")
        
        # Opción 2: Archivo local
        if cred is None:
            key_path = os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json')
            if os.path.exists(key_path):
                cred = credentials.Certificate(key_path)
                print(f"[Firebase] Credenciales cargadas desde {key_path}")
            else:
                print(f"[Firebase] No se encontró archivo de credenciales en {key_path}")
                return False
        
        # Inicializar app
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        
        _db = firestore.client()
        print("[Firebase] Inicializado correctamente")
        return True
        
    except Exception as e:
        print(f"[Firebase] Error de inicialización: {e}")
        return False


def get_firestore() -> Optional[firestore.Client]:
    """
    Obtiene el cliente de Firestore.
    Inicializa Firebase si es necesario.
    
    Returns:
        Cliente de Firestore o None si no está configurado
    """
    global _db
    
    if _db is None:
        if not init_firebase():
            return None
    
    return _db


def upload_events_to_firestore(events: list) -> bool:
    """
    Sube los eventos a Firestore.
    
    Args:
        events: Lista de eventos en formato de la app
        
    Returns:
        bool: True si se subieron correctamente
    """
    db = get_firestore()
    if db is None:
        print("[Firebase] No se pudo conectar a Firestore")
        return False
    
    try:
        # Referencia a la colección de eventos
        eventos_ref = db.collection('eventos')
        
        # Batch write para eficiencia
        batch = db.batch()
        batch_count = 0
        total_uploaded = 0
        
        for event_data in events:
            evento = event_data.get('evento', {})
            
            # Crear ID único basado en código y fecha
            code = evento.get('code', '')
            fecha = evento.get('fecha', '')
            venue = evento.get('lugar', {}).get('nombre', '').strip()
            
            # ID del documento: venue_fecha_code
            doc_id = f"{venue}_{fecha}_{code}".replace(' ', '_').replace('/', '-')
            
            # Preparar datos para Firestore
            firestore_data = {
                'nombreEvento': evento.get('nombreEvento', ''),
                'descripcion': evento.get('descripcion', ''),
                'fecha': evento.get('fecha', ''),
                'hora_inicio': evento.get('hora_inicio', ''),
                'hora_fin': evento.get('hora_fin', ''),
                'imagen_url': evento.get('imagen_url', ''),
                'url_evento': evento.get('url_evento', ''),
                'code': code,
                'edad_minima': evento.get('edad_minima', 18),
                'codigo_vestimenta': evento.get('codigo_vestimenta', ''),
                'tags': evento.get('tags', []),
                'aforo': evento.get('aforo', 0),
                'lugar': evento.get('lugar', {}),
                'entradas': evento.get('entradas', []),
                'updated_at': firestore.SERVER_TIMESTAMP,
            }
            
            # Añadir al batch
            doc_ref = eventos_ref.document(doc_id)
            batch.set(doc_ref, firestore_data, merge=True)
            batch_count += 1
            total_uploaded += 1
            
            # Firestore tiene límite de 500 operaciones por batch
            if batch_count >= 450:
                batch.commit()
                batch = db.batch()
                batch_count = 0
                print(f"[Firebase] Batch de 450 eventos subido...")
        
        # Commit final
        if batch_count > 0:
            batch.commit()
        
        print(f"[Firebase] {total_uploaded} eventos subidos correctamente")
        return True
        
    except Exception as e:
        print(f"[Firebase] Error subiendo eventos: {e}")
        return False


def delete_old_events() -> int:
    """
    Elimina eventos con fecha pasada.
    
    Returns:
        int: Número de eventos eliminados
    """
    db = get_firestore()
    if db is None:
        return 0
    
    try:
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Buscar eventos con fecha anterior a hoy
        eventos_ref = db.collection('eventos')
        old_events = eventos_ref.where('fecha', '<', today).stream()
        
        deleted = 0
        batch = db.batch()
        batch_count = 0
        
        for doc in old_events:
            batch.delete(doc.reference)
            batch_count += 1
            deleted += 1
            
            if batch_count >= 450:
                batch.commit()
                batch = db.batch()
                batch_count = 0
        
        if batch_count > 0:
            batch.commit()
        
        if deleted > 0:
            print(f"[Firebase] {deleted} eventos antiguos eliminados")
        
        return deleted
        
    except Exception as e:
        print(f"[Firebase] Error eliminando eventos antiguos: {e}")
        return 0

