from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    # extra="forbid": só o campo "mensagem" é aceito. Se alguém tentar mandar
    # "municipio_id" (para ver dados de outro município), recebe erro 422.
    model_config = ConfigDict(extra="forbid")

    mensagem: str = Field(min_length=1, max_length=500)


class ChatResponse(BaseModel):
    """Formato único de resposta do /chat: sempre os mesmos 5 campos."""

    # mensagem = resposta de texto (saudação, ajuda, "não entendi"...)
    # pergunta = o chatbot precisa de mais informação (ex.: o mês)
    # relatorio = consulta executada, os dados estão em "dados"
    # erro = algo impediu o pedido (sem permissão, falha interna...)
    tipo: Literal["mensagem", "pergunta", "relatorio", "erro"]
    texto: str
    intencao: str | None = None
    parametros: dict[str, Any] = {}
    dados: list[dict[str, Any]] = []
