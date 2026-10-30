"""Quais perfis (users.role) podem pedir cada relatório pelo chatbot.

Hoje os dois perfis do sistema veem todos os relatórios. O que protege os dados
é o município: o chatbot sempre usa o município do usuário logado, nunca um
município vindo do pedido (veja chat_service.py).

Para restringir no futuro, basta trocar o conjunto de um perfil, por exemplo:
    "gestor": {"relatorio_gestantes", "relatorio_criancas"}
"""
from app.services.consultas import CONSULTAS

# Todas as intenções de relatório que existem no consultas.py.
TODOS_OS_RELATORIOS = frozenset(CONSULTAS)

PERMISSOES = {
    "admin": TODOS_OS_RELATORIOS,
    "gestor": TODOS_OS_RELATORIOS,
}


def pode_acessar(role: str, intencao: str) -> bool:
    """True se o perfil pode pedir esse relatório. Perfil desconhecido não pode nada."""
    return intencao in PERMISSOES.get(role, frozenset())
