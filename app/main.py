from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from app.routers.data_api import router as data_router
from app.db.firebase import get_latest_data

app = FastAPI(title="SafyraShield API")

app.include_router(data_router, prefix="/api")

templates = Jinja2Templates(directory="app/templates")
@app.get("/")
async def root(request: Request):
    data = get_latest_data()  
    return templates.TemplateResponse("index.html", {
        "request": request,
        "irms": data.irms,
        "power": data.power,
        "connection_status": "Conectado"  
    })