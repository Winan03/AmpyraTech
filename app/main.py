from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.routers.data_api import router as data_router
from app.db.firebase import get_current_data

app = FastAPI(title="SafyraShield API - Sprint 1")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include API router
app.include_router(data_router, prefix="/api")

# Templates
templates = Jinja2Templates(directory="app/templates")

@app.get("/")
async def root(request: Request):
    """
    Página principal del dashboard de monitoreo
    """
    result = get_current_data()
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "sensors": result["sensors"],
        "connected": result["connected"],
        "connection_status": result["message"],
        "umbral_corriente": result["umbral_corriente"],
        "umbral_potencia": result["umbral_potencia"]
    })

@app.get("/health")
async def health_check():
    """
    Endpoint para verificar el estado del servidor
    """
    return {
        "status": "online",
        "service": "SafyraShield IoT Monitor",
        "version": "1.0.0 - Sprint 1"
    }