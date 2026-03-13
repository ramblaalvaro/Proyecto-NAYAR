# 🛰️ NAYAR PROJECT — Wiki

> **NAYAR** is a spatial intelligence system based on WiFi Sniffing. It detects devices in an area, analyzes occupancy patterns and visualizes data in real time through a web dashboard.

---

## 📋 Table of Contents

- [Project Description](#-project-description)
- [System Architecture](#-system-architecture)
- [How Sniffing Works](#-how-sniffing-works)
- [Installation & Setup](#-installation--setup)
- [Firebase Database](#-firebase-database)
- [API & Endpoints](#-api--endpoints)
- [Flow Diagram](#-flow-diagram)

---

## 🌐 Project Description

NAYAR is a physical space monitoring system using passive WiFi technology. A Raspberry Pi listens to device signals in the area, calculates occupancy metrics and sends them to ThingSpeak. A web dashboard displays everything in real time.

| | |
|---|---|
| **Version** | v2.0 |
| **Hardware** | Raspberry Pi (Ubuntu) |
| **Backend** | Python + Flask + ThingSpeak |
| **Frontend** | HTML + CSS + JavaScript |
| **Database** | Firebase Firestore |
| **Protocol** | WiFi ARP Scan (no monitor mode required) |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       NAYAR PROJECT                         │
├─────────────────┬───────────────────┬───────────────────────┤
│   RASPBERRY PI  │    THINGSPEAK     │      WEB FRONTEND     │
│                 │                   │                       │
│  nayar.py       │  Channel: 3285772 │  index.html           │
│  ┌───────────┐  │  8 fields:        │  loginpage.html       │
│  │ ARP Scan  │──│  field1: RSSI avg │  dispositivos.html    │
│  │ nmap      │  │  field2: devices  │  solicitar-acceso.html│
│  │ ping RSSI │  │  field3: occupancy│                       │
│  └───────────┘  │  field4: RSSI min │  ┌─────────────────┐  │
│        │        │  field5: RSSI max │  │   script.js     │  │
│        │        │  field6: energy   │  │  ┌───────────┐  │  │
│  /api/status ──────────────────────────│  │ThingSpeak │  │  │
│  (Flask:5000)   │  field7: zones    │  │  │  API      │  │  │
│                 │  field8: alerts   │  │  └───────────┘  │  │
│                 │                   │  │  ┌───────────┐  │  │
│                 │                   │  │  │Raspberry  │  │  │
│                 │                   │  │  │/api/status│  │  │
│                 │                   │  │  └───────────┘  │  │
└─────────────────┴───────────────────┴──┴─────────────────┴──┘
                                              │
                                    ┌─────────────────┐
                                    │    FIREBASE     │
                                    │   FIRESTORE     │
                                    │   devices       │
                                    │  (MAC + name)   │
                                    └─────────────────┘
```

---

## 📡 How Sniffing Works

NAYAR uses **passive ARP Scan** instead of monitor mode, meaning no special network card configuration is required.

**Process:**
1. `nmap` scans the local network with ARP requests every 30 seconds
2. Devices respond revealing their **MAC address**
3. `ping` is used to estimate **RSSI** based on response latency
4. Each device is classified into a **signal zone**:

| Zone | RSSI | Estimated Distance |
|------|------|--------------------|
| 🔵 Zone A | ≥ −50 dBm | Very close |
| 🟢 Zone B | −50 / −65 dBm | Close |
| 🟡 Zone C | −65 / −75 dBm | Far |
| 🔴 Zone D | < −75 dBm | Very far |

5. Metrics are calculated and sent to **ThingSpeak** + **endpoint /api/status**

---

## ⚙️ Installation & Setup

### Raspberry Pi

```bash
# 1. Install dependencies
pip3 install flask flask-cors requests
sudo apt install nmap

# 2. Clone the repository
git clone https://github.com/your-username/nayar.git
cd nayar

# 3. Edit configuration in nayar.py
nano nayar.py
# Change:
#   RED_LOCAL    = "192.168.X.X/24"  ← your subnet
#   AFORO_MAXIMO = 50                ← your max capacity

# 4. Run
sudo python3 nayar.py
```

### Frontend (GitHub Pages)

```bash
git add .
git commit -m "Deploy NAYAR frontend"
git push origin main
# Settings → Pages → Branch: main → Save
```

### Project Files

```
📁 nayar/
├── index.html              ← System login
├── loginpage.html          ← Main dashboard
├── dispositivos.html       ← Device registry (Firebase)
├── solicitar-acceso.html   ← Access request form (EmailJS)
├── style.css               ← Dashboard styles
├── script.js               ← ThingSpeak + Raspberry Pi logic
└── nayar.py                ← Python script for Raspberry Pi
```

### Configuration Variables

| File | Variable | Description |
|------|----------|-------------|
| `nayar.py` | `RED_LOCAL` | WiFi subnet (e.g. 192.168.1.0/24) |
| `nayar.py` | `AFORO_MAXIMO` | Maximum space capacity |
| `nayar.py` | `THINGSPEAK_WRITE` | ThingSpeak Write API Key |
| `dispositivos.html` | `firebaseConfig` | Firebase credentials |
| `solicitar-acceso.html` | `EMAILJS_*` | EmailJS keys |
| `index.html` | `admin / 1234` | Login username and password |

---

## 🔥 Firebase Database

NAYAR uses **Firebase Firestore** to store the permanent registry of known devices (MAC + name).

### Data Structure

```
firestore/
└── dispositivos/           ← collection
    ├── {id}
    │   ├── mac:    "AA:BB:CC:DD:EE:FF"
    │   ├── nombre: "Office laptop"
    │   └── fecha:  "2024-01-15T10:30:00.000Z"
    └── {id}
        ├── mac:    "B8:27:EB:XX:XX:02"
        ├── nombre: "NAYAR Raspberry Pi"
        └── fecha:  "2024-01-15T09:00:00.000Z"
```

### Firebase Setup

1. Create project at [console.firebase.google.com](https://console.firebase.google.com)
2. **Firestore Database** → **Create database** → Test mode
3. Register web app `</>` → copy `firebaseConfig`
4. Paste config into `dispositivos.html`

### Recommended Security Rules

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /dispositivos/{doc} {
      allow read, write: if true; // ← change to auth in production
    }
  }
}
```

---

## 🔌 API & Endpoints

The `nayar.py` script exposes a REST API on port `5000`.

### `GET /api/status`

Returns all real-time metrics.

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
    { "mac": "AA:BB:CC:DD:EE:FF", "ip": "192.168.1.10", "rssi": -45, "zona": "Zone A" }
  ],
  "zones": [
    { "zone": "Zone A", "pct": 25.0 },
    { "zone": "Zone B", "pct": 42.0 },
    { "zone": "Zone C", "pct": 25.0 },
    { "zone": "Zone D", "pct": 8.0  }
  ],
  "bi": {
    "peak_hour":    "13:00 – 14:00",
    "top_zone":     "Zone B",
    "avg_stay_min": 18,
    "peak_count":   27,
    "peak_time":    "13:45"
  }
}
```

### `GET /api/dispositivos`
Returns only the list of active devices.

### `GET /api/ping`
Server health check.

### ThingSpeak Fields

| Field | Data |
|-------|------|
| field1 | Average RSSI (dBm) |
| field2 | Number of detected devices |
| field3 | Estimated occupancy (%) |
| field4 | Minimum RSSI (dBm) |
| field5 | Maximum RSSI (dBm) |
| field6 | Energy index (0-100) |
| field7 | Active zones (0-4) |
| field8 | Active alerts |

---

## 🔄 Flow Diagram

```
  [WiFi Devices]
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
[Historical Charts]      [Real-time KPIs]
[field1..field8]         [Devices, Zones, BI]
    │                             │
    └────────────┬────────────────┘
                 ▼
          [Web Dashboard]
          loginpage.html
                 │
    ┌────────────┴────────────┐
    │                         │
    ▼                         ▼
[solicitar-acceso.html]  [dispositivos.html]
[EmailJS → Gmail]        [Firebase Firestore]
```

---

## 🔐 Access System

| Component | Technology | Description |
|-----------|-----------|-------------|
| Login | HTML + JS | Username/password in `index.html` |
| Access request | EmailJS | Form → email to admin |
| Device registry | Firebase | Cloud database |

---

## 📦 Dependencies

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

## 👤 Author

**NAYAR Project** — Spatial Intelligence WiFi System  
`nayarcompanyservices@gmail.com`

---

*Last updated: 2025*
