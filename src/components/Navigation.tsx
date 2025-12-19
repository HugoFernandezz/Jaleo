import React from 'react';
import { NavigationContainer, DefaultTheme, DarkTheme } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import { HomeScreen } from '../screens/HomeScreen';
import { EventDetailScreen } from '../screens/EventDetailScreen';
import { Party } from '../types';
import { useTheme } from '../context/ThemeContext';

export type RootStackParamList = {
  Home: undefined;
  EventDetail: { party: Party };
};

const Stack = createStackNavigator<RootStackParamList>();

export const Navigation: React.FC = () => {
  const { colors, isDark } = useTheme();

  // Crear un tema personalizado basado en el estado actual
  const theme = {
    ...(isDark ? DarkTheme : DefaultTheme),
    colors: {
      ...(isDark ? DarkTheme.colors : DefaultTheme.colors),
      primary: colors.primary,
      background: colors.background,
      card: colors.card,
      text: colors.text,
      border: colors.border,
      notification: colors.primary,
    },
  };

  return (
    <NavigationContainer theme={theme}>
      <Stack.Navigator screenOptions={{ headerShown: false }}>
        <Stack.Screen name="Home" component={HomeScreen} />
        <Stack.Screen name="EventDetail" component={EventDetailScreen} />
      </Stack.Navigator>
    </NavigationContainer>
  );
};
