import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Cargar variables de entorno si no están cargadas
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# Singleton pattern para el cliente de Supabase
_supabase_client: Client = None

def get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY deben estar definidos en el entorno.")
        _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client
