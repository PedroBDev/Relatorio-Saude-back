# language: pt
@RF07
Funcionalidade: RF07 - Pedir relatório pelo chat
  Como gestor municipal de saúde
  Quero pedir relatórios escrevendo em português
  Para consultar os dados do meu município sem precisar de planilhas

  Contexto:
    Dado estar logado como gestor
    E existir uma gestante atendida em agosto no município do gestor

  Cenário: Pedir o relatório com o grupo e o mês
    Quando enviar a mensagem "relatório das gestantes de agosto"
    Então receber o relatório de "gestantes" de agosto
    E exibir a gestante do município do gestor no relatório

  Esquema do Cenário: Pedir o relatório de cada grupo
    Quando enviar a mensagem "<mensagem>"
    Então receber o relatório de "<grupo>" de agosto

    Exemplos:
      | mensagem                            | grupo       |
      | relatório dos hipertensos de agosto | hipertensos |
      | relatório dos diabéticos de agosto  | diabéticos  |
      | relatório das crianças de agosto    | crianças    |
      | relatório dos idosos de agosto      | idosos      |

  Esquema do Cenário: Entender o pedido escrito de jeitos diferentes
    Quando enviar a mensagem "<mensagem>"
    Então receber o relatório de "gestantes" de agosto

    Exemplos:
      | mensagem                                   |
      | pd me mandar as gestante de ago            |
      | quantas grávidas foram atendidas em agosto |
      | oi, quero as gestantes de agosto           |

  Cenário: Pedir o relatório sem informar o mês
    Quando enviar a mensagem "quero o relatório das gestantes"
    Então perguntar "De qual mês"
    Quando enviar a mensagem "agosto"
    Então receber o relatório de "gestantes" de agosto

  Cenário: Informar só o período
    Quando enviar a mensagem "agosto"
    Então perguntar "De qual relatório"
    Quando enviar a mensagem "gestantes"
    Então receber o relatório de "gestantes" de agosto

  Cenário: Pedir algo fora do escopo
    Quando enviar a mensagem "me conta uma piada"
    Então responder "só consigo ajudar com os relatórios"
    E não enviar nenhum dado de paciente
