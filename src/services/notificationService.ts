import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import Constants from 'expo-constants';
import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getFirestore, collection, doc, setDoc, getDocs, query, where, deleteDoc } from 'firebase/firestore';
import { db } from './firebase';
import { Party } from '../types';
import { NotificationAlert } from '../types/notifications';

const EVENTS_SNAPSHOT_KEY = '@partyfinder_events_snapshot';
const FCM_TOKEN_KEY = '@partyfinder_fcm_token';

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
    // Request notification permissions and get FCM token
    async requestPermissions(): Promise<string | null> {
        if (!Device.isDevice) {
            console.log('Must use physical device for Push Notifications');
            return null;
        }

        const { status: existingStatus } = await Notifications.getPermissionsAsync();
        let finalStatus = existingStatus;

        if (existingStatus !== 'granted') {
            const { status } = await Notifications.requestPermissionsAsync();
            finalStatus = status;
        }

        if (finalStatus !== 'granted') {
            console.log('Failed to get push token for push notification!');
            return null;
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

        // Get FCM token (Expo Push Token)
        try {
            // Get projectId from app.json (expo.extra.eas.projectId)
            const projectId = Constants.expoConfig?.extra?.eas?.projectId;
            
            if (!projectId || projectId === 'REEMPLAZA_CON_TU_UUID_DE_EXPO') {
                console.error('❌ Error: projectId de Expo no configurado correctamente.');
                console.error('📋 Para obtener tu projectId:');
                console.error('   1. Ve a https://expo.dev y crea un nuevo proyecto');
                console.error('   2. O ejecuta: npx eas init');
                console.error('   3. Copia el UUID del proyecto y reemplázalo en app.json');
                console.error('   4. El projectId debe ser un UUID (ej: a1b2c3d4-e5f6-7890-abcd-ef1234567890)');
                return null;
            }

            const tokenData = await Notifications.getExpoPushTokenAsync({
                projectId: projectId,
            });
            const token = tokenData.data;
            
            // Save token locally
            await AsyncStorage.setItem(FCM_TOKEN_KEY, token);
            
            return token;
        } catch (error) {
            console.error('Error getting Expo push token:', error);
            return null;
        }
    },

    // Get stored FCM token
    async getStoredToken(): Promise<string | null> {
        try {
            return await AsyncStorage.getItem(FCM_TOKEN_KEY);
        } catch (error) {
            console.error('Error getting stored token:', error);
            return null;
        }
    },

    // Register device token for an alert in Firebase
    async registerAlertToken(alertId: string, token: string): Promise<void> {
        try {
            const alertsRef = collection(db, 'alert_tokens');
            await setDoc(doc(alertsRef, `${alertId}_${token}`), {
                alertId,
                token,
                platform: Platform.OS,
                registeredAt: new Date().toISOString(),
            });
        } catch (error) {
            console.error('Error registering alert token:', error);
        }
    },

    // Unregister device token for an alert
    async unregisterAlertToken(alertId: string, token: string): Promise<void> {
        try {
            const alertsRef = collection(db, 'alert_tokens');
            await deleteDoc(doc(alertsRef, `${alertId}_${token}`));
        } catch (error) {
            console.error('Error unregistering alert token:', error);
        }
    },

    // Unregister all tokens for an alert (when alert is deleted)
    async unregisterAllAlertTokens(alertId: string): Promise<void> {
        try {
            const alertsRef = collection(db, 'alert_tokens');
            const q = query(alertsRef, where('alertId', '==', alertId));
            const snapshot = await getDocs(q);
            
            const deletePromises = snapshot.docs.map(doc => deleteDoc(doc.ref));
            await Promise.all(deletePromises);
        } catch (error) {
            console.error('Error unregistering all alert tokens:', error);
        }
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
