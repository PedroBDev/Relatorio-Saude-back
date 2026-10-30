"""Testes dos endpoints GET /relatorios (usados pelas telas do front).

Rodar (na raiz do projeto, com o venv ativado):
    pytest -v
"""
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.models.auditoria import AuditoriaRelatorio
from app.services import relatorio_service
from tests.conftest import ANO_AGOSTO, cabecalho


def buscar(client, usuario, relatorio, mes=8, ano=ANO_AGOSTO):
    return client.get(f"/relatorios/{relatorio}", params={"mes": mes, "ano": ano},
                      headers=cabecalho(usuario))


def test_sem_login_retorna_401(client):
    resposta = client.get("/relatorios/relatorio_gestantes", params={"mes": 8, "ano": ANO_AGOSTO})
    assert resposta.status_code == 401


def test_lista_os_relatorios_disponiveis(client, dados):
    resposta = client.get("/relatorios", headers=cabecalho(dados["gestor_a"]))

    assert resposta.status_code == 200
    nomes = [item["relatorio"] for item in resposta.json()]
    assert "relatorio_gestantes" in nomes
    assert "resumo_cobertura" in nomes


def test_gestor_recebe_so_o_seu_municipio(client, dados):
    resposta = buscar(client, dados["gestor_a"], "relatorio_gestantes")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["relatorio"] == "relatorio_gestantes"
    assert (corpo["mes"], corpo["ano"]) == (8, ANO_AGOSTO)
    assert corpo["total"] == len(corpo["dados"]) == 1
    codigos = [linha["codigo"] for linha in corpo["dados"]]
    assert codigos == [dados["codigo_gestante_a"]]
    assert dados["codigo_gestante_b"] not in codigos


def test_municipio_na_url_e_ignorado(client, dados):
    # Mesmo tentando passar outro município, vale o do usuário logado.
    resposta = client.get(
        "/relatorios/relatorio_gestantes",
        params={"mes": 8, "ano": ANO_AGOSTO, "municipio_id": 999999},
        headers=cabecalho(dados["gestor_a"]),
    )
    assert resposta.status_code == 200
    assert [linha["codigo"] for linha in resposta.json()["dados"]] == [dados["codigo_gestante_a"]]


def test_numeros_decimais_chegam_como_numero(client, dados):
    resposta = buscar(client, dados["gestor_a"], "resumo_cobertura")

    assert resposta.status_code == 200
    gestantes = next(linha for linha in resposta.json()["dados"] if linha["grupo"] == "gestante")
    assert gestantes["cobertura_percentual"] == 100.0  # número, não o texto "100.0"


def test_usuario_sem_municipio_recebe_403(client, dados):
    resposta = buscar(client, dados["admin_sem_municipio"], "relatorio_gestantes")

    assert resposta.status_code == 403
    assert resposta.json()["detail"] == "Seu usuário não está vinculado a um município."


def test_relatorio_inexistente_retorna_422(client, dados):
    resposta = buscar(client, dados["gestor_a"], "relatorio_vacinas")
    assert resposta.status_code == 422


def test_mes_invalido_retorna_422(client, dados):
    resposta = buscar(client, dados["gestor_a"], "relatorio_gestantes", mes=13)
    assert resposta.status_code == 422


def test_auditoria_registra_origem_api(client, db, dados):
    gestor = dados["gestor_a"]
    buscar(client, gestor, "relatorio_gestantes")

    registros = db.scalars(select(AuditoriaRelatorio).where(AuditoriaRelatorio.user_id == gestor.id)).all()
    assert [(r.origem, r.relatorio, r.resultado, r.quantidade_registros) for r in registros] == [
        ("api", "relatorio_gestantes", "ok", 1)
    ]


def test_erro_do_banco_nao_aparece_para_o_usuario(client, dados, monkeypatch):
    def consulta_quebrada(*args, **kwargs):
        raise OperationalError("SELECT ...", {}, Exception("senha do banco: segredo123"))

    monkeypatch.setattr(relatorio_service, "executar_consulta", consulta_quebrada)

    resposta = buscar(client, dados["gestor_a"], "relatorio_gestantes")

    assert resposta.status_code == 500
    assert "segredo123" not in resposta.text
    assert "SELECT" not in resposta.text


def test_chat_e_tela_devolvem_os_mesmos_dados(client, dados):
    gestor = dados["gestor_a"]
    tela = buscar(client, gestor, "relatorio_gestantes").json()
    chat = client.post("/chat", json={"mensagem": f"relatório das gestantes de agosto de {ANO_AGOSTO}"},
                       headers=cabecalho(gestor)).json()

    assert chat["dados"] == tela["dados"]
