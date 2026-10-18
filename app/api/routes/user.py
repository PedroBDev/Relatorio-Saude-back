from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas.user import UserUpdate
from app.services.user_service import delete_user, get_user_by_id, get_all_users, get_user_by_email, update_user
from app.core.database import get_db
from app.api.dependencies import  get_current_admin

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/get_all")
def get_all_users_route(db: Session = Depends(get_db), current_admin = Depends(get_current_admin)):
    users = get_all_users(db)
    return users

@router.get("/get_by_email")
def get_user_by_email_route(email: str, db: Session = Depends(get_db), current_admin = Depends(get_current_admin)):
    try:
        user = get_user_by_email(db, email)
        return user
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch("/{user_id}")
def update_user_route(user_id: int, updated_data: UserUpdate, db: Session = Depends(get_db), current_admin = Depends(get_current_admin)):
    try:
        user = update_user(db, user_id, updated_data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{user_id}")
def delete_user_route(user_id: int, db: Session = Depends(get_db), current_admin = Depends(get_current_admin)):
    try:
        delete_user(db, user_id)
        return {"message": "Usuário deletado com sucesso."}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{user_id}")
def get_user_by_id_route(user_id: int, db: Session = Depends(get_db), current_admin = Depends(get_current_admin)):
    try:
        user = get_user_by_id(db, user_id)
        return user
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
