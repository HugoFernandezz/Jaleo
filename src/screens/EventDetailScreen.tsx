import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Image,
  TouchableOpacity,
  Linking,
  Dimensions,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Party, TicketType } from '../types';

const { width } = Dimensions.get('window');

interface EventDetailScreenProps {
  route: {
    params: {
      party: Party;
    };
  };
  navigation: any;
}

export const EventDetailScreen: React.FC<EventDetailScreenProps> = ({ route, navigation }) => {
  const { party } = route.params;
  const [imageError, setImageError] = useState(false);

  // Formatear fecha
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('es-ES', {
      weekday: 'long',
      day: 'numeric',
      month: 'long'
    });
  };

  // Abrir URL de compra
  const handleBuyTicket = (ticket: TicketType) => {
    if (ticket.purchaseUrl) {
      Linking.openURL(ticket.purchaseUrl);
    } else if (party.ticketUrl) {
      Linking.openURL(party.ticketUrl);
    }
  };

  // Abrir ubicación en mapas
  const handleOpenMaps = () => {
    if (party.latitude && party.longitude) {
      const url = `https://www.google.com/maps/search/?api=1&query=${party.latitude},${party.longitude}`;
      Linking.openURL(url);
    } else if (party.venueAddress) {
      const url = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(party.venueAddress)}`;
      Linking.openURL(url);
    }
  };

  // Renderizar cada entrada
  const renderTicket = (ticket: TicketType, index: number) => {
    const isSoldOut = ticket.isSoldOut || !ticket.isAvailable;
    const hasFewLeft = ticket.fewLeft && !isSoldOut;
    
    return (
      <View 
        key={ticket.id || index} 
        style={[
          styles.ticketCard,
          isSoldOut && styles.ticketCardSoldOut
        ]}
      >
        <View style={styles.ticketContent}>
          {/* Nombre y badges */}
          <View style={styles.ticketHeader}>
            <Text 
              style={[
                styles.ticketName, 
                isSoldOut && styles.ticketNameSoldOut
              ]} 
              numberOfLines={2}
            >
              {ticket.name}
            </Text>
            
            {hasFewLeft && (
              <View style={styles.fewLeftBadge}>
                <Text style={styles.fewLeftText}>Últimas</Text>
              </View>
            )}
          </View>

          {/* Descripción si existe */}
          {ticket.description ? (
            <Text style={styles.ticketDescription} numberOfLines={2}>
              {ticket.description}
            </Text>
          ) : null}

          {/* Precio y botón */}
          <View style={styles.ticketFooter}>
            <View style={styles.priceContainer}>
              <Text style={[
                styles.ticketPrice,
                isSoldOut && styles.ticketPriceSoldOut
              ]}>
                {isSoldOut ? 'Agotado' : (ticket.price === 0 ? 'Gratis' : `${ticket.price}€`)}
              </Text>
            </View>

            {!isSoldOut && (
              <TouchableOpacity 
                style={[
                  styles.buyButton,
                  hasFewLeft && styles.buyButtonFewLeft
                ]}
                onPress={() => handleBuyTicket(ticket)}
              >
                <Text style={styles.buyButtonText}>Comprar</Text>
                <Ionicons name="arrow-forward" size={16} color="#FFFFFF" />
              </TouchableOpacity>
            )}
          </View>
        </View>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <ScrollView 
        showsVerticalScrollIndicator={false}
        bounces={false}
      >
        {/* Imagen del evento */}
        <View style={styles.imageContainer}>
          <Image
            source={
              imageError 
                ? require('../../assets/icon.png')
                : { uri: party.imageUrl }
            }
            style={styles.image}
            onError={() => setImageError(true)}
          />
          
          {/* Botón volver */}
          <TouchableOpacity 
            style={styles.backButton}
            onPress={() => navigation.goBack()}
          >
            <Ionicons name="chevron-back" size={24} color="#1F2937" />
          </TouchableOpacity>

          {/* Gradient overlay */}
          <View style={styles.imageGradient} />
        </View>

        {/* Contenido */}
        <View style={styles.content}>
          {/* Título y venue */}
          <View style={styles.titleSection}>
            <Text style={styles.title}>{party.title}</Text>
            <Text style={styles.venue}>{party.venueName}</Text>
          </View>

          {/* Info cards */}
          <View style={styles.infoCards}>
            {/* Fecha */}
            <View style={styles.infoCard}>
              <View style={styles.infoIconContainer}>
                <Ionicons name="calendar-outline" size={20} color="#6B7280" />
              </View>
              <View style={styles.infoContent}>
                <Text style={styles.infoLabel}>Fecha</Text>
                <Text style={styles.infoValue}>{formatDate(party.date)}</Text>
              </View>
            </View>

            {/* Hora */}
            <View style={styles.infoCard}>
              <View style={styles.infoIconContainer}>
                <Ionicons name="time-outline" size={20} color="#6B7280" />
              </View>
              <View style={styles.infoContent}>
                <Text style={styles.infoLabel}>Horario</Text>
                <Text style={styles.infoValue}>
                  {party.startTime} - {party.endTime}
                </Text>
              </View>
            </View>

            {/* Edad y vestimenta */}
            <View style={styles.infoRow}>
              {party.ageMinimum && (
                <View style={[styles.infoCard, styles.infoCardHalf]}>
                  <View style={styles.infoIconContainer}>
                    <Ionicons name="person-outline" size={20} color="#6B7280" />
                  </View>
                  <View style={styles.infoContent}>
                    <Text style={styles.infoLabel}>Edad</Text>
                    <Text style={styles.infoValue}>+{party.ageMinimum}</Text>
                  </View>
                </View>
              )}

              {party.dressCode && (
                <View style={[styles.infoCard, styles.infoCardHalf]}>
                  <View style={styles.infoIconContainer}>
                    <Ionicons name="shirt-outline" size={20} color="#6B7280" />
                  </View>
                  <View style={styles.infoContent}>
                    <Text style={styles.infoLabel}>Vestimenta</Text>
                    <Text style={styles.infoValue}>{party.dressCode}</Text>
                  </View>
                </View>
              )}
            </View>

            {/* Ubicación */}
            <TouchableOpacity 
              style={styles.infoCard}
              onPress={handleOpenMaps}
              activeOpacity={0.7}
            >
              <View style={styles.infoIconContainer}>
                <Ionicons name="location-outline" size={20} color="#6B7280" />
              </View>
              <View style={[styles.infoContent, { flex: 1 }]}>
                <Text style={styles.infoLabel}>Ubicación</Text>
                <Text style={styles.infoValue} numberOfLines={2}>
                  {party.venueAddress || party.venueName}
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={20} color="#D1D5DB" />
            </TouchableOpacity>
          </View>

          {/* Sección de entradas */}
          {party.ticketTypes && party.ticketTypes.length > 0 && (
            <View style={styles.ticketsSection}>
              <Text style={styles.sectionTitle}>Entradas</Text>
              <Text style={styles.sectionSubtitle}>
                {party.ticketTypes.filter(t => t.isAvailable).length} tipos disponibles
              </Text>

              <View style={styles.ticketsList}>
                {party.ticketTypes.map((ticket, index) => renderTicket(ticket, index))}
              </View>
            </View>
          )}

          {/* Descripción */}
          {party.description && (
            <View style={styles.descriptionSection}>
              <Text style={styles.sectionTitle}>Información</Text>
              <Text style={styles.description}>
                {party.description}
              </Text>
            </View>
          )}

          {/* Tags */}
          {party.tags && party.tags.length > 0 && (
            <View style={styles.tagsSection}>
              <View style={styles.tagsContainer}>
                {party.tags.map((tag, index) => (
                  <View key={index} style={styles.tag}>
                    <Text style={styles.tagText}>{tag}</Text>
                  </View>
                ))}
              </View>
            </View>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  imageContainer: {
    height: 280,
    position: 'relative',
  },
  image: {
    width: '100%',
    height: '100%',
    backgroundColor: '#F3F4F6',
  },
  backButton: {
    position: 'absolute',
    top: 50,
    left: 16,
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#FFFFFF',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  imageGradient: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    height: 100,
    backgroundColor: 'transparent',
  },
  content: {
    flex: 1,
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    marginTop: -24,
    paddingTop: 24,
    paddingHorizontal: 20,
    paddingBottom: 40,
  },
  titleSection: {
    marginBottom: 24,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    color: '#1F2937',
    lineHeight: 30,
    marginBottom: 4,
  },
  venue: {
    fontSize: 15,
    color: '#6B7280',
  },
  infoCards: {
    marginBottom: 32,
  },
  infoCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F9FAFB',
    borderRadius: 12,
    padding: 14,
    marginBottom: 8,
  },
  infoCardHalf: {
    flex: 1,
  },
  infoRow: {
    flexDirection: 'row',
    gap: 8,
  },
  infoIconContainer: {
    width: 36,
    height: 36,
    borderRadius: 10,
    backgroundColor: '#FFFFFF',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  infoContent: {
    flex: 1,
  },
  infoLabel: {
    fontSize: 12,
    color: '#9CA3AF',
    marginBottom: 2,
  },
  infoValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#1F2937',
    textTransform: 'capitalize',
  },
  ticketsSection: {
    marginBottom: 32,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#1F2937',
    marginBottom: 4,
  },
  sectionSubtitle: {
    fontSize: 13,
    color: '#9CA3AF',
    marginBottom: 16,
  },
  ticketsList: {
    gap: 12,
  },
  ticketCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: '#E5E7EB',
    overflow: 'hidden',
  },
  ticketCardSoldOut: {
    backgroundColor: '#F9FAFB',
    borderColor: '#E5E7EB',
  },
  ticketContent: {
    padding: 16,
  },
  ticketHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  ticketName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1F2937',
    flex: 1,
    marginRight: 8,
  },
  ticketNameSoldOut: {
    color: '#9CA3AF',
  },
  fewLeftBadge: {
    backgroundColor: '#FEF3C7',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  fewLeftText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#D97706',
  },
  ticketDescription: {
    fontSize: 13,
    color: '#6B7280',
    lineHeight: 18,
    marginBottom: 12,
  },
  ticketFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  priceContainer: {
    flex: 1,
  },
  ticketPrice: {
    fontSize: 20,
    fontWeight: '700',
    color: '#1F2937',
  },
  ticketPriceSoldOut: {
    fontSize: 16,
    color: '#9CA3AF',
    fontWeight: '500',
  },
  buyButton: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1F2937',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 10,
    gap: 6,
  },
  buyButtonFewLeft: {
    backgroundColor: '#F59E0B',
  },
  buyButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  descriptionSection: {
    marginBottom: 24,
  },
  description: {
    fontSize: 14,
    color: '#6B7280',
    lineHeight: 22,
    marginTop: 12,
  },
  tagsSection: {
    marginBottom: 16,
  },
  tagsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  tag: {
    backgroundColor: '#F3F4F6',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  tagText: {
    fontSize: 13,
    color: '#6B7280',
    fontWeight: '500',
  },
});
