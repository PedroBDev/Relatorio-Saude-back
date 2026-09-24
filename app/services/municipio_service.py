from sqlalchemy.orm import Session

from app.models.municipio import Municipio
from app.schemas.municipio_schema import MunicipioCreate

def create_municipio(db: Session, municipio: MunicipioCreate) -> Municipio:

    new_municipio = Municipio(
        nome=municipio.nome,
        uf=municipio.uf
    )

    db.add(new_municipio)
    db.commit()
    db.refresh(new_municipio)

    return new_municipio