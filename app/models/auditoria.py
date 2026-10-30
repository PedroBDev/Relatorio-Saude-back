from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Registro de quem pediu qual relatório, por onde e quando.
# LGPD: não guarda os dados dos pacientes nem o texto digitado no chat (que poderia
# conter nomes); só o relatório, o período e quantos registros foram devolvidos.
class AuditoriaRelatorio(Base):
    __tablename__ = "auditoria_relatorios"
    __table_args__ = (
        CheckConstraint("origem IN ('chat', 'api')", name="ck_auditoria_relatorios_origem"),
        CheckConstraint("resultado IN ('ok', 'negado', 'erro')", name="ck_auditoria_relatorios_resultado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # SET NULL: se o usuário for apagado, o registro da auditoria continua.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # Cópia do email no momento do pedido, para saber quem foi mesmo depois de apagar o usuário.
    usuario_email: Mapped[str] = mapped_column(String(100), nullable=False)
    # chat = pedido pelo POST /chat, api = pelas telas (GET /relatorios/...)
    origem: Mapped[str] = mapped_column(String(10), nullable=False)
    relatorio: Mapped[str] = mapped_column(String(50), nullable=False)
    mes: Mapped[int | None] = mapped_column(SmallInteger)
    ano: Mapped[int | None] = mapped_column(SmallInteger)
    # ok = relatório entregue, negado = sem permissão/município, erro = falha ao consultar
    resultado: Mapped[str] = mapped_column(String(10), nullable=False)
    quantidade_registros: Mapped[int | None] = mapped_column(Integer)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
