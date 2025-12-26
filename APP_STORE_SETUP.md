# Configuración para App Store y Play Store

## ✅ Respuesta corta: Con Expo EAS Build, casi todo es automático

Si usas **EAS Build** (recomendado), Expo maneja automáticamente:
- ✅ Certificados APNs para iOS
- ✅ Configuración de notificaciones push
- ✅ Permisos necesarios
- ✅ Builds de producción

## 📋 Pasos necesarios antes de publicar

### 1. Obtener Project ID de Expo (OBLIGATORIO)

El `projectId` actual (`partyfinder-murcia`) **NO es válido**. Necesitas:

1. Ve a [Expo Dashboard](https://expo.dev) e inicia sesión
2. Crea un proyecto nuevo o selecciona uno existente
3. Copia el `projectId` (formato UUID: `a1b2c3d4-e5f6-7890-abcd-ef1234567890`)
4. Actualiza en:
   - `app.json` → `extra.eas.projectId`
   - `src/services/notificationService.ts` → línea 58

### 2. Configurar EAS (si aún no lo has hecho)

```bash
# Instalar EAS CLI
npm install -g eas-cli

# Iniciar sesión
eas login

# Configurar proyecto
eas build:configure
```

### 3. Compilar builds de producción

```bash
# iOS
eas build --platform ios --profile production

# Android
eas build --platform android --profile production
```

**Expo generará automáticamente**:
- Certificados APNs para iOS
- Keystore para Android
- Toda la configuración necesaria

### 4. Verificar configuración en app.json

Ya está configurado:
- ✅ `ios.bundleIdentifier`
- ✅ `android.package`
- ✅ `ios.infoPlist.UIBackgroundModes` (para notificaciones en background)
- ✅ Plugin `expo-notifications`

### 5. Probar antes de publicar

1. **Compilar build de preview**:
   ```bash
   eas build --platform ios --profile preview
   ```

2. **Instalar en dispositivo físico** (no emulador)

3. **Probar notificaciones**:
   - Crea una alerta
   - Verifica que el token se guarde en Firebase
   - Ejecuta el scraper
   - Verifica que llegue la notificación

4. **Si funciona en preview, funcionará en producción**

## 🚨 Si NO usas EAS Build

### iOS (App Store) - Configuración manual

1. **Crear certificado APNs**:
   - Ve a [Apple Developer Portal](https://developer.apple.com)
   - Certificates, Identifiers & Profiles
   - Crea certificado APNs (Development y Production)
   - Descarga e instala en tu Mac

2. **Configurar en Xcode**:
   - Abre el proyecto en Xcode
   - Target → Signing & Capabilities
   - Agrega "Push Notifications"
   - Configura el certificado APNs

3. **Compilar y subir manualmente**

### Android (Play Store)

- ✅ **Funciona automáticamente** - No necesitas configuración adicional
- Solo asegúrate de que `expo-notifications` esté instalado

## ✅ Checklist final

Antes de publicar, verifica:

- [ ] `projectId` válido de Expo configurado
- [ ] App compilada con `eas build` (o configuración manual completa)
- [ ] Notificaciones probadas en build de preview/producción
- [ ] Tokens FCM se guardan correctamente en Firebase
- [ ] Servicio `push_notifications.py` funciona
- [ ] Permisos de notificaciones funcionan en la app

## 🎯 Resumen

**Con EAS Build**: Solo necesitas el `projectId` correcto. Todo lo demás es automático.

**Sin EAS Build**: Necesitas configurar certificados APNs manualmente para iOS.

**Android**: Funciona automáticamente en ambos casos.

## 📚 Recursos

- [Expo Push Notifications](https://docs.expo.dev/push-notifications/overview/)
- [EAS Build](https://docs.expo.dev/build/introduction/)
- [Apple Push Notifications](https://developer.apple.com/documentation/usernotifications)


