# Configuración de Push Notifications

Este documento explica cómo configurar el sistema de push notifications para PartyFinder.

## Requisitos

1. **Expo Account**: Necesitas una cuenta de Expo para obtener el `projectId`
2. **Firebase Admin SDK**: Ya configurado con `serviceAccountKey.json`
3. **Dependencias Python**: `requests` (para llamar a Expo Push API)

## Configuración

### 1. Obtener Project ID de Expo

**IMPORTANTE**: El `projectId` debe ser un ID válido de Expo, no un nombre personalizado.

1. Ve a [Expo Dashboard](https://expo.dev) e inicia sesión
2. Crea un nuevo proyecto o selecciona uno existente
3. El `projectId` se genera automáticamente (formato: UUID como `a1b2c3d4-e5f6-7890-abcd-ef1234567890`)
4. También puedes obtenerlo ejecutando:
   ```bash
   npx expo whoami
   npx expo init --template blank
   ```
   O revisando el archivo `app.json` después de crear un proyecto con EAS

### 2. Actualizar app.json y notificationService.ts

**Actualiza `app.json`**:
```json
{
  "expo": {
    "extra": {
      "eas": {
        "projectId": "tu-uuid-de-expo-aqui"
      }
    }
  }
}
```

**Actualiza `src/services/notificationService.ts`** (línea 58):
```typescript
const tokenData = await Notifications.getExpoPushTokenAsync({
    projectId: 'tu-uuid-de-expo-aqui', // DEBE coincidir con app.json
});
```

> ⚠️ **NOTA**: Actualmente está configurado como `'partyfinder-murcia'` que NO es un projectId válido. Debes reemplazarlo con tu UUID real de Expo.

### 3. Instalar dependencias Python

```bash
pip install requests
```

### 4. Configurar Firebase

Asegúrate de que `serviceAccountKey.json` esté en el directorio `backend/` con los permisos correctos para:
- Leer de la colección `eventos`
- Leer de la colección `alert_tokens`
- Escribir en la colección `_metadata`

## Cómo funciona

1. **Registro de tokens**: Cuando un usuario crea una alerta, la app obtiene un token FCM (Expo Push Token) y lo guarda en Firebase en la colección `alert_tokens`

2. **Detección de nuevos eventos**: Después de cada scraping, el script `push_notifications.py`:
   - Compara los eventos actuales con un snapshot anterior
   - Detecta eventos nuevos
   - Busca alertas que coincidan con esos eventos

3. **Envío de notificaciones**: Para cada evento nuevo que coincide con una alerta:
   - Obtiene todos los tokens FCM registrados para esa alerta
   - Envía una notificación push usando Expo Push Notification API
   - La notificación llega al dispositivo aunque la app esté cerrada

## Uso

El servicio se ejecuta automáticamente después de cada scraping cuando usas `--upload`:

```bash
python3 scraper_firecrawl.py --upload
```

También puedes ejecutarlo manualmente:

```bash
python3 backend/push_notifications.py
```

## Estructura de datos en Firebase

### Colección `alert_tokens`
Documentos con formato: `{alertId}_{token}`

```json
{
  "alertId": "2024-12-25_Dodo Club_1735123456789",
  "token": "ExponentPushToken[xxxxx]",
  "platform": "ios",
  "registeredAt": "2024-12-20T10:00:00Z"
}
```

### Colección `_metadata`
Documento: `events_snapshot`

```json
{
  "event_ids": ["id1", "id2", "id3"],
  "last_updated": "2024-12-20T10:00:00Z"
}
```

## Configuración para App Store / Play Store

### ✅ Con Expo EAS Build (Recomendado)

Si usas **EAS Build** para compilar tu app, Expo maneja automáticamente la mayoría de la configuración:

#### iOS (App Store)
1. **Expo maneja automáticamente**:
   - Certificados APNs (Apple Push Notification service)
   - Provisioning profiles
   - Capabilities de notificaciones push

2. **Solo necesitas**:
   - Tener un `projectId` válido de Expo en `app.json`
   - Usar `eas build --platform ios` para compilar
   - Expo generará automáticamente los certificados necesarios

3. **Verificación**:
   ```bash
   # Verificar configuración
   eas build:configure
   ```

#### Android (Play Store)
1. **Funciona automáticamente** con Expo
2. **No requiere configuración adicional**
3. Solo asegúrate de usar `eas build --platform android`

### ⚠️ Si NO usas EAS Build (bare workflow)

Si compilas la app manualmente o usas otro método:

#### iOS
1. **Necesitas configurar APNs manualmente**:
   - Crear un certificado APNs en Apple Developer Portal
   - Configurar el certificado en Xcode
   - Agregar capability "Push Notifications" en Xcode

2. **Pasos**:
   - Ve a [Apple Developer Portal](https://developer.apple.com)
   - Certificates, Identifiers & Profiles
   - Crea un certificado APNs (Development y Production)
   - Descarga e instala en tu Mac
   - Configura en Xcode

#### Android
- Generalmente funciona sin configuración adicional
- Solo asegúrate de que `expo-notifications` esté instalado

### 📋 Checklist antes de publicar

- [ ] `projectId` válido de Expo configurado en `app.json` y `notificationService.ts`
- [ ] App compilada con `eas build` (recomendado) o configuración manual completa
- [ ] Permisos de notificaciones solicitados correctamente en la app
- [ ] Tokens FCM se están guardando en Firebase (`alert_tokens`)
- [ ] Servicio `push_notifications.py` funciona correctamente
- [ ] Probar notificaciones en build de producción antes de publicar

### 🔍 Verificar que funciona

1. **En desarrollo**:
   ```bash
   # Compilar build de preview
   eas build --platform ios --profile preview
   eas build --platform android --profile preview
   ```

2. **Probar notificaciones**:
   - Instala el build de preview en dispositivo físico
   - Crea una alerta
   - Verifica que el token se guarde en Firebase
   - Ejecuta el scraper y verifica que llegue la notificación

3. **En producción**:
   - Usa `eas build --platform ios --profile production`
   - Sube a App Store / Play Store
   - Las notificaciones funcionarán igual que en preview

## Troubleshooting

### Las notificaciones no llegan

1. Verifica que el `projectId` en `app.json` y `notificationService.ts` coincidan
2. Verifica que el token se esté guardando en Firebase (`alert_tokens`)
3. Verifica que el scraper esté detectando eventos nuevos
4. Revisa los logs del script `push_notifications.py`

### Error "Failed to get push token"

- Asegúrate de estar usando un dispositivo físico (no emulador)
- Verifica que los permisos de notificaciones estén concedidos
- En iOS, asegúrate de tener un perfil de desarrollo válido
- **En producción**: Verifica que el certificado APNs esté correcto (si no usas EAS)

### Error al enviar notificaciones

- Verifica que el token sea válido (formato: `ExponentPushToken[...]`)
- Verifica la conexión a internet
- Revisa los logs de Expo Push API
- **En producción**: Asegúrate de usar el certificado APNs de producción (no desarrollo)

