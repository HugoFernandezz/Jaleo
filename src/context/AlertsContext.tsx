import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { notificationService } from '../services/notificationService';
import { NotificationAlert } from '../types/notifications';

const ALERTS_STORAGE_KEY = '@partyfinder_alerts';

interface AlertsContextType {
    alerts: NotificationAlert[];
    isLoading: boolean;
    addAlert: (date: string, venueName?: string) => Promise<void>;
    removeAlert: (id: string) => Promise<void>;
    toggleAlert: (id: string) => Promise<void>;
    getAlertsForDate: (date: string) => NotificationAlert[];
}

const AlertsContext = createContext<AlertsContextType | undefined>(undefined);

export const useAlerts = () => {
    const context = useContext(AlertsContext);
    if (!context) {
        throw new Error('useAlerts must be used within an AlertsProvider');
    }
    return context;
};

export const AlertsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [alerts, setAlerts] = useState<NotificationAlert[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    // Load alerts from storage on mount
    useEffect(() => {
        loadAlerts();
    }, []);

    const loadAlerts = async () => {
        try {
            const stored = await AsyncStorage.getItem(ALERTS_STORAGE_KEY);
            if (stored) {
                const parsed = JSON.parse(stored) as NotificationAlert[];
                // Filter out past dates
                const today = new Date().toISOString().split('T')[0];
                const validAlerts = parsed.filter(alert => alert.date >= today);
                setAlerts(validAlerts);
                // Save filtered list back
                if (validAlerts.length !== parsed.length) {
                    await AsyncStorage.setItem(ALERTS_STORAGE_KEY, JSON.stringify(validAlerts));
                }
            }
        } catch (error) {
            console.error('Error loading alerts:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const saveAlerts = async (newAlerts: NotificationAlert[]) => {
        try {
            await AsyncStorage.setItem(ALERTS_STORAGE_KEY, JSON.stringify(newAlerts));
        } catch (error) {
            console.error('Error saving alerts:', error);
        }
    };

    const addAlert = useCallback(async (date: string, venueName?: string) => {
        const newAlert: NotificationAlert = {
            id: `${date}_${venueName || 'all'}_${Date.now()}`,
            date,
            venueName: venueName || undefined,
            enabled: true,
            createdAt: new Date().toISOString(),
        };

        const updatedAlerts = [...alerts, newAlert];
        setAlerts(updatedAlerts);
        await saveAlerts(updatedAlerts);

        // Register FCM token for this alert
        const token = await notificationService.getStoredToken();
        if (!token) {
            // Request permissions and get token if not available
            const newToken = await notificationService.requestPermissions();
            if (newToken) {
                await notificationService.registerAlertToken(newAlert.id, newToken);
            }
        } else {
            await notificationService.registerAlertToken(newAlert.id, token);
        }
    }, [alerts]);

    const removeAlert = useCallback(async (id: string) => {
        // #region agent log
        try {
            const logEntry = {
                sessionId: 'debug-session',
                runId: 'run1',
                hypothesisId: 'A',
                location: 'AlertsContext.tsx:78',
                message: 'removeAlert called',
                data: {
                    alertId: id,
                    alertsCountBefore: alerts.length,
                    timestamp: Date.now()
                },
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
        
        const updatedAlerts = alerts.filter(alert => alert.id !== id);
        
        // #region agent log
        try {
            const logEntry = {
                sessionId: 'debug-session',
                runId: 'run1',
                hypothesisId: 'A',
                location: 'AlertsContext.tsx:78',
                message: 'removeAlert filtered',
                data: {
                    alertId: id,
                    alertsCountBefore: alerts.length,
                    alertsCountAfter: updatedAlerts.length,
                    timestamp: Date.now()
                },
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
        
        setAlerts(updatedAlerts);
        await saveAlerts(updatedAlerts);
        
        // Unregister FCM tokens for this alert
        await notificationService.unregisterAllAlertTokens(id);
        
        // #region agent log
        try {
            const logEntry = {
                sessionId: 'debug-session',
                runId: 'run1',
                hypothesisId: 'A',
                location: 'AlertsContext.tsx:78',
                message: 'removeAlert completed',
                data: {
                    alertId: id,
                    alertsCountAfter: updatedAlerts.length,
                    timestamp: Date.now()
                },
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
    }, [alerts]);

    const toggleAlert = useCallback(async (id: string) => {
        const updatedAlerts = alerts.map(alert =>
            alert.id === id ? { ...alert, enabled: !alert.enabled } : alert
        );
        setAlerts(updatedAlerts);
        await saveAlerts(updatedAlerts);
    }, [alerts]);

    const getAlertsForDate = useCallback((date: string) => {
        return alerts.filter(alert => alert.date === date && alert.enabled);
    }, [alerts]);

    return (
        <AlertsContext.Provider
            value={{
                alerts,
                isLoading,
                addAlert,
                removeAlert,
                toggleAlert,
                getAlertsForDate,
            }}
        >
            {children}
        </AlertsContext.Provider>
    );
};
