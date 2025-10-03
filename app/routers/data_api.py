from fastapi import APIRouter
from app.db.firebase import get_latest_data
from app.models.data import Data

router = APIRouter(prefix="/data", tags=["data"])

@router.get("/latest", response_model=Data)
async def read_latest_data():
    return get_latest_data()