"""Testes das rotas /users (só o admin usa).

O mais importante: nenhuma resposta pode trazer o senha_hash.

Rodar (na raiz do projeto, com o venv ativado):
    pytest tests/test_users.py -v
"""
from app.core.security import verify_password
from tests.conftest import cabecalho

CAMPOS_ESPERADOS = {"id", "nome", "email", "municipio_id", "role"}


def test_gestor_nao_acessa_users(client, dados):
    resposta = client.get("/users/get_all", headers=cabecalho(dados["gestor_a"]))
    assert resposta.status_code == 403


def test_listar_nao_devolve_senha(client, dados):
    resposta = client.get("/users/get_all", headers=cabecalho(dados["admin_sem_municipio"]))

    assert resposta.status_code == 200
    for usuario in resposta.json():
        assert set(usuario) == CAMPOS_ESPERADOS


def test_buscar_por_id_e_por_email_nao_devolvem_senha(client, dados):
    admin, gestor = dados["admin_sem_municipio"], dados["gestor_a"]

    por_id = client.get(f"/users/{gestor.id}", headers=cabecalho(admin))
    por_email = client.get("/users/get_by_email", params={"email": gestor.email}, headers=cabecalho(admin))

    assert por_id.status_code == por_email.status_code == 200
    assert set(por_id.json()) == set(por_email.json()) == CAMPOS_ESPERADOS
    assert por_id.json()["role"] == "gestor"


def test_atualizar_senha_grava_o_hash(client, db, dados):
    admin, gestor = dados["admin_sem_municipio"], dados["gestor_a"]

    resposta = client.patch(f"/users/{gestor.id}", json={"password": "senha-nova"},
                            headers=cabecalho(admin))

    assert resposta.status_code == 200
    assert set(resposta.json()) == CAMPOS_ESPERADOS
    db.refresh(gestor)
    assert verify_password("senha-nova", gestor.senha_hash)


def test_me_nao_devolve_senha(client, dados):
    resposta = client.get("/auth/me", headers=cabecalho(dados["gestor_a"]))

    assert resposta.status_code == 200
    assert set(resposta.json()) == CAMPOS_ESPERADOS
