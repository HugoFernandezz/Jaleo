import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Image,
  TouchableOpacity,
  Linking,
  Dimensions,
  Animated,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Party, TicketType } from '../types';
import { RootStackParamList } from '../components/Navigation';
import { RouteProp } from '@react-navigation/native';
import { StackNavigationProp } from '@react-navigation/stack';
import { useTheme } from '../context/ThemeContext';

const { width, height } = Dimensions.get('window');
const HEADER_HEIGHT = 400; // Increased for parallax effect

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
  const scrollY = useRef(new Animated.Value(0)).current;
  
  const Container = Platform.OS === 'web' ? View : SafeAreaView;
  const containerProps = Platform.OS === 'web' 
    ? { style: [styles.container, styles.containerWeb, { backgroundColor: colors.background }] }
    : { style: [styles.container, { backgroundColor: colors.background }] };

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

    // Animation value for bounce effect
    const scaleAnim = React.useRef(new Animated.Value(1)).current;

    const handlePressIn = () => {
      Animated.spring(scaleAnim, {
        toValue: 0.95,
        useNativeDriver: true,
        speed: 50,
        bounciness: 4,
      }).start();
    };

    const handlePressOut = () => {
      Animated.spring(scaleAnim, {
        toValue: 1,
        useNativeDriver: true,
        speed: 8,
        bounciness: 12,
      }).start();
    };

    const handlePress = () => {
      if (!isSoldOut) {
        handleBuyTicket(ticket);
      }
    };

    return (
      <Animated.View
        key={ticket.id || index}
        style={[
          { transform: [{ scale: scaleAnim }] }
        ]}
      >
        <TouchableOpacity
          onPress={handlePress}
          onPressIn={handlePressIn}
          onPressOut={handlePressOut}
          activeOpacity={1}
          disabled={isSoldOut}
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

            {/* Precio y chevron indicator */}
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
                <View style={[styles.ticketChevron, { backgroundColor: isDark ? '#374151' : '#F3F4F6' }]}>
                  <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
                </View>
              )}
            </View>
          </View>
        </TouchableOpacity>
      </Animated.View>
    );
  };

  return (
    <Container {...containerProps}>
      {/* Header Image - Fixed */}
      <View style={styles.imageContainer}>
        <Image
          source={
            imageError
              ? require('../../assets/icon.png')
              : { uri: party.imageUrl }
          }
          style={styles.image}
          onError={() => setImageError(true)}
          resizeMode="cover"
        />
      </View>

      {/* Back button - fixed position */}
      <TouchableOpacity
        style={[styles.backButton, { backgroundColor: colors.surface }]}
        onPress={() => navigation.goBack()}
      >
        <Ionicons name="chevron-back" size={24} color={colors.text} />
      </TouchableOpacity>

      {/* Scrollable Content */}
      <Animated.ScrollView
        showsVerticalScrollIndicator={false}
        bounces={true}
        scrollEventThrottle={16}
        contentContainerStyle={{ paddingTop: HEADER_HEIGHT - 32 }}
        style={Platform.OS === 'web' ? styles.scrollViewWeb : undefined}
      >

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
      </Animated.ScrollView>
    </Container>
  );
};


const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  containerWeb: {
    height: '100vh',
    width: '100%',
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    overflow: 'hidden',
  },
  scrollViewWeb: {
    flex: 1,
    height: '100%',
    width: '100%',
    WebkitOverflowScrolling: 'touch' as any,
  },
  imageContainer: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: HEADER_HEIGHT,
    overflow: 'hidden',
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
    zIndex: 10,
  },
  content: {
    borderTopLeftRadius: 32,
    borderTopRightRadius: 32,
    paddingTop: 32,
    paddingHorizontal: 24,
    paddingBottom: 40,
    minHeight: height - HEADER_HEIGHT + 100,
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
  ticketChevron: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
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