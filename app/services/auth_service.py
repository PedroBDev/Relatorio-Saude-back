from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate

def create_user(db: Session, user: UserCreate) -> User:

    existing_user = db.scalar(select(User).where(User.email == user.email))

    if existing_user:
        raise ValueError("Email já cadastrado.")

    user = User(
        nome=user.nome,
        email=user.email,
        senha_hash=hash_password(user.password),
        municipio_id=user.municipio_id
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))

    if not user or not verify_password(password, user.senha_hash):
        return None

    return user