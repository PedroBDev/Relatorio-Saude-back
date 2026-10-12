from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user 
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User 
from app.schemas.user import LoginRequest, UserCreate, UserResponse
from app.services.auth_service import authenticate_user, create_user


router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)


@router.post("/register", response_model=UserResponse)
def register_user(user_data : UserCreate, db : Session = Depends(get_db)):
    try : 
        return create_user(db, user_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login")
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, login_data.email, login_data.password)

    if not user:
        raise HTTPException(status_code=401, detail="Credenciais inválidas.")

    access_token = create_access_token(user.id)

    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user    