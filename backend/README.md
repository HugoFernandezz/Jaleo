# PartyFinder Backend

Backend para scrapear eventos de discotecas y servirlos a la app móvil.

## 🎯 Discotecas Configuradas

- **Luminata Disco**: https://site.fourvenues.com/es/luminata-disco/events
- **El Club by Odiseo**: https://site.fourvenues.com/es/el-club-by-odiseo/events

## 📦 Instalación

### 1. Crear entorno virtual (recomendado)
```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Instalar Chromium (necesario para el scraper)
```bash
pip install playwright
playwright install chromium
```

## 🚀 Uso

### Opción 1: Usar scripts batch (Windows)

**Ejecutar solo el scraper:**
```
run_scraper.bat
```

**Iniciar el servidor completo:**
```
start_backend.bat
```

### Opción 2: Comandos manuales

**Ejecutar scraper:**
```bash
python scraper.py
```

**Iniciar servidor API:**
```bash
python server.py
```

## 📡 API Endpoints

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/events` | GET | Obtener todos los eventos |
| `/api/status` | GET | Estado del servidor |
| `/api/scrape` | POST | Ejecutar scraping (requiere auth) |
| `/api/health` | GET | Health check |

### Ejemplo de uso

```javascript
// Obtener eventos
const response = await fetch('http://localhost:5000/api/events');
const data = await response.json();
console.log(data.data); // Array de eventos
```

## ⏰ Actualización Automática

El servidor ejecuta el scraper automáticamente a las **20:30** (hora de Madrid) cada día.

## 🔧 Configuración

### Añadir más venues

Edita `scraper.py` y añade URLs al array `VENUE_URLS`:

```python
VENUE_URLS = [
    "https://site.fourvenues.com/es/luminata-disco/events",
    "https://site.fourvenues.com/es/el-club-by-odiseo/events",
    "https://site.fourvenues.com/es/NUEVO-VENUE/events"  # Nueva discoteca
]
```

### Cambiar hora de actualización

Edita `server.py`:

```python
UPDATE_HOUR = 20   # Hora (0-23)
UPDATE_MINUTE = 30 # Minutos (0-59)
```

## 📁 Estructura de archivos

```
backend/
├── data/
│   ├── events.json      # Eventos transformados (usados por la app)
│   └── raw_events.json  # Datos crudos del scraping
├── scraper.py           # Script de web scraping
├── server.py            # Servidor API Flask
├── requirements.txt     # Dependencias Python
├── start_backend.bat    # Script para iniciar servidor
└── run_scraper.bat      # Script para ejecutar scraper
```

## ⚠️ Notas importantes

1. **El scraper necesita un navegador**: Usa Chromium headless para bypassear Cloudflare
2. **Primera ejecución**: El scraper tarda ~30-60 segundos por venue
3. **Cloudflare**: Si el challenge no se resuelve, intenta de nuevo
4. **Producción**: Despliega en un servidor con IP fija para evitar bloqueos

