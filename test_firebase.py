from app.routers.auth_api import _firebase_auth_enabled
from app.db.firebase import *
import firebase_admin

print("Apps:", firebase_admin._apps)
print("Auth enabled:", _firebase_auth_enabled())
