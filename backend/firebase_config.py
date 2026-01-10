import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import os
import sys
from datetime import datetime

# Configuración
current_dir = os.path.dirname(os.path.abspath(__file__))
cred_path = os.path.join(current_dir, 'serviceAccountKey.json')

# Inicializar Firebase Admin
if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("✅ Firebase Admin inicializado correctamente")
    except Exception as e:
        print(f"❌ Error inicializando Firebase: {e}")
        # Si falla, no podemos continuar con funciones de BD
        pass

def get_db():
    try:
        return firestore.client()
    except Exception as e:
        print(f"❌ Error conectando a Firestore: {e}")
        return None

def is_event_past(event_data: dict) -> bool:
    """
    Verifica si un evento ya pasó comparando fecha + hora_inicio con el momento actual.
    
    Args:
        event_data: Diccionario con los datos del evento (puede estar envuelto en 'evento')
    
    Returns:
        True si el evento ya pasó (fecha + hora_inicio < ahora), False en caso contrario
    """
    # Los datos pueden venir envueltos en "evento" o planos
    evento = event_data.get('evento', event_data)
    
    fecha_str = evento.get('fecha', '')
    hora_inicio_str = evento.get('hora_inicio', '')
    
    if not fecha_str:
        # Si no hay fecha, no podemos determinar si pasó, así que lo preservamos
        return False
    
    try:
        # Parsear fecha (formato: "YYYY-MM-DD")
        fecha_parts = fecha_str.split('-')
        if len(fecha_parts) != 3:
            return False
        
        year, month, day = int(fecha_parts[0]), int(fecha_parts[1]), int(fecha_parts[2])
        
        # Parsear hora de inicio (formato: "HH:MM")
        # Si no hay hora_inicio o está vacío, usar 00:00 (inicio del día)
        if not hora_inicio_str or hora_inicio_str.strip() == '':
            hora = 0
            minuto = 0
        else:
            hora_parts = hora_inicio_str.split(':')
            if len(hora_parts) != 2:
                # Si el formato no es válido, usar 00:00 como default conservador
                hora = 0
                minuto = 0
            else:
                hora = int(hora_parts[0])
                minuto = int(hora_parts[1])
        
        # Crear datetime del evento (hora local)
        event_datetime = datetime(year, month, day, hora, minuto, 0)
        
        # Obtener datetime actual (hora local)
        now = datetime.now()
        
        # El evento pasó si su fecha+hora es anterior a ahora
        return event_datetime < now
        
    except (ValueError, TypeError, AttributeError) as e:
        # Si hay error parseando, preservar el evento por seguridad
        print(f"   ⚠️ Error parseando fecha/hora del evento: {e}")
        return False


def delete_old_events(collection_name='eventos'):
    """
    Elimina eventos pasados (todos) y eventos futuros del scraper, preservando eventos futuros manuales.
    
    Lógica:
    1. PRIMERO: Elimina TODOS los eventos pasados (fecha + hora_inicio ya pasó), 
       independientemente de si son manuales o del scraper
    2. SEGUNDO: De los eventos futuros, elimina solo los del scraper (source='scraper' o sin source)
    3. PRESERVA: Eventos futuros manuales (source='manual' o is_manual=True)
    
    Args:
        collection_name: Nombre de la colección a limpiar (default: 'eventos')
    """
    db = get_db()
    if not db: return

    print(f"🗑️  Limpiando eventos de '{collection_name}'...")
    print(f"   - Eliminando eventos pasados (todos)")
    print(f"   - Eliminando eventos futuros del scraper (preservando eventos futuros manuales)")
    
    try:
        # Obtener todos los documentos de la colección
        events_ref = db.collection(collection_name)
        docs = events_ref.stream()
        
        count_past_deleted = 0  # Eventos pasados eliminados
        count_scraper_deleted = 0  # Eventos futuros del scraper eliminados
        count_preserved = 0  # Eventos preservados
        batch = db.batch()
        
        for doc in docs:
            data = doc.to_dict()
            is_past = is_event_past(data)
            
            # PASO 1: Eliminar TODOS los eventos pasados (manuales y del scraper)
            if is_past:
                batch.delete(doc.reference)
                count_past_deleted += 1
                
                # Firestore batch limit is 500
                if (count_past_deleted + count_scraper_deleted) % 400 == 0:
                    batch.commit()
                    batch = db.batch()
                    print(f"   ... {count_past_deleted} eventos pasados, {count_scraper_deleted} eventos del scraper borrados")
                continue
            
            # PASO 2: Para eventos futuros, verificar si es manual
            source = data.get('source', '')  # Si no existe, devuelve ''
            is_manual = data.get('is_manual', False)
            
            # Preservar eventos futuros manuales
            if source == 'manual' or is_manual:
                count_preserved += 1
                continue
            
            # Eliminar eventos futuros del scraper:
            # - source='scraper' (eventos nuevos del scraper)
            # - source='' o sin campo source (eventos antiguos del scraper, antes de implementar source)
            if source == 'scraper' or source == '':
                batch.delete(doc.reference)
                count_scraper_deleted += 1
                
                # Firestore batch limit is 500
                if (count_past_deleted + count_scraper_deleted) % 400 == 0:
                    batch.commit()
                    batch = db.batch()
                    print(f"   ... {count_past_deleted} eventos pasados, {count_scraper_deleted} eventos del scraper borrados")
            else:
                # Por seguridad, si tiene un source desconocido (distinto de 'scraper', 'manual', o ''), preservarlo
                count_preserved += 1
        
        # Commit de los restantes
        if (count_past_deleted + count_scraper_deleted) % 400 != 0:
            batch.commit()
            
        print(f"✅ Limpieza completada:")
        print(f"   - {count_past_deleted} eventos pasados eliminados (todos)")
        print(f"   - {count_scraper_deleted} eventos futuros del scraper eliminados")
        print(f"   - {count_preserved} eventos futuros preservados (manuales) en '{collection_name}'")
            
    except Exception as e:
        print(f"❌ Error borrando eventos de '{collection_name}': {e}")

def upload_events_to_firestore(events_data, collection_name='eventos'):
    """
    Sube la lista de eventos a Firestore.
    
    Los eventos del scraper se marcan con source='scraper' para poder identificarlos
    y eliminarlos en futuras ejecuciones del scraper, preservando eventos manuales.
    
    Args:
        events_data: Lista de eventos a subir
        collection_name: Nombre de la colección donde subir (default: 'eventos')
    """
    db = get_db()
    if not db: return
    
    if not events_data:
        print("⚠️ No hay eventos para subir.")
        return

    print(f"📤 Subiendo {len(events_data)} eventos a Firestore (colección: '{collection_name}')...")
    
    events_ref = db.collection(collection_name)
    batch = db.batch()
    count = 0
    
    for item in events_data:
        # Los datos pueden venir envueltos en "evento" o planos
        event_dict = item.get('evento', item)
        
        # Añadir campo source='scraper' para identificar eventos del scraper
        # Este campo es ignorado por versiones antiguas de la app (compatible hacia atrás)
        # Solo se usa para distinguir entre eventos del scraper y eventos manuales
        event_dict['source'] = 'scraper'
        
        # Añadir timestamp de subida
        event_dict['last_updated'] = firestore.SERVER_TIMESTAMP
        
        # Crear documento nuevo
        new_doc_ref = events_ref.document()
        batch.set(new_doc_ref, event_dict)
        
        count += 1
        if count % 400 == 0:
            batch.commit()
            batch = db.batch()
            print(f"   ... {count} eventos subidos")
            
    # Commit final
    if count % 400 != 0:
        batch.commit()
        
    print(f"✅ Carga completada con éxito: {count} eventos activos en '{collection_name}'.")
