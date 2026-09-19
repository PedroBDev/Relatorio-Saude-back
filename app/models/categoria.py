from sqlalchemy import ForeignKey, String 
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    categoria: Mapped[str] = mapped_column(String(100), nullable=False)
    quantidade: Mapped[int] = mapped_column(String(255), nullable=True)
    municipio_id: Mapped[int] = mapped_column(ForeignKey("municipios.id"), nullable=False)