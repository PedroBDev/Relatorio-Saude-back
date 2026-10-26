from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Cada atendimento feito. As medições são opcionais: só se preenche
# a que faz sentido para o grupo da consulta.
class Consulta(Base):
    __tablename__ = "consultas"
    __table_args__ = (
        CheckConstraint(
            "grupo IN ('gestante', 'hipertenso', 'diabetico', 'crianca', 'idoso')",
            name="ck_consultas_grupo",
        ),
        # As views buscam sempre "consultas do paciente X no grupo Y, por data".
        Index("ix_consultas_paciente_grupo_data", "paciente_id", "grupo", "data_consulta"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    paciente_id: Mapped[int] = mapped_column(ForeignKey("pacientes.id"), nullable=False)
    unidade_saude_id: Mapped[int] = mapped_column(ForeignKey("unidades_saude.id"), nullable=False)
    # Qual acompanhamento esta consulta atende.
    grupo: Mapped[str] = mapped_column(String(20), nullable=False)
    data_consulta: Mapped[date] = mapped_column(Date, nullable=False)

    # Hipertensos: pressão em mmHg (ex.: 140/90)
    pressao_sistolica: Mapped[int | None] = mapped_column(SmallInteger)
    pressao_diastolica: Mapped[int | None] = mapped_column(SmallInteger)
    # Diabéticos: hemoglobina glicada em % (ex.: 7.5)
    hemoglobina_glicada: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    # Gestantes: semanas de gestação no dia da consulta
    semanas_gestacao: Mapped[int | None] = mapped_column(SmallInteger)
    # Crianças: caderneta de vacinação em dia ou atrasada
    vacinacao_em_dia: Mapped[bool | None] = mapped_column(Boolean)
