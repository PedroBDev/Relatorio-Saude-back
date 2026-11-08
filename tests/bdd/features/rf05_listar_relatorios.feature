# language: pt
@RF05
Funcionalidade: RF05 - Listar os relatórios disponíveis
  Como gestor municipal de saúde
  Quero ver quais relatórios posso pedir
  Para escolher o relatório no menu

  Cenário: Exibir todos os relatórios
    Dado estar logado como gestor
    Quando abrir o menu de relatórios
    Então exibir os relatórios:
      | relatorio             |
      | relatorio_gestantes   |
      | relatorio_hipertensos |
      | relatorio_diabeticos  |
      | relatorio_criancas    |
      | relatorio_idosos      |
      | resumo_cobertura      |
