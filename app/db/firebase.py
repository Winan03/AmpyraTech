import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv
import os
from typing import List, Dict
from datetime import datetime

load_dotenv()

# Inicializar Firebase
cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
database_url = os.getenv("FIREBASE_DATABASE_URL")

if not cred_path or not database_url:
    raise ValueError("Missing Firebase credentials or database URL in .env")

if not firebase_admin._apps:
    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {
            'databaseURL': database_url
        })
        print("Firebase initialized successfully")
    except Exception as e:
        raise Exception(f"Failed to initialize Firebase: {str(e)}")

# IDs de los 3 sensores según el código Arduino
SENSOR_IDS = ["LAB-PC-01", "LAB-PC-02", "LAB-PC-03"]

# Umbral de sobrecarga (10% sobre 10A = 11A según tu Project Charter)
UMBRAL_CORRIENTE = 11.0  # Amperios
UMBRAL_POTENCIA = 2420.0  # Watts (11A * 220V)

def get_current_data() -> dict:
    """
    Obtiene los datos actuales de los 3 sensores desde /current_data
    """
    try:
        ref = db.reference('/current_data')
        data = ref.get()
        
        sensors_data = []
        any_connected = False
        
        if data:
            for sensor_id in SENSOR_IDS:
                if sensor_id in data:
                    sensor_info = data[sensor_id]
                    irms = float(sensor_info.get('irms', 0.0))
                    potencia = float(sensor_info.get('potencia', 0.0))
                    
                    # Determinar si hay sobrecarga
                    is_overload = irms >= UMBRAL_CORRIENTE
                    
                    sensors_data.append({
                        "id": sensor_id,
                        "irms": irms,
                        "potencia": potencia,
                        "is_overload": is_overload,
                        "timestamp": sensor_info.get('timestamp', '')
                    })
                    any_connected = True
                else:
                    # Sensor sin datos
                    sensors_data.append({
                        "id": sensor_id,
                        "irms": 0.0,
                        "potencia": 0.0,
                        "is_overload": False,
                        "timestamp": ""
                    })
            
            return {
                "sensors": sensors_data,
                "connected": any_connected,
                "message": "Conectado" if any_connected else "Sin datos",
                "timestamp": datetime.now().isoformat(),
                "umbral_corriente": UMBRAL_CORRIENTE,
                "umbral_potencia": UMBRAL_POTENCIA
            }
        else:
            # No hay datos en Firebase
            return {
                "sensors": [
                    {"id": sid, "irms": 0.0, "potencia": 0.0, "is_overload": False, "timestamp": ""}
                    for sid in SENSOR_IDS
                ],
                "connected": False,
                "message": "Sin datos disponibles",
                "timestamp": datetime.now().isoformat(),
                "umbral_corriente": UMBRAL_CORRIENTE,
                "umbral_potencia": UMBRAL_POTENCIA
            }
            
    except Exception as e:
        print(f"Error al obtener datos de Firebase: {str(e)}")
        return {
            "sensors": [
                {"id": sid, "irms": 0.0, "potencia": 0.0, "is_overload": False, "timestamp": ""}
                for sid in SENSOR_IDS
            ],
            "connected": False,
            "message": f"Error: {str(e)}",
            "timestamp": datetime.now().isoformat(),
            "umbral_corriente": UMBRAL_CORRIENTE,
            "umbral_potencia": UMBRAL_POTENCIA
        }

def get_history_data(sensor_id: str, limit: int = 20) -> List[Dict]:
    """
    Obtiene el historial de un sensor específico para graficar
    """
    try:
        ref = db.reference(f'/history/{sensor_id}')
        data = ref.order_by_key().limit_to_last(limit).get()
        
        if data:
            history = []
            for key, value in data.items():
                history.append({
                    "timestamp": key,
                    "irms": float(value.get('irms', 0.0)),
                    "potencia": float(value.get('potencia', 0.0)),
                    "estado": value.get('estado', 'Normal')
                })
            return history
        return []
    except Exception as e:
        print(f"Error al obtener historial: {str(e)}")
        return []

def check_connection() -> bool:
    """
    Verifica si la conexión con Firebase está activa
    """
    try:
        ref = db.reference('/current_data')
        ref.get()
        return True
    except Exception as e:
        print(f"Error al verificar conexión: {str(e)}")
        return False