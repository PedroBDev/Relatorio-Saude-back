from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    nome : str
    email : EmailStr
    password : str
    municipio_id : int | None = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str