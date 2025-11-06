import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv
import os
import json
import time
import random
from datetime import datetime

# --- CONFIGURACIÓN DE SIMULACIÓN ---
SENSOR_IDS = ["LAB-PC-01", "LAB-PC-02", "LAB-PC-03"]
UPDATE_INTERVAL_SECONDS = 3 # Intervalo de actualización (igual que tu dashboard)
SCENARIO_DURATION_SECONDS = 30 # Duración de cada escenario
# -----------------------------------

def initialize_firebase():
    """
    Se conecta a Firebase usando las mismas credenciales que tu main.py.
    """
    load_dotenv() # Carga el archivo .env

    database_url = os.getenv("FIREBASE_DATABASE_URL")
    cred_json_content = os.getenv("FIREBASE_PRIVATE_KEY_JSON")
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")

    if not database_url:
        raise ValueError("ERROR FATAL: FIREBASE_DATABASE_URL no está configurada en el .env.")

    if not firebase_admin._apps:
        try:
            cred = None
            if cred_json_content:
                print("Simulador: Inicializando Firebase con credenciales JSON (Modo Vercel)...")
                service_account_info = json.loads(cred_json_content)
                cred = credentials.Certificate(service_account_info)
            elif cred_path:
                print(f"Simulador: Inicializando Firebase con ruta de archivo: {cred_path} (Modo Local)...")
                if not os.path.exists(cred_path):
                    raise FileNotFoundError(f"El archivo de credenciales no se encuentra en la ruta: {cred_path}")
                cred = credentials.Certificate(cred_path)
            else:
                raise ValueError("No se encontró 'FIREBASE_PRIVATE_KEY_JSON' ni 'FIREBASE_CREDENTIALS_PATH'.")

            firebase_admin.initialize_app(cred, {
                'databaseURL': database_url
            })
            print("Simulador: Firebase initialized successfully.")
            
        except Exception as e:
            print(f"Simulador: Failed to initialize Firebase: {str(e)}")
            exit(1)

def get_scenario_data(sensor_id, scenario_index):
    """
    Genera los datos de simulación basados en el escenario actual.
    """
    
    # Escenario 1: Todos los sensores en estado NORMAL
    if scenario_index == 1:
        irms = random.uniform(0.5, 2.5) # Consumo normal (ej. Laptop)
        estado = "Normal"

    # Escenario 2: ¡SOBRECARGA en LAB-PC-01!
    elif scenario_index == 2:
        if sensor_id == "LAB-PC-01":
            irms = random.uniform(12.0, 14.5) # ¡PICO ALTO! (Umbral es 11.0A)
            estado = "Sobrecarga"
        else:
            irms = random.uniform(0.5, 1.5) # Los otros están normales
            estado = "Normal"
            
    # Escenario 3: ¡SOBRECARGA en LAB-PC-03 y PC-02!
    elif scenario_index == 3:
        if sensor_id == "LAB-PC-01":
            irms = random.uniform(0.1, 0.5) # PC-01 se resolvió
            estado = "Normal"
        else:
            irms = random.uniform(11.5, 13.0) # ¡PICO ALTO en los otros dos!
            estado = "Sobrecarga"
            
    # Escenario 4: Todos vuelven a la normalidad
    else:
        irms = random.uniform(0.1, 0.8) # Consumo bajo
        estado = "Normal"

    potencia = irms * 220 # Asumimos 220V
    return irms, potencia, estado

def main():
    """
    Bucle principal del simulador.
    """
    initialize_firebase()
    
    scenario_index = 1
    scenario_start_time = time.time()
    
    print("\n=============================================")
    print("🚀 SIMULADOR DE ESP32 INICIADO")
    print(f"Cambiando escenarios cada {SCENARIO_DURATION_SECONDS} segundos.")
    print("Presiona CTRL+C para detener.")
    print("=============================================\n")
    
    try:
        while True:
            # 1. Comprobar si debemos cambiar de escenario
            current_time = time.time()
            if (current_time - scenario_start_time) > SCENARIO_DURATION_SECONDS:
                scenario_index = (scenario_index % 4) + 1 # Cicla de 1 a 4
                scenario_start_time = current_time
                print("\n=============================================")
                print(f"CAMBIANDO A ESCENARIO {scenario_index}")
                print("=============================================\n")

            # 2. Generar y escribir datos para cada sensor
            for sensor_id in SENSOR_IDS:
                irms, potencia, estado = get_scenario_data(sensor_id, scenario_index)
                
                # =================================================================
                # ¡AQUÍ ESTÁ LA CORRECCIÓN!
                # Usamos timespec='seconds' para quitar los microsegundos (el ".")
                timestamp = datetime.now().isoformat(timespec='seconds')
                # =================================================================
                
                # Formato de datos que tu app espera
                current_data = {
                    'irms': irms,
                    'potencia': potencia,
                    'timestamp': timestamp
                }
                
                history_data = {
                    'irms': irms,
                    'potencia': potencia,
                    'estado': estado # ¡CLAVE! Esto es lo que lee tu bitácora de alertas
                }
                
                # 3. Escribir en Firebase (actuando como el ESP32)
                
                # Escribe en /current_data (para el dashboard en tiempo real)
                current_ref = db.reference(f'/current_data/{sensor_id}')
                current_ref.set(current_data)
                
                # Escribe en /history (para las páginas de historial y alertas)
                # El timestamp ahora es una clave válida (ej: 2025-11-05T19:05:30)
                history_ref = db.reference(f'/history/{sensor_id}/{timestamp}')
                history_ref.set(history_data)
                
                # Imprimir en consola lo que estamos haciendo
                print(f"  [{sensor_id}] -> {estado:10} | {irms:5.2f} A | {potencia:7.1f} W")
            
            print("--- (Esperando 3s)")
            time.sleep(UPDATE_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n=============================================")
        print("🛑 Simulador detenido por el usuario.")
        print("=============================================\n")
    except Exception as e:
        print(f"\n❌ ERROR EN EL SIMULADOR: {e}")

if __name__ == "__main__":
    main()