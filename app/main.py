# app/main.py
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.routers.data_api import router as data_router
from app.routers.auth_api import router as auth_router 
from app.routers.tickets_api import router as tickets_router
from app.routers.reports_api import router as reports_router
from app.services.scheduler_service import start_scheduler, shutdown_scheduler
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
app.include_router(tickets_router)
app.include_router(reports_router)

@app.on_event("startup")
async def startup_event():
    start_scheduler()

@app.on_event("shutdown")
async def shutdown_event():
    shutdown_scheduler()

# Rutas HTML
@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/terms")
async def terms_page(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request})

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/history")
async def history_page(request: Request):
    return templates.TemplateResponse("history.html", {"request": request})

@app.get("/alerts")
async def alerts_page(request: Request):
    return templates.TemplateResponse("alerts.html", {"request": request})

@app.get("/users")
async def users_page(request: Request):
    return templates.TemplateResponse("users.html", {"request": request})

@app.get("/schedule")
async def schedule_page(request: Request):
    return templates.TemplateResponse("schedule.html", {"request": request})

@app.get("/tickets")
async def tickets_page(request: Request):
    return templates.TemplateResponse("tickets.html", {"request": request})

@app.get("/reports")
async def reports_page(request: Request):
    return templates.TemplateResponse("reports.html", {"request": request})


@app.get("/health")
async def health_check():
    return {
        "status": "online",
        "service": "SafyraShield IoT Monitor",
        "version": "3.0.0 - Sprint 3"
    }
