from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

class Municipio(Base):
    __tablename__ = "municipios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    uf: Mapped[str] = mapped_column(String(2), nullable=False)