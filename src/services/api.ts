import { ApiResponse, Party, Venue, TicketType } from '../types';
import { subscribeToEventos, getEventos } from './firebase';

// CONFIGURACIÓN: El backend local suele usarse para pruebas rápidas
// Intenta conectar a 192.168.1.49 porque es la IP que se configuró originalmente 
// como tu servidor de desarrollo. Puedes cambiarla por 'localhost' o tu IP actual.
const API_BASE_URL = 'http://localhost:5000/api/events';

// Cambia a true si quieres que la APP intente buscar un servidor local antes que en Firebase
const USE_LOCAL_BACKEND = false;

// CONFIGURACIÓN: Alias para unificar nombres de discotecas
const VENUE_ALIASES: { [key: string]: string } = {
  "Luminata Disco": "Luminata",
  "LUMINATA": "Luminata",
  "DODO CLUB": "Dodo Club",
  "Dodo club": "Dodo Club",
  "OW CLUB": "OW Club",
  "Ow Club": "OW Club",
  // Añadir más alias aquí según se detecten
};

const normalizeVenueName = (rawName: string): string => {
  if (!rawName) return '';
  const trimmed = rawName.trim();

  // 1. Buscar coincidencia exacta en alias
  if (VENUE_ALIASES[trimmed]) {
    return VENUE_ALIASES[trimmed];
  }

  // 2. Buscar coincidencia insensible a mayúsculas/minúsculas en alias keys
  const lowerTrimmed = trimmed.toLowerCase();
  const aliasKey = Object.keys(VENUE_ALIASES).find(k => k.toLowerCase() === lowerTrimmed);
  if (aliasKey) {
    return VENUE_ALIASES[aliasKey];
  }

  // 3. Normalización básica de capitalización (Opcional, pero ayuda con "DODO CLUB" -> "Dodo Club" si no está en alias)
  // Si está TODO EN MAYÚSCULAS o todo en minúsculas, intentar Title Case
  if (trimmed === trimmed.toUpperCase() || trimmed === trimmed.toLowerCase()) {
    return trimmed.replace(/\w\S*/g, (txt) => txt.charAt(0).toUpperCase() + txt.substr(1).toLowerCase());
  }

  return trimmed;
};

// Función para transformar los datos de la API al formato que la app espera
const transformData = (apiData: any[]): { venues: Venue[], parties: Party[] } => {
  const venues: Venue[] = [];
  const parties: Party[] = [];
  const venueMap = new Map<string, Venue>();

  apiData.forEach((item, index) => {
    // Soporte para datos envueltos en 'evento' (backend local) o planos (Firestore)
    const eventoData = item.evento || item;
    const lugarData = eventoData.lugar;

    if (!eventoData || !lugarData || !lugarData.nombre) {
      console.warn(`Saltando item con datos incompletos en el índice ${index}:`, item);
      return;
    }

    const normalizedVenueName = normalizeVenueName(lugarData.nombre);

    // 1. Procesar y añadir el Venue (si no existe ya)
    let venue: Venue | undefined = venues.find(v => v.name === normalizedVenueName);
    if (!venue) {
      venue = {
        id: `v${venues.length + 1}`,
        name: normalizedVenueName,
        description: lugarData.descripcion || `Eventos en ${lugarData.nombre}`,
        address: lugarData.direccion || lugarData.direccion_corta || '',
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
      venues.push(venue);
    }

    // 2. Procesar los Tipos de Entrada
    const ticketTypes: TicketType[] = (eventoData.entradas || []).map((t: any, i: number) => ({
      id: t.id || `t${index}-${i}`,
      name: t.tipo || t.nombre || 'Entrada',
      description: t.descripcion || '',
      price: typeof t.precio === 'string' ? parseFloat(t.precio.replace(',', '.')) : (t.precio || 0),
      isAvailable: t.agotadas !== undefined ? !t.agotadas : (t.isAvailable !== false),
      isSoldOut: t.agotadas || t.isSoldOut || false,
      fewLeft: t.quedan_pocas || t.fewLeft || false,
      restrictions: t.restricciones || '',
      purchaseUrl: t.url_compra || t.link_compra || '',
    }));

    // 3. Procesar y añadir la Party
    const party: Party = {
      id: eventoData.id || `p${index + 1}`,
      venueId: venue.id,
      venueName: venue.name,
      title: eventoData.nombreEvento || eventoData.titulo || 'Sin título',
      description: eventoData.descripcion || `Únete a la fiesta en ${venue.name}`,
      date: eventoData.fecha,
      startTime: eventoData.hora_inicio,
      endTime: eventoData.hora_fin,
      price: ticketTypes.length > 0 && ticketTypes.some(t => t.price > 0)
        ? Math.min(...ticketTypes.map(t => t.price).filter(p => p > 0))
        : 0,
      imageUrl: eventoData.imagen_url || eventoData.imageUrl || venue.imageUrl,
      ticketUrl: eventoData.url_evento || eventoData.url_entradas || '',
      isAvailable: ticketTypes.length > 0 ? ticketTypes.some(t => t.isAvailable) : true,
      fewLeft: ticketTypes.some(t => t.fewLeft && t.isAvailable),
      capacity: eventoData.aforo || 500,
      soldTickets: eventoData.entradas_vendidas || 0,
      tags: eventoData.tags || ['Fiesta'],
      venueAddress: lugarData.direccion || venue.address,
      ticketTypes: ticketTypes,
      ageMinimum: eventoData.edad_minima || eventoData.ageMinimum,
      dressCode: eventoData.codigo_vestimenta || eventoData.dressCode,
      latitude: lugarData.latitud || lugarData.latitude,
      longitude: lugarData.longitud || lugarData.longitude,
    };

    // Solo añadir si tiene fecha y título mínimo
    if (party.date && party.title) {
      parties.push(party);
    }
  });

  return { venues, parties };
};


class ApiService {
  private cache = new Map<string, { data: any; timestamp: number; lastUpdateDate: string }>();
  private readonly UPDATE_HOUR = 20; // 20:30 Madrid
  private readonly UPDATE_MINUTE = 30;

  // Obtener la fecha/hora actual en zona horaria de Madrid
  private getMadridTime(): Date {
    return new Date(new Date().toLocaleString("en-US", { timeZone: "Europe/Madrid" }));
  }

  // Verificar si necesitamos hacer una nueva petición
  private shouldFetchNewData(): boolean {
    const madridTime = this.getMadridTime();
    const currentHour = madridTime.getHours();
    const currentMinute = madridTime.getMinutes();
    const currentDate = madridTime.toDateString();

    // Obtener información del caché
    const cached = this.cache.get(API_BASE_URL);

    // Si no hay caché, necesitamos datos
    if (!cached) {
      // Solo si ya es después de las 20:30
      const shouldFetch = currentHour > this.UPDATE_HOUR ||
        (currentHour === this.UPDATE_HOUR && currentMinute >= this.UPDATE_MINUTE);
      return shouldFetch;
    }

    // Si ya tenemos datos de hoy después de las 20:30, no necesitamos más
    if (cached.lastUpdateDate === currentDate) {
      return false;
    }

    // Si es un día nuevo y ya es después de las 20:30
    const shouldFetch = currentHour > this.UPDATE_HOUR ||
      (currentHour === this.UPDATE_HOUR && currentMinute >= this.UPDATE_MINUTE);
    return shouldFetch;
  }

  // Verificar si hay datos válidos en caché (aunque sean del día anterior)
  private hasValidCachedData(): boolean {
    const cached = this.cache.get(API_BASE_URL);
    return cached != null && cached.data != null;
  }

  private getCachedData<T>(key: string): T | null {
    const cached = this.cache.get(key);
    if (cached && cached.data) {
      return cached.data;
    }
    return null;
  }

  private setCachedData(key: string, data: any): void {
    const madridTime = this.getMadridTime();
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      lastUpdateDate: madridTime.toDateString()
    });
  }

  public clearCache(): void {
    this.cache.clear();
  }

  // Obtener información sobre cuándo será la próxima actualización
  public getNextUpdateInfo(): { nextUpdate: Date; hasNewDataAvailable: boolean; usingCacheFrom: string | null } {
    const madridTime = this.getMadridTime();
    const today = new Date(madridTime);
    const tomorrow = new Date(madridTime);
    tomorrow.setDate(tomorrow.getDate() + 1);

    // Calcular próxima actualización
    let nextUpdate: Date;
    if (madridTime.getHours() < this.UPDATE_HOUR ||
      (madridTime.getHours() === this.UPDATE_HOUR && madridTime.getMinutes() < this.UPDATE_MINUTE)) {
      // Hoy a las 20:30
      nextUpdate = new Date(today.setHours(this.UPDATE_HOUR, this.UPDATE_MINUTE, 0, 0));
    } else {
      // Mañana a las 20:30
      nextUpdate = new Date(tomorrow.setHours(this.UPDATE_HOUR, this.UPDATE_MINUTE, 0, 0));
    }

    const cached = this.cache.get(API_BASE_URL);
    const hasNewDataAvailable = this.shouldFetchNewData();
    const usingCacheFrom = cached ? new Date(cached.timestamp).toLocaleDateString('es-ES') : null;

    return { nextUpdate, hasNewDataAvailable, usingCacheFrom };
  }

  // Intenta obtener datos del backend local (si está activo para desarrollo)
  private async fetchFromLocalBackend(): Promise<any[] | null> {
    try {
      const response = await fetch(API_BASE_URL, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        throw new Error(`Backend error: ${response.status}`);
      }

      const data = await response.json();

      // El backend local devuelve { success, data, meta }
      if (data.success && data.data) {
        return data.data;
      }

      return null;
    } catch (error) {
      console.log('Backend local no disponible, usando fallback...');
      return null;
    }
  }

  private async makeRequest<T>(forceRequest: boolean = false): Promise<ApiResponse<T>> {
    const cacheKey = API_BASE_URL;

    // Siempre intentar usar datos en caché primero si están disponibles
    if (this.hasValidCachedData() && !forceRequest) {
      const cachedData = this.getCachedData<ApiResponse<T>>(cacheKey);
      if (cachedData) {
        return cachedData;
      }
    }

    // Permitir la primera carga de datos siempre, luego aplicar restricción de horario
    const isFirstLoad = !this.hasValidCachedData();
    const shouldFetch = forceRequest || isFirstLoad || this.shouldFetchNewData();

    if (!shouldFetch) {
      // Si no es momento de hacer petición y ya hay caché, usar el caché
      if (this.hasValidCachedData()) {
        const cachedData = this.getCachedData<ApiResponse<T>>(cacheKey);
        if (cachedData) {
          return cachedData;
        }
      }

      // Si no hay caché y no es momento, devolver vacío
      return {
        success: true,
        data: { venues: [], parties: [] } as T,
      };
    }

    try {
      let rawData: any[] | null = null;
      // Intentar backend local solo si está habilitado expresamente
      if (USE_LOCAL_BACKEND) {
        rawData = await this.fetchFromLocalBackend();
      }

      // Si no hay datos del backend local (o está desactivado), USAR FIREBASE como principal
      if (!rawData) {
        console.log('Obteniendo datos desde Firebase Firestore...');
        rawData = await getEventos();
      }

      if (!rawData || rawData.length === 0) {
        throw new Error('No se pudieron obtener datos de Firebase ni del Backend Local');
      }

      // Transformar los datos crudos al formato que la app espera
      const transformedData = transformData(rawData);

      const result: ApiResponse<T> = {
        success: true,
        data: transformedData as any,
      };

      // Cachear la respuesta exitosa
      this.setCachedData(cacheKey, result);

      return result;
    } catch (error) {
      console.error('API Error:', error);

      // Si hay error pero tenemos datos en caché, usarlos silenciosamente
      if (this.hasValidCachedData()) {
        const cachedData = this.getCachedData<ApiResponse<T>>(cacheKey);
        if (cachedData) {
          return cachedData;
        }
      }

      // Si no hay caché, devolver datos vacíos (no error al usuario)
      return {
        success: true,
        data: { venues: [], parties: [] } as T,
      };
    }
  }

  // Obtener datos completos (venues + parties)
  async getCompleteData(): Promise<ApiResponse<{ venues: Venue[], parties: Party[] }>> {
    return this.makeRequest<{ venues: Venue[], parties: Party[] }>();
  }

  // Forzar obtención de datos frescos (solo si es después de las 20:30)
  async getFreshData(): Promise<ApiResponse<{ venues: Venue[], parties: Party[] }>> {
    // Intentar obtener datos frescos, pero si no es momento, usar caché
    return this.makeRequest<{ venues: Venue[], parties: Party[] }>(this.shouldFetchNewData());
  }

  // Suscribirse a actualizaciones en tiempo real vía Firebase
  public subscribeToUpdates(callback: (data: { venues: Venue[], parties: Party[] }) => void): () => void {
    return subscribeToEventos((rawEvents) => {
      // Los datos de Firebase vienen como DocumentData[], necesitamos adaptarlos
      // Si los datos ya vienen en el formato que transformData espera:
      const transformed = transformData(rawEvents);
      callback(transformed);
    });
  }
}

export const apiService = new ApiService(); 