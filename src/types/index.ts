// Tipos para la aplicación PartyFinder Murcia

export interface VenueCategory {
  id: string;
  name: string;
  icon: string;
}

export interface Venue {
  id: string;
  name: string;
  description: string;
  address: string;
  imageUrl: string;
  website: string;
  phone: string;
  isActive: boolean;
  category: VenueCategory;
}

export interface TicketType {
  id: string;
  name: string;
  description?: string;
  price: number;
  isAvailable: boolean;
  isSoldOut: boolean;
  fewLeft?: boolean;
  isPromotion?: boolean;
  isVip?: boolean;
  restrictions?: string;
  purchaseUrl?: string;
}

export interface Party {
  id: string;
  venueId: string;
  venueName: string;
  title: string;
  description: string;
  date: string; // YYYY-MM-DD format
  startTime: string; // HH:MM format
  endTime: string; // HH:MM format
  price: number; // Precio mínimo para mostrar en la lista
  imageUrl: string;
  ticketUrl?: string;
  isAvailable: boolean;
  fewLeft?: boolean;
  capacity?: number;
  soldTickets?: number;
  tags: string[];
  venueAddress?: string;
  ticketTypes?: TicketType[];
  // Nuevos campos
  ageMinimum?: number;
  dressCode?: string;
  latitude?: number;
  longitude?: number;
}

export interface TicketPurchase {
  partyId: string;
  quantity: number;
  totalPrice: number;
  purchaseDate: string;
  ticketUrl: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: string;
} 