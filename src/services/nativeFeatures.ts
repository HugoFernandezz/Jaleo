import * as Calendar from 'expo-calendar';
import { Platform, Share, Alert, Linking } from 'react-native';
import { Party } from '../types';

// Mapeo de venues a códigos de Apple Maps para usar con maps://
// Estos códigos vienen de las URLs de compartir de Apple Maps
const VENUE_MAPS_CODES: { [key: string]: string } = {
  'Luminata': 'itGZSadpbipJQt',
  'Luminata Disco': 'itGZSadpbipJQt',
  'LUMINATA': 'itGZSadpbipJQt',
  'Dodo Club': 'uk6pni7eVHh88q',
  'DODO CLUB': 'uk6pni7eVHh88q',
  'El Club By Odiseo': '2Z~MV7G82b1TUw',
  'Sala REM': 'sy8EbmP0y9EWm5',
};

// Función helper para parsear fecha sin problemas de zona horaria
const parseLocalDate = (dateStr: string): Date => {
  const [year, month, day] = dateStr.split('-').map(Number);
  return new Date(year, month - 1, day);
};

// Función helper para parsear hora HH:MM a Date
const parseTime = (timeStr: string, baseDate: Date): Date => {
  // Limpiar y parsear la hora (puede venir como "23:00" o "23:00:00")
  const timeParts = timeStr.trim().split(':');
  const hours = parseInt(timeParts[0], 10);
  const minutes = timeParts.length > 1 ? parseInt(timeParts[1], 10) : 0;
  
  const date = new Date(baseDate);
  date.setHours(hours, minutes, 0, 0);
  return date;
};

// Función helper para verificar si una hora es anterior a otra (considerando día siguiente)
const isTimeBefore = (time1: string, time2: string): boolean => {
  const parts1 = time1.split(':').map(Number);
  const parts2 = time2.split(':').map(Number);
  const hours1 = parts1[0];
  const minutes1 = parts1[1] || 0;
  const hours2 = parts2[0];
  const minutes2 = parts2[1] || 0;
  
  // Si la hora1 es mayor que hora2, probablemente hora2 es del día siguiente
  // Ejemplo: 23:00 vs 02:00 -> 02:00 es del día siguiente
  if (hours1 > hours2 || (hours1 === hours2 && minutes1 > minutes2)) {
    return false; // hora2 es del día siguiente
  }
  return true; // hora1 es antes que hora2 en el mismo día
};

/**
 * Agrega un evento al calendario nativo del sistema
 * Nota: Esta función ahora solo agrega el evento. La confirmación debe manejarse en el componente.
 */
export async function addEventToCalendar(party: Party): Promise<boolean> {
  try {
    // Solicitar permisos
    const { status } = await Calendar.requestCalendarPermissionsAsync();
    
    if (status !== 'granted') {
      Alert.alert(
        'Permisos necesarios',
        'Necesitamos acceso a tu calendario para agregar eventos. Por favor, habilita los permisos en Configuración.',
        [{ text: 'OK' }]
      );
      return false;
    }

    // Obtener calendarios disponibles
    const calendars = await Calendar.getCalendarsAsync(Calendar.EntityTypes.EVENT);
    
    // Buscar calendario predeterminado o usar el primero disponible
    let defaultCalendar = calendars.find(cal => cal.allowsModifications);
    
    if (!defaultCalendar) {
      defaultCalendar = calendars[0];
    }

    if (!defaultCalendar) {
      Alert.alert('Error', 'No se encontró ningún calendario disponible.');
      return false;
    }

    // Parsear fecha y hora
    const eventDate = parseLocalDate(party.date);
    const startDate = parseTime(party.startTime, eventDate);
    let endDate = parseTime(party.endTime, eventDate);
    
    // Si la hora de fin es anterior a la hora de inicio, significa que termina al día siguiente
    // Ejemplo: inicio 23:00, fin 02:00 -> termina al día siguiente
    if (!isTimeBefore(party.startTime, party.endTime)) {
      // Agregar un día a la fecha de fin
      endDate = new Date(endDate);
      endDate.setDate(endDate.getDate() + 1);
    }
    
    // Validar que la fecha de inicio sea anterior a la de fin
    if (startDate >= endDate) {
      // Si aún así startDate >= endDate, agregar un día a endDate como fallback
      endDate = new Date(startDate);
      endDate.setHours(endDate.getHours() + 4); // Agregar 4 horas por defecto si hay error
      console.warn(`Ajustando fecha de fin para evento ${party.title}: inicio ${party.startTime}, fin ${party.endTime}`);
    }

    // Crear el evento
    const eventId = await Calendar.createEventAsync(defaultCalendar.id, {
      title: party.title,
      startDate: startDate,
      endDate: endDate,
      location: party.venueAddress || party.venueName,
      notes: `Evento en ${party.venueName}\n\n${party.description || ''}\n\nEntradas desde ${party.price}€${party.ticketUrl ? `\n${party.ticketUrl}` : ''}`,
      url: party.ticketUrl || undefined,
      timeZone: 'Europe/Madrid',
      alarms: [
        {
          relativeOffset: -1440, // Recordatorio 1 día antes (en minutos)
          method: Calendar.AlarmMethod.ALERT,
        },
      ],
    });

    if (eventId) {
      Alert.alert(
        '✅ Evento agregado',
        `"${party.title}" ha sido agregado a tu calendario.`,
        [{ text: 'OK' }]
      );
      return true;
    }

    return false;
  } catch (error: any) {
    console.error('Error adding event to calendar:', error);
    Alert.alert(
      'Error',
      error.message || 'No se pudo agregar el evento al calendario.',
      [{ text: 'OK' }]
    );
    return false;
  }
}

/**
 * Comparte un evento usando el Share Sheet nativo
 */
export async function shareEvent(party: Party): Promise<void> {
  try {
    const formattedDate = parseLocalDate(party.date).toLocaleDateString('es-ES', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
    });

    const priceText = party.price === 0 ? 'Gratis' : `Desde ${party.price}€`;
    const ticketText = party.ticketUrl ? `\n🔗 Entradas: ${party.ticketUrl}` : '';

    const message = `🎉 ${party.title}

📍 ${party.venueName}
📅 ${formattedDate}
🕐 ${party.startTime} - ${party.endTime}
💰 ${priceText}${ticketText}

Descubre más eventos en Jaleo! 🎊`;

    const result = await Share.share({
      message: Platform.OS === 'ios' ? message : message,
      title: party.title,
      url: Platform.OS === 'ios' ? undefined : party.ticketUrl,
    });

    if (result.action === Share.sharedAction) {
      if (result.activityType) {
        // Compartido con una actividad específica (ej: WhatsApp, Email)
        console.log('Shared with activity type:', result.activityType);
      } else {
        // Compartido
        console.log('Event shared successfully');
      }
    } else if (result.action === Share.dismissedAction) {
      // Usuario canceló
      console.log('Share dismissed');
    }
  } catch (error: any) {
    console.error('Error sharing event:', error);
    Alert.alert('Error', 'No se pudo compartir el evento.');
  }
}

/**
 * Abre la ubicación en Apple Maps con la URL específica del venue
 */
export async function openVenueInMaps(party: Party): Promise<void> {
  try {
    if (Platform.OS !== 'ios') {
      // En Android, usar Google Maps
      await openVenueFallback(party);
      return;
    }

    const venueName = party.venueName.trim();
    
    // Buscar código específico del venue (case-insensitive)
    const venueKey = Object.keys(VENUE_MAPS_CODES).find(
      key => key.toLowerCase() === venueName.toLowerCase()
    );

    // Prioridad 1: Si tenemos coordenadas, usarlas (más confiable)
    if (party.latitude && party.longitude) {
      // Intentar con maps:// primero (app nativa)
      const mapsUrl = `maps://maps.apple.com/?ll=${party.latitude},${party.longitude}`;
      try {
        const canOpen = await Linking.canOpenURL(mapsUrl);
        if (canOpen) {
          await Linking.openURL(mapsUrl);
          return;
        }
      } catch (error) {
        console.log('maps:// no disponible, usando http://');
      }
      
      // Fallback a http:// que también debería abrir la app nativa
      const httpUrl = `http://maps.apple.com/?ll=${party.latitude},${party.longitude}`;
      await Linking.openURL(httpUrl);
      return;
    }
    
    // Prioridad 2: Si tenemos código específico del venue, usar el nombre del lugar
    // (Los códigos /p/ no funcionan con maps://, así que usamos el nombre)
    if (venueKey && VENUE_MAPS_CODES[venueKey]) {
      const query = encodeURIComponent(party.venueName);
      
      // Intentar con maps:// usando el nombre del lugar (más confiable)
      const mapsUrl = `maps://maps.apple.com/?q=${query}`;
      try {
        const canOpen = await Linking.canOpenURL(mapsUrl);
        if (canOpen) {
          await Linking.openURL(mapsUrl);
          return;
        }
      } catch (error) {
        console.log('maps:// no disponible, usando http://');
      }
      
      // Fallback a http:// (puede abrir en Safari, pero es mejor que nada)
      const httpUrl = `http://maps.apple.com/?q=${query}`;
      await Linking.openURL(httpUrl);
      return;
    }
    
    // Prioridad 3: Usar dirección o nombre del venue
    if (party.venueAddress || party.venueName) {
      const query = encodeURIComponent(party.venueAddress || party.venueName);
      const mapsUrl = `maps://maps.apple.com/?q=${query}`;
      
      try {
        const canOpen = await Linking.canOpenURL(mapsUrl);
        if (canOpen) {
          await Linking.openURL(mapsUrl);
          return;
        }
      } catch (error) {
        console.log('maps:// con nombre no disponible');
      }
      
      // Fallback a http://
      const httpUrl = `http://maps.apple.com/?q=${query}`;
      await Linking.openURL(httpUrl);
      return;
    }
    
    // Si llegamos aquí, usar fallback genérico
    await openVenueFallback(party);
  } catch (error: any) {
    console.error('Error opening maps:', error);
    Alert.alert('Error', 'No se pudo abrir la ubicación en mapas.');
  }
}

/**
 * Fallback para abrir ubicación cuando no hay URL específica
 */
async function openVenueFallback(party: Party): Promise<void> {
  try {
    if (Platform.OS === 'ios') {
      // En iOS, usar Apple Maps con esquema que abre la app nativa
      if (party.latitude && party.longitude) {
        // Intentar primero con maps:// (app nativa)
        const nativeUrl = `maps://maps.apple.com/?ll=${party.latitude},${party.longitude}`;
        const canOpen = await Linking.canOpenURL(nativeUrl);
        
        if (canOpen) {
          try {
            await Linking.openURL(nativeUrl);
            return;
          } catch (error) {
            console.log('Fallback a http://');
          }
        }
        
        // Fallback a http:// que también abre la app nativa en iOS
        const httpUrl = `http://maps.apple.com/?ll=${party.latitude},${party.longitude}`;
        await Linking.openURL(httpUrl);
      } else if (party.venueAddress) {
        const url = `http://maps.apple.com/?q=${encodeURIComponent(party.venueAddress)}`;
        await Linking.openURL(url);
      } else {
        const url = `http://maps.apple.com/?q=${encodeURIComponent(party.venueName)}`;
        await Linking.openURL(url);
      }
    } else {
      // En Android, usar Google Maps
      if (party.latitude && party.longitude) {
        const url = `https://www.google.com/maps/search/?api=1&query=${party.latitude},${party.longitude}`;
        await Linking.openURL(url);
      } else if (party.venueAddress) {
        const url = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(party.venueAddress)}`;
        await Linking.openURL(url);
      }
    }
  } catch (error) {
    console.error('Error in fallback maps:', error);
    throw error;
  }
}

