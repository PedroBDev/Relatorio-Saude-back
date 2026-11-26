# language: pt
@RF11
Funcionalidade: RF11 - Exportar relatório em Excel e PDF
  Como gestor municipal de saúde
  Quero baixar o relatório em Excel ou PDF
  Para guardar, imprimir ou enviar os dados para a equipe

  Contexto:
    Dado estar logado como gestor
    E existir uma gestante atendida em agosto no município do gestor

  Esquema do Cenário: Baixar o relatório de gestantes de agosto
    Quando exportar o relatório de gestantes de agosto em "<formato>"
    Então baixar um arquivo "<extensao>"

    Exemplos:
      | formato | extensao |
      | excel   | xlsx     |
      | pdf     | pdf      |

  Cenário: Exibir no Excel o relatório, o município e o período
    Quando exportar o relatório de gestantes de agosto em "excel"
    Então exibir no título da planilha "Relatório de gestantes"
    E exibir no subtítulo da planilha o município do gestor e o mês de agosto
    E exibir a gestante do município do gestor na planilha

  Cenário: Exportar sem fazer login
    Dado não estar logado
    Quando exportar o relatório de gestantes de agosto em "pdf"
    Então pedir para fazer login
