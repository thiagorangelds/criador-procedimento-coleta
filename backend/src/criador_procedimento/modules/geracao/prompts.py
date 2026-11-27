"""Os dois prompts enviados ao Gemini, em sequência e dependentes.

O primeiro devolve o levantamento inteiro em texto livre, partido depois no
marcador `SEPARADOR_CATALOGO`. O segundo **recebe esse levantamento de volta** e
devolve JSON estrito — é esse JSON que vira o `.docx`. Mexer no prompt do
levantamento muda o documento final por tabela.
"""

SEPARADOR_CATALOGO = "\n\n--- INICIO_CATALOGO ---\n\n"
MARCADOR_CATALOGO = "6. Catálogo de Dados de Logs de Segurança (Padronização ECS)"


def levantamento(tecnologia: str) -> str:
    return f'''
Responda em português do Brasil, com a acentuação e a cedilha corretas em todas as palavras (solução, análise, segurança, tráfego, configuração). Nunca escreva sem acento nem transcreva para ASCII.

Tecnologia-Alvo: {tecnologia}

1. Requisitos e Métodos de Coleta de Logs
1.1. Suporte a Protocolos de Coleta:
Qual é a versão/edição da tecnologia que oferece suporte para coleta de logs via TCP/UDP? (Preferencialmente)
Se não for TCP/UDP, qual é a versão/edição que oferece suporte à coleta via API?

1.2. Configuração de Coleta:
Detalhe como é configurada a coleta de logs para o método preferencial (TCP/UDP, ou API, se for a única opção). Inclua comandos ou passos chave.
Alternativa Filebeat (se aplicável): Qual é a versão/edição que permite a instalação do Filebeat em um diretório específico onde o arquivo de log é gerado? Descreva brevemente a configuração necessária (ex: arquivo de configuração, input path).

2. Versões e Custos de Licenciamento
Quais são as principais versões/edições da tecnologia?
Para cada versão relevante para a coleta de logs de segurança, qual é o custo com licença (ou modelo de licenciamento)? (Ex: Gratuita, Paga - Enterprise, por usuário, etc.)

3. Eventos de Segurança Relevantes e Exemplos
Quais são os 5 a 10 eventos de segurança mais relevantes que devem ser monitorados? (Ex: Falha de Login, Criação de Usuário Privilegiado, Mudança de Configuração Crítica, etc.)
Forneça logs de exemplo (cerca de 3 a 5 logs) que sejam relevantes para a segurança.

4. Links de Referência
Adicione links de documentação oficiais da tecnologia para os seguintes tópicos:
- Documentação de Coleta/Exportação de Logs.
- Documentação de Eventos de Segurança/Auditoria.

5. Estimativa de Volumetria
Com base em um ambiente corporativo de médio a grande porte, forneça uma estimativa de volumetria dos dados de logs gerados por esta tecnologia (exemplo: GB/dia, quantidade de Eventos por Segundo - EPS médio). Inclua breves fatores que podem aumentar ou diminuir consideravelmente esse volume.

{SEPARADOR_CATALOGO}{MARCADOR_CATALOGO}
Gere uma tabela com o Catálogo de Dados para os campos mais importantes dos logs de segurança, usando a padronização Elastic Common Schema (ECS) como recomendação.
Campos do catálogo de dados: Nome do Campo Original (na ferramenta), Nome do campo ECS, Descrição, Tipo de dados, Exemplo de valor, Tipo de dado ECS.
'''


def procedimento(tecnologia: str, levantamento_gerado: str) -> str:
    return f'''
Tecnologia-Alvo: {tecnologia}

Com base no levantamento abaixo, escreva o conteúdo de um documento formal de PROCEDIMENTO DE COLETA de logs dessa tecnologia, destinado à equipe do cliente que vai executar a configuração.
Use o método de coleta preferencial do levantamento (TCP/UDP; API somente se for a única opção; Filebeat se for o caso). Não inclua licenciamento, volumetria, catálogo de dados nem links.

Responda SOMENTE com um JSON válido, em português, no formato:
{{
  "introducao": ["1 a 3 parágrafos: o que é a tecnologia, qual o método de coleta escolhido e por quê"],
  "pre_requisitos": ["acessos, versões/edições, portas e informações necessárias antes de começar"],
  "passos": [
    {{
      "titulo": "título curto do passo",
      "descricao": "o que fazer neste passo",
      "itens": ["ações ou parâmetros a configurar neste passo (pode ser vazio)"],
      "codigo": "comandos ou trecho de configuração, um por linha (string vazia se não houver)"
    }}
  ],
  "validacao": ["como confirmar que os logs estão sendo recebidos"]
}}

Regras: texto puro, sem markdown (sem **, #, crases ou listas com hífen dentro das strings); não numere os títulos dos passos; onde houver valores do ambiente do cliente use marcadores como <IP_DO_COLETOR> e <PORTA>.

Acentuação: escreva em português do Brasil com a acentuação e a cedilha corretas em todas as palavras (solução, análise, segurança, tráfego, endereço, pré-requisito). Nunca escreva sem acento nem transcreva para ASCII, mesmo que o levantamento abaixo esteja sem acentos. Os acentos devem ser caracteres UTF-8 reais nas strings do JSON.

--- LEVANTAMENTO ---
{levantamento_gerado}
'''
