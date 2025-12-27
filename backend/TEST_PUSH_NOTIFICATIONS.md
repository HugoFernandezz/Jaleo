# 🧪 Test de Notificaciones Push

Este documento explica cómo testear las notificaciones push manualmente.

## 📋 Requisitos

1. Tener la app corriendo en un dispositivo físico (no funciona en emulador)
2. Tener permisos de notificaciones concedidos
3. Tener `requests` instalado: `pip install requests`

## 🚀 Pasos para Testear

### 1. Obtener el Token

Hay dos formas de obtener el token:

#### Opción A: Desde la Consola
1. Abre la app en tu dispositivo físico
2. Abre la consola de desarrollo (Metro bundler o DevTools)
3. Busca el mensaje que dice:
   ```
   ==================================================
   🔑 TOKEN PARA TEST DE NOTIFICACIONES PUSH:
   ==================================================
   ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]
   ==================================================
   ```
4. Copia el token completo

#### Opción B: Desde la App (Botón de Debug)
1. En la pantalla principal, toca el botón de "bug" (🐛) en el header
2. Se mostrará un alerta con el token
3. Copia el token completo

### 2. Enviar Notificación de Prueba

Ejecuta el script de prueba:

```bash
cd backend
python test_push_notification.py ExponentPushToken[tu-token-aqui]
```

**Ejemplo:**
```bash
python test_push_notification.py ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]
```

### 3. Verificar

Si todo funciona correctamente, deberías:
- ✅ Ver un mensaje de éxito en la terminal
- 📱 Recibir la notificación en tu dispositivo

## 🔍 Troubleshooting

### Error: "Invalid token"
- Asegúrate de copiar el token completo, incluyendo `ExponentPushToken[...]`
- Verifica que el token no tenga espacios al inicio o final
- El token debe ser del dispositivo físico donde está corriendo la app

### Error: "DeviceNotRegistered"
- El token puede haber expirado
- Reinicia la app para obtener un nuevo token
- Asegúrate de que la app esté corriendo cuando envías la notificación

### No llega la notificación
- Verifica que los permisos de notificaciones estén concedidos
- Asegúrate de que la app esté instalada en un dispositivo físico (no emulador)
- Verifica que el `projectId` en `app.json` sea correcto
- Revisa la consola de la app por errores

### Error de conexión
- Verifica tu conexión a internet
- Asegúrate de que puedas acceder a `https://exp.host`

## 📝 Notas

- Este script es solo para testing
- Las notificaciones push reales se envían desde el backend cuando hay nuevos eventos
- El botón de debug en la app es temporal y se puede eliminar después de las pruebas

