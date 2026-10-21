from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Unidade de saúde onde os pacientes são acompanhados (ex.: "UBS Vila Nova").
class UnidadeSaude(Base):
    __tablename__ = "unidades_saude"
    __table_args__ = (
        CheckConstraint("tipo IN ('UBS', 'ESF')", name="ck_unidades_saude_tipo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    # UBS = Unidade Básica de Saúde, ESF = Estratégia Saúde da Família
    tipo: Mapped[str] = mapped_column(String(3), nullable=False)
    municipio_id: Mapped[int] = mapped_column(ForeignKey("municipios.id"), nullable=False)
