from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Outras condições de saúde do paciente (ex.: "Osteoporose").
# Hipertensão e diabetes não entram aqui: já estão em paciente_grupos,
# e a view dos idosos soma as duas coisas.
class Comorbidade(Base):
    __tablename__ = "comorbidades"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    paciente_id: Mapped[int] = mapped_column(ForeignKey("pacientes.id"), nullable=False)
    descricao: Mapped[str] = mapped_column(String(100), nullable=False)
