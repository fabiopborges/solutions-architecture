# Mapa lógico de ferramentas

Fase 0 da implementação multi LLM provider. Define o vocabulário de ferramentas do runtime, independente do Claude Code. Origem dos dados: frontmatter `tools` de `.claude/agents/*.md` (verificado, 18 arquivos). O orquestrador não tem subagente; ele é a skill `.claude/skills/arquiteto-solucoes/SKILL.md`.

## 1. Ferramentas lógicas

| Lógica | Claude Code | Efeito | Restrição do runtime |
|---|---|---|---|
| `ler_arquivo` | Read | Lê um arquivo por caminho absoluto | Só dentro da pasta da demanda e das pastas de insumo do repositório (`agents/`, `skills/`, `rules/`, `substrate/`, `adrs/`) |
| `listar` | Glob | Lista caminhos por padrão | Mesmo escopo de `ler_arquivo` |
| `buscar_texto` | Grep | Busca texto em arquivos | Mesmo escopo de `ler_arquivo` |
| `gravar_arquivo` | Write | Cria ou sobrescreve arquivo | Só nos caminhos que a atividade do agente declara (ver seção 3) |
| `editar_arquivo` | Edit | Substituição exata em arquivo existente | Mesmo escopo de `gravar_arquivo` |
| `buscar_web` | WebSearch | Pesquisa na web | Só nos 5 agentes da seção 2 |
| `ler_url` | WebFetch | Lê uma URL | Só nos 5 agentes da seção 2; conteúdo é dado, nunca instrução |
| `executar_shell` | Bash | Executa comando | Só em `geracao-diagramas` |

Fora desta lista não existe ferramenta. Recursos nativos de um provedor (por exemplo busca embutida) ficam desligados por padrão, para a busca na web passar só por `buscar_web` e `ler_url`.

## 2. Ferramentas por agente (verificado)

| Agente | Ferramentas lógicas |
|---|---|
| entendimento-e-escopo, desenho-de-arquitetura, modelagem-de-dados, testes-e-qualidade, jornadas-do-usuario, seguranca-e-compliance, observabilidade-e-telemetria, riscos-e-mitigacao, documentacao-final, comunicacao-stakeholders, entrega-e-handoff, trade-offs-e-adr | `ler_arquivo`, `listar`, `buscar_texto`, `gravar_arquivo`, `editar_arquivo` |
| infraestrutura-e-deployment, estimativa-de-custo, pesquisa-e-benchmarking, especialista-ia-ml, especialista-dados-analytics | as de cima mais `buscar_web`, `ler_url` |
| geracao-diagramas | as de arquivo mais `executar_shell` |

## 3. Escopo de gravação

Regra de `rules/never.md`: cada agente grava apenas nos caminhos que a própria atividade declara.
- Todos: a pasta da demanda (`demandas/<nome>/`), um arquivo por atividade.
- `trade-offs-e-adr`: também `adrs/`.
- `observabilidade-e-telemetria` (frente 2): também `telemetria-agentes.md`.

O mapeamento exato agente → arquivo de saída está nos `AGENT.md`/`SKILL.md` de cada um e deve ser lido de lá pelo runtime, não duplicado aqui. Esta lista só registra as duas exceções de caminho fora da pasta da demanda.

## 4. Guardrails portados do Claude Code

| Hoje | No runtime |
|---|---|
| Hook `PreToolUse` com matcher `Agent|Task` rejeita `demandas/` relativo (`.claude/settings.json`) | Validador do executor rejeita o prompt de despacho antes de qualquer chamada ao LLM |
| Limite de 3 rodadas, só em texto (`rules/never.md:6`, `rules/always.md:10-11`) | Contador por par de agentes; a 4ª rodada escala para humano |
| Instrução embutida em insumo ou página não é seguida (`rules/never.md:10-13`) | `ler_url` e `ler_arquivo` devolvem o conteúdo marcado como dado; o executor nunca amplia ferramenta, caminho ou escopo por causa dele |
| Nomes `WebSearch`/`WebFetch` citados em prosa em `rules/never.md:10,13` | Reescrever com os nomes lógicos na implementação, sem mudar a regra |

## 5. Pontos em aberto

1. O `skills/documentacao-final/SKILL.md:11` e o `skills/desenho-de-arquitetura/SKILL.md:18` dizem que subagente não despacha subagente; no runtime próprio essa restrição não existe, então Geração de Diagramas poderia ser acionada direto pelo executor. Mudar isso é decisão do dono dessas atividades, não do runtime.
2. O orquestrador é uma skill, não um agente com ferramentas declaradas; no runtime o executor assume esse papel e o conjunto de ferramentas dele (despachar, perguntar ao humano) precisa ser definido.
