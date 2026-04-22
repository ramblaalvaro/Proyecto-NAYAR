import requests
import time
import subprocess
import re
from datetime import datetime
from collections import defaultdict

# ══════════════════════════════════════════════════════════════════════
#  CANALES THINGSPEAK
# ══════════════════════════════════════════════════════════════════════

# Canal GENERAL — tipos de dispositivo + alertas
API_KEY_GENERAL  = "TSXNP7UL4V51O25E"
CANAL_GENERAL    = "3285772"

# Canal OFICINAS — zonas + estancias (demo_nuevo.html)
API_KEY_OFICINAS = "1EUF2CEJOXZRO2O0"
CANAL_OFICINAS   = "3349520"

URL = "https://api.thingspeak.com/update"

# ══════════════════════════════════════════════════════════════════════
#  CANAL GENERAL  (field1-8)
#  field1 → RSSI promedio (dBm)
#  field2 → Dispositivos totales
#  field3 → Ocupacion (%)
#  field4 → Moviles
#  field5 → Portatiles
#  field6 → IoT / Smart
#  field7 → Otros
#  field8 → Alertas activas
#
#  CANAL OFICINAS  (field1-8)
#  field1 → RSSI promedio (dBm)
#  field2 → Dispositivos totales
#  field3 → Ocupacion (%)
#  field4 → Zona A dispositivos  (0-5 m)
#  field5 → Zona B dispositivos  (5-15 m)
#  field6 → Zona C dispositivos  (>15 m)
#  field7 → Estancia media Zona A (min)
#  field8 → Estancia media Zona B (min)
# ══════════════════════════════════════════════════════════════════════

# ── AJUSTES ────────────────────────────────────────────────────────────
INTERFACE    = "wlan0"
MAX_CAPACITY = 30     # dispositivos = aforo 100%
ZONA_A_MAX   =  5.0   # metros — Zona A (Oficinas)
ZONA_B_MAX   = 15.0   # metros — Zona B (Salas)
VENTANA      = 10     # ciclos para promediar estancia

# Intervalo: ThingSpeak free permite 1 envio cada 15 s por canal.
# Con 2 canales: 15 s entre canal1 y canal2, luego 15 s de espera = 30 s ciclo.
PAUSA_ENTRE_CANALES = 15
PAUSA_FINAL         = 15

# ── ESTADO ─────────────────────────────────────────────────────────────
historial_zonas = defaultdict(list)
ciclo = 0

# ── FUNCIONES ──────────────────────────────────────────────────────────
def rssi_to_metros(rssi):
    metros = 10 ** ((-40 - rssi) / (10 * 2.0))
    return round(max(0.1, min(metros, 99.9)), 1)

def zona_por_distancia(rssi):
    d = rssi_to_metros(rssi)
    if   d <= ZONA_A_MAX: return "A"
    elif d <= ZONA_B_MAX: return "B"
    else:                  return "C"

def classify_device(rssi):
    d = rssi_to_metros(rssi)
    if   d < 2:  return "mobile"
    elif d < 5:  return "laptop"
    elif d < 15: return "iot"
    else:         return "other"

def estancia_media(zona):
    datos = historial_zonas[zona]
    if not datos:
        return 0
    promedio = sum(datos) / len(datos)
    minutos  = round((promedio * (PAUSA_ENTRE_CANALES + PAUSA_FINAL) * len(datos)) / 60, 1)
    return min(minutos, 99.9)

def escanear_wifi():
    try:
        resultado = subprocess.run(
            ["sudo", "iwlist", INTERFACE, "scan"],
            capture_output=True, text=True, timeout=15
        )
        rssi_valores = re.findall(r"Signal level=(-\d+) dBm", resultado.stdout)
        return [int(r) for r in rssi_valores]
    except Exception as e:
        print(f"  Err escaneando: {e}")
        return []

def enviar_canal(api_key, nombre, fields):
    fields["api_key"] = api_key
    try:
        r = requests.post(URL, data=fields, timeout=10)
        entry = r.text.strip()
        ok = entry not in ("0", "", "-1")
        print(f"  {'OK' if ok else 'ERR'} {nombre}: entry_id={entry}")
    except Exception as e:
        print(f"  ERR {nombre}: {e}")

# ── INICIO ─────────────────────────────────────────────────────────────
print("=" * 52)
print("  NAYAR - Sensor WiFi activo")
print(f"  Canal General  : {CANAL_GENERAL}")
print(f"  Canal Oficinas : {CANAL_OFICINAS}")
print(f"  Zona A: 0-{ZONA_A_MAX}m  |  Zona B: {ZONA_A_MAX}-{ZONA_B_MAX}m  |  Zona C: >{ZONA_B_MAX}m")
print(f"  Ciclo: {PAUSA_ENTRE_CANALES+PAUSA_FINAL}s  ({PAUSA_ENTRE_CANALES}s entre canales + {PAUSA_FINAL}s espera)")
print("=" * 52)

# ── BUCLE PRINCIPAL ────────────────────────────────────────────────────
while True:
    ciclo += 1
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Ciclo {ciclo}")

    rssi_lista = escanear_wifi()

    if not rssi_lista:
        print("  Sin senales. Reintentando en 15s...")
        time.sleep(15)
        continue

    # ── Metricas comunes ───────────────────────────────────────────────
    rssi_medio = round(sum(rssi_lista) / len(rssi_lista), 1)
    total      = len(rssi_lista)
    ocupacion  = min(100, round((total / MAX_CAPACITY) * 100))
    dist_media = rssi_to_metros(rssi_medio)

    # ── Clasificacion por ZONA ─────────────────────────────────────────
    nA = nB = nC = 0
    for rssi in rssi_lista:
        z = zona_por_distancia(rssi)
        if   z == "A": nA += 1
        elif z == "B": nB += 1
        else:          nC += 1

    for zona, n in [("A", nA), ("B", nB), ("C", nC)]:
        historial_zonas[zona].append(n)
        if len(historial_zonas[zona]) > VENTANA:
            historial_zonas[zona].pop(0)

    estA = estancia_media("A")
    estB = estancia_media("B")

    # ── Clasificacion por TIPO ─────────────────────────────────────────
    counts = {"mobile": 0, "laptop": 0, "iot": 0, "other": 0}
    for rssi in rssi_lista:
        counts[classify_device(rssi)] += 1

    alertas = 0
    if ocupacion >= 90:                alertas += 1
    if rssi_medio < -75 and total > 0: alertas += 1

    # ── Log consola ────────────────────────────────────────────────────
    print(f"  Dispositivos: {total}  |  Ocupacion: {ocupacion}%  |  Dist media: {dist_media}m")
    print(f"  Zonas  -> A: {nA} ({estA}min)  B: {nB} ({estB}min)  C: {nC}")
    print(f"  Tipos  -> moviles:{counts['mobile']} portatiles:{counts['laptop']} iot:{counts['iot']} otros:{counts['other']} alertas:{alertas}")

    # ── ENVIO canal GENERAL ────────────────────────────────────────────
    enviar_canal(API_KEY_GENERAL, "General ", {
        "field1": rssi_medio,
        "field2": total,
        "field3": ocupacion,
        "field4": counts["mobile"],
        "field5": counts["laptop"],
        "field6": counts["iot"],
        "field7": counts["other"],
        "field8": alertas,
    })

    time.sleep(PAUSA_ENTRE_CANALES)   # esperar 15s antes del segundo envio

    # ── ENVIO canal OFICINAS ───────────────────────────────────────────
    enviar_canal(API_KEY_OFICINAS, "Oficinas", {
        "field1": rssi_medio,
        "field2": total,
        "field3": ocupacion,
        "field4": nA,
        "field5": nB,
        "field6": nC,
        "field7": estA,
        "field8": estB,
    })

    print("-" * 52)
    time.sleep(PAUSA_FINAL)           # esperar 15s mas antes del siguiente ciclo
