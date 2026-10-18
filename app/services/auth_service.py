from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.municipio import Municipio
from app.models.user import User
from app.schemas.user import UserCreate

def create_user(db: Session, user_data: UserCreate) -> User:

    existing_user = db.scalar(select(User).where(User.email == user_data.email))

    if existing_user:
        raise ValueError("Email já cadastrado.")

    if user_data.role not in ["gestor", "admin"]:
        raise ValueError("Role inválida. Deve ser 'gestor' ou 'admin'.")

    if user_data.role == "gestor" and not user_data.municipio_id:
        raise ValueError("Gestores devem estar associados a um município.")
        
    if user_data.role == "gestor":
        if not db.get(Municipio, user_data.municipio_id):
            raise ValueError("Municipio não encontrado.")    

    user = User(
        nome=user_data.nome,
        email=user_data.email,
        senha_hash=hash_password(user_data.password),
        municipio_id=user_data.municipio_id,
        role=user_data.role
    )


    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))

    if not user or not verify_password(password, user.senha_hash):
        return None

    return user


