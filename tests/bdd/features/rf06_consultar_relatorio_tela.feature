# language: pt
@RF06
Funcionalidade: RF06 - Consultar relatório pela tela
  Como gestor municipal de saúde
  Quero abrir um relatório escolhendo o mês e o ano
  Para acompanhar os pacientes atendidos no período

  Contexto:
    Dado estar logado como gestor
    E existir uma gestante atendida em agosto no município do gestor

  Cenário: Abrir o relatório de um mês passado
    Quando abrir a tela do relatório de gestantes de agosto
    Então exibir 1 paciente na tela
    E exibir a gestante do município do gestor no relatório

  Esquema do Cenário: Pedir um mês que não existe
    Quando abrir a tela do relatório de gestantes do mês <mes>
    Então recusar o pedido por parâmetro inválido

    Exemplos:
      | mes |
      | 0   |
      | 13  |

  Cenário: Comparar a tela com o chat
    Quando abrir a tela do relatório de gestantes de agosto
    E enviar a mensagem "relatório das gestantes de agosto"
    Então exibir os mesmos pacientes no chat e na tela
