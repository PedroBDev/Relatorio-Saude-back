"""Testes da rota POST /municipios/ (só o admin cadastra municípios).

Rodar (na raiz do projeto, com o venv ativado):
    pytest tests/test_municipios.py -v
"""
from tests.conftest import cabecalho

NOVO_MUNICIPIO = {"nome": "Município Teste C", "uf": "PE"}


def test_sem_login_retorna_401(client):
    assert client.post("/municipios/", json=NOVO_MUNICIPIO).status_code == 401


def test_gestor_nao_cadastra_municipio(client, dados):
    resposta = client.post("/municipios/", json=NOVO_MUNICIPIO, headers=cabecalho(dados["gestor_a"]))
    assert resposta.status_code == 403


def test_admin_cadastra_municipio(client, dados):
    resposta = client.post("/municipios/", json=NOVO_MUNICIPIO,
                           headers=cabecalho(dados["admin_sem_municipio"]))

    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Município Teste C"
    assert "id" in resposta.json()
