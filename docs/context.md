# Contexto do projeto

## Nome e propósito

**Plataforma de Consulta da Disponibilidade de Medicamentos na Rede Pública de Saúde**

O projeto busca facilitar a consulta pública de disponibilidade de medicamentos nas unidades da rede municipal de saúde de Montes Claros (MG). A proposta é organizar e apresentar informações de forma acessível para ajudar a população a descobrir onde um medicamento aparece como disponível e reduzir deslocamentos desnecessários.

A plataforma pretende complementar os canais oficiais existentes, como o Portal Cidadão – Estoque do Vivver, e não substituí-los. Integrações com sistemas municipais e formas de atualização pelas unidades dependem de viabilidade técnica, autorização e validação com os responsáveis.

## Problema observado

Encontrar um medicamento na rede pública depende tanto da existência do produto quanto de informação clara, acessível e suficientemente atualizada sobre sua disponibilidade e localização. Pessoas podem se deslocar até uma unidade sem saber se o medicamento consta no estoque, com impacto maior para quem usa medicamentos continuamente, pessoas idosas, pessoas com mobilidade reduzida e quem mora longe dos serviços.

As conversas iniciais também destacaram a comunicação entre unidades, Secretaria de Saúde e população sobre estoque, faltas e reposição. Uma informação desatualizada pode, por si só, causar deslocamentos e frustração; confiabilidade e transparência fazem parte do problema central.

## Público e benefícios pretendidos

- **Público principal:** pessoas que procuram medicamentos fornecidos pela rede pública de saúde de Montes Claros, especialmente usuários de tratamento contínuo, pessoas idosas, pessoas com dificuldade de locomoção e moradores distantes das unidades.
- **Benefício direto pretendido:** tornar mais fácil consultar o medicamento e as unidades em que há informação de disponibilidade, com indicação explícita de quando os dados foram atualizados.
- **Benefícios indiretos possíveis:** apoiar profissionais e gestores na comunicação e observação de faltas e reposição, caso haja parceria e acesso autorizado a dados apropriados.
- **Estimativa inicial do grupo:** cerca de 100 pessoas beneficiadas. É uma estimativa de projeto, não uma medição de alcance ou resultado.

## Contexto de extensão e responsabilidade social

O projeto é uma atividade de extensão do Afya Centro Universitário de Montes Claros. O grupo entende extensão como aproximação entre faculdade e comunidade: aplicar conhecimentos acadêmicos a necessidades reais, aprender em colaboração e contribuir de forma responsável.

A referência global é o **Objetivo de Desenvolvimento Sustentável 3 (ODS 3) da ONU — Saúde e Bem-Estar**. O projeto contribui de forma delimitada para o acesso à informação relacionada à saúde. Não substitui serviços de saúde, assistência farmacêutica, avaliação profissional nem políticas públicas de abastecimento.

Princípios orientadores:

- respeito à dignidade, às diferenças e às necessidades da comunidade;
- comunicação clara, inclusiva e não estigmatizante;
- transparência sobre a origem, a data e as limitações dos dados;
- proteção da privacidade e coleta mínima de dados pessoais;
- validação das necessidades e dos efeitos da solução com a comunidade e os responsáveis pelo serviço.

## Evidências e descoberta

O grupo identificou o Portal Cidadão – Estoque do Vivver como iniciativa semelhante e fonte potencial de informação pública. Discussões com pessoas que buscam medicamentos, uma farmacêutica e uma participante ligada ao setor de compras levantaram necessidades de:

- localizar medicamentos e unidades;
- compreender melhor a disponibilidade informada;
- evitar viagens antes de confirmar a situação;
- melhorar a comunicação sobre faltas e reposição;
- eventualmente receber avisos de disponibilidade.

Essas conversas são descoberta inicial, não uma pesquisa representativa da população nem confirmação de que as unidades podem atualizar dados diretamente. As necessidades, a frequência de atualização desejada e as condições de acesso aos sistemas precisam ser verificadas com mais pessoas e com os responsáveis municipais.

## Visão do produto

Uma experiência pública simples, de fácil acesso e útil em dispositivos móveis, que ofereça o máximo de informação **confiável e autorizada** sobre:

- nome do medicamento conforme a fonte;
- unidades nas quais há registro de disponibilidade;
- quantidade, somente quando a fonte permitir sua divulgação e interpretação segura;
- data e hora da coleta ou atualização;
- fonte dos dados e explicação do significado de cada situação;
- avisos claros quando os dados estiverem antigos, incompletos ou indisponíveis.

Busca com sugestões por medicamento, filtro por unidade, diretório e mapa de cobertura parcial fazem parte do MVP atual. Alternativas próximas, alertas de reposição e previsões são possibilidades futuras. Não devem ser apresentados como capacidades existentes ou compromissos de abastecimento sem dados, autorização e validação suficientes. Em particular, uma previsão de reposição só deve ser exibida quando houver fonte oficial, método validado e data de referência explícitos.

O MVP inclui um mapa interativo no final da página. Ele apresenta pinos para unidades relacionadas a pontos publicados ou localizadas provisoriamente por endereço no OpenStreetMap; as 48 unidades continuam disponíveis no seletor e no diretório, com busca por nome/bairro, filtro por cobertura e pesquisa externa para as que não têm correspondência confiável. A fonte de estoque não fornece coordenadas, e pontos/endereço podem divergir; a interface explicita essa limitação e recomenda confirmar antes do deslocamento. A lista de pontos, referências OSM e notas de proveniência está em `src/static/unit_locations.json`. Ampliar a cobertura exige validar cada correspondência com uma fonte oficial ou com a unidade, além de manter atribuição e respeitar as condições de uso dos mapas e tiles. Não tratar uma geocodificação de endereço como confirmação operacional sem validação.

## Estado atual do repositório

O projeto inclui uma aplicação web local em Python, além da pipeline de coleta e processamento. O MVP pode consumir a captura JSON bruta `.txt` mais recente validada, ignorando arquivos de fixture identificados, e mantém um snapshot JSON validado como fallback. A interface oferece busca, sugestões, filtro por unidade e um mapa com cobertura geográfica parcial; o coletor registra o status das tentativas. A integração das rotas tabulares legadas, hospedagem pública, banco de dados, execução agendada, alertas ao usuário e atualização direta pelas unidades ainda não estão implementados.

A fonte pública de estoque do MVP continua sendo somente o Portal Vivver. A coleta agora passa por um adaptador explícito em `src.extract.sources`, o que permite testar ou adicionar fontes autorizadas sem misturar estoques automaticamente. Uma futura fonte cadastral, geográfica ou de contexto deve permanecer separada da fonte de quantidade; só deve ser publicada após autorização, contrato de dados, frequência de atualização e regra documentada para divergências.

Consulte [pipeline.md](./pipeline.md) para os detalhes técnicos confirmados. Trate capturas e contagens existentes como exemplos históricos: não significam disponibilidade atual.

## Direção para um MVP robusto

1. **Confiabilidade da coleta:** definir contrato da fonte, timeout, tentativas controladas, limites de requisição, identificação da execução e tratamento visível de falhas; preservar o dado original e sua proveniência.
2. **Qualidade e atualidade:** validar esquema, tipos, duplicidades e consistência; registrar horário de observação e resultado da execução; não substituir silenciosamente o último conjunto válido por uma coleta incompleta.
3. **Apresentação honesta:** separar “consta como disponível na fonte” de confirmação na unidade; exibir horário da última atualização, origem e avisos de defasagem.
4. **Acesso público:** evoluir a interface responsiva e compreensível com validação de acessibilidade e testes com a comunidade; validar e ampliar a cobertura geográfica do mapa sem criar localizações não confirmadas.
5. **Parceria e governança:** conversar com usuários, unidades e Secretaria de Saúde para validar interpretação, permissões, frequência de atualização e eventual integração.
6. **Evolução medida:** avaliar uso e redução de deslocamentos com métodos apropriados e sem presumir impacto antes de medi-lo.

Essa é uma direção de produto, não uma especificação técnica fechada. Decisões de infraestrutura, integração, autenticação, alertas e previsões devem seguir evidências, restrições e autorização dos responsáveis.

## Fonte mencionada

- [Portal Cidadão – Estoque (Vivver)](https://www.montesclaros-mg.vivver.com/estoque)
- [Artigo SciELO indicado na pesquisa do grupo](https://www.scielo.br/j/csp/a/SQNxybJVbkLFLRbNwmvMTdd/?lang=pt)

As fontes apoiam a descoberta e precisam ser verificadas quanto a atualidade, escopo e adequação a cada afirmação pública.
