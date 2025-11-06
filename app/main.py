# app/main.py
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from routers.data_api import router as data_router
from routers.auth_api import router as auth_router
import os

app = FastAPI(title="SafyraShield API - Sprint 3")

# RUTAS ABSOLUTAS (funciona en Vercel y local)
BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Routers
app.include_router(data_router, prefix="/api")
app.include_router(auth_router)

# Rutas HTML
@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/history")
async def history_page(request: Request):
    return templates.TemplateResponse("history.html", {"request": request})

@app.get("/alerts")
async def alerts_page(request: Request):
    return templates.TemplateResponse("alerts.html", {"request": request})

@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "service": "SafyraShield IoT Monitor",
        "version": "3.0.0 - Sprint 3"
    }