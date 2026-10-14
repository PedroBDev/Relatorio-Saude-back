from pydantic import BaseModel, EmailStr, ConfigDict

class UserCreate(BaseModel):
    nome : str
    email : EmailStr
    password : str
    municipio_id : int 

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)    

    id: int
    nome: str
    email: EmailStr
    municipio_id: int


class LoginRequest(BaseModel):
    email: EmailStr
    password: str