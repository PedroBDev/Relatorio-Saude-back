# language: pt
@RF04
Funcionalidade: RF04 - Cadastrar município
  Como administrador do sistema
  Quero cadastrar os municípios atendidos
  Para vincular gestores e unidades de saúde a eles

  Cenário: Cadastrar um município
    Dado estar logado como administrador
    Quando cadastrar o município "Cidade Nova" de "PE"
    Então concluir o cadastro

  Cenário: Impedir o gestor de cadastrar municípios
    Dado estar logado como gestor
    Quando cadastrar o município "Cidade Nova" de "PE"
    Então negar o acesso

  Cenário: Cadastrar um município sem fazer login
    Dado não estar logado
    Quando cadastrar o município "Cidade Nova" de "PE"
    Então pedir para fazer login
