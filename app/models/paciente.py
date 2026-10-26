from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Uma linha por pessoa. Os grupos (gestante, hipertenso...) ficam em paciente_grupos,
# e criança/idoso são definidos pela idade nas views.
class Paciente(Base):
    __tablename__ = "pacientes"
    __table_args__ = (
        CheckConstraint("sexo IN ('F', 'M')", name="ck_pacientes_sexo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    # A idade não é guardada: é calculada a partir da data de nascimento.
    data_nascimento: Mapped[date] = mapped_column(Date, nullable=False)
    sexo: Mapped[str] = mapped_column(String(1), nullable=False)
    unidade_saude_id: Mapped[int] = mapped_column(ForeignKey("unidades_saude.id"), nullable=False)
