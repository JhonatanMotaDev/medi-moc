# Base para artigo científico

## Título provisório

**Desenvolvimento e validação inicial de uma plataforma pública para consulta de registros de estoque de medicamentos em Montes Claros (MG)**

## Resumo estruturado

### Introdução

Encontrar medicamentos na rede pública pode exigir deslocamentos desnecessários, especialmente para pessoas idosas, com mobilidade reduzida ou em tratamento contínuo. O projeto propõe organizar registros públicos do Portal Cidadão – Estoque (Vivver) em uma interface simples, transparente e orientada à confirmação com a unidade.

### Objetivo

Desenvolver e avaliar inicialmente uma aplicação web local capaz de coletar, validar, preservar e apresentar registros públicos de medicamentos e unidades de saúde de Montes Claros, sem apresentar a captura como garantia de estoque atual.

### Método

Foi implementada uma pipeline em Python com quatro responsabilidades: coleta da fonte, transformação/validação, persistência de arquivos e apresentação web. A coleta preserva a resposta bruta; a validação verifica estrutura, identificadores, quantidades, duplicidades e consistência; o snapshot é publicado atomicamente somente após validação. A interface oferece busca, sugestões, filtro por unidade, catálogo, contatos e mapa com proveniência das localizações. A validação com a comunidade deve usar sessões individuais, consentimento e registros anônimos, sem coletar diagnóstico, medicamento pessoal ou dados identificáveis.

### Resultados disponíveis

Na captura histórica completa incluída no repositório, foram observados 215 produtos, 48 unidades e 6.791 registros produto–unidade. O mapa contém 31 localizações: 3 pontos previamente documentados e 28 localizações provisórias obtidas por correspondência de endereço no Nominatim/OpenStreetMap. Dezessete unidades permanecem sem correspondência cartográfica confiável. Esses números descrevem a captura e a implementação; não representam atualização atual, cobertura populacional, redução de deslocamentos ou impacto em saúde.

### Conclusão provisória

O MVP demonstra a viabilidade técnica de organizar uma fonte pública de estoque com transparência de origem, data de consulta e limitações. Antes de divulgação contínua, são necessárias coleta recente, autorização institucional, validação de acessibilidade, monitoramento operacional e confirmação dos dados cadastrais e geográficos.

## Pergunta de pesquisa sugerida

Uma interface pública, transparente e orientada à confirmação com a unidade melhora a capacidade de pessoas usuárias localizarem registros de medicamentos e compreenderem as limitações temporais desses dados?

## Objetivos

### Geral

Avaliar a viabilidade técnica e a compreensão do usuário de uma plataforma pública de consulta de registros de estoque de medicamentos.

### Específicos

1. Implementar uma pipeline reprodutível de coleta, validação e publicação.
2. Descrever a cobertura de produtos, unidades e registros da fonte.
3. Medir a facilidade de localizar um medicamento e uma unidade.
4. Verificar se as pessoas distinguem horário de consulta de confirmação de estoque atual.
5. Identificar barreiras de acessibilidade e comunicação.
6. Documentar limitações, falhas e requisitos para parceria institucional.

## Desenho de avaliação

Realizar 5 a 8 sessões exploratórias individuais, com diversidade de idade, familiaridade digital, mobilidade e participação profissional. O número é adequado para descoberta inicial, não para estimar prevalência ou impacto municipal.

### Tarefas

1. Encontrar um medicamento fictício.
2. Identificar uma unidade com quantidade positiva.
3. Localizar endereço e telefone.
4. Explicar o significado do horário da consulta.
5. Explicar o que faria antes de se deslocar.

### Indicadores

- proporção que conclui cada tarefa sem ajuda;
- tempo aproximado por tarefa;
- erros de interpretação sobre “disponível”;
- localização correta de contato;
- barreiras de leitura, contraste, teclado e tela móvel;
- compreensão da necessidade de confirmação com a unidade;
- sugestões de informação pública adicional.

A interface foi ajustada para esse público com texto-base maior, campos e botões de 50 px, contraste reforçado, foco visível, link para saltar diretamente à busca e instruções explícitas sobre como pesquisar. Essas mudanças são decisões de acessibilidade implementadas, não evidência de eficácia; devem ser avaliadas nas sessões com usuários.

### Critérios iniciais

- pelo menos 4 de 5 participantes localizam o resultado sem ajuda;
- todas compreendem que o horário é da consulta à fonte;
- todas identificam a necessidade de confirmar antes do deslocamento;
- qualquer interpretação de garantia de estoque exige revisão dos avisos e nova rodada.

## Dados e reprodutibilidade

- Fonte de estoque: Portal Cidadão – Estoque (Vivver), município de Montes Claros, código `3143302`.
- Captura bruta: `data/raw/`.
- Snapshot público processado: `data/processed/public_snapshot.json`.
- Status da coleta: `data/processed/collection_status.json`.
- Coordenadas e proveniência cartográfica: `src/static/unit_locations.json`.
- Fixture para testes: `tests/fixtures/stock_demo.json`.
- Execução de demonstração: `python -m src.extract.collector --fixture tests/fixtures/stock_demo.json`.
- Execução da coleta: `python -m src.extract.collector`.
- Testes: `python -m pytest -q`.

## Limitações que devem aparecer no artigo

- As capturas disponíveis são históricas; horário de consulta não é horário de atualização na unidade.
- O Vivver é a única fonte pública de estoque usada pelo MVP.
- O projeto não confirma disponibilidade presencial, não prevê reposição e não integra sistemas municipais.
- O mapa tem cobertura parcial e mistura pontos publicados com geocodificações provisórias claramente identificadas.
- As conversas iniciais e a estimativa de 100 pessoas beneficiadas não são evidência representativa.
- Não há, neste estágio, medição de redução de deslocamentos, desabastecimento ou desfechos clínicos.
- Resultados de sessões exploratórias não devem ser generalizados para a população.

## Estrutura sugerida do artigo

1. Introdução e problema social.
2. Contexto de Montes Claros, extensão universitária e ODS 3.
3. Métodos: arquitetura, fonte, validação, ética e avaliação com usuários.
4. Resultados técnicos: cobertura, qualidade e comportamento diante de falhas.
5. Resultados da avaliação com a comunidade.
6. Discussão: transparência, acessibilidade, limites de dados secundários e governança.
7. Limitações.
8. Conclusão e próximos passos.

## Evidências que ainda precisam ser produzidas

- coleta real recente registrada antes da demonstração;
- autorização institucional para coleta automatizada e republicação;
- teste de compreensão com usuários;
- validação de nomes, telefones, endereços e coordenadas;
- registro dos testes de acessibilidade;
- histórico de falhas e duração das coletas;
- revisão ética/institucional aplicável ao formato de participação comunitária.

Não preencher essas lacunas com estimativas. Resultados de impacto só devem ser afirmados depois de medidos com método e amostra adequados.
