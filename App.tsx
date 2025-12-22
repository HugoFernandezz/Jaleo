import React, { useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import { Navigation } from './src/components/Navigation';
import { ThemeProvider, useTheme } from './src/context/ThemeContext';
import { AlertsProvider } from './src/context/AlertsContext';
import { notificationService } from './src/services/notificationService';

const AppContent: React.FC = () => {
  const { isDark } = useTheme();

  useEffect(() => {
    // Request notification permissions on app start
    notificationService.requestPermissions();
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

