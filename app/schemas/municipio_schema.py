from pydantic import BaseModel, ConfigDict

class MunicipioCreate(BaseModel):
    nome: str
    uf: str

class MunicipioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str    
    uf: str
    