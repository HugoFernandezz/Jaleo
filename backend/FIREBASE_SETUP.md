# Configuración de Firebase

Sigue estos pasos para configurar Firebase para PartyFinder.

## 1. Crear Proyecto Firebase

1. Ve a [Firebase Console](https://console.firebase.google.com)
2. Haz clic en "Añadir proyecto"
3. Nombre: `partyfinder-murcia` (o el que prefieras)
4. Desactiva Google Analytics (no es necesario)
5. Clic en "Crear proyecto"

## 2. Configurar Firestore Database

1. En el menú lateral, ve a **Build > Firestore Database**
2. Clic en "Crear base de datos"
3. Selecciona **"Iniciar en modo de producción"**
4. Selecciona ubicación: `europe-west1` (Bélgica) - la más cercana a España
5. Clic en "Habilitar"

## 3. Configurar Reglas de Seguridad

1. En Firestore, ve a la pestaña **"Reglas"**
2. Reemplaza el contenido con:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Los eventos de producción son públicos (solo lectura)
    match /eventos/{eventoId} {
      allow read: if true;
      allow write: if false; // Solo el scraper puede escribir
    }
    
    // Los eventos de desarrollo también son públicos (solo lectura)
    match /eventos-dev/{eventoId} {
      allow read: if true;
      allow write: if false; // Solo el scraper puede escribir
    }
  }
}
```

3. Clic en "Publicar"

## 4. Generar Credenciales para el Scraper

1. Ve a **Configuración del proyecto** (icono de engranaje)
2. Pestaña **"Cuentas de servicio"**
3. Clic en **"Generar nueva clave privada"**
4. Confirma y descarga el archivo JSON
5. **Renombra** el archivo a `serviceAccountKey.json`
6. **Mueve** el archivo a la carpeta `backend/`

> ⚠️ **IMPORTANTE**: No subas este archivo a GitHub. Ya está en `.gitignore`

## 5. Configurar para GitHub Actions

Para que el scraper automático funcione:

1. Ve a tu repositorio en GitHub
2. Settings > Secrets and variables > Actions
3. Clic en "New repository secret"
4. Nombre: `FIREBASE_SERVICE_ACCOUNT`
5. Valor: Copia todo el contenido del archivo JSON

## 6. Configurar App Móvil

### Android
1. En Firebase Console, ve a **Configuración del proyecto**
2. En "Tus apps", clic en el icono de Android
3. Nombre del paquete: `com.partyfinder.app` (o el tuyo)
4. Registra la app
5. Descarga `google-services.json`
6. Cópialo a la carpeta raíz del proyecto

### iOS
1. En Firebase Console, añade una app iOS
2. Bundle ID: `com.partyfinder.app`
3. Descarga `GoogleService-Info.plist`
4. Cópialo a la carpeta raíz del proyecto

## Verificar Configuración

Ejecuta este comando para probar:

```bash
cd backend
python -c "from firebase_config import init_firebase; print('OK' if init_firebase() else 'ERROR')"
```

Si ves "OK", Firebase está configurado correctamente.

