import React, { useState, useMemo, useEffect } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    FlatList,
    Modal,
    ScrollView,
    Alert,
    Dimensions,
    Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { Calendar, LocaleConfig } from 'react-native-calendars';
import { useTheme } from '../context/ThemeContext';
import { useAlerts } from '../context/AlertsContext';
import { NotificationAlert } from '../types/notifications';
import { apiService } from '../services/api';

const { width } = Dimensions.get('window');

// Spanish locale config
LocaleConfig.locales['es'] = {
    monthNames: ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'],
    monthNamesShort: ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'],
    dayNames: ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'],
    dayNamesShort: ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'],
    today: 'Hoy'
};
LocaleConfig.defaultLocale = 'es';

interface AlertsScreenProps {
    navigation: any;
}

export const AlertsScreen: React.FC<AlertsScreenProps> = ({ navigation }) => {
    const { colors, isDark } = useTheme();
    const { alerts, addAlert, removeAlert, toggleAlert, isLoading } = useAlerts();

    const [showCreateModal, setShowCreateModal] = useState(false);
    const [selectedDate, setSelectedDate] = useState<string | null>(null);
    const [selectedVenue, setSelectedVenue] = useState<string>('Todas las discotecas');
    const [venues, setVenues] = useState<string[]>(['Todas las discotecas']);

    // Determine text/icon color when on top of primary color
    // In Dark Mode: Primary is White -> Text should be Dark
    // In Light Mode: Primary is Dark -> Text should be White
    const contentOnPrimary = isDark ? colors.background : '#FFFFFF';

    useEffect(() => {
        loadVenues();
    }, []);

    const loadVenues = async () => {
        try {
            const parties = await apiService.getParties();
            const uniqueVenues = Array.from(new Set(parties.map(p => p.venueName))).sort();
            setVenues(['Todas las discotecas', ...uniqueVenues]);
        } catch (error) {
            console.error('Error loading venues:', error);
        }
    };

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        return date.toLocaleDateString('es-ES', {
            weekday: 'long',
            day: 'numeric',
            month: 'long',
        });
    };

    const handleCreateAlert = async () => {
        if (!selectedDate) {
            Alert.alert('Error', 'Selecciona una fecha');
            return;
        }

        const venueName = selectedVenue === 'Todas las discotecas' ? undefined : selectedVenue;
        await addAlert(selectedDate, venueName);

        setShowCreateModal(false);
        setSelectedDate(null);
        setSelectedVenue('Todas las discotecas');
    };

    const handleDeleteAlert = (alert: NotificationAlert) => {
        // #region agent log
        const logPath = Platform.OS === 'web' 
            ? '/.cursor/debug.log' 
            : require('path').join(require('os').homedir(), '.cursor', 'debug.log');
        try {
            const logEntry = {
                sessionId: 'debug-session',
                runId: 'run1',
                hypothesisId: 'A',
                location: 'AlertsScreen.tsx:88',
                message: 'handleDeleteAlert called',
                data: {
                    alertId: alert.id,
                    alertDate: alert.date,
                    platform: Platform.OS,
                    timestamp: Date.now()
                },
                timestamp: Date.now()
            };
            if (Platform.OS === 'web' && typeof fetch !== 'undefined') {
                fetch('http://127.0.0.1:7242/ingest/4f265990-1ec1-45f9-8d10-28c483de2c27', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(logEntry)
                }).catch(() => {});
            }
        } catch (e) {}
        // #endregion
        
        if (Platform.OS === 'web') {
            // En web, usar confirm nativo que es más confiable
            if (typeof window !== 'undefined' && window.confirm('¿Seguro que quieres eliminar esta alerta?')) {
                // #region agent log
                try {
                    const logEntry = {
                        sessionId: 'debug-session',
                        runId: 'run1',
                        hypothesisId: 'A',
                        location: 'AlertsScreen.tsx:88',
                        message: 'handleDeleteAlert confirmed (web)',
                        data: { alertId: alert.id },
                        timestamp: Date.now()
                    };
                    if (typeof fetch !== 'undefined') {
                        fetch('http://127.0.0.1:7242/ingest/4f265990-1ec1-45f9-8d10-28c483de2c27', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(logEntry)
                        }).catch(() => {});
                    }
                } catch (e) {}
                // #endregion
                removeAlert(alert.id);
            }
        } else {
            Alert.alert(
                'Eliminar alerta',
                '¿Seguro que quieres eliminar esta alerta?',
                [
                    { text: 'Cancelar', style: 'cancel' },
                    { 
                        text: 'Eliminar', 
                        style: 'destructive', 
                        onPress: () => {
                            // #region agent log
                            try {
                                const logEntry = {
                                    sessionId: 'debug-session',
                                    runId: 'run1',
                                    hypothesisId: 'A',
                                    location: 'AlertsScreen.tsx:88',
                                    message: 'handleDeleteAlert confirmed (mobile)',
                                    data: { alertId: alert.id },
                                    timestamp: Date.now()
                                };
                            } catch (e) {}
                            // #endregion
                            removeAlert(alert.id);
                        }
                    },
                ]
            );
        }
    };

    const renderAlert = ({ item }: { item: NotificationAlert }) => (
        <View style={[styles.alertCard, { backgroundColor: colors.surface, borderColor: colors.border }]}>
            <View style={styles.alertContent}>
                <View style={styles.alertIcon}>
                    <Ionicons name="calendar" size={24} color={colors.primary} />
                </View>
                <View style={styles.alertInfo}>
                    <Text style={[styles.alertDate, { color: colors.text }]}>
                        {formatDate(item.date)}
                    </Text>
                    <Text style={[styles.alertVenue, { color: colors.textSecondary }]}>
                        {item.venueName ? `🏠 ${item.venueName}` : '🎉 Todas las discotecas'}
                    </Text>
                </View>
                <View style={styles.alertActions}>
                    <TouchableOpacity
                        style={[styles.toggleButton, { backgroundColor: item.enabled ? colors.primary : colors.border }]}
                        onPress={() => toggleAlert(item.id)}
                    >
                        <Ionicons
                            name={item.enabled ? 'notifications' : 'notifications-off'}
                            size={18}
                            color={item.enabled ? contentOnPrimary : colors.textSecondary}
                        />
                    </TouchableOpacity>
                    <TouchableOpacity
                        style={[
                            styles.deleteButton,
                            Platform.OS === 'web' && styles.deleteButtonWeb
                        ]}
                        onPress={(e) => {
                            e.stopPropagation();
                            handleDeleteAlert(item);
                        }}
                        activeOpacity={0.7}
                        hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                    >
                        <Ionicons name="trash-outline" size={20} color="#EF4444" />
                    </TouchableOpacity>
                </View>
            </View>
        </View>
    );

    const sortedAlerts = useMemo(() => {
        return [...alerts].sort((a, b) => a.date.localeCompare(b.date));
    }, [alerts]);

    return (
        <SafeAreaView style={[styles.container, { backgroundColor: colors.background }]}>
            {/* Header */}
            <View style={styles.header}>
                <TouchableOpacity
                    style={[styles.backButton, { backgroundColor: colors.surface }]}
                    onPress={() => navigation.goBack()}
                >
                    <Ionicons name="chevron-back" size={24} color={colors.text} />
                </TouchableOpacity>
                <Text style={[styles.title, { color: colors.text }]}>Mis Alertas</Text>
                <TouchableOpacity
                    style={[styles.addButton, { backgroundColor: colors.primary }]}
                    onPress={() => setShowCreateModal(true)}
                >
                    <Ionicons name="add" size={24} color={contentOnPrimary} />
                </TouchableOpacity>
            </View>

            {/* Alerts List */}
            {sortedAlerts.length === 0 ? (
                <View style={styles.emptyState}>
                    <View style={[styles.emptyIcon, { backgroundColor: colors.surface }]}>
                        <Ionicons name="notifications-outline" size={40} color={colors.textSecondary} />
                    </View>
                    <Text style={[styles.emptyTitle, { color: colors.text }]}>Sin alertas</Text>
                    <Text style={[styles.emptySubtitle, { color: colors.textSecondary }]}>
                        Crea una alerta para recibir notificaciones cuando salgan nuevas entradas
                    </Text>
                    <TouchableOpacity
                        style={[styles.createButton, { backgroundColor: colors.primary }]}
                        onPress={() => setShowCreateModal(true)}
                    >
                        <Ionicons name="add" size={20} color={contentOnPrimary} />
                        <Text style={[styles.createButtonText, { color: contentOnPrimary }]}>Crear alerta</Text>
                    </TouchableOpacity>
                </View>
            ) : (
                <FlatList
                    data={sortedAlerts}
                    renderItem={renderAlert}
                    keyExtractor={(item) => item.id}
                    contentContainerStyle={styles.listContent}
                    showsVerticalScrollIndicator={false}
                />
            )}

            {/* Create Alert Modal */}
            <Modal
                visible={showCreateModal}
                animationType="slide"
                transparent={true}
                onRequestClose={() => setShowCreateModal(false)}
            >
                <View style={styles.modalOverlay}>
                    <View style={[styles.modalContent, { backgroundColor: colors.surface }]}>
                        <View style={styles.modalHeader}>
                            <Text style={[styles.modalTitle, { color: colors.text }]}>Nueva Alerta</Text>
                            <TouchableOpacity onPress={() => setShowCreateModal(false)}>
                                <Ionicons name="close" size={24} color={colors.text} />
                            </TouchableOpacity>
                        </View>

                        <ScrollView showsVerticalScrollIndicator={false}>
                            {/* Date Selection */}
                            <Text style={[styles.sectionLabel, { color: colors.textSecondary }]}>
                                ¿Qué día?
                            </Text>
                            <Calendar
                                onDayPress={(day: { dateString: string }) => setSelectedDate(day.dateString)}
                                markedDates={selectedDate ? {
                                    [selectedDate]: { selected: true, selectedColor: colors.primary }
                                } : {}}
                                minDate={new Date().toISOString().split('T')[0]}
                                theme={{
                                    backgroundColor: colors.surface,
                                    calendarBackground: colors.surface,
                                    textSectionTitleColor: colors.textSecondary,
                                    selectedDayBackgroundColor: colors.primary,
                                    selectedDayTextColor: contentOnPrimary,
                                    todayTextColor: colors.primary,
                                    dayTextColor: colors.text,
                                    textDisabledColor: colors.border,
                                    monthTextColor: colors.text,
                                    arrowColor: colors.primary,
                                }}
                            />

                            {/* Venue Selection */}
                            <Text style={[styles.sectionLabel, { color: colors.textSecondary, marginTop: 20 }]}>
                                ¿Discoteca específica? (opcional)
                            </Text>
                            <View style={styles.venueList}>
                                {venues.map((venue: string) => (
                                    <TouchableOpacity
                                        key={venue}
                                        style={[
                                            styles.venueChip,
                                            { backgroundColor: colors.background, borderColor: colors.border },
                                            selectedVenue === venue && { backgroundColor: colors.primary, borderColor: colors.primary }
                                        ]}
                                        onPress={() => setSelectedVenue(venue)}
                                    >
                                        <Text style={[
                                            styles.venueChipText,
                                            { color: colors.text },
                                            selectedVenue === venue && { color: contentOnPrimary }
                                        ]}>
                                            {venue}
                                        </Text>
                                    </TouchableOpacity>
                                ))}
                            </View>
                        </ScrollView>

                        {/* Actions */}
                        <View style={[styles.modalActions, { borderTopColor: colors.border }]}>
                            <TouchableOpacity
                                style={[styles.cancelButton, { borderColor: colors.border }]}
                                onPress={() => setShowCreateModal(false)}
                            >
                                <Text style={[styles.cancelButtonText, { color: colors.text }]}>Cancelar</Text>
                            </TouchableOpacity>
                            <TouchableOpacity
                                style={[styles.confirmButton, { backgroundColor: colors.primary }]}
                                onPress={handleCreateAlert}
                            >
                                <Text style={[styles.confirmButtonText, { color: contentOnPrimary }]}>Crear Alerta</Text>
                            </TouchableOpacity>
                        </View>
                    </View>
                </View>
            </Modal>
        </SafeAreaView>
    );
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: 16,
        paddingVertical: 12,
    },
    backButton: {
        width: 44,
        height: 44,
        borderRadius: 22,
        justifyContent: 'center',
        alignItems: 'center',
    },
    title: {
        fontSize: 20,
        fontWeight: '700',
    },
    addButton: {
        width: 44,
        height: 44,
        borderRadius: 22,
        justifyContent: 'center',
        alignItems: 'center',
    },
    listContent: {
        padding: 16,
        gap: 12,
    },
    alertCard: {
        borderRadius: 16,
        borderWidth: 1,
        marginBottom: 12,
    },
    alertContent: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: 16,
    },
    alertIcon: {
        width: 48,
        height: 48,
        borderRadius: 12,
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        justifyContent: 'center',
        alignItems: 'center',
        marginRight: 12,
    },
    alertInfo: {
        flex: 1,
    },
    alertDate: {
        fontSize: 16,
        fontWeight: '600',
        textTransform: 'capitalize',
        marginBottom: 4,
    },
    alertVenue: {
        fontSize: 14,
    },
    alertActions: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 8,
    },
    toggleButton: {
        width: 36,
        height: 36,
        borderRadius: 18,
        justifyContent: 'center',
        alignItems: 'center',
    },
    deleteButton: {
        width: 36,
        height: 36,
        justifyContent: 'center',
        alignItems: 'center',
    },
    deleteButtonWeb: {
        minWidth: 44,
        minHeight: 44,
        zIndex: 10,
        position: 'relative',
    },
    emptyState: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        paddingHorizontal: 40,
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
        marginBottom: 24,
    },
    createButton: {
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: 24,
        paddingVertical: 14,
        borderRadius: 25,
        gap: 8,
    },
    createButtonText: {
        color: '#FFFFFF', // This will be overridden in render
        fontSize: 16,
        fontWeight: '600',
    },
    modalOverlay: {
        flex: 1,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        justifyContent: 'flex-end',
    },
    modalContent: {
        borderTopLeftRadius: 24,
        borderTopRightRadius: 24,
        padding: 20,
        maxHeight: '90%',
    },
    modalHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 20,
    },
    modalTitle: {
        fontSize: 20,
        fontWeight: '700',
    },
    sectionLabel: {
        fontSize: 14,
        fontWeight: '600',
        marginBottom: 12,
        textTransform: 'uppercase',
        letterSpacing: 0.5,
    },
    venueList: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: 8,
    },
    venueChip: {
        paddingHorizontal: 16,
        paddingVertical: 10,
        borderRadius: 20,
        borderWidth: 1,
    },
    venueChipText: {
        fontSize: 14,
        fontWeight: '500',
    },
    modalActions: {
        flexDirection: 'row',
        gap: 12,
        marginTop: 24,
        paddingTop: 16,
        borderTopWidth: 1,
    },
    cancelButton: {
        flex: 1,
        paddingVertical: 14,
        borderRadius: 12,
        borderWidth: 1,
        alignItems: 'center',
    },
    cancelButtonText: {
        fontSize: 16,
        fontWeight: '600',
    },
    confirmButton: {
        flex: 1,
        paddingVertical: 14,
        borderRadius: 12,
        alignItems: 'center',
    },
    confirmButtonText: {
        color: '#FFFFFF', // This will be overridden in render
        fontSize: 16,
        fontWeight: '600',
    },
});
