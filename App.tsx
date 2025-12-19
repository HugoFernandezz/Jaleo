import React from 'react';
import { StatusBar } from 'expo-status-bar';
import { Navigation } from './src/components/Navigation';
import { ThemeProvider, useTheme } from './src/context/ThemeContext';

const AppContent: React.FC = () => {
  const { isDark } = useTheme();

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
      <AppContent />
    </ThemeProvider>
  );
}

