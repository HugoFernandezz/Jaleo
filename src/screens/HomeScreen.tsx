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
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { PartyCard } from '../components/PartyCard';
import { Party } from '../types';
import { apiService } from '../services/api';
import { RootStackParamList } from '../components/Navigation';
import { StackNavigationProp } from '@react-navigation/stack';

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

  useEffect(() => {
    loadParties();
    
    // Suscribirse a actualizaciones en tiempo real
    const unsubscribe = apiService.subscribeToUpdates((data) => {
      if (data.parties.length > 0) {
        setParties(data.parties);
      }
    });

    return () => unsubscribe();
  }, []);

  useEffect(() => {
    // Extraer venues únicos
    const allVenues = new Set<string>();
    parties.forEach(party => {
      if (party.venueName) {
        allVenues.add(party.venueName.trim());
      }
    });
    setAvailableVenues(['Todas', ...Array.from(allVenues).sort()]);
  }, [parties]);

  // Filtrar y agrupar eventos
  const groupedParties = useMemo(() => {
    let filtered = parties;

    if (selectedVenue !== 'Todas') {
      filtered = filtered.filter(party => party.venueName.trim() === selectedVenue);
    }

    // Ordenar por fecha
    filtered.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

    // Agrupar por fecha
    const groups: { [key: string]: Party[] } = {};
    filtered.forEach(party => {
      const dateKey = party.date;
      if (!groups[dateKey]) {
        groups[dateKey] = [];
      }
      groups[dateKey].push(party);
    });

    return Object.entries(groups).map(([date, items]) => ({
      date,
      items,
    }));
  }, [parties, selectedVenue]);

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

  // Formatear fecha para header
  const formatSectionDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    const isToday = date.toDateString() === today.toDateString();
    const isTomorrow = date.toDateString() === tomorrow.toDateString();

    if (isToday) return 'Hoy';
    if (isTomorrow) return 'Mañana';

    const options: Intl.DateTimeFormatOptions = { 
      weekday: 'long', 
      day: 'numeric', 
      month: 'long' 
    };
    return date.toLocaleDateString('es-ES', options);
  };

  const renderItem = ({ item }: { item: { date: string; items: Party[] } }) => (
    <View style={styles.section}>
      {/* Header de fecha */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionDate}>{formatSectionDate(item.date)}</Text>
        <Text style={styles.sectionCount}>
          {item.items.length} {item.items.length === 1 ? 'evento' : 'eventos'}
        </Text>
      </View>

      {/* Eventos del día */}
      {item.items.map((party) => (
        <PartyCard 
          key={party.id} 
          party={party} 
          onPress={() => handlePartyPress(party)}
        />
      ))}
    </View>
  );

  const renderHeader = () => (
    <View style={styles.header}>
      {/* Título */}
      <View style={styles.titleContainer}>
        <Text style={styles.title}>Eventos</Text>
        <Text style={styles.subtitle}>Murcia</Text>
      </View>

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
                selectedVenue === venue && styles.filterChipActive
              ]}
              onPress={() => setSelectedVenue(venue)}
            >
              <Text style={[
                styles.filterText,
                selectedVenue === venue && styles.filterTextActive
              ]}>
                {venue}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>
    </View>
  );

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <View style={styles.emptyIcon}>
        <Ionicons name="calendar-outline" size={48} color="#D1D5DB" />
      </View>
      <Text style={styles.emptyTitle}>No hay eventos</Text>
      <Text style={styles.emptySubtitle}>
        {selectedVenue !== 'Todas' 
          ? `No hay eventos en ${selectedVenue}`
          : 'Vuelve más tarde para ver nuevos eventos'
        }
      </Text>
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#1F2937" />
          <Text style={styles.loadingText}>Cargando eventos...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <FlatList
        data={groupedParties}
        renderItem={renderItem}
        keyExtractor={(item) => item.date}
        ListHeaderComponent={renderHeader}
        ListEmptyComponent={renderEmpty}
        showsVerticalScrollIndicator={false}
        contentContainerStyle={[
          styles.listContent,
          groupedParties.length === 0 && styles.listContentEmpty
        ]}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="#1F2937"
          />
        }
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 15,
    color: '#6B7280',
  },
  header: {
    paddingTop: 8,
    paddingBottom: 16,
    backgroundColor: '#F9FAFB',
  },
  titleContainer: {
    paddingHorizontal: 20,
    marginBottom: 20,
  },
  title: {
    fontSize: 32,
    fontWeight: '700',
    color: '#1F2937',
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 32,
    fontWeight: '300',
    color: '#9CA3AF',
    letterSpacing: -0.5,
  },
  filterContainer: {
    marginBottom: 8,
  },
  filterScroll: {
    paddingHorizontal: 16,
  },
  filterChip: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#FFFFFF',
    marginRight: 8,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  filterChipActive: {
    backgroundColor: '#1F2937',
    borderColor: '#1F2937',
  },
  filterText: {
    fontSize: 14,
    fontWeight: '500',
    color: '#6B7280',
  },
  filterTextActive: {
    color: '#FFFFFF',
  },
  listContent: {
    paddingBottom: 32,
  },
  listContentEmpty: {
    flex: 1,
  },
  section: {
    marginBottom: 8,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 12,
  },
  sectionDate: {
    fontSize: 18,
    fontWeight: '600',
    color: '#1F2937',
    textTransform: 'capitalize',
  },
  sectionCount: {
    fontSize: 13,
    color: '#9CA3AF',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 40,
  },
  emptyIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#F3F4F6',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 16,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#1F2937',
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#9CA3AF',
    textAlign: 'center',
    lineHeight: 20,
  },
});
