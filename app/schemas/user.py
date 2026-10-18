from pydantic import BaseModel, EmailStr, ConfigDict

class UserCreate(BaseModel):
    nome : str
    email : EmailStr
    password : str
    municipio_id : int | None = None
    role : str

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)    

    id: int
    nome: str
    email: EmailStr
    municipio_id: int | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    nome: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    municipio_id: int | None = None 
    role: str | None = None