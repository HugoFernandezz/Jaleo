/**
 * Configuración de Firebase para PartyFinder
 * 
 * Las credenciales se cargan desde variables de entorno (archivo .env)
 * IMPORTANTE: Crea un archivo .env en la raíz del proyecto con las variables EXPO_PUBLIC_FIREBASE_*
 * Puedes encontrar los valores en:
 * Firebase Console > Configuración del proyecto > Tus apps > SDK snippet
 */

import { initializeApp } from 'firebase/app';
import { 
  getFirestore, 
  collection, 
  getDocs, 
  onSnapshot,
  query,
  where,
  orderBy,
  Timestamp,
  QuerySnapshot,
  DocumentData
} from 'firebase/firestore';

// Configuración de Firebase desde variables de entorno
const firebaseConfig = {
    apiKey: process.env.EXPO_PUBLIC_FIREBASE_API_KEY,
    authDomain: process.env.EXPO_PUBLIC_FIREBASE_AUTH_DOMAIN,
    projectId: process.env.EXPO_PUBLIC_FIREBASE_PROJECT_ID,
    storageBucket: process.env.EXPO_PUBLIC_FIREBASE_STORAGE_BUCKET,
    messagingSenderId: process.env.EXPO_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
    appId: process.env.EXPO_PUBLIC_FIREBASE_APP_ID,
  };

// Validar que todas las variables de entorno estén definidas
if (!firebaseConfig.apiKey || !firebaseConfig.authDomain || !firebaseConfig.projectId) {
  throw new Error(
    'Error: Variables de entorno de Firebase no configuradas. ' +
    'Por favor, crea un archivo .env con las variables EXPO_PUBLIC_FIREBASE_* ' +
    'o revisa .env.example para más información.'
  );
}

// Inicializar Firebase
const app = initializeApp(firebaseConfig);
const db = getFirestore(app);

// Referencia a la colección de eventos
const eventosCollection = collection(db, 'eventos');

/**
 * Obtiene todos los eventos de Firestore
 */
export async function getEventos(): Promise<DocumentData[]> {
  try {
    // Query: eventos con fecha >= hoy, ordenados por fecha
    const today = new Date().toISOString().split('T')[0];
    
    const q = query(
      eventosCollection,
      where('fecha', '>=', today),
      orderBy('fecha', 'asc')
    );
    
    const snapshot = await getDocs(q);
    
    const eventos: DocumentData[] = [];
    snapshot.forEach((doc) => {
      eventos.push({
        id: doc.id,
        ...doc.data()
      });
    });
    
    return eventos;
  } catch (error) {
    console.error('Error obteniendo eventos de Firebase:', error);
    return [];
  }
}

/**
 * Suscribe a cambios en tiempo real de los eventos
 */
export function subscribeToEventos(
  callback: (eventos: DocumentData[]) => void
): () => void {
  try {
    const today = new Date().toISOString().split('T')[0];
    
    const q = query(
      eventosCollection,
      where('fecha', '>=', today),
      orderBy('fecha', 'asc')
    );
    
    const unsubscribe = onSnapshot(q, (snapshot: QuerySnapshot) => {
      const eventos: DocumentData[] = [];
      snapshot.forEach((doc) => {
        eventos.push({
          id: doc.id,
          ...doc.data()
        });
      });
      callback(eventos);
    }, (error) => {
      console.error('Error en suscripción de Firebase:', error);
    });
    
    return unsubscribe;
  } catch (error) {
    console.error('Error configurando suscripción:', error);
    return () => {};
  }
}

export { db };

