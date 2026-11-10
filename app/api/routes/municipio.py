from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin
from app.core.database import get_db
from app.schemas.municipio_schema import MunicipioCreate, MunicipioResponse
from app.services.municipio_service import create_municipio

router = APIRouter(
    prefix="/municipios",
    tags=["municipios"]
)

@router.post("/", response_model=MunicipioResponse)
def create_municipio_endpoint(municipio: MunicipioCreate, db: Session = Depends(get_db),
                              current_admin = Depends(get_current_admin)):
    return create_municipio(db=db, municipio=municipio)