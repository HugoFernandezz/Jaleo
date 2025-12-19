import React, { createContext, useContext, useState, useEffect } from 'react';
import { useColorScheme } from 'react-native';

export type ThemeMode = 'light' | 'dark' | 'system';

interface ThemeColors {
    background: string;
    surface: string;
    text: string;
    textSecondary: string;
    primary: string;
    border: string;
    card: string;
    error: string;
    success: string;
}

const lightColors: ThemeColors = {
    background: '#F9FAFB',
    surface: '#FFFFFF',
    text: '#1F2937',
    textSecondary: '#6B7280',
    primary: '#1F2937', // Estilo premium oscuro/monocromo por defecto
    border: '#E5E7EB',
    card: '#FFFFFF',
    error: '#EF4444',
    success: '#10B981',
};

const darkColors: ThemeColors = {
    background: '#111827',
    surface: '#1F2937',
    text: '#F9FAFB',
    textSecondary: '#9CA3AF',
    primary: '#FFFFFF',
    border: '#374151',
    card: '#1F2937',
    error: '#F87171',
    success: '#34D399',
};

interface ThemeContextType {
    theme: ThemeMode;
    isDark: boolean;
    colors: ThemeColors;
    setTheme: (theme: ThemeMode) => void;
    toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const systemColorScheme = useColorScheme();
    const [theme, setTheme] = useState<ThemeMode>('system');

    const isDark = theme === 'system' ? systemColorScheme === 'dark' : theme === 'dark';
    const colors = isDark ? darkColors : lightColors;

    const toggleTheme = () => {
        setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
    };

    return (
        <ThemeContext.Provider value={{ theme, isDark, colors, setTheme, toggleTheme }}>
            {children}
        </ThemeContext.Provider>
    );
};

export const useTheme = () => {
    const context = useContext(ThemeContext);
    if (!context) {
        throw new Error('useTheme must be used within a ThemeProvider');
    }
    return context;
};
