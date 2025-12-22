import React, { useState, useRef } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Image,
  Dimensions,
  Animated,
  TouchableWithoutFeedback
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Party } from '../types';
import { useTheme } from '../context/ThemeContext';

const { width } = Dimensions.get('window');

interface PartyCardProps {
  party: Party;
  onPress: () => void;
}

export const PartyCard: React.FC<PartyCardProps> = ({ party, onPress }) => {
  const [imageError, setImageError] = useState(false);
  const { colors, isDark } = useTheme();

  // Animation value
  const scaleAnim = useRef(new Animated.Value(1)).current;

  const handlePressIn = () => {
    Animated.spring(scaleAnim, {
      toValue: 0.95,
      useNativeDriver: true,
      speed: 20,
      bounciness: 4,
    }).start();
  };

  const handlePressOut = () => {
    Animated.spring(scaleAnim, {
      toValue: 1,
      useNativeDriver: true,
      speed: 20,
      bounciness: 4,
    }).start();
  };

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

  // Dynamic styles based on theme
  const dynamicStyles = {
    card: {
      backgroundColor: colors.card,
    },
    dateBadge: {
      backgroundColor: colors.surface,
    },
    dateDay: {
      color: colors.text,
    },
    dateMonth: {
      color: colors.textSecondary,
    },
    title: {
      color: colors.text,
    },
    venue: {
      color: colors.textSecondary,
    },
    time: {
      color: colors.textSecondary,
    },
    tag: {
      backgroundColor: isDark ? '#374151' : '#F3F4F6',
    },
    tagText: {
      color: colors.textSecondary,
    },
    priceContainer: {
      backgroundColor: isDark ? '#FFFFFF' : '#1F2937',
    },
    price: {
      color: isDark ? '#1F2937' : '#FFFFFF',
    },
  };

  return (
    <TouchableWithoutFeedback
      onPress={onPress}
      onPressIn={handlePressIn}
      onPressOut={handlePressOut}
    >
      <Animated.View
        style={[
          styles.card,
          dynamicStyles.card,
          { transform: [{ scale: scaleAnim }] }
        ]}
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
          <View style={[styles.dateBadge, dynamicStyles.dateBadge]}>
            <Text style={[styles.dateDay, dynamicStyles.dateDay]}>{day}</Text>
            <Text style={[styles.dateMonth, dynamicStyles.dateMonth]}>{month}</Text>
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
          <Text style={[styles.title, dynamicStyles.title]} numberOfLines={2}>
            {party.title}
          </Text>

          {/* Venue */}
          <View style={styles.venueRow}>
            <Ionicons name="location-outline" size={14} color={colors.textSecondary} />
            <Text style={[styles.venue, dynamicStyles.venue]} numberOfLines={1}>
              {party.venueName}
            </Text>
          </View>

          {/* Hora */}
          <View style={styles.timeRow}>
            <Ionicons name="time-outline" size={14} color={colors.textSecondary} />
            <Text style={[styles.time, dynamicStyles.time]}>
              {party.startTime} - {party.endTime}
            </Text>
          </View>

          {/* Footer con precio y tags */}
          <View style={styles.footer}>
            {/* Tags */}
            <View style={styles.tagsContainer}>
              {party.tags?.slice(0, 2).map((tag, index) => (
                <View key={index} style={[styles.tag, dynamicStyles.tag]}>
                  <Text style={[styles.tagText, dynamicStyles.tagText]}>{tag}</Text>
                </View>
              ))}
            </View>

            {/* Precio */}
            <View style={[
              styles.priceContainer,
              dynamicStyles.priceContainer,
              isSoldOut && styles.priceSoldOut,
              hasFewLeft && styles.priceFewLeft,
            ]}>
              <Text style={[
                styles.price,
                dynamicStyles.price,
                isSoldOut && styles.priceSoldOutText,
              ]}>
                {formatPrice()}
              </Text>
            </View>
          </View>
        </View>
      </Animated.View>
    </TouchableWithoutFeedback>
  );
};

const styles = StyleSheet.create({
  card: {
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
    backgroundColor: '#374151',
  },
  dateBadge: {
    position: 'absolute',
    top: 12,
    left: 12,
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
    lineHeight: 20,
  },
  dateMonth: {
    fontSize: 10,
    fontWeight: '600',
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
    borderRadius: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    marginRight: 6,
  },
  tagText: {
    fontSize: 11,
    fontWeight: '500',
  },
  priceContainer: {
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
    fontSize: 14,
    fontWeight: '600',
  },
  priceSoldOutText: {
    fontSize: 12,
  },
});