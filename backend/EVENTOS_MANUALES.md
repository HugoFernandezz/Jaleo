# Creación de Eventos Manuales

Este documento explica cómo crear eventos manualmente en Firebase sin que sean eliminados por el scraper.

## Problema Resuelto

Anteriormente, cuando el scraper se ejecutaba, eliminaba **TODOS** los eventos de la base de datos antes de subir los nuevos. Esto causaba que los eventos creados manualmente también fueran eliminados.

## Solución Implementada

Se implementó un sistema de identificación de origen usando el campo `source` y eliminación automática de eventos pasados:

- **Eventos del scraper**: `source: "scraper"` (añadido automáticamente)
- **Eventos manuales**: `source: "manual"` (debes añadirlo manualmente)

### Lógica de Eliminación

El scraper ahora realiza dos tipos de eliminación:

1. **Eventos pasados (TODOS)**: Elimina automáticamente todos los eventos cuya fecha + hora_inicio ya haya pasado, independientemente de si son manuales o del scraper.
   - Ejemplo: Si un evento es el viernes a las 17:00, se eliminará el viernes a las 17:01 o más tarde.

2. **Eventos futuros del scraper**: De los eventos futuros, solo elimina los del scraper (`source: "scraper"` o sin campo `source`), preservando eventos futuros manuales (`source: "manual"`).

## Cómo Crear un Evento Manual

### Método 1: A través de Firebase Console

1. Ve a la consola de Firebase
2. Selecciona Firestore Database
3. Navega a la colección `eventos` (o `eventos-dev` si estás en desarrollo)
4. Haz clic en "Agregar documento"
5. Añade los campos del evento en el siguiente formato:

```json
{
  "nombreEvento": "Nombre del Evento",
  "descripcion": "Descripción del evento",
  "fecha": "2025-12-25",
  "hora_inicio": "23:00",
  "hora_fin": "06:00",
  "imagen_url": "https://ejemplo.com/imagen.jpg",
  "url_evento": "https://ejemplo.com/evento",
  "code": "MANUAL001",
  "entradas": [
    {
      "tipo": "Entrada General",
      "precio": "15",
      "agotadas": false,
      "url_compra": "https://ejemplo.com/comprar"
    }
  ],
  "tags": ["Fiesta", "Reggaetón"],
  "edad_minima": 18,
  "lugar": {
    "nombre": "Nombre del Lugar",
    "direccion": "Dirección del lugar",
    "ciudad": "Murcia",
    "codigo_postal": "30001",
    "latitud": 37.9922,
    "longitud": -1.1307,
    "categoria": "Discoteca"
  },
  "source": "manual",
  "last_updated": [TIMESTAMP]
}
```

**IMPORTANTE**: Asegúrate de incluir `"source": "manual"` para que el evento no sea eliminado por el scraper.

### Método 2: Usando un Script de Python

Si tienes un script que inyecta eventos manualmente, asegúrate de añadir el campo `source`:

```python
from firebase_config import get_db
from firebase_admin import firestore

db = get_db()

evento_manual = {
    "nombreEvento": "Nombre del Evento",
    "descripcion": "Descripción del evento",
    "fecha": "2025-12-25",
    "hora_inicio": "23:00",
    "hora_fin": "06:00",
    # ... otros campos ...
    "source": "manual",  # ⚠️ IMPORTANTE: Añade este campo
    "last_updated": firestore.SERVER_TIMESTAMP
}

# Añadir a Firestore
doc_ref = db.collection('eventos').document()
doc_ref.set(evento_manual)
```

### Método 3: Usando un JSON File

Si inyectas JSONs directamente, asegúrate de incluir el campo `source`:

```json
{
  "evento": {
    "nombreEvento": "Nombre del Evento",
    "fecha": "2025-12-25",
    // ... otros campos ...
    "source": "manual"
  }
}
```

## Compatibilidad con Versiones Antiguas de la App

**Buena noticia**: El campo `source` es completamente compatible con versiones antiguas de la app.

- Las versiones antiguas de la app **ignorarán** el campo `source` (no crasheará)
- JavaScript/TypeScript simplemente ignora campos extra en los objetos
- El código de la app solo accede a los campos que necesita

## Verificación

Para verificar que un evento manual está correctamente marcado:

1. Ve a Firebase Console
2. Busca el evento en la colección `eventos`
3. Verifica que tenga el campo `source` con valor `"manual"`

Si el evento tiene `source: "manual"`, **no será eliminado** por el scraper en futuras ejecuciones.

## Eventos Pasados

**IMPORTANTE**: Los eventos (tanto manuales como del scraper) se eliminan automáticamente cuando su fecha + hora_inicio ya pasó.

- Un evento del viernes a las 17:00 se eliminará el viernes a las 17:01 o más tarde
- Esto aplica a TODOS los eventos, sin excepción
- No necesitas eliminarlos manualmente

## Eventos Antiguos (Sin Campo source)

Los eventos creados antes de implementar esta solución:

- **Si no tienen campo `source`**: Serán eliminados por el scraper si son futuros (se asumen como eventos antiguos del scraper)
- **Si ya pasaron**: Se eliminarán automáticamente como eventos pasados
- **Si quieres preservarlos**: Actualiza manualmente añadiendo `source: "manual"` (solo si son futuros)

## Notas Importantes

1. **Siempre incluye `source: "manual"`** al crear eventos manuales futuros
2. El campo `source` es opcional para la app (no causa problemas si falta)
3. El scraper automáticamente añade `source: "scraper"` a sus eventos
4. Puedes usar `is_manual: true` como alternativa a `source: "manual"` (ambos funcionan)
5. **Los eventos pasados se eliminan automáticamente**, independientemente del campo `source`
