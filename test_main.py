from app.main import app
from app.routers.auth_api import _firebase_auth_enabled

print("Auth enabled after main import:", _firebase_auth_enabled())
