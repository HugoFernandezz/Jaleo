/**
 * Configuración de Firebase para PartyFinder
 * 
 * IMPORTANTE: Reemplaza los valores de firebaseConfig con los de tu proyecto Firebase.
 * Puedes encontrarlos en:
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

// Configuración de Firebase - REEMPLAZAR CON TUS VALORES
const firebaseConfig = {
    apiKey: "AIzaSyACNEPsAldntktsfyR6uXNPzY3bwZcfjgU",
    authDomain: "partyfinder-murcia.firebaseapp.com",
    projectId: "partyfinder-murcia",
    storageBucket: "partyfinder-murcia.firebasestorage.app",
    messagingSenderId: "711278175802",
    appId: "1:711278175802:web:f0e041c143d2816af5b703"
  };

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

