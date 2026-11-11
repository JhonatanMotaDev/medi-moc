# Vivver Estoque MVP

Pipeline local para coletar e transformar dados públicos de estoque de medicamentos de Montes Claros disponíveis no portal Vivver. O projeto preserva a resposta recebida em `data/raw/` e contém uma transformação dimensional que produz tabelas de produto, unidade e estoque.

O objetivo de evolução é a **Plataforma de Consulta da Disponibilidade de Medicamentos na Rede Pública de Saúde**, uma ferramenta pública que complemente os canais oficiais com informações claras e atualizadas. O contexto do produto, público, princípios e direção do MVP estão em [docs/context.md](docs/context.md); orientações para agentes de IA estão em [docs/agents.md](docs/agents.md).

## Arquitetura

```text
Portal Vivver
    ↓
Extract (`src.extract.source`)
    ↓
data/raw/*.txt
    ↓
Transform dimensional (`src.transform.transform`)
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

> Há também o executor `src.pipeline`, com `src.transform.parse`, `src.transform.normalize`, `src.transform.quality` e `src.load.load`. Ele gera `estoque_montes_claros.csv`, Parquet quando disponível e `quality_report.csv`. Essa é uma saída tabular normalizada adicional; ele **não** chama `src.transform.transform` e não produz as três tabelas dimensionais.

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
│   ├── config.py
│   ├── extract/
│   │   ├── collector.py
│   │   ├── source.py
│   │   └── sources.py
│   ├── transform/
│   │   ├── transform.py
│   │   ├── snapshot.py
│   │   ├── parse.py
│   │   ├── normalize.py
│   │   └── quality.py
│   ├── load/
│   │   └── load.py
│   ├── pipeline.py
│   ├── monitoring.py
│   ├── presentation.py
│   ├── snapshot_store.py
│   ├── web.py
│   ├── template/
│   │   ├── stock.html
│   │   └── _macros.html
│   └── static/
│       ├── styles.css
│       ├── search.js
│       └── unit_locations.json
├── tests/
│   ├── fixtures/estoque_sample.html
│   ├── fixtures/stock_demo.json
│   ├── test_mvp.py
│   └── test_normalize.py
└── requirements.txt
```

### Fluxo em poucas palavras

1. **Extração:** `src.extract` consulta o portal e preserva a resposta original.
2. **Leitura e validação:** `src.transform` interpreta o retorno, valida os campos e organiza o estoque por medicamento e unidade.
3. **Publicação:** `StockCollectionPipeline` salva uma cópia pública sanitizada; `src.web` apresenta a consulta, e `src.presentation` prepara os dados da tela.
4. **Atualização e aviso:** GitHub Actions pode executar uma coleta diária autorizada, verificar a idade dos dados e sinalizar falhas.

As etapas ficam em módulos separados, com classes para coordenar os fluxos e descrições nos pontos de entrada. Para uma visão rápida do processamento, consulte `src/extract/collector.py`, `src/pipeline.py` e `src/monitoring.py`.

## Executar localmente

Requer Python 3.10 ou superior. No PowerShell, crie e ative um ambiente virtual e instale as dependências:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Para carregar a demonstração e iniciar a interface sem consultar a fonte externa:

```bash
python -m src.extract.collector --fixture tests/fixtures/stock_demo.json
python -m src.web
```

Abra [http://127.0.0.1:8000](http://127.0.0.1:8000). O fixture contém dados fictícios e não representa o estoque atual.

### Plataforma de consulta (MVP)

Se já houver uma captura JSON `vivver_estoque_*.txt` em `data/raw/`, a interface consegue carregá-la diretamente. Para obter dados novos ou criar uma captura quando não houver nenhuma válida, faça uma coleta:

```bash
python -m src.extract.collector
```

O coletor consulta o endpoint configurado do Vivver com timeout e retentativas limitadas, guarda a resposta bruta em `data/raw/`, valida o contrato e publica atomicamente `data/processed/public_snapshot.json`. A interface lê diretamente a captura JSON `.txt` válida mais recente em `data/raw/`, pela data embutida no nome do arquivo; ignora `.txt` que não tenham o formato JSON esperado e ignora também uma captura gerada por `--fixture`, identificada pelo status da coleta mesmo que tenha timestamp no nome. Se a captura mais recente tiver menos da metade dos medicamentos de uma captura válida anterior com pelo menos 50 produtos, a interface mantém a maior captura e avisa que ela pode estar desatualizada. O snapshot processado é usado como fallback se nenhuma captura bruta válida estiver disponível. O resultado de cada tentativa fica em `data/processed/collection_status.json`. Se uma coleta falhar, o snapshot válido anterior é preservado e a interface sinaliza a falha.

A orquestração dessas etapas fica em `StockCollectionPipeline`, em `src.extract.collector`: `extract` obtém a resposta, `transform` valida e normaliza os dados, e `load` publica o snapshot e o status. Cada etapa continua usando os módulos especializados do projeto.

As capturas preexistentes são históricas: a interface usa o timestamp do nome do arquivo (ou, se ausente, a data de modificação) como horário da captura, não como confirmação de atualização do estoque na unidade. Execute uma coleta nova antes de divulgar os resultados.

O MVP publica apenas o Vivver como fonte de estoque. A coleta usa o adaptador `src.extract.sources.VivverSource`, que mantém a identidade da fonte separada da validação do snapshot. Isso permite adicionar fontes autorizadas no futuro sem somar estoques ou escolher silenciosamente entre respostas divergentes; cadastros, mapas e compras devem continuar como fontes complementares, não como prova de disponibilidade.

Para depurar qual arquivo a interface selecionará, quantos registros foram lidos e por que capturas foram rejeitadas, rode:

```bash
python -m src.diagnostics
```

O diagnóstico informa apenas nomes de arquivos, status e contagens; não despeja os registros de estoque no terminal.

No diagnóstico, **“válida estruturalmente”** significa que o arquivo passou pelo contrato de dados; não confirma que a coleta trouxe o catálogo completo. Se uma captura mais recente trouxer menos da metade dos medicamentos de uma captura anterior com pelo menos 50, ela é preterida e a mais completa é exibida com aviso. Quando um status legado não identifica a origem, essa limitação aparece no diagnóstico.

Para visualizar a interface sem consultar a internet, use **somente o fixture fictício**:

```bash
python -m src.extract.collector --fixture tests/fixtures/stock_demo.json
```

O fixture é rotulado como demonstração e **não representa o estoque atual**. Para voltar a usar os dados consultados à fonte, execute a coleta sem `--fixture`.

Inicie o servidor local. Este comando mantém o terminal ocupado enquanto a aplicação estiver rodando; use `Ctrl+C` para encerrar. Depois de atualizar o código, encerre o servidor anterior e inicie-o novamente para garantir que o processo carregue as alterações:

```bash
python -m src.web
```

Abra [http://127.0.0.1:8000](http://127.0.0.1:8000). A aplicação oferece sugestões acessíveis de medicamentos enquanto a pessoa digita, filtro por unidade, catálogo paginado, ordenação por relevância, resumo de disponibilidade e filtros removíveis. Quantidade, apresentação do medicamento e horário da consulta aparecem juntos para facilitar a leitura. O mapa destaca pontos documentados e oferece pesquisa externa para as demais unidades. O diretório pode ser pesquisado e filtrado junto com o mapa. Em implantação, `APP_STALE_AFTER_HOURS` ajusta o limite do aviso de desatualização (padrão: 24 horas; não é SLA oficial).

### Publicar no Render

O arquivo `render.yaml` configura um serviço web Python com Waitress e deploy automático a cada atualização da branch `master`. Para publicar:

1. Envie o repositório ao GitHub e autorize o Render a acessá-lo.
2. No Render, crie um **Blueprint** e selecione `JhonatanMotaDev/medi-moc`; confirme o serviço gratuito `medi-moc`.
3. Após o deploy, abra a URL pública `*.onrender.com` atribuída e exibida no painel do Render.

O snapshot inicial em `data/processed/public_snapshot.json` permite que o site já abra com dados; ele é uma captura histórica e a página sinaliza sua idade. Com a atualização diária autorizada, o workflow publica uma nova captura quando os dados mudam. O site não exige conta para consulta; autenticação de usuários não está implementada.

### Atualização diária e alertas

O workflow `.github/workflows/refresh-stock.yml` pode consultar a fonte uma vez por dia às 09:17 UTC e publicar um snapshot novo no GitHub; essa atualização aciona o deploy automático do Render. Para evitar coleta não autorizada, o workflow fica desativado até confirmar que a autorização cobre consulta automatizada e republicação dos dados. Em **Settings → Secrets and variables → Actions → Variables → New repository variable**, crie `VIVVER_COLLECTION_AUTHORIZED` com o valor `true`.

O workflow verifica se a atualização falhou ou se os dados passaram de 36 horas. Uma execução problemática fica marcada como falha no GitHub Actions. Para receber também um aviso em webhook compatível com Slack, crie em **Settings → Secrets and variables → Actions → Secrets** o segredo `COLLECTION_ALERT_WEBHOOK_URL`. O webhook é opcional; sem ele, o log e o status da execução no GitHub Actions registram a falha. Para testar após habilitar a autorização, use **Actions → Atualizar consulta de estoque → Run workflow**.

Antes de disponibilizar publicamente, confirme que a autorização acadêmica também cobre a coleta automatizada e a republicação dos campos na aplicação.

A busca oferece sugestões de medicamentos após duas letras e o filtro de unidades lista unidades com quantidade positiva nos resultados correspondentes; sem busca, lista todas as unidades. A camada `src.presentation` transforma o snapshot validado em um modelo de tela sem alterar os dados, e `src.snapshot_store.SnapshotRepository` reutiliza a leitura enquanto os arquivos de origem não mudam. O mapa não comprova estoque nem substitui a confirmação do endereço e da disponibilidade com a unidade. Os pontos mapeados vêm do OpenStreetMap; os endereços operacionais vêm do conjunto de estoque do Vivver e podem divergir. A tela sinaliza unidades sem pino documentado e permite pesquisá-las no Google Maps.

Antes de disponibilizar publicamente, confirme que a autorização acadêmica também cobre a coleta automatizada e a republicação dos campos na aplicação. A tela distingue o horário de consulta do horário de atualização do estoque na unidade: a fonte consultada não fornece este último. A página orienta as pessoas a confirmar diretamente com a unidade antes do deslocamento.

Valide o fluxo sem rede:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

O roteiro para testar compreensão e utilidade com a comunidade está em [docs/mvp-validation.md](docs/mvp-validation.md). Testes automatizados não substituem essa validação com pessoas usuárias.

### Pipeline tabular e transformação dimensional legadas

Para executar a transformação dimensional sobre a captura incluída:

```bash
python -m src.transform.transform data/raw/vivver_estoque_2026-09-22T131443016020+0000.txt data/processed
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
| Extract | Implementado em `src.extract.source` |
| Raw storage | Implementado em `src.extract.source.save_raw` |
| Transform dimensional | Implementado em `src.transform.transform` |
| Data validation | Implementado na transformação dimensional; relatório de perfil também existe em `src.transform.quality` |
| Load em destino externo | Não implementado |

## Próximos passos

As funcionalidades abaixo não existem hoje e são apenas evoluções possíveis:

- carregar os dados processados em um destino persistente externo;
- definir atualização incremental entre coletas;
- orquestrar as execuções recorrentes;
- monitorar execuções e qualidade dos dados.
