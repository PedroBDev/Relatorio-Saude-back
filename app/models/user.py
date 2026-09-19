from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

class User(Base):

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    municipio_id: Mapped[int] = mapped_column(ForeignKey("municipios.id"), nullable=False)