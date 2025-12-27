import React, { useEffect } from 'react';
import { Platform, StyleSheet } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { Navigation } from './src/components/Navigation';
import { ThemeProvider, useTheme } from './src/context/ThemeContext';
import { AlertsProvider } from './src/context/AlertsContext';
import { notificationService } from './src/services/notificationService';

// Estilos globales para web
if (Platform.OS === 'web' && typeof document !== 'undefined') {
  const style = document.createElement('style');
  style.textContent = `
    html, body {
      height: 100%;
      width: 100%;
      margin: 0;
      padding: 0;
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
    }
    #root {
      height: 100%;
      width: 100%;
      position: relative;
    }
  `;
  document.head.appendChild(style);
}

const AppContent: React.FC = () => {
  const { isDark } = useTheme();

  useEffect(() => {
    // Request notification permissions and get FCM token on app start
    const initializeNotifications = async () => {
      const token = await notificationService.requestPermissions();
      if (token) {
        console.log('='.repeat(50));
        console.log('🔑 TOKEN PARA TEST DE NOTIFICACIONES PUSH:');
        console.log('='.repeat(50));
        console.log(token);
        console.log('='.repeat(50));
        console.log('💡 Copia este token y úsalo con:');
        console.log('   python backend/test_push_notification.py ' + token);
        console.log('='.repeat(50));
        // Token is automatically saved in notificationService
      }
    };
    initializeNotifications();
  }, []);

  return (
    <>
      <Navigation />
      <StatusBar style={isDark ? "light" : "dark"} />
    </>
  );
};

export default function App() {
  return (
    <ThemeProvider>
      <AlertsProvider>
        <AppContent />
      </AlertsProvider>
    </ThemeProvider>
  );
}

