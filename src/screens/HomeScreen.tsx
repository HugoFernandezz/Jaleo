import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Platform,
  Animated,
  Modal,
  TouchableWithoutFeedback,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Calendar, LocaleConfig } from 'react-native-calendars';
import { PartyCard } from '../components/PartyCard';
import { Party } from '../types';
import { apiService } from '../services/api';
import { RootStackParamList } from '../components/Navigation';
import { RouteProp } from '@react-navigation/native';
import { StackNavigationProp } from '@react-navigation/stack';
import { useTheme } from '../context/ThemeContext';

// Configure Spanish locale for calendar
LocaleConfig.locales['es'] = {
  monthNames: ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'],
  monthNamesShort: ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],
  dayNames: ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'],
  dayNamesShort: ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'],
  today: 'Hoy'
};
LocaleConfig.defaultLocale = 'es';

type HomeScreenNavigationProp = StackNavigationProp<RootStackParamList, 'Home'>;

interface HomeScreenProps {
  navigation: HomeScreenNavigationProp;
}

export const HomeScreen: React.FC<HomeScreenProps> = ({ navigation }) => {
  const [parties, setParties] = useState<Party[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedVenue, setSelectedVenue] = useState<string>('Todas');
  const [availableVenues, setAvailableVenues] = useState<string[]>(['Todas']);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [showUpdateToast, setShowUpdateToast] = useState(false);
  const [showCalendar, setShowCalendar] = useState(false);

  const fadeAnim = useMemo(() => new Animated.Value(0), []);

  const triggerUpdateToast = useCallback(() => {
    setShowUpdateToast(true);
    Animated.sequence([
      Animated.timing(fadeAnim, {
        toValue: 1,
        duration: 500,
        useNativeDriver: true,
      }),
      Animated.delay(3000),
      Animated.timing(fadeAnim, {
        toValue: 0,
        duration: 500,
        useNativeDriver: true,
      }),
    ]).start(() => setShowUpdateToast(false));
  }, [fadeAnim]);

  useEffect(() => {
    loadParties();

    // Suscribirse a actualizaciones en tiempo real
    const unsubscribe = apiService.subscribeToUpdates((data) => {
      if (data.parties.length > 0) {
        setParties(data.parties);
        triggerUpdateToast();
      }
    });

    return () => unsubscribe();
  }, []);

  useEffect(() => {
    // Extraer venues únicos con normalización para evitar duplicados (ej: "Dodo Club" vs "DODO CLUB")
    const allVenues = new Map<string, string>();

    parties.forEach(party => {
      if (party.venueName) {
        const rawName = party.venueName.trim();
        const normalizedKey = rawName.toLowerCase();

        if (!allVenues.has(normalizedKey)) {
          allVenues.set(normalizedKey, rawName);
        } else {
          // Si ya existe, preferimos la versión que NO sea todo mayúsculas (Mixed Case)
          const currentName = allVenues.get(normalizedKey)!;
          if (currentName === currentName.toUpperCase() && rawName !== rawName.toUpperCase()) {
            allVenues.set(normalizedKey, rawName);
          }
        }
      }
    });

    setAvailableVenues(['Todas', ...Array.from(allVenues.values()).sort()]);
  }, [parties]);

  const { colors, toggleTheme, isDark } = useTheme();

  // Create marked dates object for calendar (dates with events get a blue dot)
  const markedDates = useMemo(() => {
    const marks: { [key: string]: any } = {};

    // Get all unique dates from parties
    const eventDates = new Set(parties.map(p => p.date));

    eventDates.forEach(date => {
      marks[date] = {
        marked: true,
        dotColor: '#3B82F6', // Blue dot
      };
    });

    // Add selection styling if a date is selected
    if (selectedDate) {
      marks[selectedDate] = {
        ...marks[selectedDate],
        selected: true,
        selectedColor: colors.primary,
      };
    }

    return marks;
  }, [parties, selectedDate, colors.primary]);

  // Filtrar y agrupar eventos
  const filteredParties = useMemo(() => {
    let filtered = parties;

    if (selectedVenue !== 'Todas') {
      filtered = filtered.filter(party => party.venueName.trim().toLowerCase() === selectedVenue.toLowerCase());
    }

    // Filtrar por fecha seleccionada (si hay una)
    if (selectedDate) {
      filtered = filtered.filter(party => party.date === selectedDate);
    } else {
      // Si no hay fecha seleccionada ("Todas"), mostrar solo eventos futuros (hoy en adelante)
      const today = new Date().toISOString().split('T')[0];
      filtered = filtered.filter(party => party.date >= today);
    }

    // Ordenar: Si es "Todas", por fecha. Si es un día específico, por título/hora.
    return filtered.sort((a, b) => {
      if (!selectedDate) {
        // Ordenar por fecha asc
        return new Date(a.date).getTime() - new Date(b.date).getTime();
      }
      return a.title.localeCompare(b.title);
    });
  }, [parties, selectedVenue, selectedDate]);

  const loadParties = async () => {
    try {
      setLoading(true);
      const response = await apiService.getCompleteData();
      if (response.success) {
        setParties(response.data.parties);
      }
    } catch (error) {
      console.error('Error loading parties:', error);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    apiService.clearCache();
    await loadParties();
    setRefreshing(false);
  }, []);

  const handlePartyPress = useCallback((party: Party) => {
    navigation.navigate('EventDetail', { party });
  }, [navigation]);

  const formatSectionDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const options: Intl.DateTimeFormatOptions = {
      weekday: 'long',
      day: 'numeric',
      month: 'long'
    };
    return date.toLocaleDateString('es-ES', options);
  };

  const renderItem = ({ item, index }: { item: Party; index: number }) => {
    const previousItem = index > 0 ? filteredParties[index - 1] : null;
    const showDateSeparator = !selectedDate && previousItem && previousItem.date !== item.date;

    return (
      <View>
        {showDateSeparator && (
          <View style={[styles.dateSeparator, { borderTopColor: colors.border }]}>
            <Text style={[styles.dateSeparatorText, { color: colors.textSecondary }]}>
              {formatSectionDate(item.date)}
            </Text>
          </View>
        )}
        <PartyCard
          party={item}
          onPress={() => handlePartyPress(item)}
        />
      </View>
    );
  };

  const renderHeader = () => (
    <View style={[styles.header, { backgroundColor: colors.background }]}>
      {/* Título con iconos */}
      <View style={styles.topHeader}>
        {/* Calendar icon button (left) */}
        <TouchableOpacity
          style={[styles.headerButton, { backgroundColor: colors.surface, borderColor: colors.border }]}
          onPress={() => setShowCalendar(true)}
        >
          <Ionicons name="calendar-outline" size={20} color={colors.text} />
          {selectedDate && (
            <View style={styles.calendarBadge}>
              <Text style={styles.calendarBadgeText}>
                {new Date(selectedDate).getDate()}
              </Text>
            </View>
          )}
        </TouchableOpacity>

        {/* Title */}
        <View style={styles.titleContainer}>
          <Text style={[styles.title, { color: colors.text }]}>Eventos</Text>
          <Text style={styles.subtitle}>Murcia</Text>
        </View>

        {/* Theme toggle (right) */}
        <TouchableOpacity
          style={[styles.headerButton, { backgroundColor: colors.surface, borderColor: colors.border }]}
          onPress={toggleTheme}
        >
          <Ionicons name={isDark ? "sunny-outline" : "moon-outline"} size={20} color={colors.text} />
        </TouchableOpacity>
      </View>

      {/* Selected date chip (if date selected) */}
      {selectedDate && (
        <TouchableOpacity
          style={[styles.selectedDateChip, { backgroundColor: colors.primary }]}
          onPress={() => setSelectedDate(null)}
        >
          <Text style={[styles.selectedDateText, { color: isDark ? colors.background : colors.surface }]}>
            {formatSectionDate(selectedDate)}
          </Text>
          <Ionicons name="close-circle" size={18} color={isDark ? colors.background : colors.surface} />
        </TouchableOpacity>
      )}

      {/* Filtro de venues */}
      <View style={styles.filterContainer}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterScroll}
        >
          {availableVenues.map((venue) => (
            <TouchableOpacity
              key={venue}
              style={[
                styles.filterChip,
                { backgroundColor: colors.surface, borderColor: colors.border },
                selectedVenue === venue && { backgroundColor: colors.primary, borderColor: colors.primary }
              ]}
              onPress={() => setSelectedVenue(venue)}
            >
              <Text style={[
                styles.filterText,
                { color: colors.textSecondary },
                selectedVenue === venue && { color: isDark ? colors.background : colors.surface }
              ]}>
                {venue}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      {/* Indicador de sección */}
      {filteredParties.length > 0 && (
        <View style={styles.selectionIndicator}>
          <Text style={[styles.sectionDate, { color: colors.text }]}>
            {selectedDate ? formatSectionDate(selectedDate) : 'Próximos Eventos'}
          </Text>
          <Text style={[styles.sectionCount, { color: colors.textSecondary }]}>
            {filteredParties.length} {filteredParties.length === 1 ? 'evento' : 'eventos'}
          </Text>
        </View>
      )}
    </View>
  );

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <View style={[styles.emptyIcon, { backgroundColor: colors.surface }]}>
        <Ionicons name="calendar-outline" size={48} color={colors.border} />
      </View>
      <Text style={[styles.emptyTitle, { color: colors.text }]}>No hay eventos</Text>
      <Text style={[styles.emptySubtitle, { color: colors.textSecondary }]}>
        {selectedVenue !== 'Todas'
          ? `No hay eventos en ${selectedVenue} para este día`
          : 'No hay eventos programados para este día'
        }
      </Text>
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={[styles.loadingText, { color: colors.textSecondary }]}>Cargando eventos...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]} edges={['top']}>
      <FlatList
        data={filteredParties}
        renderItem={renderItem}
        keyExtractor={(item) => item.id}
        ListHeaderComponent={renderHeader}
        ListEmptyComponent={renderEmpty}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[
          styles.listContent,
          filteredParties.length === 0 && styles.listContentEmpty
        ]}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={colors.primary}
          />
        }
      />


      {/* Toast de Actualización (Debug Temporal) */}
      {showUpdateToast && (
        <Animated.View
          style={[
            styles.updateToast,
            { opacity: fadeAnim }
          ]}
        >
          <Ionicons name="cloud-download-outline" size={20} color="#FFFFFF" />
          <Text style={styles.updateToastText}>Base de datos actualizada</Text>
        </Animated.View>
      )}

      {/* Calendar Modal */}
      <Modal
        visible={showCalendar}
        transparent={true}
        animationType="fade"
        onRequestClose={() => setShowCalendar(false)}
      >
        <TouchableWithoutFeedback onPress={() => setShowCalendar(false)}>
          <View style={styles.modalOverlay}>
            <TouchableWithoutFeedback>
              <View style={[styles.calendarModal, { backgroundColor: colors.surface }]}>
                <View style={styles.calendarHeader}>
                  <Text style={[styles.calendarTitle, { color: colors.text }]}>Seleccionar fecha</Text>
                  <TouchableOpacity onPress={() => { setSelectedDate(null); setShowCalendar(false); }}>
                    <Text style={[styles.calendarClearText, { color: colors.primary }]}>Ver todos</Text>
                  </TouchableOpacity>
                </View>
                <Calendar
                  markedDates={markedDates}
                  onDayPress={(day: { dateString: string }) => {
                    setSelectedDate(day.dateString);
                    setShowCalendar(false);
                  }}
                  theme={{
                    backgroundColor: colors.surface,
                    calendarBackground: colors.surface,
                    textSectionTitleColor: colors.textSecondary,
                    selectedDayBackgroundColor: colors.primary,
                    selectedDayTextColor: isDark ? colors.background : colors.surface,
                    todayTextColor: colors.primary,
                    dayTextColor: colors.text,
                    textDisabledColor: colors.border,
                    monthTextColor: colors.text,
                    arrowColor: colors.primary,
                    textDayFontWeight: '500',
                    textMonthFontWeight: '700',
                    textDayHeaderFontWeight: '600',
                  }}
                  minDate={new Date().toISOString().split('T')[0]}
                  enableSwipeMonths={true}
                />
              </View>
            </TouchableWithoutFeedback>
          </View>
        </TouchableWithoutFeedback>
      </Modal>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 15,
  },
  header: {
    paddingTop: 8,
    paddingBottom: 16,
  },
  topHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    marginBottom: 20,
  },
  titleContainer: {
    flex: 1,
    alignItems: 'center', // Centrado solicitado
  },
  title: {
    fontSize: 32,
    fontWeight: '700',
    letterSpacing: -0.5,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 32,
    fontWeight: '300',
    color: '#9CA3AF',
    letterSpacing: -0.5,
    textAlign: 'center',
  },
  filterContainer: {
    marginBottom: 20,
  },
  filterScroll: {
    paddingHorizontal: 16,
    gap: 8,
  },
  filterChip: {
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 25,
    marginRight: 4,
    borderWidth: 1,
  },
  filterText: {
    fontSize: 14,
    fontWeight: '600',
  },
  selectionIndicator: {
    paddingHorizontal: 20,
    paddingTop: 8,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
  },
  listContent: {
    paddingBottom: 32,
  },
  listContentEmpty: {
    flex: 1,
  },
  sectionDate: {
    fontSize: 20,
    fontWeight: '700',
    textTransform: 'capitalize',
  },
  sectionCount: {
    fontSize: 14,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 40,
    marginTop: 60,
  },
  emptyIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '700',
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 15,
    textAlign: 'center',
    lineHeight: 22,
  },
  updateToast: {
    position: 'absolute',
    bottom: 40,
    alignSelf: 'center',
    backgroundColor: '#10B981',
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 25,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
    elevation: 5,
    gap: 8,
  },
  updateToastText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: 14,
  },
  dateSeparator: {
    borderTopWidth: 1,
    marginHorizontal: 16,
    marginTop: 8,
    marginBottom: 16,
    paddingTop: 16,
  },
  dateSeparatorText: {
    fontSize: 16,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  headerButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
  },
  calendarBadge: {
    position: 'absolute',
    top: -4,
    right: -4,
    backgroundColor: '#3B82F6',
    width: 18,
    height: 18,
    borderRadius: 9,
    justifyContent: 'center',
    alignItems: 'center',
  },
  calendarBadgeText: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '700',
  },
  selectedDateChip: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    gap: 8,
    marginBottom: 16,
  },
  selectedDateText: {
    fontSize: 14,
    fontWeight: '600',
    textTransform: 'capitalize',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  calendarModal: {
    borderRadius: 20,
    padding: 16,
    width: '100%',
    maxWidth: 360,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 10,
  },
  calendarHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
    paddingHorizontal: 4,
  },
  calendarTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  calendarClearText: {
    fontSize: 14,
    fontWeight: '600',
  },
});

