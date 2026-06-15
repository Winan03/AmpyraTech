from app.db.firebase import db

try:
    users = db.reference("/app_users").get()
    print("Usuarios en la base de datos:")
    for key, value in (users or {}).items():
        if isinstance(value, dict):
            print(f" - {key}: {value.get('email')} ({value.get('role')}) status: {value.get('status')}")
except Exception as e:
    print(f"Error: {e}")
