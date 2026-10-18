from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserUpdate

def get_user_by_id(db: Session, user_id: int) -> User | None:
    user = db.get(User, user_id)
    if not user:
        raise ValueError("Usuário não encontrado.")
    return user

def get_user_by_email(db: Session, email: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        raise ValueError("Usuário não encontrado.")
    return user

def get_all_users(db: Session) -> list[User]:
    return db.scalars(select(User)).all()

def update_user(db: Session, user_id: int, updated_data: UserUpdate) -> User:
    user = db.get(User, user_id)
    if not user:
        raise ValueError("Usuário não encontrado.")
    
    update_fields = updated_data.dict(exclude_unset=True)

    for key, value in update_fields.items():
        if value is not None:
            setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> None:
    user = db.get(User, user_id)
    if not user:
        raise ValueError("Usuário não encontrado.")

    db.delete(user)
    db.commit()