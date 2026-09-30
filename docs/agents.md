# Contexto para agentes — Vivver Estoque MVP

Este arquivo registra o estado conhecido do repositório em 2026-09-22. Use-o como ponto de partida para análises e mudanças posteriores. Ele não substitui a leitura do código afetado antes de uma alteração.

## Objetivo atual

O projeto coleta dados públicos de estoque de medicamentos do portal Vivver para Montes Claros, armazena a resposta bruta e contém uma transformação dimensional para analisar o estoque por produto e unidade.

## Estrutura e rotas existentes

Existem **duas rotas de processamento no código atual**. Elas compartilham parte do contexto, mas não formam uma única execução encadeada.

### 1. Rota dimensional

```text
arquivo JSON em data/raw/*.txt
  → src.transform
  → dim_produto.csv
  → dim_unidade.csv
  → fato_estoque.csv
  → transform_log.json
```

- `src/transform.py` é executado independentemente; ele não chama a coleta.
- Entrada esperada: lista JSON de produtos, cada um com `estoque_unidade` como lista.
- A captura incluída é `data/raw/vivver_estoque_2026-09-22T131443016020+0000.txt`.
- A última execução registrada produziu 215 produtos, 48 unidades e 6.791 registros de estoque.
- O modelo é `dim_produto` 1:N `fato_estoque` N:1 `dim_unidade`.

Comando:

```bash
python -m src.transform data/raw/vivver_estoque_2026-09-22T131443016020+0000.txt data/processed
```

### 2. Rota tabular adicional

```text
Vivver ou fixture HTML
  → src.extract
  → data/raw/*.txt
  → src.parse
  → src.normalize
  → src.quality
  → src.load
  → estoque_montes_claros.csv / .parquet / quality_report.csv
```

- `src/pipeline.py` coordena esta rota.
- `src/extract.py` consulta as URLs declaradas em `src/config.py`, com timeout de 30 segundos e `raise_for_status()`; não há retry ou tratamento estruturado de falhas.
- `src/load.py` somente escreve arquivos processados; não carrega dados em banco, API ou serviço externo.
- `src.parse` aceita JSON ou uma tabela HTML detectável. `src.normalize` não expande `estoque_unidade`; por isso essa rota preserva esse campo como valor tabular, em vez de gerar os CSVs dimensionais.

Comandos:

```bash
# sem rede, usando o fixture incluído
python -m src.pipeline --fixture tests/fixtures/estoque_sample.html

# consulta a fonte configurada
python -m src.pipeline
```

## Fatos importantes para mudanças futuras

- O nome `load.py` pode induzir a erro: não existe carga em destino externo.
- `src.pipeline` não invoca `src.transform`. Uma integração entre as duas rotas seria uma mudança de arquitetura e precisa ser decidida explicitamente.
- A transformação dimensional exige que as quantidades sejam inteiros, inclusive quando recebidas como string como `"2.0"`.
- As validações dimensionais impedem a escrita das saídas quando falham: esquema obrigatório, integridade do produto filho, unicidade de produto–unidade, consistência de metadados da unidade e soma de estoque por produto.
- O relatório de `src.quality` é apenas descritivo (tipos, nulos e distintos); ele não bloqueia dados por limiares.
- `requirements.txt` declara `requests`, `pandas`, `beautifulsoup4`, `lxml` e `pyarrow`. `pytest` não está declarado; neste ambiente, `python -m pytest -q` falhou porque o módulo não está instalado.

## Documentação disponível

- `README.md`: visão geral, comandos e status.
- `docs/pipeline.md`: descrição técnica detalhada, colunas, transformações e validações confirmadas no código.

## Diretriz para a próxima fase

Antes de modularizar ou ampliar o MVP, definir com clareza:

1. qual rota será a pipeline canônica;
2. qual contrato de entrada e de saída deve ser mantido;
3. qual destino deve receber os dados após `data/processed`;
4. quais regras de qualidade são obrigatórias para o problema de negócio;
5. quais módulos devem ser estáveis e quais podem ser substituídos.

Não presumir banco de dados, orquestrador, nuvem, autenticação adicional ou infraestrutura que não esteja no repositório.
