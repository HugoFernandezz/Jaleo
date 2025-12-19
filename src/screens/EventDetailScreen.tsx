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
import { RootStackParamList } from '../components/Navigation';
import { RouteProp } from '@react-navigation/native';
import { StackNavigationProp } from '@react-navigation/stack';
import { useTheme } from '../context/ThemeContext';

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
  const { colors, isDark } = useTheme();

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
          { backgroundColor: colors.surface, borderColor: colors.border },
          isSoldOut && styles.ticketCardSoldOut
        ]}
      >
        <View style={styles.ticketContent}>
          {/* Nombre y badges */}
          <View style={styles.ticketHeader}>
            <Text
              style={[
                styles.ticketName,
                { color: colors.text },
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
            <Text style={[styles.ticketDescription, { color: colors.textSecondary }]} numberOfLines={2}>
              {ticket.description}
            </Text>
          ) : null}

          {/* Precio y botón */}
          <View style={styles.ticketFooter}>
            <View style={styles.priceContainer}>
              <Text style={[
                styles.ticketPrice,
                { color: colors.text },
                isSoldOut && styles.ticketPriceSoldOut
              ]}>
                {isSoldOut ? 'Agotado' : (ticket.price === 0 ? 'Gratis' : `${ticket.price}€`)}
              </Text>
            </View>

            {!isSoldOut && (
              <TouchableOpacity
                style={[
                  styles.buyButton,
                  { backgroundColor: colors.primary },
                  hasFewLeft && styles.buyButtonFewLeft
                ]}
                onPress={() => handleBuyTicket(ticket)}
              >
                <Text style={[styles.buyButtonText, { color: isDark ? colors.background : colors.surface }]}>Comprar</Text>
                <Ionicons name="arrow-forward" size={16} color={isDark ? colors.background : colors.surface} />
              </TouchableOpacity>
            )}
          </View>
        </View>
      </View>
    );
  };

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['bottom']}>
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
            style={[styles.backButton, { backgroundColor: colors.surface }]}
            onPress={() => navigation.goBack()}
          >
            <Ionicons name="chevron-back" size={24} color={colors.text} />
          </TouchableOpacity>

          {/* Gradient overlay logic could be here */}
        </View>

        {/* Contenido */}
        <View style={[styles.content, { backgroundColor: colors.background }]}>
          {/* Título y venue */}
          <View style={styles.titleSection}>
            <Text style={[styles.title, { color: colors.text }]}>{party.title}</Text>
            <Text style={[styles.venue, { color: colors.textSecondary }]}>{party.venueName}</Text>
          </View>

          {/* Info cards */}
          <View style={styles.infoCards}>
            {/* Fecha */}
            <View style={[styles.infoCard, { backgroundColor: colors.surface }]}>
              <View style={[styles.infoIconContainer, { backgroundColor: colors.background }]}>
                <Ionicons name="calendar-outline" size={20} color={colors.textSecondary} />
              </View>
              <View style={styles.infoContent}>
                <Text style={styles.infoLabel}>Fecha</Text>
                <Text style={[styles.infoValue, { color: colors.text }]}>{formatDate(party.date)}</Text>
              </View>
            </View>

            {/* Hora */}
            <View style={[styles.infoCard, { backgroundColor: colors.surface }]}>
              <View style={[styles.infoIconContainer, { backgroundColor: colors.background }]}>
                <Ionicons name="time-outline" size={20} color={colors.textSecondary} />
              </View>
              <View style={styles.infoContent}>
                <Text style={styles.infoLabel}>Horario</Text>
                <Text style={[styles.infoValue, { color: colors.text }]}>
                  {party.startTime} - {party.endTime}
                </Text>
              </View>
            </View>

            {/* Edad y vestimenta */}
            <View style={styles.infoRow}>
              {party.ageMinimum && (
                <View style={[styles.infoCard, styles.infoCardHalf, { backgroundColor: colors.surface }]}>
                  <View style={[styles.infoIconContainer, { backgroundColor: colors.background }]}>
                    <Ionicons name="person-outline" size={20} color={colors.textSecondary} />
                  </View>
                  <View style={styles.infoContent}>
                    <Text style={styles.infoLabel}>Edad</Text>
                    <Text style={[styles.infoValue, { color: colors.text }]}>+{party.ageMinimum}</Text>
                  </View>
                </View>
              )}

              {party.dressCode && (
                <View style={[styles.infoCard, styles.infoCardHalf, { backgroundColor: colors.surface }]}>
                  <View style={[styles.infoIconContainer, { backgroundColor: colors.background }]}>
                    <Ionicons name="shirt-outline" size={20} color={colors.textSecondary} />
                  </View>
                  <View style={styles.infoContent}>
                    <Text style={styles.infoLabel}>Vestimenta</Text>
                    <Text style={[styles.infoValue, { color: colors.text }]}>{party.dressCode}</Text>
                  </View>
                </View>
              )}
            </View>

            {/* Ubicación */}
            <TouchableOpacity
              style={[styles.infoCard, { backgroundColor: colors.surface }]}
              onPress={handleOpenMaps}
              activeOpacity={0.7}
            >
              <View style={[styles.infoIconContainer, { backgroundColor: colors.background }]}>
                <Ionicons name="location-outline" size={20} color={colors.textSecondary} />
              </View>
              <View style={[styles.infoContent, { flex: 1 }]}>
                <Text style={styles.infoLabel}>Ubicación</Text>
                <Text style={[styles.infoValue, { color: colors.text }]} numberOfLines={2}>
                  {party.venueAddress || party.venueName}
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={20} color={colors.border} />
            </TouchableOpacity>
          </View>

          {/* Sección de entradas */}
          {party.ticketTypes && party.ticketTypes.length > 0 && (
            <View style={styles.ticketsSection}>
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Entradas</Text>
              <Text style={[styles.sectionSubtitle, { color: colors.textSecondary }]}>
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
              <Text style={[styles.sectionTitle, { color: colors.text }]}>Información</Text>
              <Text style={[styles.description, { color: colors.textSecondary }]}>
                {party.description}
              </Text>
            </View>
          )}

          {/* Tags */}
          {party.tags && party.tags.length > 0 && (
            <View style={styles.tagsSection}>
              <View style={styles.tagsContainer}>
                {party.tags.map((tag, index) => (
                  <View key={index} style={[styles.tag, { backgroundColor: colors.surface }]}>
                    <Text style={[styles.tagText, { color: colors.textSecondary }]}>{tag}</Text>
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
  },
  imageContainer: {
    height: 320,
    position: 'relative',
  },
  image: {
    width: '100%',
    height: '100%',
  },
  backButton: {
    position: 'absolute',
    top: 50,
    left: 16,
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2,
    shadowRadius: 8,
    elevation: 5,
  },
  content: {
    flex: 1,
    borderTopLeftRadius: 32,
    borderTopRightRadius: 32,
    marginTop: -32,
    paddingTop: 32,
    paddingHorizontal: 24,
    paddingBottom: 40,
  },
  titleSection: {
    marginBottom: 32,
    alignItems: 'center', // Centrado solicitado
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    lineHeight: 36,
    marginBottom: 8,
    textAlign: 'center',
    letterSpacing: -0.5,
  },
  venue: {
    fontSize: 18,
    fontWeight: '500',
    textAlign: 'center',
  },
  infoCards: {
    marginBottom: 32,
  },
  infoCard: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 20,
    padding: 16,
    marginBottom: 12,
  },
  infoCardHalf: {
    flex: 1,
  },
  infoRow: {
    flexDirection: 'row',
    gap: 12,
  },
  infoIconContainer: {
    width: 40,
    height: 40,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 16,
  },
  infoContent: {
    flex: 1,
  },
  infoLabel: {
    fontSize: 13,
    color: '#9CA3AF',
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 2,
  },
  infoValue: {
    fontSize: 16,
    fontWeight: '700',
    textTransform: 'capitalize',
  },
  ticketsSection: {
    marginBottom: 32,
  },
  sectionTitle: {
    fontSize: 22,
    fontWeight: '800',
    marginBottom: 4,
  },
  sectionSubtitle: {
    fontSize: 14,
    marginBottom: 20,
  },
  ticketsList: {
    gap: 16,
  },
  ticketCard: {
    borderRadius: 24,
    borderWidth: 1,
    overflow: 'hidden',
  },
  ticketCardSoldOut: {
    opacity: 0.6,
  },
  ticketContent: {
    padding: 20,
  },
  ticketHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  ticketName: {
    fontSize: 18,
    fontWeight: '700',
    flex: 1,
    marginRight: 12,
    lineHeight: 24,
  },
  ticketNameSoldOut: {
    opacity: 0.5,
  },
  fewLeftBadge: {
    backgroundColor: '#FEF3C7',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 10,
  },
  fewLeftText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#D97706',
  },
  ticketDescription: {
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 16,
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
    fontSize: 22,
    fontWeight: '800',
  },
  ticketPriceSoldOut: {
    fontSize: 18,
    fontWeight: '600',
  },
  buyButton: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 16,
    gap: 8,
  },
  buyButtonFewLeft: {
    backgroundColor: '#F59E0B',
  },
  buyButtonText: {
    fontSize: 15,
    fontWeight: '700',
  },
  descriptionSection: {
    marginBottom: 32,
  },
  description: {
    fontSize: 15,
    lineHeight: 24,
    marginTop: 12,
  },
  tagsSection: {
    marginBottom: 24,
  },
  tagsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
  },
  tag: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 10,
  },
  tagText: {
    fontSize: 14,
    fontWeight: '600',
  },
});