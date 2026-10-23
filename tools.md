# Ferramentas / Conexões

Como os agentes alcançam fontes de dados reais. Somente leitura por padrão, nenhum segredo mora nesta pasta.

## Hoje
Nenhuma conexão externa está ligada ainda. Os agentes trabalham só com o que está em `substrate/` e com os documentos que eles mesmos geram (como `entendimento-<demanda>.md`). Isso é suficiente para começar.

## Servidor MCP interno do substrato (MVP 5 de aderência ao MuleSoft Agent Fabric)
`servidor/servidor_mcp.py` expõe `substrate/compendium.md` e `adrs/` como três ferramentas MCP (`consultar_stack_aprovada`, `consultar_adr`, `listar_padroes_da_casa`), no espírito da Enterprise Actionability do Agent Fabric: tornar um sistema existente consultável por agente sem reescrever a fonte. Roda hoje só localmente (`python3 servidor/servidor_mcp.py`, requer `pip install mcp`) e lê diretamente os arquivos do repositório — não altera nada, e retorna "não encontrado" em vez de inventar quando o substrato não cobre o assunto perguntado.

**Limitação conhecida:** a busca de `consultar_adr` é por substring simples (nome do arquivo ou conteúdo), não tokenizada — um termo com espaço ("cloud agnostica") não bate num nome de arquivo com hífen (`cloud-agnostica`) a menos que o texto do ADR também contenha a frase com espaço. Buscar por uma palavra só (ex.: "agnostica") funciona.

**Caminho de registro no Agent Fabric, quando a migração acontecer:** registrar este servidor no Agent Registry (URL do processo MCP, hoje inexistente porque roda local via stdio); aplicar as políticas do Omni Gateway já mapeadas em `governanca/policies.yaml` (MVP 3) ao tráfego MCP dele — em especial `MCP Schema Validation` nas três ferramentas; e decidir se algum agente do time passa a consumi-lo via MCP em vez de ler `substrate/compendium.md`/`adrs/` direto do disco (hoje nenhum consome, é só o servidor existindo isolado, testável via `python3 servidor/servidor_mcp.py --selftest`).

## MCP Bridge de operações internas (MVP 7 de aderência ao MuleSoft Agent Fabric)
`servidor/servidor_mcp_operacoes.py` expõe as operações hoje só disparáveis manualmente via `.claude/skills/arquiteto-solucoes/SKILL.md` (`argument-hint: "<pedido/SDR> | status <nome-da-demanda> | help"`) como três ferramentas MCP: `consultar_status_demanda` e `ajuda` (LEITURA, ativas por padrão) e `iniciar_demanda` (ESCRITA, **desativada por padrão** — decisão explícita registrada na sessão que criou este arquivo; ative `ESCRITA_ATIVADA` no script só com autorização humana). Servidor separado do MVP 5 porque este despacha operação, aquele só consulta conhecimento.

**Limitação real, não escondida:** este servidor roda como processo Python isolado, sem acesso à ferramenta `Task` do Claude Code — mesmo com `iniciar_demanda` ativada, ele não consegue de fato despachar os 19 subagentes. A tool, quando ativada, só confirma a intenção e aponta de volta para `/arquiteto-solucoes <pedido>` dentro de uma sessão Claude Code real. `consultar_status_demanda` funciona de verdade hoje (lê `demandas/<nome>/` no disco), incluindo os nomes de artefato pré-padronização (`apresentacao.md`, `pacote-final.md`).

**Caminho de registro no Agent Fabric, quando a migração acontecer:** aplicar `MCP Schema Validation` (MVP 3) às três ferramentas; manter `iniciar_demanda` como operação de escrita sob controle de acesso (ABAC/aprovação) mesmo depois de ativada, dado o custo de tokens que uma demanda completa representa (ver `telemetria-agentes.md`); resolver a limitação de despacho real de subagente antes de considerar esta tool utilizável em produção — hoje ela é só a interface, não a execução.

## Planejadas (a conectar quando fizer sentido)

| Fonte | Para que serve | Acesso | Como conectar depois |
|---|---|---|---|
| Repositório de código/documentação (Git, Confluence, Notion) | Trazer ADRs, diagramas e documentação de sistemas existentes de verdade para dentro de `substrate/compendium.md` | Somente leitura | Um conector já existente (ex: integração nativa) ou uma skill de sincronização que copia o conteúdo relevante para o compêndio |
| Ferramenta de backlog/projeto (Jira, Linear) | Trazer a demanda original e os requisitos de negócio para o agente de Entendimento e Escopo | Somente leitura | Um pequeno wrapper de linha de comando ou integração nativa que lê o card/ticket da demanda |
| Ferramenta de observabilidade real (Grafana, Datadog) | Dar ao agente de observabilidade dados reais de sistemas em produção, em vez de só propor métricas no vácuo | Somente leitura | Integração nativa de leitura de dashboards/métricas |

## Segredos
Nenhum segredo (senha, chave de API, token) deve morar nesta pasta. Quando qualquer uma das conexões acima for ligada de verdade, as credenciais ficam fora daqui, num cofre de segredos ou variável de ambiente do lado de fora do OS.
