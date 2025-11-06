from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.routers.data_api import router as data_router
from app.routers.auth_api import router as auth_router 

app = FastAPI(title="SafyraShield API - Sprint 3")

# CORREGIDO: rutas relativas desde app/main.py
app.mount("/static", StaticFiles(directory="static"), name="static") 
templates = Jinja2Templates(directory="templates")

# 3. Incluir routers de API
app.include_router(data_router, prefix="/api")
app.include_router(auth_router) # Para /token

# ======================================================================
# ENDPOINTS DE PÁGINAS (HTML)
# ======================================================================

@app.get("/login")
async def login_page(request: Request):
    """Sirve la página de inicio de sesión"""
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/")
async def root(request: Request):
    """SirVE la página principal del dashboard"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/history")
async def history_page(request: Request):
    """Sirve la página de historial"""
    return templates.TemplateResponse("history.html", {"request": request})

# ======================================================================
# ¡NUEVA RUTA DE PÁGINA DE ALERTAS!
# ======================================================================
@app.get("/alerts")
async def alerts_page(request: Request):
    """Sirve la página de registro de alertas"""
    return templates.TemplateResponse("alerts.html", {"request": request})
# ======================================================================

# ======================================================================
# HEALTH CHECK
# ======================================================================
@app.get("/health")
async def health_check():
    """
    Endpoint para verificar el estado del servidor
    """
    return {
        "status": "online",
        "service": "SafyraShield IoT Monitor",
        "version": "3.0.0 - Sprint 3"
    }