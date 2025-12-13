import { ApiResponse, Party, Venue, TicketType } from '../types';
import { getEventos, subscribeToEventos } from './firebase';
import { DocumentData } from 'firebase/firestore';

// Configuración: usar Firebase o fallback local
const USE_FIREBASE = true;

// URLs de fallback para desarrollo local
const LOCAL_API_URL = 'http://192.168.1.49:5000/api/events';
const JSONBIN_URL = 'https://api.jsonbin.io/v3/b/686d49718960c979a5b94ce1/latest';
const JSONBIN_KEY = '$2a$10$h64fSgvYbJKKoITgCHExTOqLoX6KlNaeNoN0VJAHHgcf9SJ9pDRUq';

/**
 * Transforma un evento de Firebase al formato de la app
 */
function transformFirebaseEvent(doc: DocumentData, index: number): { venue: Venue, party: Party } {
  const lugar = doc.lugar || {};
  
  // Crear venue
  const venue: Venue = {
    id: `v_${lugar.nombre?.replace(/\s/g, '_') || index}`,
    name: lugar.nombre || 'Venue',
    description: lugar.descripcion || '',
    address: lugar.direccion || '',
    imageUrl: lugar.imagen_url || lugar.imagen_portada || '',
    website: lugar.sitio_web || '',
    phone: lugar.telefono || '',
    isActive: true,
    category: {
      id: '1',
      name: lugar.categoria || 'Discoteca',
      icon: 'musical-notes',
    },
  };
  
  // Transformar entradas
  const entradas = doc.entradas || [];
  const ticketTypes: TicketType[] = entradas.map((entrada: any, i: number) => ({
    id: entrada.id || `t_${index}_${i}`,
    name: entrada.tipo || 'Entrada General',
    description: entrada.descripcion || '',
    price: parseFloat(entrada.precio) || 0,
    isAvailable: !entrada.agotadas,
    isSoldOut: entrada.agotadas || false,
    fewLeft: entrada.quedan_pocas || false,
    restrictions: entrada.restricciones || '',
    purchaseUrl: entrada.url_compra || '',
  }));
  
  // Calcular precio mínimo
  const prices = ticketTypes.map(t => t.price).filter(p => p > 0);
  const minPrice = prices.length > 0 ? Math.min(...prices) : 0;
  
  // Crear party
  const party: Party = {
    id: doc.id || `p_${index}`,
    venueId: venue.id,
    venueName: venue.name,
    title: doc.nombreEvento || 'Evento',
    description: doc.descripcion || '',
    date: doc.fecha || '',
    startTime: doc.hora_inicio || '23:00',
    endTime: doc.hora_fin || '06:00',
    price: minPrice,
    imageUrl: doc.imagen_url || venue.imageUrl,
    ticketUrl: doc.url_evento || '',
    isAvailable: ticketTypes.some(t => t.isAvailable),
    fewLeft: ticketTypes.some(t => t.fewLeft && t.isAvailable),
    capacity: doc.aforo || 500,
    soldTickets: doc.entradas_vendidas || 0,
    tags: doc.tags || ['Fiesta'],
    venueAddress: venue.address,
    ticketTypes: ticketTypes,
    // Campos adicionales
    ageMinimum: doc.edad_minima || 18,
    dressCode: doc.codigo_vestimenta || '',
    latitude: lugar.latitud,
    longitude: lugar.longitud,
  };
  
  return { venue, party };
}

/**
 * Transforma los eventos de Firebase al formato de la app
 */
function transformFirebaseData(eventos: DocumentData[]): { venues: Venue[], parties: Party[] } {
  const venues: Venue[] = [];
  const parties: Party[] = [];
  const venueMap = new Map<string, Venue>();
  
  eventos.forEach((doc, index) => {
    const { venue, party } = transformFirebaseEvent(doc, index);
    
    // Añadir venue si no existe
    if (!venueMap.has(venue.name)) {
      venueMap.set(venue.name, venue);
      venues.push(venue);
    }
    
    parties.push(party);
  });
  
  return { venues, parties };
}

/**
 * Transforma datos del formato antiguo (JSONBin/local)
 */
function transformLegacyData(apiData: any[]): { venues: Venue[], parties: Party[] } {
  const venues: Venue[] = [];
  const parties: Party[] = [];
  const venueMap = new Map<string, Venue>();

  apiData.forEach((item, index) => {
    if (!item || !item.evento || !item.evento.lugar) {
      return;
    }

    const eventoData = item.evento;
    const lugarData = eventoData.lugar;

    let venue: Venue | undefined = venueMap.get(lugarData.nombre);
    if (!venue) {
      venue = {
        id: `v${venueMap.size + 1}`,
        name: lugarData.nombre,
        description: lugarData.descripcion || `Eventos en ${lugarData.nombre}`,
        address: lugarData.direccion,
        imageUrl: lugarData.imagen_url || 'https://images.unsplash.com/photo-1514933651103-005eec06c04b?w=800&h=600&fit=crop&crop=center',
        website: lugarData.sitio_web || '',
        phone: lugarData.telefono || '',
        isActive: true,
        category: {
          id: '1',
          name: lugarData.categoria || 'Discoteca',
          icon: 'musical-notes',
        },
      };
      venueMap.set(venue.name, venue);
      venues.push(venue);
    }

    const ticketTypes: TicketType[] = (eventoData.entradas || []).map((t: any, i: number) => ({
      id: t.id || `t${index}-${i}`,
      name: t.tipo,
      description: t.descripcion || '',
      price: parseFloat(t.precio) || 0,
      isAvailable: !t.agotadas,
      isSoldOut: t.agotadas,
      fewLeft: t.quedan_pocas || false,
      restrictions: t.restricciones,
      purchaseUrl: t.url_compra || '',
    }));

    const party: Party = {
      id: `p${index + 1}`,
      venueId: venue.id,
      venueName: venue.name,
      title: eventoData.nombreEvento,
      description: eventoData.descripcion || `Únete a la fiesta en ${venue.name}`,
      date: eventoData.fecha,
      startTime: eventoData.hora_inicio,
      endTime: eventoData.hora_fin,
      price: Math.min(...ticketTypes.map(t => t.price).filter(p => p > 0), Infinity),
      imageUrl: eventoData.imagen_url || venue.imageUrl,
      ticketUrl: eventoData.url_evento || '',
      isAvailable: ticketTypes.some(t => t.isAvailable),
      fewLeft: ticketTypes.some(t => t.fewLeft && t.isAvailable),
      capacity: eventoData.aforo || 500,
      soldTickets: eventoData.entradas_vendidas || 0,
      tags: eventoData.tags || ['Fiestas'],
      venueAddress: venue.address,
      ticketTypes: ticketTypes,
      ageMinimum: eventoData.edad_minima || 18,
      dressCode: eventoData.codigo_vestimenta || '',
    };
    parties.push(party);
  });

  return { venues, parties };
}


class ApiService {
  private cache: { venues: Venue[], parties: Party[] } | null = null;
  private unsubscribe: (() => void) | null = null;
  private listeners: ((data: { venues: Venue[], parties: Party[] }) => void)[] = [];

  /**
   * Obtiene los datos de Firebase con actualización en tiempo real
   */
  async getCompleteData(): Promise<ApiResponse<{ venues: Venue[], parties: Party[] }>> {
    // Si hay caché, devolverlo inmediatamente
    if (this.cache) {
      return { success: true, data: this.cache };
    }

    try {
      if (USE_FIREBASE) {
        // Obtener datos de Firebase
        const eventos = await getEventos();
        
        if (eventos.length > 0) {
          const data = transformFirebaseData(eventos);
          this.cache = data;
          return { success: true, data };
        }
      }

      // Fallback a API local o JSONBin
      return this.fetchFromFallback();

    } catch (error) {
      console.error('Error obteniendo datos:', error);
      
      // Intentar fallback
      return this.fetchFromFallback();
    }
  }

  /**
   * Fallback a fuentes alternativas
   */
  private async fetchFromFallback(): Promise<ApiResponse<{ venues: Venue[], parties: Party[] }>> {
    try {
      // Intentar API local primero
      const localResponse = await fetch(LOCAL_API_URL);
      if (localResponse.ok) {
        const localData = await localResponse.json();
        if (localData.data && localData.data.length > 0) {
          const data = transformLegacyData(localData.data);
          this.cache = data;
          return { success: true, data };
        }
      }
    } catch (e) {
      // API local no disponible
    }

    try {
      // Intentar JSONBin
      const jsonbinResponse = await fetch(JSONBIN_URL, {
        headers: { 'X-Master-Key': JSONBIN_KEY },
      });
      if (jsonbinResponse.ok) {
        const jsonbinData = await jsonbinResponse.json();
        if (jsonbinData.record) {
          const data = transformLegacyData(jsonbinData.record);
          this.cache = data;
          return { success: true, data };
        }
      }
    } catch (e) {
      // JSONBin no disponible
    }

    // Sin datos disponibles
    return {
      success: true,
      data: { venues: [], parties: [] },
    };
  }

  /**
   * Suscribe a actualizaciones en tiempo real de Firebase
   */
  subscribeToUpdates(callback: (data: { venues: Venue[], parties: Party[] }) => void): () => void {
    this.listeners.push(callback);

    // Si ya hay suscripción activa, no crear otra
    if (this.unsubscribe) {
      // Enviar datos en caché si existen
      if (this.cache) {
        callback(this.cache);
      }
      return () => {
        this.listeners = this.listeners.filter(l => l !== callback);
      };
    }

    // Crear suscripción a Firebase
    if (USE_FIREBASE) {
      this.unsubscribe = subscribeToEventos((eventos) => {
        const data = transformFirebaseData(eventos);
        this.cache = data;
        
        // Notificar a todos los listeners
        this.listeners.forEach(listener => listener(data));
      });
    }

    return () => {
      this.listeners = this.listeners.filter(l => l !== callback);
      
      // Si no quedan listeners, cancelar suscripción
      if (this.listeners.length === 0 && this.unsubscribe) {
        this.unsubscribe();
        this.unsubscribe = null;
      }
    };
  }

  /**
   * Limpia la caché
   */
  clearCache(): void {
    this.cache = null;
  }
}

export const apiService = new ApiService();
