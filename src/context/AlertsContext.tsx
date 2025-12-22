import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
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
    }, [alerts]);

    const removeAlert = useCallback(async (id: string) => {
        const updatedAlerts = alerts.filter(alert => alert.id !== id);
        setAlerts(updatedAlerts);
        await saveAlerts(updatedAlerts);
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
