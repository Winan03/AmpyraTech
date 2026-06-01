"""
SIMULADOR DE CARGA - LAB-PC-01 (SafyraShield) - Versión para Alertas
"""

import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv
import os
import json
import base64
import binascii
import time
import random
from datetime import datetime
from typing import Any, Optional

# ──────────────────────────────────────────────
# ⚙️ PARÁMETROS
# ──────────────────────────────────────────────
TARGET_SENSOR         = "LAB-PC-01"
VOLTAGE               = 220
UPDATE_INTERVAL       = 3
PHASE_DURATION        = 40

CURRENT_MIN           = 3.00
CURRENT_MAX           = 3.30
# ──────────────────────────────────────────────


def load_service_account_from_env() -> Optional[dict[str, Any]]:
    cred_json_base64 = os.getenv("FIREBASE_PRIVATE_KEY_JSON_BASE64")
    cred_json_raw = os.getenv("FIREBASE_PRIVATE_KEY_JSON")

    if cred_json_base64:
        decoded_json_string = base64.b64decode(cred_json_base64).decode("utf-8")
        return json.loads(decoded_json_string)

    if cred_json_raw:
        try:
            decoded_json_string = base64.b64decode(cred_json_raw, validate=True).decode("utf-8")
            return json.loads(decoded_json_string)
        except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
            return json.loads(cred_json_raw)

    return None


def initialize_firebase() -> None:
    load_dotenv()
    database_url = os.getenv("FIREBASE_DATABASE_URL")
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")

    if firebase_admin._apps:
        return

    service_account_info = load_service_account_from_env()
    if service_account_info:
        cred = credentials.Certificate(service_account_info)
    elif cred_path:
        cred = credentials.Certificate(cred_path)
    else:
        raise ValueError("No hay credenciales de Firebase")

    firebase_admin.initialize_app(cred, {"databaseURL": database_url})
    print("✅ Firebase inicializado correctamente.\n")


def get_sensor_threshold() -> float:
    """Obtiene el umbral actual configurado para el sensor"""
    try:
        ref = db.reference(f'/config/thresholds/{TARGET_SENSOR}')
        threshold = ref.get()
        if threshold and "corriente" in threshold:
            return float(threshold["corriente"])
        return 5.0
    except Exception:
        return 5.0


def write_to_firebase(irms: float, potencia: float, estado: str, timestamp: str) -> None:
    current_data = {
        "irms": irms,
        "potencia": potencia,
        "timestamp": timestamp,
    }
    history_data = {
        "irms": irms,
        "potencia": potencia,
        "estado": estado,   # ← Este es el que importa para las alertas
    }

    db.reference(f"/current_data/{TARGET_SENSOR}").set(current_data)
    db.reference(f"/history/{TARGET_SENSOR}/{timestamp}").set(history_data)


def main() -> None:
    initialize_firebase()
    print("🚀 Simulador con soporte para Alertas\n")

    phase = 1
    step_in_phase = 0
    phase_start = time.time()
    reading_count = 0

    try:
        while True:
            irms = round(random.uniform(CURRENT_MIN, CURRENT_MAX), 3)
            potencia = round(irms * VOLTAGE, 2)
            
            threshold = get_sensor_threshold()
            
            # === CLAVE: Usamos exactamente el formato que espera la query de alertas ===
            estado = "Sobrecarga" if irms >= threshold else "Normal"
            
            timestamp = datetime.now().isoformat(timespec="seconds")

            write_to_firebase(irms, potencia, estado, timestamp)
            reading_count += 1

            print(
                f"[{timestamp}]  {irms:.3f} A | {potencia:.0f} W | "
                f"Estado: {estado} (Umbral: {threshold} A)"
            )

            step_in_phase += 1
            if (time.time() - phase_start) >= PHASE_DURATION:
                phase = (phase % 4) + 1
                step_in_phase = 0
                phase_start = time.time()
                print(f"🔄 Cambiando a Fase {phase}\n")

            time.sleep(UPDATE_INTERVAL)

    except KeyboardInterrupt:
        print(f"\n🛑 Simulador detenido. Total lecturas: {reading_count}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
