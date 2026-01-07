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
  Modal,
  TouchableWithoutFeedback,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Party, TicketType } from '../types';
import { RootStackParamList } from '../components/Navigation';
import { RouteProp } from '@react-navigation/native';
import { StackNavigationProp } from '@react-navigation/stack';
import { useTheme } from '../context/ThemeContext';
import { addEventToCalendar, shareEvent, openVenueInMaps } from '../services/nativeFeatures';

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
  const [showCalendarConfirm, setShowCalendarConfirm] = useState(false);
  const { colors, isDark } = useTheme();
  const scrollY = useRef(new Animated.Value(0)).current;
  
  const Container = Platform.OS === 'web' ? View : SafeAreaView;
  const containerProps = Platform.OS === 'web' 
    ? { style: [styles.container, styles.containerWeb, { backgroundColor: colors.background }] }
    : { style: [styles.container, { backgroundColor: colors.background }] };

  // Función helper para parsear fecha sin problemas de zona horaria
  const parseLocalDate = (dateStr: string): Date => {
    // Parsear YYYY-MM-DD manualmente para evitar problemas de zona horaria
    const [year, month, day] = dateStr.split('-').map(Number);
    // new Date(year, monthIndex, day) crea la fecha en hora local
    return new Date(year, month - 1, day);
  };

  // Formatear fecha
  const formatDate = (dateString: string) => {
    const date = parseLocalDate(dateString);
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

  // Abrir ubicación en mapas usando el servicio nativo
  const handleOpenMaps = () => {
    openVenueInMaps(party);
  };

  // Mostrar confirmación antes de agregar al calendario
  const handleAddToCalendar = () => {
    setShowCalendarConfirm(true);
  };

  // Confirmar y agregar al calendario
  const handleConfirmAddToCalendar = async () => {
    setShowCalendarConfirm(false);
    await addEventToCalendar(party);
  };

  // Compartir evento
  const handleShareEvent = async () => {
    await shareEvent(party);
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
      {/* Header Image - Se oculta al hacer scroll */}
      <Animated.View 
        style={[
          styles.imageContainer,
          {
            transform: [
              {
                translateY: scrollY.interpolate({
                  inputRange: [0, HEADER_HEIGHT],
                  outputRange: [0, -HEADER_HEIGHT],
                  extrapolate: 'clamp',
                }),
              },
            ],
            opacity: scrollY.interpolate({
              inputRange: [0, HEADER_HEIGHT * 0.5, HEADER_HEIGHT],
              outputRange: [1, 0.3, 0],
              extrapolate: 'clamp',
            }),
          },
        ]}
      >
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
      </Animated.View>

      {/* Back button - fixed position */}
      <TouchableOpacity
        style={[styles.backButton, { backgroundColor: colors.surface }]}
        onPress={() => navigation.goBack()}
      >
        <Ionicons name="chevron-back" size={24} color={colors.text} />
      </TouchableOpacity>

      {/* Action buttons - fixed position */}
      <View style={styles.actionButtons}>
        <TouchableOpacity
          style={[styles.actionButton, { backgroundColor: colors.surface }]}
          onPress={handleAddToCalendar}
          activeOpacity={0.7}
        >
          <Ionicons name="calendar" size={22} color={colors.primary} />
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.actionButton, { backgroundColor: colors.surface }]}
          onPress={handleShareEvent}
          activeOpacity={0.7}
        >
          <Ionicons name="share-outline" size={22} color={colors.primary} />
        </TouchableOpacity>
      </View>

      {/* Scrollable Content */}
      <Animated.ScrollView
        showsVerticalScrollIndicator={false}
        bounces={true}
        scrollEventThrottle={16}
        onScroll={Animated.event(
          [{ nativeEvent: { contentOffset: { y: scrollY } } }],
          { useNativeDriver: false }
        )}
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

              <View style={styles.ticketsList}>
                {[...party.ticketTypes]
                  .sort((a, b) => a.price - b.price)
                  .map((ticket, index) => renderTicket(ticket, index))}
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

      {/* Calendar Confirmation Modal */}
      <Modal
        visible={showCalendarConfirm}
        transparent={true}
        animationType="fade"
        onRequestClose={() => setShowCalendarConfirm(false)}
      >
        <TouchableWithoutFeedback onPress={() => setShowCalendarConfirm(false)}>
          <View style={styles.modalOverlay}>
            <TouchableWithoutFeedback>
              <View style={[styles.confirmModal, { backgroundColor: colors.surface }]}>
                {/* Icon */}
                <View style={[styles.confirmIconContainer, { backgroundColor: colors.background }]}>
                  <Ionicons name="calendar" size={32} color={colors.primary} />
                </View>

                {/* Title */}
                <Text style={[styles.confirmTitle, { color: colors.text }]}>
                  Agregar al calendario
                </Text>

                {/* Message */}
                <Text style={[styles.confirmMessage, { color: colors.textSecondary }]}>
                  ¿Quieres guardar "{party.title}" en tu calendario?
                </Text>

                {/* Event Info Preview */}
                <View style={[styles.eventPreview, { backgroundColor: colors.background, borderColor: colors.border }]}>
                  <View style={styles.eventPreviewRow}>
                    <Ionicons name="location-outline" size={16} color={colors.textSecondary} />
                    <Text style={[styles.eventPreviewText, { color: colors.textSecondary }]} numberOfLines={1}>
                      {party.venueName}
                    </Text>
                  </View>
                  <View style={styles.eventPreviewRow}>
                    <Ionicons name="time-outline" size={16} color={colors.textSecondary} />
                    <Text style={[styles.eventPreviewText, { color: colors.textSecondary }]}>
                      {formatDate(party.date)} • {party.startTime} - {party.endTime}
                    </Text>
                  </View>
                </View>

                {/* Actions */}
                <View style={styles.confirmActions}>
                  <TouchableOpacity
                    style={[styles.confirmCancelButton, { borderColor: colors.border }]}
                    onPress={() => setShowCalendarConfirm(false)}
                    activeOpacity={0.7}
                  >
                    <Text style={[styles.confirmCancelText, { color: colors.text }]}>
                      Cancelar
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.confirmSaveButton, { backgroundColor: colors.primary }]}
                    onPress={handleConfirmAddToCalendar}
                    activeOpacity={0.8}
                  >
                    <Ionicons name="checkmark" size={20} color={isDark ? colors.background : colors.surface} />
                    <Text style={[styles.confirmSaveText, { color: isDark ? colors.background : colors.surface }]}>
                      Guardar
                    </Text>
                  </TouchableOpacity>
                </View>
              </View>
            </TouchableWithoutFeedback>
          </View>
        </TouchableWithoutFeedback>
      </Modal>
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
  actionButtons: {
    position: 'absolute',
    top: 50,
    right: 16,
    flexDirection: 'row',
    gap: 12,
    zIndex: 10,
  },
  actionButton: {
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
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  confirmModal: {
    borderRadius: 24,
    padding: 24,
    width: '100%',
    maxWidth: 400,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.3,
    shadowRadius: 16,
    elevation: 10,
  },
  confirmIconContainer: {
    width: 64,
    height: 64,
    borderRadius: 32,
    justifyContent: 'center',
    alignItems: 'center',
    alignSelf: 'center',
    marginBottom: 16,
  },
  confirmTitle: {
    fontSize: 22,
    fontWeight: '800',
    textAlign: 'center',
    marginBottom: 8,
  },
  confirmMessage: {
    fontSize: 16,
    textAlign: 'center',
    lineHeight: 24,
    marginBottom: 20,
  },
  eventPreview: {
    borderRadius: 16,
    padding: 16,
    marginBottom: 24,
    borderWidth: 1,
  },
  eventPreviewRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    gap: 8,
  },
  eventPreviewText: {
    fontSize: 14,
    flex: 1,
  },
  confirmActions: {
    flexDirection: 'row',
    gap: 12,
  },
  confirmCancelButton: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 12,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  confirmCancelText: {
    fontSize: 16,
    fontWeight: '600',
  },
  confirmSaveButton: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  confirmSaveText: {
    fontSize: 16,
    fontWeight: '700',
  },
});