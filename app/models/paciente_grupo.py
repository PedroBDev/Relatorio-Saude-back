from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Em quais grupos de acompanhamento o paciente foi cadastrado, e durante qual período.
# Só gestante, hipertenso e diabético: criança e idoso entram automaticamente pela idade.
class PacienteGrupo(Base):
    __tablename__ = "paciente_grupos"
    __table_args__ = (
        CheckConstraint(
            "grupo IN ('gestante', 'hipertenso', 'diabetico')",
            name="ck_paciente_grupos_grupo",
        ),
        CheckConstraint(
            "data_saida IS NULL OR data_saida >= data_inclusao",
            name="ck_paciente_grupos_periodo",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    paciente_id: Mapped[int] = mapped_column(ForeignKey("pacientes.id"), nullable=False)
    grupo: Mapped[str] = mapped_column(String(20), nullable=False)
    data_inclusao: Mapped[date] = mapped_column(Date, nullable=False)
    # Quando saiu do grupo (ex.: data do parto). Vazio = continua no grupo.
    # Guardar a data, e não só "ativo sim/não", permite montar relatórios de meses passados.
    # Uma mesma mulher pode ter várias linhas de "gestante", uma por gestação.
    data_saida: Mapped[date | None] = mapped_column(Date)
