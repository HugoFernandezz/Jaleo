import React, { useState } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  Image, 
  TouchableOpacity, 
  Dimensions 
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Party } from '../types';

const { width } = Dimensions.get('window');
const CARD_WIDTH = width - 32;

interface PartyCardProps {
  party: Party;
  onPress: () => void;
}

export const PartyCard: React.FC<PartyCardProps> = ({ party, onPress }) => {
  const [imageError, setImageError] = useState(false);
  
  const isSoldOut = !party.isAvailable;
  const hasFewLeft = party.fewLeft && !isSoldOut;

  // Formatear fecha
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const day = date.getDate();
    const month = date.toLocaleDateString('es-ES', { month: 'short' });
    return { day, month: month.toUpperCase() };
  };

  const { day, month } = formatDate(party.date);

  // Formatear precio
  const formatPrice = () => {
    if (isSoldOut) return 'Agotado';
    if (party.price === 0) return 'Gratis';
    return `${party.price}€`;
  };

  return (
    <TouchableOpacity 
      style={styles.card} 
      onPress={onPress}
      activeOpacity={0.7}
    >
      {/* Imagen con overlay de fecha */}
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
        
        {/* Badge de fecha */}
        <View style={styles.dateBadge}>
          <Text style={styles.dateDay}>{day}</Text>
          <Text style={styles.dateMonth}>{month}</Text>
        </View>

        {/* Overlay de agotado */}
        {isSoldOut && (
          <View style={styles.soldOutOverlay}>
            <Text style={styles.soldOutText}>AGOTADO</Text>
          </View>
        )}

        {/* Indicador de pocas entradas */}
        {hasFewLeft && (
          <View style={styles.fewLeftBadge}>
            <Text style={styles.fewLeftText}>Últimas</Text>
          </View>
        )}
      </View>

      {/* Contenido */}
      <View style={styles.content}>
        {/* Título */}
        <Text style={styles.title} numberOfLines={2}>
          {party.title}
        </Text>

        {/* Venue */}
        <View style={styles.venueRow}>
          <Ionicons name="location-outline" size={14} color="#9CA3AF" />
          <Text style={styles.venue} numberOfLines={1}>
            {party.venueName}
          </Text>
        </View>

        {/* Hora */}
        <View style={styles.timeRow}>
          <Ionicons name="time-outline" size={14} color="#9CA3AF" />
          <Text style={styles.time}>
            {party.startTime} - {party.endTime}
          </Text>
        </View>

        {/* Footer con precio y tags */}
        <View style={styles.footer}>
          {/* Tags */}
          <View style={styles.tagsContainer}>
            {party.tags?.slice(0, 2).map((tag, index) => (
              <View key={index} style={styles.tag}>
                <Text style={styles.tagText}>{tag}</Text>
              </View>
            ))}
          </View>

          {/* Precio */}
          <View style={[
            styles.priceContainer,
            isSoldOut && styles.priceSoldOut,
            hasFewLeft && styles.priceFewLeft,
          ]}>
            <Text style={[
              styles.price,
              isSoldOut && styles.priceSoldOutText,
            ]}>
              {formatPrice()}
            </Text>
          </View>
        </View>
      </View>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    marginHorizontal: 16,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 3,
    overflow: 'hidden',
  },
  imageContainer: {
    position: 'relative',
    height: 160,
  },
  image: {
    width: '100%',
    height: '100%',
    backgroundColor: '#F3F4F6',
  },
  dateBadge: {
    position: 'absolute',
    top: 12,
    left: 12,
    backgroundColor: '#FFFFFF',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  dateDay: {
    fontSize: 18,
    fontWeight: '700',
    color: '#1F2937',
    lineHeight: 20,
  },
  dateMonth: {
    fontSize: 10,
    fontWeight: '600',
    color: '#6B7280',
    letterSpacing: 0.5,
  },
  soldOutOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  soldOutText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
    letterSpacing: 2,
  },
  fewLeftBadge: {
    position: 'absolute',
    top: 12,
    right: 12,
    backgroundColor: '#F59E0B',
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  fewLeftText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '600',
  },
  content: {
    padding: 16,
  },
  title: {
    fontSize: 17,
    fontWeight: '600',
    color: '#1F2937',
    lineHeight: 22,
    marginBottom: 8,
  },
  venueRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  venue: {
    fontSize: 13,
    color: '#6B7280',
    marginLeft: 4,
    flex: 1,
  },
  timeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  time: {
    fontSize: 13,
    color: '#6B7280',
    marginLeft: 4,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  tagsContainer: {
    flexDirection: 'row',
    flex: 1,
  },
  tag: {
    backgroundColor: '#F3F4F6',
    borderRadius: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    marginRight: 6,
  },
  tagText: {
    fontSize: 11,
    color: '#6B7280',
    fontWeight: '500',
  },
  priceContainer: {
    backgroundColor: '#1F2937',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  priceSoldOut: {
    backgroundColor: '#9CA3AF',
  },
  priceFewLeft: {
    backgroundColor: '#F59E0B',
  },
  price: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '600',
  },
  priceSoldOutText: {
    fontSize: 12,
  },
});
