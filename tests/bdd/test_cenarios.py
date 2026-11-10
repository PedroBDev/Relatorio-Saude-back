"""Testes BDD: os cenários dos arquivos .feature (em português) ligados ao código.

Cada arquivo .feature é um requisito funcional (RF01 a RF10), e os passos estão
no infinitivo ("Dado estar logado...", "Quando enviar...", "Então receber...").
Cada frase é uma das funções abaixo. O {texto} entre chaves vira um parâmetro
da função, então a mesma função serve para várias frases.

Usa a mesma preparação dos outros testes (tests/conftest.py): o banco é desfeito
no final, e existem dois municípios, cada um com uma gestante atendida em agosto.

Rodar (na raiz do projeto, com o venv ativado):
    pytest tests/bdd -v
    pytest tests/bdd --gherkin-terminal-reporter -vv    # mostra os passos de cada cenário
    pytest tests/bdd -m RF07                            # só os cenários de um requisito
"""
import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from sqlalchemy import func, select

from app.models import Paciente
from app.models.auditoria import AuditoriaRelatorio
from app.models.interacao_chat import InteracaoChat
from tests.conftest import ANO_AGOSTO, cabecalho

scenarios("features")  # todos os .feature da pasta features/


@pytest.fixture
def estado():
    """O que um passo deixa para os próximos: quem está logado e a última resposta."""
    return {"usuario": None, "resposta": None, "tela": None, "mensagem": None}


def ultima_resposta(estado) -> dict:
    return estado["resposta"].json()


def codigos(linhas: list[dict]) -> list[str]:
    return [linha["codigo"] for linha in linhas]


def cabecalhos(estado) -> dict:
    return cabecalho(estado["usuario"]) if estado["usuario"] else {}


def abrir_relatorio(estado, client, mes: int) -> None:
    estado["resposta"] = client.get("/relatorios/relatorio_gestantes", params={"mes": mes, "ano": ANO_AGOSTO},
                                    headers=cabecalhos(estado))
    if estado["resposta"].status_code == 200:
        estado["tela"] = estado["resposta"].json()


# --- Dado (a situação inicial) ------------------------------------------------

@given("estar logado como gestor")
def gestor_logado(estado, dados):
    estado["usuario"] = dados["gestor_a"]


@given("estar logado como administrador")
@given("estar logado como um usuário sem município")
def admin_logado(estado, dados):
    # O administrador dos testes não tem município.
    estado["usuario"] = dados["admin_sem_municipio"]


@given("não estar logado")
def sem_login(estado):
    estado["usuario"] = None


@given(parsers.parse('existir o gestor "{email}" com a senha "{senha}"'))
def gestor_existe(dados, email, senha):
    assert dados["gestor_a"].email == email


@given("existir uma gestante atendida em agosto no município do gestor")
@given("existir uma gestante atendida em agosto em outro município")
def gestantes_cadastradas(dados):
    # As duas gestantes (uma em cada município) já vêm do conftest.py.
    assert dados["codigo_gestante_a"] and dados["codigo_gestante_b"]


# --- Quando (a ação) ------------------------------------------------------------

@when(parsers.parse('fazer login com o e-mail "{email}" e a senha "{senha}"'))
def fazer_login(estado, client, email, senha):
    estado["resposta"] = client.post("/auth/login", json={"email": email, "password": senha})


@when(parsers.parse('enviar a mensagem "{mensagem}"'))
def enviar_mensagem(estado, client, mensagem):
    estado["mensagem"] = mensagem
    estado["resposta"] = client.post("/chat", json={"mensagem": mensagem}, headers=cabecalhos(estado))


@when(parsers.parse('cadastrar o gestor "{email}" no município do gestor A'))
def cadastrar_gestor(estado, client, dados, email):
    novo = {"nome": "Novo Gestor", "email": email, "password": "senha123",
            "municipio_id": dados["gestor_a"].municipio_id, "role": "gestor"}
    estado["resposta"] = client.post("/auth/register", json=novo, headers=cabecalhos(estado))


@when("listar os usuários")
def listar_usuarios(estado, client):
    estado["resposta"] = client.get("/users/get_all", headers=cabecalhos(estado))


@when(parsers.parse('trocar a senha do usuário "{email}" para "{senha}"'))
def trocar_senha(estado, client, dados, email, senha):
    assert dados["gestor_a"].email == email
    estado["resposta"] = client.patch(f"/users/{dados['gestor_a'].id}", json={"password": senha},
                                      headers=cabecalhos(estado))
    assert estado["resposta"].status_code == 200


@when(parsers.parse('remover o usuário "{email}"'))
def remover_usuario(estado, client, dados, email):
    assert dados["gestor_a"].email == email
    estado["resposta"] = client.delete(f"/users/{dados['gestor_a'].id}", headers=cabecalhos(estado))
    assert estado["resposta"].status_code == 200


@when(parsers.parse('cadastrar o município "{nome}" de "{uf}"'))
def cadastrar_municipio(estado, client, nome, uf):
    estado["resposta"] = client.post("/municipios/", json={"nome": nome, "uf": uf}, headers=cabecalhos(estado))


@when("abrir o menu de relatórios")
def abrir_menu(estado, client):
    estado["resposta"] = client.get("/relatorios", headers=cabecalhos(estado))


@when("abrir a tela do relatório de gestantes de agosto")
def abrir_tela(estado, client):
    abrir_relatorio(estado, client, 8)


@when(parsers.parse("abrir a tela do relatório de gestantes do mês {mes:d}"))
def abrir_tela_mes(estado, client, mes):
    abrir_relatorio(estado, client, mes)


# --- Então (o resultado esperado) ---------------------------------------------------

@then("receber um token de acesso")
def recebe_token(estado):
    assert estado["resposta"].status_code == 200
    assert ultima_resposta(estado)["access_token"]


@then(parsers.parse('identificar pelo token o usuário "{email}"'))
def token_identifica(estado, client, email):
    token = ultima_resposta(estado)["access_token"]
    eu = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert eu["email"] == email


@then("recusar o login")
def login_recusado(estado):
    assert estado["resposta"].status_code == 401


@then(parsers.parse('conseguir fazer login com o e-mail "{email}" e a senha "{senha}"'))
def consegue_login(client, email, senha):
    resposta = client.post("/auth/login", json={"email": email, "password": senha})
    assert resposta.status_code == 200


@then("concluir o cadastro")
def cadastro_concluido(estado):
    assert estado["resposta"].status_code == 200
    assert ultima_resposta(estado)["id"]


@then(parsers.parse('recusar o cadastro com a mensagem "{trecho}"'))
def cadastro_recusado(estado, trecho):
    assert estado["resposta"].status_code == 400
    assert trecho in ultima_resposta(estado)["detail"]


@then("não exibir a senha na resposta")
def sem_senha_na_resposta(estado):
    assert not {"password", "senha_hash"} & set(ultima_resposta(estado))


@then(parsers.parse('exibir o usuário "{email}" na lista'))
def usuario_na_lista(estado, email):
    assert email in [usuario["email"] for usuario in ultima_resposta(estado)]


@then("não exibir a senha de nenhum usuário")
def sem_senha_na_lista(estado):
    for usuario in ultima_resposta(estado):
        assert not {"password", "senha_hash"} & set(usuario)


@then(parsers.parse('não encontrar mais o usuário "{email}"'))
def usuario_removido(estado, client, email):
    resposta = client.get("/users/get_by_email", params={"email": email}, headers=cabecalhos(estado))
    assert resposta.status_code == 404


@then("exibir os relatórios:")
def relatorios_do_menu(estado, datatable):
    esperados = [linha[0] for linha in datatable[1:]]  # a linha 0 é o cabeçalho
    assert [item["relatorio"] for item in ultima_resposta(estado)] == esperados


@then(parsers.parse('receber o relatório de "{grupo}" de agosto'))
def recebo_relatorio(estado, grupo):
    corpo = ultima_resposta(estado)
    assert corpo["tipo"] == "relatorio", corpo["texto"]
    assert grupo in corpo["texto"]
    assert corpo["parametros"] == {"mes": 8, "ano": ANO_AGOSTO}


@then("exibir a gestante do município do gestor no relatório")
def aparece_gestante_do_municipio(estado, dados):
    linhas = estado["tela"]["dados"] if estado["tela"] else ultima_resposta(estado)["dados"]
    assert dados["codigo_gestante_a"] in codigos(linhas)


@then("não exibir a gestante do outro município no relatório")
def nao_aparece_outro_municipio(estado, dados):
    assert dados["codigo_gestante_b"] not in codigos(ultima_resposta(estado)["dados"])


@then(parsers.parse("exibir {quantidade:d} paciente na tela"))
def tela_mostra(estado, quantidade):
    assert estado["tela"]["total"] == quantidade


@then("exibir os mesmos pacientes no chat e na tela")
def chat_igual_tela(estado):
    assert ultima_resposta(estado)["dados"] == estado["tela"]["dados"]


@then("recusar o pedido por parâmetro inválido")
def parametro_invalido(estado):
    assert estado["resposta"].status_code == 422


@then(parsers.parse('perguntar "{trecho}"'))
def assistente_pergunta(estado, trecho):
    corpo = ultima_resposta(estado)
    assert corpo["tipo"] == "pergunta"
    assert trecho in corpo["texto"]


@then(parsers.parse('responder "{trecho}"'))
def assistente_responde(estado, trecho):
    assert trecho in ultima_resposta(estado)["texto"]


@then("não enviar nenhum dado de paciente")
def sem_dados(estado):
    assert ultima_resposta(estado)["dados"] == []


@then(parsers.parse('negar o acesso com a mensagem "{trecho}"'))
def acesso_negado_com_mensagem(estado, trecho):
    assert estado["resposta"].status_code == 403
    assert trecho in ultima_resposta(estado)["texto"]


@then("negar o acesso")
def acesso_negado(estado):
    assert estado["resposta"].status_code == 403


@then("pedir para fazer login")
def pede_login(estado):
    assert estado["resposta"].status_code == 401


@then("não apagar nenhum paciente do banco")
def banco_intacto(estado, db):
    assert estado["resposta"].status_code != 500
    assert db.scalar(select(func.count()).select_from(Paciente)) > 0


@then(parsers.parse('registrar na auditoria o relatório "{relatorio}" pedido {artigo} "{origem}" '
                    'com resultado "{resultado}"'))
def auditoria_registrada(estado, db, relatorio, artigo, origem, resultado):
    registro = db.scalars(select(AuditoriaRelatorio)
                          .where(AuditoriaRelatorio.user_id == estado["usuario"].id)
                          .order_by(AuditoriaRelatorio.id.desc())).first()
    assert (registro.relatorio, registro.origem, registro.resultado) == (relatorio, origem, resultado)


@then(parsers.parse('registrar a mensagem com o resultado "{resultado}" e a intenção "{intencao}"'))
def interacao_registrada(estado, db, resultado, intencao):
    registro = db.scalars(select(InteracaoChat)
                          .where(InteracaoChat.user_id == estado["usuario"].id)
                          .order_by(InteracaoChat.id.desc())).first()
    assert (registro.resultado, registro.intencao_prevista) == (resultado, intencao)


@then("não guardar o texto digitado")
def sem_texto_guardado(estado, db):
    registro = db.scalars(select(InteracaoChat).where(InteracaoChat.user_id == estado["usuario"].id)).first()
    valores = [getattr(registro, coluna.key) for coluna in InteracaoChat.__table__.columns]
    assert estado["mensagem"] not in valores
