import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv
import os
from app.models.data import Data  # Importar el modelo Pydantic

load_dotenv()

# Inicializar Firebase
cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
database_url = os.getenv("FIREBASE_DATABASE_URL")

if not firebase_admin._apps:
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred, {
        'databaseURL': database_url
    })

# Función mock para simular lectura de Firebase (retorna valores estáticos)
def get_latest_data() -> Data:
    # En futuras iteraciones, reemplazar con lectura real: db.reference('/path/to/node').get()
    return Data(irms=1.5, power=330.0)