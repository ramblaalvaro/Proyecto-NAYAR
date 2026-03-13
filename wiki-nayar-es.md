# 🛰️ PROYECTO NAYAR — Wiki

> **NAYAR** es un sistema de inteligencia espacial basado en WiFi Sniffing. Detecta dispositivos en una zona, analiza patrones de ocupación y visualiza los datos en tiempo real desde un dashboard web.

---

## 📋 Índice

- [Descripción del proyecto](#-descripción-del-proyecto)
- [Arquitectura del sistema](#-arquitectura-del-sistema)
- [Cómo funciona el sniffing](#-cómo-funciona-el-sniffing)
- [Instalación y configuración](#-instalación-y-configuración)
- [Base de datos Firebase](#-base-de-datos-firebase)
- [API y endpoints](#-api-y-endpoints)
- [Diagrama de flujo](#-diagrama-de-flujo)

---

## 🌐 Descripción del proyecto

NAYAR es un sistema de monitorización de espacios físicos usando tecnología WiFi pasiva. Una Raspberry Pi escucha las señales de los dispositivos presentes en la zona, calcula métricas de ocupación y las envía a ThingSpeak. Un dashboard web muestra todo en tiempo real.

| | |
|---|---|
| **Versión** | v2.0 |
| **Hardware** | Raspberry Pi (Ubuntu) |
| **Backend** | Python + Flask + ThingSpeak |
| **Frontend** | HTML + CSS + JavaScript |
| **Base de datos** | Firebase Firestore |
| **Protocolo** | WiFi ARP Scan (sin modo monitor) |

---

## 🏗️ Arquitectura del sistema

```
┌─────────────────────────────────────────────────────────────┐
│                      PROYECTO NAYAR                         │
├─────────────────┬───────────────────┬───────────────────────┤
│   RASPBERRY PI  │    THINGSPEAK     │      WEB FRONTEND     │
│                 │                   │                       │
│  nayar.py       │  Canal: 3285772   │  index.html           │
│  ┌───────────┐  │  8 fields:        │  loginpage.html       │
│  │ ARP Scan  │──│  field1: RSSI avg │  dispositivos.html    │
│  │ nmap      │  │  field2: devices  │  solicitar-acceso.html│
│  │ ping RSSI │  │  field3: ocupación│                       │
│  └───────────┘  │  field4: RSSI min │  ┌─────────────────┐  │
│        │        │  field5: RSSI max │  │   script.js     │  │
│        │        │  field6: energía  │  │  ┌───────────┐  │  │
│  /api/status ──────────────────────────│  │ThingSpeak │  │  │
│  (Flask:5000)   │  field7: zonas    │  │  │  API      │  │  │
│                 │  field8: alertas  │  │  └───────────┘  │  │
│                 │                   │  │  ┌───────────┐  │  │
│                 │                   │  │  │Raspberry  │  │  │
│                 │                   │  │  │/api/status│  │  │
│                 │                   │  │  └───────────┘  │  │
└─────────────────┴───────────────────┴──┴─────────────────┴──┘
                                              │
                                    ┌─────────────────┐
                                    │    FIREBASE     │
                                    │   FIRESTORE     │
                                    │  dispositivos   │
                                    │  (MAC + nombre) │
                                    └─────────────────┘
```

---

## 📡 Cómo funciona el sniffing

NAYAR utiliza **ARP Scan pasivo** en lugar de modo monitor, lo que significa que no requiere configuración especial de la tarjeta de red.

**Proceso:**
1. `nmap` escanea la red local con ARP requests cada 30 segundos
2. Los dispositivos responden revelando su **dirección MAC**
3. Se hace `ping` a cada IP para estimar el **RSSI** según la latencia
4. Cada dispositivo se clasifica en una **zona de señal**:

| Zona | RSSI | Distancia estimada |
|------|------|--------------------|
| 🔵 Zona A | ≥ −50 dBm | Muy cerca |
| 🟢 Zona B | −50 / −65 dBm | Cerca |
| 🟡 Zona C | −65 / −75 dBm | Lejos |
| 🔴 Zona D | < −75 dBm | Muy lejos |

5. Las métricas se calculan y envían a **ThingSpeak** + **endpoint /api/status**

---

## ⚙️ Instalación y configuración

### Raspberry Pi

```bash
# 1. Instalar dependencias
pip3 install flask flask-cors requests
sudo apt install nmap

# 2. Clonar el repositorio
git clone https://github.com/tu-usuario/nayar.git
cd nayar

# 3. Editar configuración en nayar.py
nano nayar.py
# Cambiar:
#   RED_LOCAL    = "192.168.X.X/24"  ← tu subred
#   AFORO_MAXIMO = 50                ← tu aforo real

# 4. Ejecutar
sudo python3 nayar.py
```

### Frontend (GitHub Pages)

```bash
git add .
git commit -m "Deploy NAYAR frontend"
git push origin main
# Settings → Pages → Branch: main → Save
```

### Archivos del proyecto

```
📁 nayar/
├── index.html              ← Login del sistema
├── loginpage.html          ← Dashboard principal
├── dispositivos.html       ← Registro de dispositivos (Firebase)
├── solicitar-acceso.html   ← Formulario de solicitud (EmailJS)
├── style.css               ← Estilos del dashboard
├── script.js               ← Lógica ThingSpeak + Raspberry Pi
└── nayar.py                ← Script Python para Raspberry Pi
```

### Variables a configurar

| Archivo | Variable | Descripción |
|---------|----------|-------------|
| `nayar.py` | `RED_LOCAL` | Subred WiFi (ej: 192.168.1.0/24) |
| `nayar.py` | `AFORO_MAXIMO` | Aforo máximo del espacio |
| `nayar.py` | `THINGSPEAK_WRITE` | Write API Key de ThingSpeak |
| `dispositivos.html` | `firebaseConfig` | Credenciales de Firebase |
| `solicitar-acceso.html` | `EMAILJS_*` | Claves de EmailJS |
| `index.html` | `admin / 1234` | Usuario y contraseña de acceso |

---

## 🔥 Base de datos Firebase

NAYAR usa **Firebase Firestore** para almacenar el registro permanente de dispositivos conocidos (MAC + nombre).

### Estructura de datos

```
firestore/
└── dispositivos/           ← colección
    ├── {id}
    │   ├── mac:    "AA:BB:CC:DD:EE:FF"
    │   ├── nombre: "Portátil oficina"
    │   └── fecha:  "2024-01-15T10:30:00.000Z"
    └── {id}
        ├── mac:    "B8:27:EB:XX:XX:02"
        ├── nombre: "Raspberry Pi NAYAR"
        └── fecha:  "2024-01-15T09:00:00.000Z"
```

### Configuración Firebase

1. Crear proyecto en [console.firebase.google.com](https://console.firebase.google.com)
2. **Firestore Database** → **Create database** → Modo prueba
3. Registrar app web `</>` → copiar `firebaseConfig`
4. Pegar config en `dispositivos.html`

### Reglas de seguridad recomendadas

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /dispositivos/{doc} {
      allow read, write: if true; // ← cambiar a autenticación en producción
    }
  }
}
```

---

## 🔌 API y endpoints

El script `nayar.py` expone una API REST en el puerto `5000`.

### `GET /api/status`

Devuelve todas las métricas en tiempo real.

```json
{
  "device_count":   12,
  "rssi_avg":       -61.5,
  "rssi_min":       -82,
  "rssi_max":       -44,
  "occupancy_pct":  24.0,
  "energy_index":   76.0,
  "zone_count":     3,
  "alert_count":    1,
  "uptime_seconds": 3600,
  "devices": [
    { "mac": "AA:BB:CC:DD:EE:FF", "ip": "192.168.1.10", "rssi": -45, "zona": "Zona A" }
  ],
  "zones": [
    { "zone": "Zona A", "pct": 25.0 },
    { "zone": "Zona B", "pct": 42.0 },
    { "zone": "Zona C", "pct": 25.0 },
    { "zone": "Zona D", "pct": 8.0  }
  ],
  "bi": {
    "peak_hour":    "13:00 – 14:00",
    "top_zone":     "Zona B",
    "avg_stay_min": 18,
    "peak_count":   27,
    "peak_time":    "13:45"
  }
}
```

### `GET /api/dispositivos`
Lista solo los dispositivos activos.

### `GET /api/ping`
Health check del servidor.

### Campos ThingSpeak

| Field | Dato |
|-------|------|
| field1 | RSSI promedio (dBm) |
| field2 | Nº dispositivos detectados |
| field3 | Ocupación estimada (%) |
| field4 | RSSI mínimo (dBm) |
| field5 | RSSI máximo (dBm) |
| field6 | Índice energético (0-100) |
| field7 | Zonas activas (0-4) |
| field8 | Alertas activas |

---

## 🔄 Diagrama de flujo

```
  [Dispositivos WiFi]
         │
         ▼
  [Raspberry Pi — nayar.py]
         │
    ┌────┴────────────────────────┐
    │                             │
    ▼                             ▼
[ThingSpeak]              [/api/status :5000]
    │                             │
    ▼                             ▼
[Gráficas históricas]    [KPIs en tiempo real]
[field1..field8]         [Dispositivos, Zonas, BI]
    │                             │
    └────────────┬────────────────┘
                 ▼
          [Dashboard Web]
          loginpage.html
                 │
    ┌────────────┴────────────┐
    │                         │
    ▼                         ▼
[solicitar-acceso.html]  [dispositivos.html]
[EmailJS → Gmail]        [Firebase Firestore]
```

---

## 🔐 Sistema de acceso

| Componente | Tecnología | Descripción |
|------------|-----------|-------------|
| Login | HTML + JS | Usuario/contraseña en `index.html` |
| Solicitud acceso | EmailJS | Formulario → email a admin |
| Registro dispositivos | Firebase | Base de datos en la nube |

---

## 📦 Dependencias

### Python (Raspberry Pi)
```bash
pip3 install flask flask-cors requests
sudo apt install nmap
```

### JavaScript (Frontend)
```html
<!-- EmailJS -->
<script src="https://cdn.jsdelivr.net/npm/@emailjs/browser@4/dist/email.min.js"></script>

<!-- Firebase -->
<script type="module" src="https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js"></script>
<script type="module" src="https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js"></script>
```

---

## 👤 Autor

**Proyecto NAYAR** — Sistema de Inteligencia Espacial WiFi  
`nayarcompanyservices@gmail.com`

---

*Última actualización: 2025*
