import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Party } from '../types';
import { NotificationAlert } from '../types/notifications';

const EVENTS_SNAPSHOT_KEY = '@partyfinder_events_snapshot';

// Configure notification behavior
Notifications.setNotificationHandler({
    handleNotification: async () => ({
        shouldShowAlert: true,
        shouldPlaySound: true,
        shouldSetBadge: false,
        shouldShowBanner: true,
        shouldShowList: true,
    }),
});

export const notificationService = {
    // Request notification permissions
    async requestPermissions(): Promise<boolean> {
        if (!Device.isDevice) {
            console.log('Must use physical device for Push Notifications');
            return false;
        }

        const { status: existingStatus } = await Notifications.getPermissionsAsync();
        let finalStatus = existingStatus;

        if (existingStatus !== 'granted') {
            const { status } = await Notifications.requestPermissionsAsync();
            finalStatus = status;
        }

        if (finalStatus !== 'granted') {
            console.log('Failed to get push token for push notification!');
            return false;
        }

        // Configure Android channel
        if (Platform.OS === 'android') {
            await Notifications.setNotificationChannelAsync('default', {
                name: 'default',
                importance: Notifications.AndroidImportance.MAX,
                vibrationPattern: [0, 250, 250, 250],
                lightColor: '#FF231F7C',
            });
        }

        return true;
    },

    // Show a local notification
    async showNotification(title: string, body: string, data?: any): Promise<void> {
        await Notifications.scheduleNotificationAsync({
            content: {
                title,
                body,
                data: data || {},
                sound: true,
            },
            trigger: null, // Show immediately
        });
    },

    // Save current events snapshot for comparison
    async saveEventsSnapshot(events: Party[]): Promise<void> {
        try {
            const snapshot = events.map(e => ({
                id: e.id,
                date: e.date,
                venueName: e.venueName,
                title: e.title,
            }));
            await AsyncStorage.setItem(EVENTS_SNAPSHOT_KEY, JSON.stringify(snapshot));
        } catch (error) {
            console.error('Error saving events snapshot:', error);
        }
    },

    // Get previous events snapshot
    async getEventsSnapshot(): Promise<{ id: string; date: string; venueName: string; title: string }[]> {
        try {
            const stored = await AsyncStorage.getItem(EVENTS_SNAPSHOT_KEY);
            return stored ? JSON.parse(stored) : [];
        } catch (error) {
            console.error('Error getting events snapshot:', error);
            return [];
        }
    },

    // Check for new events and trigger notifications
    async checkForNewEvents(
        currentEvents: Party[],
        alerts: NotificationAlert[]
    ): Promise<void> {
        if (alerts.length === 0) return;

        const previousSnapshot = await this.getEventsSnapshot();
        const previousIds = new Set(previousSnapshot.map(e => e.id));

        // Find new events
        const newEvents = currentEvents.filter(event => !previousIds.has(event.id));

        if (newEvents.length === 0) {
            // Still save the snapshot
            await this.saveEventsSnapshot(currentEvents);
            return;
        }

        // Check each new event against active alerts
        const enabledAlerts = alerts.filter(a => a.enabled);

        for (const event of newEvents) {
            for (const alert of enabledAlerts) {
                const dateMatches = event.date === alert.date;
                const venueMatches = !alert.venueName ||
                    event.venueName.toLowerCase().includes(alert.venueName.toLowerCase());

                if (dateMatches && venueMatches) {
                    // Format notification
                    const formattedDate = new Date(event.date).toLocaleDateString('es-ES', {
                        weekday: 'long',
                        day: 'numeric',
                        month: 'long',
                    });

                    await this.showNotification(
                        '🎉 ¡Nuevas entradas disponibles!',
                        `${event.title} en ${event.venueName} - ${formattedDate}`,
                        { eventId: event.id }
                    );

                    // Only notify once per event (break inner loop)
                    break;
                }
            }
        }

        // Save updated snapshot
        await this.saveEventsSnapshot(currentEvents);
    },
};
