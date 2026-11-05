from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# Uma linha por mensagem recebida no POST /chat, para monitorar o modelo (data drift):
# se a taxa de "não entendi" subir ou a confiança média cair com o tempo, os gestores
# estão escrevendo de um jeito que o modelo não conhece, e é hora de retreinar.
# LGPD: NÃO guarda o texto digitado (poderia conter nomes de pacientes), só o que o
# modelo decidiu e o tipo de resposta. Relatório no ml/monitorar_drift.py.
class InteracaoChat(Base):
    __tablename__ = "interacoes_chat"
    __table_args__ = (
        CheckConstraint(
            "resultado IN ('relatorio', 'pergunta', 'mensagem', 'nao_entendi', 'erro')",
            name="ck_interacoes_chat_resultado",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # SET NULL: se o usuário for apagado, o histórico continua servindo para o monitoramento.
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # Intenção mais provável e a confiança (0 a 1). Ficam vazias quando o modelo não foi
    # usado (ex.: "agosto" respondendo a "de qual mês?", que completa o pedido anterior).
    intencao_prevista: Mapped[str | None] = mapped_column(String(50))
    confianca: Mapped[float | None] = mapped_column(Float)
    # relatorio, pergunta (faltou mês ou relatório), mensagem (saudação/ajuda/fora do escopo),
    # nao_entendi (confiança abaixo do limite) ou erro
    resultado: Mapped[str] = mapped_column(String(20), nullable=False)
    # Data do treino do modelo (do metricas.json), para comparar um modelo com o outro.
    versao_modelo: Mapped[str | None] = mapped_column(String(30))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
