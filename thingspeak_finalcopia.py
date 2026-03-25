import requests
import time
import subprocess
import re
from datetime import datetime

# ── CONFIGURACIÓN ──────────────────────────────────────────
API_KEY      = "ZP4YZJRVUUSRHD1R"
URL          = "https://api.thingspeak.com/update"
INTERFACE    = "wlan0"
MAX_CAPACITY = 20

def get_zone(rssi):
    if rssi >= -50: return "A"
    if rssi >= -65: return "B"
    if rssi >= -75: return "C"
    return "D"

def escanear_wifi():
    """Escanea redes WiFi cercanas sin modo monitor y devuelve lista de RSSI."""
    try:
        resultado = subprocess.run(
            ["sudo", "iwlist", INTERFACE, "scan"],
            capture_output=True, text=True, timeout=15
        )
        rssi_valores = re.findall(r"Signal level=(-\d+) dBm", resultado.stdout)
        return [int(r) for r in rssi_valores]
    except Exception as e:
        print(f"Error escaneando: {e}")
        return []

# ── BUCLE PRINCIPAL ────────────────────────────────────────
while True:

    print(f"\nEscaneando redes WiFi en {INTERFACE}...")
    active_rssi = escanear_wifi()

    if not active_rssi:
        print("Sin señales detectadas, reintentando...")
        time.sleep(15)
        continue

    # field1 → RSSI Promedio (dBm)
    field1 = round(sum(active_rssi) / len(active_rssi), 1)

    # field2 → Dispositivos/redes detectadas
    field2 = len(active_rssi)

    # field3 → Ocupación (%)
    field3 = min(100, round((field2 / MAX_CAPACITY) * 100))

    # field4 → RSSI Mínimo (dBm)
    field4 = min(active_rssi)

    # field5 → RSSI Máximo (dBm)
    field5 = max(active_rssi)

    # field6 → Índice Energético
    field6 = max(0, 100 - field3)

    # field7 → Zonas Activas
    zonas_con_gente = set(get_zone(r) for r in active_rssi)
    field7 = len(zonas_con_gente)

    # field8 → Alertas
    field8 = 0
    if field3 >= 90:
        field8 += 1
    if field1 < -75 and field2 > 0:
        field8 += 1

    # Enviar a ThingSpeak
    payload = {
        "api_key": API_KEY,
        "field1":  field1,
        "field2":  field2,
        "field3":  field3,
        "field4":  field4,
        "field5":  field5,
        "field6":  field6,
        "field7":  field7,
        "field8":  field8,
    }

    r = requests.post(URL, data=payload)

    print(f"Dispositivos : {field2}")
    print(f"RSSI promedio: {field1} dBm")
    print(f"Ocupación    : {field3}%")
    print(f"RSSI mín/máx : {field4} / {field5} dBm")
    print(f"Índice energ.: {field6}")
    print(f"Zonas activas: {field7}")
    print(f"Alertas      : {field8}")
    print(f"ThingSpeak   : entry_id={r.text.strip()}")
    print("─" * 40)

    time.sleep(15)
