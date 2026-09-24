from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.user import UserCreate
from app.services.auth_service import create_user, authenticate_user
from app.core.security import create_access_token


router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)


@router.post("/register")
def register_user(user_data : UserCreate, db : Session = Depends(get_db)):
    try : 
        user  = create_user(db, user_data)

        return {"Message" : "Usuário criado com sucesso", "user" : user}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login")
def login(email: str, password: str, db: Session = Depends(get_db)):
    user = authenticate_user(db, email, password)

    if not user:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    access_token = create_access_token(user.id)

    return {"access_token": access_token, "token_type": "bearer"}