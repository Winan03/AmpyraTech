# api/index.py
import traceback

try:
    from app.main import app
    from mangum import Mangum
    handler = Mangum(app)
    print("App loaded successfully")
except Exception as e:
    print("FATAL ERROR LOADING APP:")
    print(traceback.format_exc())
    raise