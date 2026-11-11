# Instruções para agentes de IA

Este documento orienta agentes que trabalham neste repositório. Leia o código afetado e valide o estado atual antes de alterar comportamento; este resumo não substitui a implementação como fonte de verdade.

## Contexto do produto

O projeto pretende evoluir para a **Plataforma de Consulta da Disponibilidade de Medicamentos na Rede Pública de Saúde**, voltada à população de Montes Claros (MG). Seu objetivo é facilitar a consulta sobre medicamentos e unidades, contribuir para evitar deslocamentos desnecessários e complementar canais oficiais, como o Portal Cidadão – Estoque do Vivver.

Leia [context.md](./context.md) para o contexto destinado a pessoas: problema, público, descoberta, princípios éticos, visão de produto e direção de evolução. Leia [pipeline.md](./pipeline.md) para os detalhes técnicos documentados.

## Princípios obrigatórios de produto e dados

- Nunca apresente uma captura histórica ou dado local como disponibilidade atual.
- Diferencie claramente “disponível segundo a fonte” de confirmação de estoque pela unidade.
- Preserve e exponha proveniência e horário de observação/atualização sempre que a interface ou saída for usada para informar o público.
- Não invente previsão de reposição, disponibilidade futura, geolocalização ou alternativas.
- Não afirme integração com sistemas municipais, atualização por UBS ou autorização que ainda não foi estabelecida.
- Trate falha, dado parcial, desatualização e ausência de informação explicitamente; não transforme incerteza em sucesso ou em “indisponível”.
- Minimize dados pessoais. O projeto não precisa de informações clínicas ou identificáveis para consulta pública de estoque; não introduza sua coleta sem necessidade demonstrada, salvaguardas e autorização apropriada.
- Prefira linguagem acessível, inclusiva e não alarmista. A ferramenta informa; não substitui orientação profissional, assistência farmacêutica ou canais oficiais.
- Respeite a fonte, seus termos e limites de acesso. Prefira integrações oficiais e autorizadas; não contorne controles de acesso.
- O mapa interativo atual usa Leaflet/OpenStreetMap e tem cobertura parcial. Use somente pontos documentados em `src/static/unit_locations.json`; preserve a nota de proveniência e diferencie pontos publicados de geocodificações provisórias por endereço. Não marque unidades sem correspondência confiável. Preserve os links de origem OSM e a atribuição dos tiles. Todas as unidades podem aparecer no diretório, seletor, busca e pesquisa externa mesmo sem pino.

## Contexto de extensão

É um projeto de extensão acadêmica do Afya Centro Universitário de Montes Claros, com referência ao ODS 3 da ONU — Saúde e Bem-Estar. Deve promover aproximação responsável com a comunidade, respeito às diferenças, transparência e validação com usuários e responsáveis municipais. As conversas iniciais e a estimativa de 100 pessoas beneficiadas são insumos exploratórios, não evidência representativa nem impacto medido.

## Estado técnico conhecido

O repositório implementa uma pipeline local em Python e contém **duas rotas independentes**:

1. **Transformação dimensional:** um JSON local em `data/raw/` alimenta `src.transform.transform`, que escreve dimensões de produto e unidade, fatos de estoque e log em `data/processed/`.
2. **Pipeline tabular:** `src.pipeline` coordena `src.extract.source`, `src.transform.parse`, `src.transform.normalize`, `src.transform.quality` e `src.load.load`, gerando CSV/Parquet e relatório de qualidade. Pode usar um fixture HTML ou consultar a fonte configurada.

`src.pipeline` não chama `src.transform.transform`. `src.load.load` grava arquivos locais; não é integração com banco ou serviço externo. A aplicação web do MVP está em `src.web`; ela lê um snapshot JSON local e oferece busca com sugestões acessíveis, filtro de unidade, resumo de disponibilidade, catálogo paginado com ordenação, filtros ativos removíveis, diretório recolhível e mapa geográfico de cobertura parcial. `src.snapshot_store` concentra a seleção e o cache da captura pública; `src.presentation` transforma o snapshot validado em modelo de tela sem alterar os dados. O coletor público está em `src.extract.collector`. Não há hospedagem pública, agendamento, alertas para pessoas usuárias, banco de dados ou mecanismo de edição por unidades. Confirme esses fatos no código antes de usar, pois o repositório pode evoluir.

## Direção para coleta robusta

Em mudanças de coleta ou transformação, favoreça soluções verificáveis e explícitas:

- preservar a resposta bruta e registrar fonte, instante de coleta, duração e resultado;
- estabelecer limites de tempo, tentativas e requisições adequados à fonte, sem loops agressivos;
- validar esquema e invariantes antes de publicar saídas;
- evitar substituir dados válidos por uma coleta incompleta ou inválida;
- distinguir falha de coleta, ausência de registros e quantidade zero;
- produzir logs/erros úteis sem expor segredos ou dados sensíveis;
- testar sucesso, dados inválidos, falhas de rede e comportamento com fixtures locais.

Esses pontos são critérios de evolução, não funcionalidades que se deve presumir implementadas. Evite escolher infraestrutura ou fundir as rotas sem requisito explícito e análise dos contratos existentes.

## Fluxos e validações existentes

```text
# Transformação dimensional de captura local
python -m src.transform.transform data/raw/<arquivo>.txt data/processed

# Pipeline tabular com fixture (sem depender da rede)
python -m src.pipeline --fixture tests/fixtures/estoque_sample.html

# Pipeline tabular consultando a fonte
python -m src.pipeline
```

As validações dimensionais incluem esquema requerido, integridade de produto filho, unicidade do par produto–unidade, consistência de metadados da unidade e soma do estoque por produto. O relatório de `src.transform.quality` é descritivo. Verifique `requirements.txt` e o ambiente antes de escolher comandos de teste; não presuma ferramentas instaladas.

## Procedimento ao implementar

1. Inspecione a implementação, os testes e a documentação pertinentes.
2. Mantenha a alteração alinhada aos contratos existentes ou explicite e teste uma mudança de contrato.
3. Use fixtures nos testes sempre que possível; não dependa da rede para testes unitários.
4. Atualize documentação diretamente relacionada e execute o menor teste/build relevante.
5. Descreva limitações e premissas que continuem abertas; não apresente metas futuras como capacidades atuais.
