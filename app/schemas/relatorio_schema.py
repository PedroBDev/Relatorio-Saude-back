from typing import Any

from pydantic import BaseModel


class RelatorioDisponivel(BaseModel):
    relatorio: str
    descricao: str


class RelatorioResponse(BaseModel):
    relatorio: str
    descricao: str
    mes: int
    ano: int
    total: int
    dados: list[dict[str, Any]]
