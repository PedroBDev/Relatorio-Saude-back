from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.municipio_schema import MunicipioCreate
from app.services.municipio_service import create_municipio

router = APIRouter(
    prefix="/municipios",
    tags=["municipios"]
)

@router.post("/municipios/", response_model=MunicipioCreate)
def create_municipio_endpoint(municipio: MunicipioCreate, db: Session = Depends(get_db)):
    return create_municipio(db=db, municipio=municipio)