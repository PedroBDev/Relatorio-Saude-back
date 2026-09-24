from pydantic import BaseModel

class MunicipioCreate(BaseModel):
    nome : str
    uf : str