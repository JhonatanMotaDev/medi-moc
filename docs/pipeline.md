# Pipeline ETL: Vivver Estoque MVP

Este documento descreve o comportamento presente no repositório. A fonte é o portal Vivver configurado para o município `3143302`; o código adiciona a descrição fixa `Montes Claros` e UF `MG` apenas na rota de normalização tabular (`src.transform.normalize`).

## Visão do fluxo

```text
Vivver
  ↓
src.extract.source.fetch_stock
  ↓
src.extract.source.save_raw
  ↓
data/raw/*.txt
  ↓
src.transform.transform (execução independente)
  ↓
dim_produto.csv + dim_unidade.csv + fato_estoque.csv + transform_log.json
  ↓
[Load em destino externo — não implementado]
```

O repositório também tem a rota `src.pipeline`, que usa `src.transform.parse`, `src.transform.normalize`, `src.transform.quality` e `src.load.load`. Ela preserva o raw, mas escreve uma representação tabular diferente em `estoque_montes_claros.csv` e, se o suporte estiver instalado, em `estoque_montes_claros.parquet`. Como `src.pipeline` não invoca `src.transform.transform`, as duas rotas não devem ser tratadas como uma única execução encadeada.

### Orquestração da coleta pública

`StockCollectionPipeline`, em `src.extract.collector`, coordena as etapas sem substituir os módulos especializados:

1. `extract()` consulta o adaptador de fonte ou lê um fixture JSON.
2. A resposta bruta é preservada em `data/raw/` antes da validação.
3. `transform()` valida o contrato e normaliza os dados para o snapshot público.
4. `load()` grava atomicamente o snapshot e o status da coleta.

`run()` executa essas etapas em ordem e registra falhas sem substituir o último snapshot válido. A função `collect()` permanece como entrada compatível para os chamadores existentes.

### Fontes adicionais

`src.extract.sources` define o contrato mínimo de uma fonte de estoque (`source_id`, `display_name` e `fetch`). O `VivverSource` é a implementação padrão e a única fonte de estoque publicada pelo MVP. Esse ponto de extensão não consolida dados de fontes diferentes: cada adaptador futuro deve produzir uma resposta que passe pela validação do snapshot e preservar sua própria origem e horário de coleta.

Cadastros de unidades, mapas, compras públicas ou confirmações manuais podem complementar a aplicação, mas não devem ser interpretados como quantidade disponível sem uma regra e autorização específicas. Em caso de divergência, a aplicação deve mostrar as fontes separadamente ou rejeitar a publicação; não deve somar quantidades nem escolher silenciosamente a fonte mais favorável.

## Extract

### Fonte e configuração

`src/config.py` declara:

- `BASE_URL`: base do portal Vivver de Montes Claros;
- `STOCK_PAGE`: página de estoque usada para obter o HTML inicial;
- `GRID_URL`: recurso consultado para os dados de estoque;
- `MUNICIPIO`: `3143302`.

`fetch_stock(config)` cria uma `requests.Session`, define os cabeçalhos `User-Agent` e `Accept`, e faz as requisições para `stock_page` e `grid_url` com timeout de 20 segundos por chamada. Do HTML retornado, `_csrf_from_html` tenta localizar o campo `authenticity_token` com duas expressões regulares. Em seguida, faz outro `GET` para `grid_url` com o município e os parâmetros de filtros vazios definidos no código; o token é incluído somente quando encontrado.

O retorno é um `ExtractedResponse` imutável com conteúdo textual, `Content-Type`, URL final, horário UTC da coleta e código HTTP. As duas chamadas usam `raise_for_status()`: erros de conexão são repetidos até três tentativas e respostas HTTP 429 ou 5xx usam espera limitada antes de uma nova tentativa. Se as tentativas se esgotarem, a exceção é propagada para `StockCollectionPipeline.run()`, que registra o status de falha.

### Armazenamento Raw

`save_raw(result, raw_dir)` cria o diretório quando necessário e grava `result.content` em UTF-8. O nome é construído como `vivver_estoque_<coletado_em>.txt`, usando o timestamp informado e removendo `:`, `.`, e substituindo o sufixo `+00:00` por `Z`.

Preservar a resposta antes da transformação permite reprocessar uma coleta, comparar mudanças na origem e investigar um resultado sem consultar novamente o portal. Os arquivos raw não são convertidos durante a gravação.

Comandos reais:

```bash
# consulta o portal e grava o raw; depois executa a rota tabular adicional
python -m src.pipeline

# usa o HTML de teste, sem chamada de rede
python -m src.pipeline --fixture tests/fixtures/estoque_sample.html
```

No modo fixture, `pipeline.py` lê o arquivo local, simula uma resposta HTTP com status 200 e salva o conteúdo em `data/raw/vivver_estoque_fixture.txt`.

## Formato Raw usado pela transformação dimensional

O arquivo `data/raw/vivver_estoque_2026-09-22T131443016020+0000.txt` é uma lista JSON com 215 objetos de produto. Cada objeto tem os campos obrigatórios:

```text
id_produto
nomproduto
unidade_fornecimento
qdeestoque
estoque_unidade[]
```

`estoque_unidade` é uma lista de registros por unidade, cujos campos obrigatórios são:

```text
codmunicipio, codunidade, id_produto, nomproduto,
nomfantasia, numtelefone, endereco_unidade, qdeestoque
```

Exemplo encurtado e anonimizado, mantendo a estrutura da captura:

```json
[
  {
    "id_produto": 9383,
    "nomproduto": "MEDICAMENTO EXEMPLO",
    "unidade_fornecimento": "AMPOLA",
    "qdeestoque": "2.0",
    "estoque_unidade": [
      {
        "codmunicipio": 3143302,
        "codunidade": 938,
        "id_produto": 9383,
        "nomproduto": "MEDICAMENTO EXEMPLO",
        "nomfantasia": "UNIDADE EXEMPLO",
        "numtelefone": "38 2211-4504",
        "endereco_unidade": "ENDEREÇO EXEMPLO",
        "qdeestoque": 2
      }
    ]
  }
]
```

O sufixo `.txt` não determina o formato: para a transformação dimensional, o conteúdo precisa ser uma lista JSON. `src.transform.transform` faz `json.load()` e rejeita uma raiz que não seja lista.

## Transform dimensional

### Execução

```bash
python -m src.transform.transform data/raw/vivver_estoque_2026-09-22T131443016020+0000.txt data/processed
```

Os dois argumentos posicionais são, nesta ordem, o arquivo JSON/TXT de entrada e o diretório de saída. O módulo não chama `fetch_stock` nem escolhe automaticamente o arquivo raw mais recente; a seleção é responsabilidade de quem executa o comando.

### Etapas executadas por `src.transform.transform`

1. Abre o arquivo em UTF-8 e faz o parsing JSON.
2. Valida a raiz, os campos obrigatórios do produto e os campos obrigatórios de cada registro em `estoque_unidade`.
3. Converte `id_produto`, `codmunicipio`, `codunidade` e as quantidades para inteiro. O conversor aceita representações como `"2.0"`, mas rejeita números não inteiros e valores inválidos.
4. Limpa textos: converte para string, aplica normalização Unicode NFKC, reduz sequências de espaços e remove espaços nas extremidades. Para telefone, mantém somente dígitos.
5. Separa dados de produto, dados únicos de unidade e relações de estoque por unidade.
6. Verifica as regras de consistência descritas em [Validações](#validações-da-transformação-dimensional).
7. Ordena produtos por `id_produto`, unidades por `codunidade` e fatos por `(id_produto, codunidade)`.
8. Grava os três CSVs com cabeçalho UTF-8 e gera `transform_log.json`.

O modelo passa de uma coleção aninhada para tabelas relacionáveis assim:

```text
Produto
└── estoque_unidade[]

dim_produto  ── 1:N ── fato_estoque ── N:1 ── dim_unidade
```

```text
                 ┌───────────────────┐
                 │    dim_produto    │
                 │   id_produto PK   │
                 └─────────┬─────────┘
                           │ 1:N
                           ▼
                 ┌───────────────────┐
                 │   fato_estoque    │
                 │   id_produto FK   │
                 │   codunidade FK   │
                 └─────────┬─────────┘
                           │ N:1
                           ▼
                 ┌───────────────────┐
                 │    dim_unidade    │
                 │   codunidade PK   │
                 └───────────────────┘
```

## Dados Processed

### `dim_produto.csv`

Uma linha por objeto de produto de entrada. `qdeestoque` é o total recalculado a partir das linhas de unidade, após a conferência contra o total informado na origem.

| Coluna | Tipo escrito | Papel |
| --- | --- | --- |
| `id_produto` | inteiro | Chave principal da dimensão. |
| `nomproduto` | texto | Nome normalizado do produto. |
| `unidade_fornecimento` | texto | Unidade de fornecimento normalizada. |
| `qdeestoque` | inteiro | Soma de estoque nas unidades. |

### `dim_unidade.csv`

Uma linha para cada `codunidade` encontrado. A primeira ocorrência do código fornece a linha; ocorrências posteriores precisam ter o mesmo nome, telefone e endereço.

| Coluna | Tipo escrito | Papel |
| --- | --- | --- |
| `codmunicipio` | inteiro | Código do município fornecido na linha de estoque. |
| `codunidade` | inteiro | Identificador da unidade e chave principal lógica. |
| `nomfantasia` | texto | Nome normalizado da unidade. |
| `numtelefone` | texto numérico | Telefone sem caracteres não numéricos. |
| `endereco_unidade` | texto | Endereço normalizado. |

### `fato_estoque.csv`

Uma linha por par `(id_produto, codunidade)`, contendo:

| Coluna | Tipo escrito | Papel |
| --- | --- | --- |
| `id_produto` | inteiro | Chave estrangeira lógica para `dim_produto`. |
| `codmunicipio` | inteiro | Município da ocorrência de estoque. |
| `codunidade` | inteiro | Chave estrangeira lógica para `dim_unidade`. |
| `qdeestoque` | inteiro | Quantidade do produto naquela unidade. |

Um registro em `fato_estoque` representa o estoque de um determinado produto em uma determinada unidade. A combinação produto–unidade deve ser única dentro da execução.

### `transform_log.json`

O log tem `arquivo_entrada`, `status` e `metricas`. As métricas incluem contagem de produtos, unidades, registros de estoque, estoque total e indicadores booleanos das validações aprovadas. Para a captura incluída, o log registra `success`, 215 produtos, 48 unidades, 6.791 registros e estoque total de 6.601.802.

### Saídas da rota tabular adicional

`src.pipeline` não é a transformação dimensional acima. Depois de `parse_response`, `normalize` renomeia colunas conhecidas, limpa textos, preserva identificadores como texto, tenta converter quantidades, adiciona metadados da fonte e remove linhas exatamente duplicadas. `quality_report.csv` descreve, por coluna, tipo, quantidade de linhas, nulos e valores distintos. `src.load.load.save_processed` grava `estoque_montes_claros.csv` e tenta gravar o Parquet; se o motor Parquet não estiver disponível, captura apenas `ImportError` e mantém o CSV.

O nome `load.py` nessa rota significa escrita de arquivos processados. Ele não realiza carga em banco, serviço ou outro destino externo.

## Interface web e apresentação

A interface não altera a pipeline de aquisição, transformação ou validação. Ela apenas lê uma captura pública já validada:

- `src.snapshot_store.SnapshotRepository` escolhe a captura válida mais recente em `data/raw/`, aplica a proteção contra quedas bruscas de volume, usa `data/processed/public_snapshot.json` como fallback e mantém um cache em memória enquanto a assinatura de modificação dos arquivos não muda. Isso evita reler e revalidar o JSON grande a cada requisição.
- `src.presentation.build_home_context` converte o snapshot em um modelo de tela imutável: resumo de disponibilidade por medicamento, unidades ordenadas com quantidade positiva primeiro, filtros ativos, opções de ordenação e janela de paginação. A função não modifica o snapshot validado.
- `src.web` expõe a página em `/` e as sugestões de medicamentos em `/api/medicines`. A busca ignora acentos e maiúsculas. Com uma busca ativa, o filtro de unidades relaciona apenas unidades com quantidade positiva nos resultados correspondentes; sem busca, relaciona todas as unidades.
- O template usa macros em `src/template/_macros.html` para cartões, linhas de catálogo, paginação e itens do diretório. O JavaScript em `src/static/search.js` implementa o combobox acessível, a atualização automática dos filtros e as interações do mapa. O mapa continua restrito aos pontos documentados em `src/static/unit_locations.json`.

O diretório de unidades fica recolhido por padrão e pode ser filtrado pela mesma pesquisa do mapa. A opção “Somente com pino” limita a lista às unidades com coordenadas documentadas; as demais continuam disponíveis para pesquisa externa. A interface não transforma ausência de pino em indisponibilidade e não confirma estoque atual.

## Validações da transformação dimensional

| O que é validado | Por que é importante | O que acontece quando falha |
| --- | --- | --- |
| Campos obrigatórios no produto e no registro filho; `estoque_unidade` deve ser lista. | Garante que a transformação encontra os atributos que usa. | `validate_schema` lança `ValueError` antes de gerar saídas. |
| Identificadores e quantidades devem ser inteiros. | Mantém chaves e quantidades consistentes. | `to_int` lança `ValueError`. |
| `estoque_unidade.id_produto` deve ser igual ao `id_produto` do pai. | Impede relacionar uma unidade ao produto errado. | O erro é acumulado; ao fim, `transform` lança `ValueError`. |
| `estoque_unidade.nomproduto` deve coincidir com o nome do pai após limpeza. | Detecta divergência descritiva entre pai e filho. | Erro acumulado e falha ao final. |
| O par `(id_produto, codunidade)` não pode se repetir. | Mantém a granularidade de um fato por produto e unidade. | Erro acumulado e falha ao final. |
| Mesmo `codunidade` deve ter o mesmo nome, telefone e endereço. | Evita uma dimensão de unidade ambígua. | Erro acumulado e falha ao final. |
| `qdeestoque` do produto deve ser igual à soma de `qdeestoque` das unidades. | Confere que o total publicado tem decomposição completa por unidade. | Erro acumulado e falha ao final. |

Quando há regras acumuladas inválidas, a exceção lista no máximo 20 mensagens e acrescenta `...` se houver outras. Como os arquivos são gravados somente depois de `transform` concluir, uma falha de validação impede a criação das saídas daquela execução.

`src.transform.quality.quality_report` também existe na rota tabular: ele apenas calcula perfil de coluna (tipo, linhas, nulos, percentual de nulos e distintos). Não impõe limiares nem bloqueia o processamento.

## Dependências e testes existentes

`requirements.txt` declara `requests`, `pandas`, `beautifulsoup4`, `lxml` e `pyarrow`. `requests` atende à coleta; `pandas`, Beautiful Soup e lxml são usados na rota tabular; `pyarrow` permite a escrita Parquet nessa rota. `transform.py` usa somente módulos da biblioteca padrão.

O teste em `tests/test_normalize.py` cobre a leitura de tabela HTML, a preservação de identificadores com zero à esquerda, a interpretação de `1.250` como 1250 e a remoção de duplicatas exatas. `tests/test_mvp.py` cobre validação do snapshot, coleta, seleção de capturas, diagnóstico, busca, filtros, ordenação, paginação, cache da interface e mapa. Não há teste automatizado da transformação dimensional em `src.transform.transform` no repositório atual.

## Estado atual e futuras evoluções

| Etapa | Status |
| --- | --- |
| Extract | Implementado |
| Raw storage | Implementado |
| Transform dimensional | Implementado |
| Validações dimensionais | Implementadas conforme `src.transform.transform` |
| Escrita de arquivos processados pela rota tabular | Implementada |
| Load em destino externo | Não implementado |

Uma carga em banco ou outro destino, atualização incremental, orquestração, monitoramento e alertas seriam evoluções futuras. Nenhuma dessas capacidades está configurada no código atual.
