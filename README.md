# PartyFinder Murcia 🎉

Una aplicación móvil para descubrir las mejores fiestas y eventos nocturnos en Murcia.

## 🚀 Características Principales

- **Descubrimiento de Eventos**: Navega por los mejores eventos de la vida nocturna murciana
- **Filtrado por Venue**: Filtra eventos por discoteca específica
- **Organización por Fechas**: Eventos agrupados por fecha con headers sticky
- **Compra de Entradas**: Enlaces directos a la compra de tickets individuales
- **Eventos de Transporte**: Identificación especial para eventos con bus incluido
- **Sistema de Caché Inteligente**: Actualizaciones automáticas desde las 20:30h Madrid

## 🔧 Tecnologías Utilizadas

- **React Native** + **Expo** para desarrollo móvil multiplataforma
- **TypeScript** para tipado estático
- **React Navigation** para navegación entre pantallas
- **Firebase Firestore** para almacenamiento de datos en tiempo real
- **Expo Notifications** para notificaciones push
- **Expo Vector Icons** para iconografía

## 📱 Funcionalidades

### Pantalla Principal (HomeScreen)
- Lista de eventos organizados por fecha
- Selector horizontal de discotecas
- Indicadores visuales para eventos agotados y últimas entradas
- Identificación especial de eventos con transporte (bus)

### Pantalla de Detalle (EventDetailScreen)
- Información completa del evento
- Tarjetas de tickets individuales con estados (disponible/últimas/agotado)
- Botones interactivos para compra de entradas
- Información de transporte para eventos de bus

### Sistema de Tickets
- **TicketCard**: Componente interactivo con animaciones
- Estados visuales claros (disponible, pocas quedan, agotado)
- Apertura directa del navegador para compra
- Manejo de errores en la apertura de URLs

## 🎯 Optimizaciones Recientes (2024)

### Rendimiento y Memoria
- ✅ **Eliminación de Memory Leaks**: Corregidas dependencias en useEffect
- ✅ **Optimización con useMemo**: Procesamiento de eventos optimizado
- ✅ **useCallback**: Callbacks optimizados para evitar re-renders
- ✅ **Comparación Eficiente**: Reemplazado JSON.stringify por comparación directa

### Limpieza de Código
- ✅ **Eliminación de Debug**: Removidos todos los console.log de producción
- ✅ **Dependencias Limpiadas**: Eliminada @react-navigation/bottom-tabs no utilizada
- ✅ **Imports Optimizados**: Removidos imports no utilizados
- ✅ **Funciones Muertas**: Eliminadas funciones no utilizadas del API service

### Gestión de API
- ✅ **Lógica de Horarios Restaurada**: Sistema de actualización a las 20:30h Madrid funcionando
- ✅ **Caché Inteligente**: Optimizado para mejores tiempos de respuesta
- ✅ **Manejo de Errores**: Mejorado en carga de imágenes y navegación

### Tipos y Estructura
- ✅ **Tipos Optimizados**: Campos opcionales donde corresponde
- ✅ **Componentes Limpiados**: Eliminado ConnectionStatus no utilizado
- ✅ **Estructura Mejorada**: Código más mantenible y eficiente

## 🏗️ Arquitectura del Proyecto

```
src/
├── components/          # Componentes reutilizables
│   ├── Navigation.tsx   # Configuración de navegación
│   ├── PartyCard.tsx    # Tarjeta de evento
│   ├── TicketCard.tsx   # Tarjeta de ticket individual
│   └── TagFilter.tsx    # Filtro de etiquetas
├── screens/            # Pantallas principales
│   ├── HomeScreen.tsx   # Pantalla principal de eventos
│   ├── EventDetailScreen.tsx # Detalle de evento
│   ├── VenuesScreen.tsx # Lista de venues
│   └── ProfileScreen.tsx # Perfil de usuario
├── services/           # Servicios y APIs
│   └── api.ts          # Servicio de API con caché inteligente
├── types/              # Definiciones de tipos TypeScript
│   └── index.ts        # Tipos principales
└── utils/              # Utilidades
```

## 🚀 Instalación y Desarrollo

### Requisitos Previos
- Node.js 18+ 
- npm o yarn
- Expo CLI
- Cuenta de Firebase (para la base de datos)

### Instalación
```bash
# Clonar el repositorio
git clone <repository-url>
cd PartyFinder

# Instalar dependencias
npm install

# Configurar variables de entorno
cp .env.example .env
# Edita .env y añade tus credenciales de Firebase
# Puedes encontrarlas en: Firebase Console > Configuración del proyecto > Tus apps > SDK snippet

# Iniciar en modo desarrollo
npm start
```

### ⚙️ Configuración de Variables de Entorno

**IMPORTANTE**: Este proyecto usa variables de entorno para las credenciales de Firebase. 

1. Copia el archivo `.env.example` a `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edita `.env` y reemplaza los valores con los de tu proyecto Firebase:
   - Ve a [Firebase Console](https://console.firebase.google.com)
   - Selecciona tu proyecto
   - Ve a **Configuración del proyecto** > **Tus apps** > **SDK snippet**
   - Copia los valores y pégalos en `.env`

3. **NUNCA subas el archivo `.env` a Git** - Ya está en `.gitignore`

> ⚠️ **Nota de Seguridad**: Si este repositorio ya tenía credenciales expuestas en el historial de Git, considera rotar las API keys en Firebase Console para mayor seguridad.

### Scripts Disponibles
```bash
npm start          # Iniciar servidor de desarrollo
npm run android    # Abrir en Android
npm run ios        # Abrir en iOS  
npm run web        # Abrir en navegador web
npm run clear-cache # Limpiar caché de Expo
```

## 🔄 Sistema de Actualizaciones

La aplicación utiliza un sistema inteligente de caché que:
- **Actualiza datos automáticamente** a las 20:30h (hora de Madrid)
- **Verifica cambios** cada hora en segundo plano
- **Mantiene datos offline** cuando no hay conexión
- **Optimiza peticiones** evitando llamadas innecesarias

## 🎨 Diseño y UX

- **Interfaz Moderna**: Diseño limpio con colores vibrantes
- **Navegación Intuitiva**: Stack navigation simple y efectiva
- **Animaciones Suaves**: Transiciones y feedback visual
- **Estados Visuales**: Indicadores claros para diferentes estados de tickets
- **Responsive**: Adaptado para diferentes tamaños de pantalla

## 📊 Estado del Proyecto

**✅ PROYECTO OPTIMIZADO Y FUNCIONAL**

- ✅ Rendimiento mejorado significativamente
- ✅ Memory leaks corregidos
- ✅ Código limpio y mantenible
- ✅ API service optimizado
- ✅ Sistema de caché funcionando correctamente
- ✅ Tipos TypeScript optimizados
- ✅ Componentes optimizados con React hooks

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:
1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/nueva-feature`)
3. Commit tus cambios (`git commit -am 'Añadir nueva feature'`)
4. Push a la rama (`git push origin feature/nueva-feature`)
5. Abre un Pull Request

## 📄 Licencia

MIT License - ver archivo LICENSE para más detalles. 