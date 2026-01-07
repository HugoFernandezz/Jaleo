import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import os
import sys

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

def delete_old_events(collection_name='eventos'):
    """
    BORRADO COMPLETO: Elimina TODOS los eventos existentes en la colección especificada.
    Esto asegura que no queden duplicados antiguos cuando se suben nuevos datos.
    
    Args:
        collection_name: Nombre de la colección a limpiar (default: 'eventos')
    """
    db = get_db()
    if not db: return

    print(f"🗑️  Iniciando borrado de TODOS los eventos antiguos de '{collection_name}'...")
    
    try:
        # Obtener todos los documentos de la colección
        events_ref = db.collection(collection_name)
        docs = events_ref.stream()
        
        count = 0
        batch = db.batch()
        
        for doc in docs:
            batch.delete(doc.reference)
            count += 1
            
            # Firestore batch limit is 500
            if count % 400 == 0:
                batch.commit()
                batch = db.batch()
                print(f"   ... {count} eventos borrados")
        
        # Commit de los restantes
        if count % 400 != 0:
            batch.commit()
            
        print(f"✅ Limpieza completada: {count} eventos eliminados de '{collection_name}'.")
            
    except Exception as e:
        print(f"❌ Error borrando eventos de '{collection_name}': {e}")

def upload_events_to_firestore(events_data, collection_name='eventos'):
    """
    Sube la lista de eventos a Firestore.
    
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
        
        # Generar un ID determinista si es posible, o dejar que Firestore asigne uno
        # Para evitar problemas, usamos Firestore auto-id, ya que acabamos de borrar todo.
        # Pero si queremos consistencia, podríamos usar code + fecha.
        
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
