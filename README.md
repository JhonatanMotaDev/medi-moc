# Vivver Estoque MVP

Pipeline local para coletar e transformar dados públicos de estoque de medicamentos de Montes Claros disponíveis no portal Vivver. O projeto preserva a resposta recebida em `data/raw/` e contém uma transformação dimensional que produz tabelas de produto, unidade e estoque.

## Arquitetura

```text
Portal Vivver
    ↓
Extract (`src.extract`)
    ↓
data/raw/*.txt
    ↓
Transform dimensional (`src.transform`)
    ↓
data/processed/dim_produto.csv
data/processed/dim_unidade.csv
data/processed/fato_estoque.csv
data/processed/transform_log.json
    ↓
Load em destino externo [ainda não implementado]
```

- **Extract** consulta as URLs configuradas do Vivver, obtém a resposta e a grava como texto UTF-8.
- **Raw** guarda a resposta sem a remodelar. O arquivo `.txt` usado pela transformação dimensional contém JSON.
- **Transform** valida, normaliza e separa o JSON aninhado em três CSVs relacionáveis.
- **Processed** é a camada de arquivos gerados para consumo local.
- **Load** para banco de dados, API ou outro destino externo não existe neste repositório.

> Há também o executor `src.pipeline`, com `src.parse`, `src.normalize`, `src.quality` e `src.load`. Ele gera `estoque_montes_claros.csv`, Parquet quando disponível e `quality_report.csv`. Essa é uma saída tabular normalizada adicional; ele **não** chama `src.transform` e não produz as três tabelas dimensionais.

## Estrutura do projeto

```text
vivver-estoque-mvp/
├── data/
│   ├── raw/
│   │   ├── vivver_estoque_2026-09-22T131443016020+0000.txt
│   │   └── vivver_estoque_fixture.txt
│   └── processed/
│       ├── dim_produto.csv
│       ├── dim_unidade.csv
│       ├── fato_estoque.csv
│       ├── transform_log.json
│       ├── estoque_montes_claros.csv
│       ├── estoque_montes_claros.parquet
│       └── quality_report.csv
├── docs/
│   └── pipeline.md
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── extract.py
│   ├── transform.py
│   ├── parse.py
│   ├── normalize.py
│   ├── quality.py
│   ├── load.py
│   └── pipeline.py
├── tests/
│   ├── fixtures/estoque_sample.html
│   └── test_normalize.py
└── requirements.txt
```

## Executar localmente

Instale as dependências declaradas:

```bash
python -m pip install -r requirements.txt
```

Para executar a transformação dimensional sobre a captura incluída:

```bash
python -m src.transform data/raw/vivver_estoque_2026-09-22T131443016020+0000.txt data/processed
```

O comando imprime as métricas e grava ou atualiza `dim_produto.csv`, `dim_unidade.csv`, `fato_estoque.csv` e `transform_log.json` no diretório informado. Na execução registrada, foram produzidos **215 produtos**, **48 unidades** e **6.791 registros de estoque**.

Para executar a rota alternativa completa, usando o fixture HTML local em vez de consultar o portal:

```bash
python -m src.pipeline --fixture tests/fixtures/estoque_sample.html
```

Sem `--fixture`, o mesmo executor faz a consulta configurada no Vivver:

```bash
python -m src.pipeline
```

Verifique as saídas geradas com:

```bash
Get-ChildItem data/processed
Get-Content data/processed/transform_log.json
```

## Modelo dos dados transformados

Cada produto na origem contém uma coleção `estoque_unidade`. A transformação reduz essa estrutura para dimensões reutilizáveis e uma tabela de fatos:

```text
                 ┌───────────────────┐
                 │   dim_produto     │
                 │   id_produto (PK) │
                 └─────────┬─────────┘
                           │ 1:N
                           ▼
                 ┌───────────────────┐
                 │   fato_estoque    │
                 │   id_produto (FK) │
                 │   codunidade (FK) │
                 └─────────┬─────────┘
                           │ N:1
                           ▼
                 ┌───────────────────┐
                 │   dim_unidade     │
                 │  codunidade (PK)  │
                 └───────────────────┘
```

Um registro em `fato_estoque.csv` representa o estoque de um determinado produto em uma determinada unidade. Essa separação evita repetir o nome e os metadados de produto e unidade em cada relação de estoque.

| Arquivo | Finalidade |
| --- | --- |
| `dim_produto.csv` | Um registro por produto, com seu nome, unidade de fornecimento e estoque total calculado. |
| `dim_unidade.csv` | Uma linha por unidade de saúde, identificada por `codunidade`. |
| `fato_estoque.csv` | Relação produto–unidade e a quantidade disponível naquela unidade. |
| `transform_log.json` | Status, arquivo de entrada, métricas e validações bem-sucedidas da execução dimensional. |

As colunas e as validações efetivamente implementadas estão detalhadas em [docs/pipeline.md](docs/pipeline.md).

## Status da pipeline

| Etapa | Status |
| --- | --- |
| Extract | Implementado em `src.extract` |
| Raw storage | Implementado em `src.extract.save_raw` |
| Transform dimensional | Implementado em `src.transform` |
| Data validation | Implementado na transformação dimensional; relatório de perfil também existe em `src.quality` |
| Load em destino externo | Não implementado |

## Próximos passos

As funcionalidades abaixo não existem hoje e são apenas evoluções possíveis:

- carregar os dados processados em um destino persistente externo;
- definir atualização incremental entre coletas;
- orquestrar as execuções recorrentes;
- monitorar execuções e qualidade dos dados.
