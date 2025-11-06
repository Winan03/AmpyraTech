# api/index.py
import os
from mangum import Mangum

# Forzar que el directorio de trabajo sea la raíz del proyecto
os.chdir(os.path.dirname(os.path.dirname(__file__)))

try:
    from app.main import app
    handler = Mangum(app)
    print("API loaded successfully")
except Exception as e:
    print("FATAL ERROR:")
    import traceback
    traceback.print_exc()
    raise