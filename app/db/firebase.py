import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv
import os
import json
import base64  # <--- 1. IMPORTANTE: Añade esta línea
from typing import List, Dict
from datetime import datetime

# ==================================
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter
# ==================================

load_dotenv()

# ======================================================================
# INICIALIZACIÓN DE FIREBASE (Modificado para Base64)
# ======================================================================

database_url = os.getenv("FIREBASE_DATABASE_URL")
cred_json_content = os.getenv("FIREBASE_PRIVATE_KEY_JSON") # Esto ahora será el texto Base64
cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")

if not database_url:
    raise ValueError("ERROR FATAL: FIREBASE_DATABASE_URL no está configurada en el entorno.")

if not firebase_admin._apps:
    try:
        cred = None
        if cred_json_content:
            print("Inicializando Firebase con credenciales JSON (Modo Vercel)...")
            
            # --- 2. INICIO DE LA MODIFICACIÓN ---
            # Decodifica el string Base64 a un string JSON normal
            print("Decodificando credenciales Base64...")
            decoded_json_string = base64.b64decode(cred_json_content).decode('utf-8')
            service_account_info = json.loads(decoded_json_string)
            # --- FIN DE LA MODIFICACIÓN ---
            
            cred = credentials.Certificate(service_account_info)
            
        elif cred_path:
            print(f"Inicializando Firebase con ruta de archivo: {cred_path} (Modo Local)...")
            if not os.path.exists(cred_path):
                raise FileNotFoundError(f"El archivo de credenciales no se encuentra en la ruta: {cred_path}")
            cred = credentials.Certificate(cred_path)
        else:
            raise ValueError("No se encontró 'FIREBASE_PRIVATE_KEY_JSON' ni 'FIREBASE_CREDENTIALS_PATH'. Revisa tu .env")

        firebase_admin.initialize_app(cred, {
            'databaseURL': database_url
        })
        print("Firebase initialized successfully")
        
    except Exception as e:
        # Imprime un error más detallado si falla la decodificación o inicialización
        print(f"ERROR FATAL AL INICIALIZAR FIREBASE: {str(e)}")
        raise Exception(f"Failed to initialize Firebase: {str(e)}")

# ======================================================================
# ¡FUNCIÓN DE DETECCIÓN MODIFICADA!
# ======================================================================

def detect_device_type(irms: float, threshold: float) -> dict:
    """
    Detecta el tipo de dispositivo basándose en el consumo Y EL UMBRAL.
    Retorna: {type, icon, description, color}
    """
    
    # 1. ¡REVISAR SOBRECARGA PRIMERO!
    if irms >= threshold:
        # Sobrecarga masiva (posible cortocircuito)
        if irms >= 15.0: 
            return {
                "type": "¡PICO EXTREMO!",
                "icon": "💥",
                "description": f"Cortocircuito o falla grave detectada ({irms:.2f}A)",
                "color": "#ff0000"
            }
        # Sobrecarga "normal"
        else:
            return {
                "type": "SOBRECARGA",
                "icon": "⚠️",
                "description": f"Consumo ({irms:.2f}A) supera el umbral ({threshold:.1f}A)",
                "color": "#e74c3c" # Rojo peligro
            }

    # 2. SI NO ES SOBRECARGA, identificar el dispositivo
    if irms < 0.01:
        return {
            "type": "Sin carga",
            "icon": "🔌",
            "description": "No hay dispositivos conectados",
            "color": "#95a5a6"
        }
    elif 0.01 <= irms < 0.1:
        return {
            "type": "Audífonos / Carga baja",
            "icon": "🎧",
            "description": "Carga de audífonos o dispositivo de bajo consumo",
            "color": "#3498db"
        }
    elif 0.1 <= irms < 1.5:
        return {
            "type": "Cargador de celular",
            "icon": "📱",
            "description": "Smartphone o tablet en carga",
            "color": "#27ae60"
        }
    elif 1.5 <= irms < 4.0:
        return {
            "type": "Laptop",
            "icon": "💻",
            "description": "Laptop en uso o carga",
            "color": "#f39c12"
        }
    elif 4.0 <= irms < 8.0:
        return {
            "type": "PC de escritorio",
            "icon": "🖥️",
            "description": "Computadora de escritorio (CPU + Monitor)",
            "color": "#e67e22"
        }
    
    # 3. Rango entre "PC" y el umbral: Carga alta pero segura
    elif 8.0 <= irms < threshold:
        return {
            "type": "Múltiples dispositivos",
            "icon": "⚡",
            "description": "Varios dispositivos conectados o carga alta",
            "color": "#e67e22" # Naranja (advertencia, no peligro)
        }
    
    # Fallback (no debería ocurrir)
    return {
        "type": "Desconocido",
        "icon": "❓",
        "description": f"Consumo no catalogado: {irms:.2f}A",
        "color": "#95a5a6"
    }


# ======================================================================
# UMBRALES CONFIGURABLES POR SENSOR (Sin cambios)
# ======================================================================

SENSOR_IDS = ["LAB-PC-01", "LAB-PC-02", "LAB-PC-03"]

DEFAULT_THRESHOLDS = {
    "LAB-PC-01": {"corriente": 11.0, "potencia": 2420.0},
    "LAB-PC-02": {"corriente": 11.0, "potencia": 2420.0},
    "LAB-PC-03": {"corriente": 11.0, "potencia": 2420.0}
}

def get_sensor_threshold(sensor_id: str) -> dict:
    try:
        ref = db.reference(f'/config/thresholds/{sensor_id}')
        threshold = ref.get()
        if threshold:
            return threshold
        else:
            default = DEFAULT_THRESHOLDS.get(sensor_id, {"corriente": 11.0, "potencia": 2420.0})
            ref.set(default) 
            return default
    except Exception as e:
        print(f"Error al obtener umbral: {str(e)}")
        return DEFAULT_THRESHOLDS.get(sensor_id, {"corriente": 11.0, "potencia": 2420.0})

def update_sensor_threshold(sensor_id: str, corriente: float, potencia: float) -> bool:
    try:
        ref = db.reference(f'/config/thresholds/{sensor_id}')
        ref.set({
            "corriente": corriente,
            "potencia": potencia,
            "updated_at": datetime.now().isoformat()
        })
        return True
    except Exception as e:
        print(f"Error al actualizar umbral: {str(e)}")
        return False

# ======================================================================
# ¡FUNCIÓN DE LECTURA MODIFICADA!
# ======================================================================

def get_current_data() -> dict:
    """
    Obtiene los datos actuales con detección de dispositivos MEJORADA.
    """
    try:
        ref = db.reference('/current_data')
        data = ref.get()
        
        sensors_data = []
        any_connected = False
        total_consumption = 0
        
        if data:
            for sensor_id in SENSOR_IDS:
                # 1. Obtener umbral específico del sensor
                threshold = get_sensor_threshold(sensor_id)
                
                if sensor_id in data:
                    sensor_info = data[sensor_id]
                    irms = float(sensor_info.get('irms', 0.0))
                    potencia = float(sensor_info.get('potencia', 0.0))
                    
                    # 2. Determinar si hay sobrecarga
                    is_overload = irms >= threshold["corriente"]
                    
                    # 3. ¡LÓGICA MEJORADA!
                    #    Pasamos el 'irms' Y el 'threshold' a la función
                    device_info = detect_device_type(irms, threshold["corriente"])
                    
                    sensors_data.append({
                        "id": sensor_id,
                        "irms": irms,
                        "potencia": potencia,
                        "is_overload": is_overload,
                        "timestamp": sensor_info.get('timestamp', ''),
                        "device": device_info,       # Info del dispositivo (ahora es más inteligente)
                        "threshold": threshold      # Info del umbral
                    })
                    
                    total_consumption += potencia
                    any_connected = True
                else:
                    # Sensor sin datos
                    sensors_data.append({
                        "id": sensor_id, "irms": 0.0, "potencia": 0.0, "is_overload": False,
                        "timestamp": "", 
                        "device": detect_device_type(0.0, threshold["corriente"]), # "Sin carga"
                        "threshold": threshold
                    })
            
            return {
                "sensors": sensors_data, "connected": any_connected,
                "message": "Sistema activo" if any_connected else "Sin dispositivos conectados",
                "timestamp": datetime.now().isoformat(), "total_consumption": total_consumption
            }
        else:
            # No hay datos en Firebase
            return {
                "sensors": [
                    {
                        "id": sid, "irms": 0.0, "potencia": 0.0, "is_overload": False, 
                        "timestamp": "", "device": detect_device_type(0.0, get_sensor_threshold(sid)["corriente"]),
                        "threshold": get_sensor_threshold(sid)
                    } for sid in SENSOR_IDS
                ],
                "connected": False, "message": "Sin datos disponibles",
                "timestamp": datetime.now().isoformat(), "total_consumption": 0
            }
            
    except Exception as e:
        print(f"Error al obtener datos de Firebase: {str(e)}")
        # Devuelve una estructura de error que el frontend pueda manejar
        return {
            "sensors": [
                {
                    "id": sid, "irms": 0.0, "potencia": 0.0, "is_overload": False, 
                    "timestamp": "", "device": detect_device_type(0.0, get_sensor_threshold(sid)["corriente"]),
                    "threshold": get_sensor_threshold(sid)
                } for sid in SENSOR_IDS
            ],
            "connected": False, "message": f"Error de conexión: {str(e)}",
            "timestamp": datetime.now().isoformat(), "total_consumption": 0
        }

# ======================================================================
# ¡FUNCIONES DE HISTORIAL Y ALERTAS MODIFICADAS!
# ======================================================================

def get_history_data(sensor_id: str, limit: int = 20, start_date: str = None, end_date: str = None) -> List[Dict]:
    """
    Obtiene el historial con filtros de fecha (HU-010)
    """
    try:
        ref = db.reference(f'/history/{sensor_id}')
        threshold = get_sensor_threshold(sensor_id)["corriente"] # Obtener umbral
        
        if start_date and end_date:
            data = ref.order_by_key().start_at(start_date).end_at(end_date).get()
        else:
            data = ref.order_by_key().limit_to_last(limit).get()
        
        if data:
            history = []
            for key, value in data.items():
                irms = float(value.get('irms', 0.0))
                # Usamos la nueva lógica de detección aquí también
                device_info = detect_device_type(irms, threshold) 
                
                history.append({
                    "timestamp": key,
                    "irms": irms,
                    "potencia": float(value.get('potencia', 0.0)),
                    "estado": value.get('estado', 'Normal'), # El estado sigue siendo el mismo
                    "device": device_info # Pero la info del dispositivo es más rica
                })
            return history
        return []
    except Exception as e:
        print(f"Error al obtener historial: {str(e)}")
        return []

def get_alert_history(start_date: str = None, end_date: str = None) -> List[Dict]:
    """
    Obtiene un historial de ÚNICAMENTE los eventos de sobrecarga.
    """
    try:
        all_alerts = []
        for sensor_id in SENSOR_IDS:
            ref = db.reference(f'/history/{sensor_id}')
            threshold = get_sensor_threshold(sensor_id) # Obtener umbral como dict
            
            query = ref.order_by_child('estado').equal_to('Sobrecarga')
            data = query.get()
            
            if data:
                for key, value in data.items():
                    if start_date and key < start_date:
                        continue
                    if end_date and key > end_date:
                        continue

                    irms = float(value.get('irms', 0.0))
                    # Usamos la nueva lógica de detección aquí también
                    device_info = detect_device_type(irms, threshold["corriente"])
                    
                    all_alerts.append({
                        "sensor_id": sensor_id,
                        "timestamp": key,
                        "irms": irms,
                        "potencia": float(value.get('potencia', 0.0)),
                        "estado": value.get('estado', 'Sobrecarga'),
                        "device": device_info,
                        "threshold": threshold 
                    })
        
        all_alerts.sort(key=lambda x: x['timestamp'], reverse=True)
        return all_alerts
        
    except Exception as e:
        print(f"Error al obtener historial de alertas: {str(e)}")
        return []

# ======================================================================
# FUNCIONES DE EXPORTACIÓN (Sin cambios)
# ======================================================================

def export_history_csv(sensor_id: str = None, start_date: str = None, end_date: str = None) -> str:
    try:
        if sensor_id:
            sensors = [sensor_id]
        else:
            sensors = SENSOR_IDS
        
        csv_data = "Sensor ID,Fecha/Hora,Corriente (A),Potencia (W),Dispositivo,Estado\n"
        
        for sid in sensors:
            history = get_history_data(sid, limit=1000, start_date=start_date, end_date=end_date)
            for record in history:
                csv_data += f"{sid},{record['timestamp']},{record['irms']:.3f},{record['potencia']:.2f},{record['device']['type']},{record['estado']}\n"
        
        return csv_data
    except Exception as e:
        print(f"Error al exportar CSV: {str(e)}")
        return ""

def check_connection() -> bool:
    try:
        ref = db.reference('/current_data')
        ref.get()
        return True
    except Exception as e:
        print(f"Error al verificar conexión: {str(e)}")
        return False
    
def export_history_excel(sensor_id: str = None, start_date: str = None, end_date: str = None) -> bytes:
    try:
        if sensor_id:
            sensors = [sensor_id]
        else:
            sensors = SENSOR_IDS
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Historial SafyraShield"
        
        header_font = Font(bold=True, color="FFFFFF", name="Inter")
        header_fill = PatternFill(start_color="0A0E27", end_color="0A0E27", fill_type="solid")
        cell_font = Font(name="Inter")
        center_align = Alignment(horizontal="center", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")
        thin_border = Border(left=Side(style='thin'), 
                             right=Side(style='thin'), 
                             top=Side(style='thin'), 
                             bottom=Side(style='thin'))

        headers = ["Sensor ID", "Fecha/Hora (ISO)", "Corriente (A)", "Potencia (W)", "Dispositivo Detectado", "Estado"]
        ws.append(headers)
        
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = thin_border
            cell.alignment = center_align
            ws.row_dimensions[1].height = 25

        row_idx = 2
        for sid in sensors:
            history = get_history_data(sid, limit=1000, start_date=start_date, end_date=end_date)
            for record in history:
                row_data = [
                    sid,
                    record['timestamp'],
                    record['irms'],
                    record['potencia'],
                    record['device']['type'],
                    record['estado']
                ]
                ws.append(row_data)
                
                for col_num in range(1, len(headers) + 1):
                    cell = ws.cell(row=row_idx, column=col_num)
                    cell.border = thin_border
                    cell.font = cell_font
                    if col_num in [1, 5, 6]: cell.alignment = center_align
                    else: cell.alignment = left_align
                    if col_num == 3: cell.number_format = '0.000 "A"'
                    if col_num == 4: cell.number_format = '0.00 "W"'
                
                ws.row_dimensions[row_idx].height = 20
                row_idx += 1
        
        ws.column_dimensions[get_column_letter(1)].width = 15
        ws.column_dimensions[get_column_letter(2)].width = 28
        ws.column_dimensions[get_column_letter(3)].width = 15
        ws.column_dimensions[get_column_letter(4)].width = 15
        ws.column_dimensions[get_column_letter(5)].width = 25
        ws.column_dimensions[get_column_letter(6)].width = 12
        
        with io.BytesIO() as buffer:
            wb.save(buffer)
            return buffer.getvalue()

    except Exception as e:
        print(f"Error al exportar Excel: {str(e)}")
        return b""