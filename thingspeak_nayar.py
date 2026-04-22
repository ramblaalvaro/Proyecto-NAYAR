import requests
import time
import subprocess
import re
from datetime import datetime, date
from collections import defaultdict

# ══════════════════════════════════════════════════════════════════════
#  CANALES THINGSPEAK
# ══════════════════════════════════════════════════════════════════════

# Canal GENERAL — tipos de dispositivo + alertas
API_KEY_GENERAL   = "TSXNP7UL4V51O25E"
CANAL_GENERAL     = "3285772"

# Canal OFICINAS — zonas + estancias (demo_nuevo.html)
API_KEY_OFICINAS  = "1EUF2CEJOXZRO2O0"
CANAL_OFICINAS    = "3349520"

# Canal HOSTELERÍA & RETAIL — 5 campos nuevos
API_KEY_RETAIL    = "Z9DNFOL6F9A336WG"
CANAL_RETAIL      = "3349550"

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
#
#  CANAL HOSTELERÍA & RETAIL  (field1-5)
#  field1 → Dispositivos detectados
#  field2 → Ocupacion (%)
#  field3 → Clientes diarios (acumulado)
#  field4 → Clientes ultima hora (ventana 60 min)
#  field5 → Tendencia semanal (media movil 7 dias)

URL = "https://api.thingspeak.com/update"

# ── AJUSTES ────────────────────────────────────────────────────────────
INTERFACE    = "wlan0"
MAX_CAPACITY = 30     # dispositivos = aforo 100%
ZONA_A_MAX   =  5.0   # metros — Zona A (Oficinas)
ZONA_B_MAX   = 15.0   # metros — Zona B (Salas)
VENTANA      = 10     # ciclos para promediar estancia

# Con 3 canales: 15s + 15s + 15s entre envíos = ciclo de ~45s
# ThingSpeak free permite 1 envío cada 15s por canal
PAUSA_ENTRE_CANALES = 15
PAUSA_FINAL         = 15

# ── ESTADO GENERAL ─────────────────────────────────────────────────────
historial_zonas = defaultdict(list)
ciclo = 0

# ── ESTADO HOSTELERÍA & RETAIL ─────────────────────────────────────────
_hoy_retail        = date.today()
clientes_diarios   = 0
_dispositivos_ant  = 0
_max_hoy           = 0
_historial_7d      = []          # lista de (fecha, dispositivos_max)
_ultima_hora       = []          # [(timestamp, dispositivos)] ventana 60 min

# ── FUNCIONES COMUNES ──────────────────────────────────────────────────
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

# ── FUNCIONES HOSTELERÍA & RETAIL ──────────────────────────────────────
def reset_diario_retail():
    """Resetea contadores al comenzar un nuevo día."""
    global clientes_diarios, _dispositivos_ant, _max_hoy, _hoy_retail, _ultima_hora
    if _max_hoy > 0:
        _historial_7d.append((_hoy_retail, _max_hoy))
        if len(_historial_7d) > 7:
            _historial_7d.pop(0)
    clientes_diarios  = 0
    _dispositivos_ant = 0
    _max_hoy          = 0
    _ultima_hora      = []
    _hoy_retail       = date.today()
    print(f"  [i] Retail — nuevo día, contadores reseteados ({_hoy_retail})")

def calcular_campos_retail(total):
    """
    Calcula los 5 campos del canal Hostelería & Retail a partir
    del número total de dispositivos detectados en este ciclo.
    """
    global clientes_diarios, _dispositivos_ant, _max_hoy, _ultima_hora

    # field1 — dispositivos detectados (directo)
    f1 = total

    # field2 — ocupación % (igual que los otros canales)
    f2 = min(100, round((total / MAX_CAPACITY) * 100))

    # field3 — clientes diarios acumulados
    # Si hay más dispositivos que en el ciclo anterior → nuevas entradas
    if total > _dispositivos_ant:
        clientes_diarios += (total - _dispositivos_ant)
    _dispositivos_ant = total
    f3 = clientes_diarios

    # Actualiza máximo del día para el historial semanal
    if total > _max_hoy:
        _max_hoy = total

    # field4 — clientes última hora (ventana deslizante 60 min)
    ts_ahora = datetime.now().timestamp()
    _ultima_hora.append((ts_ahora, total))
    _ultima_hora[:] = [(ts, v) for ts, v in _ultima_hora if ts_ahora - ts <= 3600]
    f4 = sum(v for _, v in _ultima_hora)

    # field5 — tendencia semanal (media móvil de dispositivos máx. 7 días)
    if _historial_7d:
        f5 = round(sum(v for _, v in _historial_7d) / len(_historial_7d), 1)
    else:
        f5 = 0

    return f1, f2, f3, f4, f5


# ── INICIO ─────────────────────────────────────────────────────────────
print("=" * 56)
print("  NAYAR - Sensor WiFi activo")
print(f"  Canal General        : {CANAL_GENERAL}")
print(f"  Canal Oficinas       : {CANAL_OFICINAS}")
print(f"  Canal Hostelería+Retail : {CANAL_RETAIL}")
print(f"  Zona A: 0-{ZONA_A_MAX}m  |  Zona B: {ZONA_A_MAX}-{ZONA_B_MAX}m  |  Zona C: >{ZONA_B_MAX}m")
print(f"  Ciclo: {PAUSA_ENTRE_CANALES*2+PAUSA_FINAL}s  ({PAUSA_ENTRE_CANALES}s entre canales + {PAUSA_FINAL}s espera final)")
print("=" * 56)

# ── BUCLE PRINCIPAL ────────────────────────────────────────────────────
while True:
    ciclo += 1
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Ciclo {ciclo}")

    # Reset si cambió el día
    if date.today() != _hoy_retail:
        reset_diario_retail()

    rssi_lista = escanear_wifi()

    if not rssi_lista:
        print("  Sin senales. Reintentando en 15s...")
        time.sleep(15)
        continue

    # ── Métricas comunes ───────────────────────────────────────────────
    rssi_medio = round(sum(rssi_lista) / len(rssi_lista), 1)
    total      = len(rssi_lista)
    ocupacion  = min(100, round((total / MAX_CAPACITY) * 100))
    dist_media = rssi_to_metros(rssi_medio)

    # ── Clasificación por ZONA ─────────────────────────────────────────
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

    # ── Clasificación por TIPO ─────────────────────────────────────────
    counts = {"mobile": 0, "laptop": 0, "iot": 0, "other": 0}
    for rssi in rssi_lista:
        counts[classify_device(rssi)] += 1

    alertas = 0
    if ocupacion >= 90:                alertas += 1
    if rssi_medio < -75 and total > 0: alertas += 1

    # ── Campos Hostelería & Retail ─────────────────────────────────────
    r_f1, r_f2, r_f3, r_f4, r_f5 = calcular_campos_retail(total)

    # ── Log consola ────────────────────────────────────────────────────
    print(f"  Dispositivos: {total}  |  Ocupacion: {ocupacion}%  |  Dist media: {dist_media}m")
    print(f"  Zonas  -> A: {nA} ({estA}min)  B: {nB} ({estB}min)  C: {nC}")
    print(f"  Tipos  -> moviles:{counts['mobile']} portatiles:{counts['laptop']} iot:{counts['iot']} otros:{counts['other']} alertas:{alertas}")
    print(f"  Retail -> disp:{r_f1} ocup:{r_f2}% diarios:{r_f3} hora:{r_f4} tend7d:{r_f5}")

    # ── ENVÍO canal GENERAL ────────────────────────────────────────────
    enviar_canal(API_KEY_GENERAL, "General       ", {
        "field1": rssi_medio,
        "field2": total,
        "field3": ocupacion,
        "field4": counts["mobile"],
        "field5": counts["laptop"],
        "field6": counts["iot"],
        "field7": counts["other"],
        "field8": alertas,
    })

    time.sleep(PAUSA_ENTRE_CANALES)

    # ── ENVÍO canal OFICINAS ───────────────────────────────────────────
    enviar_canal(API_KEY_OFICINAS, "Oficinas      ", {
        "field1": rssi_medio,
        "field2": total,
        "field3": ocupacion,
        "field4": nA,
        "field5": nB,
        "field6": nC,
        "field7": estA,
        "field8": estB,
    })

    time.sleep(PAUSA_ENTRE_CANALES)

    # ── ENVÍO canal HOSTELERÍA & RETAIL ───────────────────────────────
    enviar_canal(API_KEY_RETAIL, "Hosteleria+Retail", {
        "field1": r_f1,   # dispositivos detectados
        "field2": r_f2,   # ocupación %
        "field3": r_f3,   # clientes diarios
        "field4": r_f4,   # clientes última hora
        "field5": r_f5,   # tendencia semanal (media 7d)
    })

    print("-" * 56)
    time.sleep(PAUSA_FINAL)
