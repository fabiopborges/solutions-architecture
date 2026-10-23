# Especificação: time de agentes multi LLM provider

| Campo | Valor |
|---|---|
| Status | Rascunho para revisão do time (nada aprovado, nada implementado) |
| Origem | Plano aprovado em `~/.claude/plans/fa-a-uma-an-lise-completa-snuggly-spring.md` |
| Decisões já tomadas | Runtime próprio em Python; roteamento por configuração fixa por agente, com cadeia de fallback; 6 provedores na primeira entrega |
| Pré-requisito | PR #7 (`feat/governanca-...`) mergeado: cards A2A, `orquestracao/agent-network.yaml`, `governanca/policies.yaml`, `telemetria/interacoes.jsonl` |
| Decisão pendente de humano | Quais provedores podem receber dados reais de demanda (seção 9) |

**Convenção de leitura.** "Verificado" significa conferido no repositório. "A confirmar" significa hipótese que a doc oficial do provedor precisa validar antes da implementação. Nenhum comportamento de API de terceiros foi testado.

---

## 1. Contexto e problema

O time de 19 agentes só roda dentro do Claude Code. O conteúdo é portável (`agents/*/AGENT.md`, `skills/*/SKILL.md`, `rules/`, `substrate/compendium.md`, fluxo em arquivos `demandas/<nome>/*.md`). A execução não é:

| Acoplamento (verificado) | Onde |
|---|---|
| Despacho e paralelismo via ferramenta `Task` | `.claude/skills/arquiteto-solucoes/SKILL.md:22-36` |
| Modelo herdado da sessão, nunca declarado | frontmatter de `.claude/agents/*.md`; `memory.md:59` |
| Nomes de ferramentas do Claude Code (`Read, Write, Edit, Glob, Grep, WebSearch, WebFetch, Bash`) | frontmatter `tools`; `rules/never.md:10,13` |
| Hook de caminho absoluto no despacho | `.claude/settings.json`; `rules/always.md:13-16` |
| Limite de 3 rodadas de dúvida só descrito em texto | `rules/never.md:6`, `rules/always.md:10-11` |
| Restrição "subagente não despacha subagente" vazada para o conteúdo | `skills/documentacao-final/SKILL.md:11`, `skills/desenho-de-arquitetura/SKILL.md:18` |
| Custo e tokens lidos à mão do painel de billing | `skills/observabilidade-e-telemetria/SKILL.md:18` |

## 2. Objetivos e não objetivos

**Objetivos**
1. Executar a mesma cadeia de agentes em Anthropic, OpenAI, Google Gemini, DeepSeek, Grok (xAI) e modelos locais, sem alterar o conteúdo de `agents/` e `skills/`.
2. Definir o modelo de cada agente em um catálogo versionado, com cadeia de fallback, em vez de herdá-lo da sessão.
3. Registrar cada chamada de LLM (provedor, modelo, tokens de entrada e saída, latência, tentativa) para custo real por agente.
4. Preservar as regras do time: caminho absoluto, limite de 3 rodadas, suposições e trade-offs escritos, nenhum agente decide fora do seu escopo, nenhum custo estimado pelo agente de observabilidade.
5. Manter o Claude Code funcionando como mais um adaptador de execução.

**Não objetivos**
- Roteamento dinâmico por custo ou latência (decisão: configuração fixa).
- Reescrever agentes ou skills.
- Treinar ou fazer fine-tuning de modelos.
- Expor o runtime como serviço de rede; nesta fase é processo local.

## 3. Requisitos

### 3.1 Funcionais

| ID | Requisito |
|---|---|
| RF-01 | O runtime lê `agents/<x>/AGENT.md` e `skills/<x>/SKILL.md` e monta o prompt do agente sem depender do formato `.claude/agents/`. |
| RF-02 | Cada agente tem entrada em `config/models.yaml` com modelo primário e cadeia de fallback ordenada. |
| RF-03 | O executor percorre o grafo de `orquestracao/agent-network.yaml`, respeitando dependências e executando em paralelo os ramos independentes. |
| RF-04 | Cada agente roda em contexto novo; o único estado compartilhado são os artefatos em disco da pasta da demanda. |
| RF-05 | Antes de rodar, o executor valida as capacidades exigidas pelo agente contra as capacidades declaradas do modelo e falha com mensagem explícita se não baterem. |
| RF-06 | O runtime implementa o catálogo lógico de ferramentas (seção 5.4) e recusa ferramenta fora da lista do agente. |
| RF-07 | O contador de rodadas de dúvida entre o mesmo par de agentes escala para humano na 4ª rodada. |
| RF-08 | Todo prompt de despacho que cite `demandas/` sem prefixo absoluto é rejeitado antes da chamada ao LLM. |
| RF-09 | Cada chamada gera uma linha em `telemetria/interacoes.jsonl` com o schema da seção 5.6. |
| RF-10 | Todo fallback gera registro e alerta; nunca é silencioso. |
| RF-11 | O gate de saída (aprovação humana) continua sendo etapa manual; o runtime só marca "preparado". |
| RF-12 | Conteúdo vindo de insumos ou de páginas buscadas não pode alterar caminho de gravação, ferramentas nem escopo (regra de `rules/never.md:10-13`). |

### 3.2 Não funcionais

| ID | Requisito | Critério mensurável |
|---|---|---|
| RNF-01 | Isolamento de SDK | Só `runtime/adapters/llm/<provedor>/` importa SDK de fornecedor; verificado por teste que falha se outro pacote importar. |
| RNF-02 | Resiliência | Falha injetada (429, 5xx, timeout) aciona retry e fallback conforme `config/models.yaml`, com teste automatizado. |
| RNF-03 | Rastreabilidade | 100% das chamadas com linha no JSONL; soma de tokens do JSONL igual ao total reportado pelo provedor na mesma janela, a conferir por amostra. |
| RNF-04 | Segredos | Chaves só por variável de ambiente; nunca em `config/`, logs nem artefatos. |
| RNF-05 | Determinismo de configuração | Mesmo `models.yaml` e mesma entrada resultam na mesma escolha de modelo. |
| RNF-06 | Testabilidade sem rede | Cada adaptador tem modo de resposta gravada para rodar a suíte sem chave. |

## 4. Princípios de arquitetura e padrões

| Padrão | Aplicação | Trade-off |
|---|---|---|
| Ports and Adapters | Núcleo depende de `LLMClient`, `ToolRunner`, `TelemetrySink`; cada provedor é um adaptador | Mais código que usar uma biblioteca única; em troca, nenhum vazamento de SDK |
| Anti-corruption layer | Cada adaptador traduz schema de ferramenta, parsing de chamada, formato de resultado e erros para o modelo canônico | Perde recursos exclusivos de um provedor, a menos que exponha como capacidade opcional |
| Capability negotiation | Modelo declara capacidades; agente declara exigências; validação antes de rodar | Exige manter o catálogo atualizado |
| Fallback chain com circuit breaker | Failover entre provedores e fallback de modelo, com cooldown por deployment | Fallback pode degradar qualidade; mitigado por RF-10 |
| Registro de execução por chamada | JSONL por chamada, mapeável para convenções GenAI do OpenTelemetry | Convenções OTel ainda em desenvolvimento; mapeamento isolado em um módulo |
| A2A + MCP | Card A2A descreve o agente e agora requisitos de inferência; MCP continua para ferramentas | Adiciona um bloco ao card existente |

Fontes de referência: [LiteLLM Router](https://docs.litellm.ai/docs/routing) (alias, ordem, cooldown, retry por tipo de erro) e [A2A 1.0.0](https://a2a-protocol.org/latest/specification/). Demais práticas citadas vêm de material secundário e valem como diretriz. Não foi encontrada fonte sólida sobre portabilidade de saída estruturada nem sobre negociação de capacidades; esses dois desenhos são proposta do time e devem ser validados no MVP 0 e no MVP 1.

## 5. Arquitetura alvo

### 5.1 Estrutura

```
agents/ skills/ rules/ substrate/       conteúdo (inalterado)
config/models.yaml                      catálogo de modelos e roteamento por agente
runtime/
  core/        executor, grafo, contador de rodadas, validador de caminho, gate de saída
  ports/       LLMClient, ToolRunner, TelemetrySink
  adapters/
    llm/       anthropic, openai, gemini, deepseek, grok, local
    tools/     fs, web, shell
  routing/     catálogo, fallback, circuit breaker, capability check
  telemetry/   JSONL por chamada, mapeamento OTel opcional
tests/runtime/ contrato por adaptador, equivalência, falha injetada
```

### 5.2 Fluxo de uma chamada

1. O executor escolhe o próximo agente pronto no grafo.
2. O roteador resolve o modelo primário em `models.yaml` e valida capacidades (RF-05).
3. O executor monta o prompt (AGENT.md, SKILL.md, regras), em contexto novo.
4. O `LLMClient` do adaptador envia; o adaptador normaliza a resposta e os erros.
5. Se houver chamada de ferramenta, o `ToolRunner` valida contra a lista do agente e o caminho absoluto, executa e devolve o resultado normalizado.
6. Em erro, aplica retry por tipo de erro; esgotado, passa ao próximo da cadeia, registrando o fallback.
7. Cada chamada grava uma linha de telemetria.

### 5.3 Porta `LLMClient` (contrato canônico)

```python
class LLMClient(Protocol):
    def capabilities(self) -> Capabilities: ...
    def complete(self, request: LLMRequest) -> LLMResponse: ...

# LLMRequest: modelo, mensagens canônicas (system/user/assistant/tool_result),
#   ferramentas (nome, descrição, JSON Schema), formato de saída opcional (JSON Schema),
#   limites (max_output_tokens, timeout_s), metadados (demanda, agente, tentativa)
# LLMResponse: texto, chamadas_de_ferramenta[], tokens{entrada,saida,cache},
#   modelo_efetivo, motivo_parada, latencia_ms, erro_normalizado?
# Capabilities: tool_use, saida_estruturada, janela_contexto, streaming, visao, raciocinio_explicito
```

Erros normalizados: `RATE_LIMIT`, `TIMEOUT`, `INDISPONIVEL`, `AUTH`, `CONTEXTO_EXCEDIDO`, `CONTEUDO_BLOQUEADO`, `REQUISICAO_INVALIDA`, `DESCONHECIDO`. Só os três primeiros disparam retry no mesmo modelo; `CONTEXTO_EXCEDIDO` e `CONTEUDO_BLOQUEADO` vão direto para fallback de modelo; `AUTH` e `REQUISICAO_INVALIDA` falham sem fallback.

### 5.4 Catálogo lógico de ferramentas

| Lógica | Equivalente no Claude Code | Implementação no runtime |
|---|---|---|
| `ler_arquivo`, `listar`, `buscar_texto` | Read, Glob, Grep | `adapters/tools/fs`, restrito às pastas da atividade |
| `gravar_arquivo`, `editar_arquivo` | Write, Edit | `adapters/tools/fs`, só nos caminhos que a atividade declara |
| `buscar_web`, `ler_url` | WebSearch, WebFetch | `adapters/tools/web`, só nos 5 agentes que hoje têm essa permissão |
| `executar_shell` | Bash | `adapters/tools/shell`, só em Geração de Diagramas |

Por `rules/never.md`, instrução encontrada em insumo ou página buscada é achado a registrar, nunca a seguir.

### 5.5 `config/models.yaml` (schema proposto)

```yaml
versao: 1
modelos:
  <alias>:                  # alias lógico, ex.: pesado, rapido, local
    provedor: anthropic     # anthropic|openai|gemini|deepseek|grok|local
    id: <id-do-modelo>      # a preencher com o id oficial vigente
    capacidades: {tool_use: true, saida_estruturada: true, janela_contexto: <n>}
    preco: {entrada_por_mtok: <n>, saida_por_mtok: <n>, fonte: <url>, verificado_em: <data>}
    politica_dados: {classificacao: aprovado|restrito|proibido_dado_real}
roteamento:
  <nome-do-agente>:
    primario: <alias>
    fallback: [<alias>, <alias>]
    exige: [tool_use]
resiliencia:
  retries: {RATE_LIMIT: 3, TIMEOUT: 2, INDISPONIVEL: 2}
  cooldown_s: 30
  falhas_para_abrir_circuito: 3
```

Os ids de modelo e os preços não são preenchidos nesta especificação: mudam com o tempo e devem vir da doc oficial no dia da implementação, com data de verificação.

### 5.6 Schema de telemetria por chamada (extensão do `interacoes.jsonl`)

Campos atuais (verificado): `timestamp_inicio`, `timestamp_fim`, `agente_origem`, `agente_destino`, `demanda`, `tipo`, `resultado`, `artefato_gerado`, `tokens_consumidos`, `confidence_score`, `hallucination_risk`, `bottleneck_flag`, `source_id`, `destination_id`.

Campos novos: `provedor`, `modelo_solicitado`, `modelo_efetivo`, `tokens_entrada`, `tokens_saida`, `tokens_cache`, `latencia_ms`, `tentativa`, `fallback_de`, `erro_normalizado`, `custo_calculado`, `fonte_preco`.

`tokens_consumidos` permanece como soma, para não quebrar `scripts/coletar_telemetria.py`. O `custo_calculado` é aritmética sobre tokens reais e a tabela versionada, com a fonte registrada; ele não é estimativa do agente de observabilidade, que continua proibido de estimar.

### 5.7 Extensão do card A2A

Bloco novo `inference` em `registry/agent-cards/<agente>.json`: `modelo_preferido` (alias), `capacidades_exigidas`, `fallback`. O campo `provider` existente continua sendo a organização dona do agente, não o provedor de LLM.

## 6. Plano de entrega: um MVP por provedor

Cada MVP é independente depois do MVP 0, entrega algo verificável e tem critério de saída próprio. A ordem sugerida reflete risco crescente.

### MVP 0: Fundação (sem provedor externo)

**Objetivo.** Núcleo do runtime rodando com um adaptador falso, para provar a arquitetura antes de gastar com API.

**Escopo**
- `runtime/core`, `ports`, `routing`, `telemetry`, `adapters/tools/fs`.
- Adaptador `fake` que devolve respostas gravadas (base do RNF-06).
- Executor do grafo com paralelismo, contador de 3 rodadas, validador de caminho absoluto.
- `config/models.yaml` com schema validado.
- ADR da decisão de runtime próprio, via agente `trade-offs-e-adr`, com gate humano.

**Critérios de aceite**
- Grafo de `agent-network.yaml` executa com o adaptador `fake`, na ordem e com o paralelismo esperados.
- 4ª rodada entre o mesmo par escala para humano; prompt com `demandas/` relativo é rejeitado.
- Teste de isolamento de SDK passa.
- Linha de telemetria gerada por chamada, no schema da seção 5.6.

**Riscos.** Reproduzir o isolamento de contexto do `Task`. Mitigação: contexto novo por agente, só artefatos em disco.

### MVP 1: Anthropic (baseline)

**Objetivo.** Reproduzir o comportamento atual no runtime próprio, para ter linha de base contra a qual comparar todos os outros.

**Escopo.** Adaptador `anthropic`; mapeamento de ferramentas; agente piloto `entendimento-e-escopo`, depois a cadeia completa.

**A confirmar na doc oficial.** Formato de tool use e de resultado de ferramenta; cache de prompt e como aparece na contagem de tokens; limites e erros de taxa.

**Critérios de aceite**
- Teste de equivalência do piloto: mesma entrada, mesmos caminhos de artefato, mesma estrutura de saída que a execução atual no Claude Code.
- Demanda sintética completa executada ponta a ponta.
- Soma de tokens do JSONL confere com o painel do provedor em amostra.

**Riscos.** Diferença de comportamento entre a sessão do Claude Code e a chamada direta de API (prompt de sistema do harness ausente). Mitigação: o equivalente do que o harness injeta precisa ser explicitado no MVP 1, não assumido.

### MVP 2: OpenAI

**Objetivo.** Segundo provedor com ferramentas, validando a normalização.

**Escopo.** Adaptador `openai`; normalização de tool use, saída estruturada e erros; capability check ativo.

**A confirmar.** Papel dedicado para resultado de ferramenta (a literatura aponta diferença para a Anthropic, que usa blocos dentro de mensagem de usuário); formato de saída estruturada; semântica de cache.

**Critérios de aceite**
- Suíte de contrato por adaptador passa (ferramenta, saída estruturada, 429 e timeout simulados).
- Piloto e mais 3 agentes da cadeia rodam ponta a ponta; diferenças de estrutura em relação ao baseline documentadas.
- Fallback Anthropic → OpenAI e o inverso funcionam com falha injetada, com registro e alerta.

**Riscos.** O adaptador vira o molde dos "compatíveis com OpenAI"; um desenho ruim aqui se replica no DeepSeek, Grok e local. Mitigação: extrair o adaptador base só depois de o MVP 2 estar verde.

### MVP 3: Google Gemini

**Objetivo.** Provedor com formato próprio, que não é compatível com os outros dois, para provar a camada anti-corrupção.

**Escopo.** Adaptador `gemini`; normalização de mensagens, ferramentas e resposta.

**A confirmar.** Formato de declaração de função e de resultado; tratamento de saída estruturada; política de bloqueio de conteúdo (`CONTEUDO_BLOQUEADO`); contagem de tokens; opção de hospedagem em região específica (Vertex AI) para residência.

**Critérios de aceite**
- Suíte de contrato passa sem alterar a porta; se a porta precisar mudar, o desvio é registrado em ADR.
- Cadeia de ao menos 5 agentes roda ponta a ponta.
- Bloqueio de conteúdo simulado cai em fallback de modelo, não em erro de execução.

**Riscos.** Capacidades divergentes forçam o menor denominador comum. Mitigação: capacidades opcionais declaradas, com validação no RF-05.

### MVP 4: DeepSeek

**Objetivo.** Provedor de baixo custo com implicações de dados, validando a política de residência.

**Escopo.** Adaptador `deepseek` sobre o adaptador base compatível com OpenAI, com `base_url` e particularidades próprias; política de dados aplicada.

**A confirmar na doc oficial (nada pesquisado ainda).** Compatibilidade real com o formato OpenAI; suporte a tool use e a saída estruturada por modelo; diferença entre modelos de raciocínio e de uso geral; limites de contexto; códigos de erro; onde a API hospedada processa e armazena dados; termos de retenção.

**Critérios de aceite**
- Suíte de contrato passa; testes de tool use e saída estruturada rodam por modelo, com as lacunas registradas como capacidade falsa em `models.yaml`.
- `politica_dados` do DeepSeek hospedado marcada conforme a decisão da seção 9; o runtime recusa enviar demanda classificada como sigilosa a ele.
- Variante auto-hospedada (pesos abertos via MVP 6) tratada como provedor `local`, sem envio a terceiros.

**Riscos.** Dado sensível enviado para jurisdição não aprovada. Mitigação: a política é checada no roteador, antes da chamada, não confiada ao operador.

### MVP 5: Grok (xAI)

**Objetivo.** Último provedor hospedado, medindo quanto do adaptador base se reaproveita.

**Escopo.** Adaptador `grok` sobre o adaptador base compatível com OpenAI, se confirmado.

**A confirmar na doc oficial (nada pesquisado ainda).** Compatibilidade com o formato OpenAI (e com o da Anthropic); tool use e saída estruturada por modelo; recursos próprios, como busca nativa, que não podem escapar das regras de `never.md`; limites e erros; termos de uso e retenção de dados.

**Critérios de aceite**
- Suíte de contrato passa com o mínimo de código específico; o que precisou de código próprio fica registrado.
- Ferramentas de busca nativas do provedor ficam desligadas por padrão, para que a busca na web siga só o `ToolRunner` e os 5 agentes autorizados.
- Classificação de dados definida na seção 9.

**Riscos.** Recurso nativo do provedor contornar o catálogo de ferramentas. Mitigação: desligar por padrão e registrar em política.

### MVP 6: Modelos locais (Ollama / vLLM)

**Objetivo.** Caminho para demandas sigilosas, sem envio a terceiros.

**Escopo.** Adaptador `local` sobre o adaptador base compatível com OpenAI, apontando para um servidor local; catálogo de modelos de pesos abertos permitidos, incluindo variante local do DeepSeek.

**A confirmar.** Suporte a tool use e saída estruturada no servidor escolhido e por modelo; janela de contexto efetiva com a memória disponível; formato de template de chat por modelo; requisitos de hardware.

**Critérios de aceite**
- Suíte de contrato passa; o que o modelo local não suporta fica declarado em capacidades, e o capability check bloqueia agentes que exigem aquilo.
- Rodada completa de ao menos os agentes sem exigência de ferramenta de busca na web.
- Nenhuma chamada de rede externa durante a execução (verificada por captura de tráfego ou política de rede).

**Riscos.** Qualidade abaixo dos hospedados nas tarefas de arquitetura. Mitigação: golden set (MVP 7) mede a diferença antes de qualquer agente passar a usar modelo local.

### MVP 7: Transversal (telemetria, avaliação e governança)

Não é um provedor, mas fecha o trabalho; roda depois do MVP 2 e cobre todos os provedores já entregues.
- Telemetria e custo por agente e por modelo (RF-09, seção 5.6), relatório via `scripts/coletar_telemetria.py` estendido.
- Golden set por agente e relatório comparativo entre provedores; preenchimento de `confidence_score`.
- Políticas novas em `governanca/policies.yaml`: residência e PII por provedor, orçamento por demanda, chaves por provedor, prompt injection (lacuna já registrada na branch).

## 7. Matriz de capacidades a preencher

Preenchida durante cada MVP, a partir da doc oficial e de teste real. Os valores abaixo estão em branco de propósito.

| Capacidade | Anthropic | OpenAI | Gemini | DeepSeek | Grok | Local |
|---|---|---|---|---|---|---|
| Tool use | | | | | | |
| Saída estruturada | | | | | | |
| Janela de contexto | | | | | | |
| Cache de prompt | | | | | | |
| Busca nativa (deve ficar desligada) | | | | | | |
| Região/residência configurável | | | | | | |
| Formato compatível com OpenAI | | | | | | |

## 8. Estratégia de testes

| Camada | O que cobre | Rede |
|---|---|---|
| Unitário do núcleo | Grafo, contador de rodadas, validador de caminho, roteador | Não |
| Contrato por adaptador | Mesma bateria em todos: texto, ferramenta, saída estruturada, 429, timeout, bloqueio de conteúdo | Gravada; real onde houver chave |
| Equivalência | Piloto contra a execução atual no Claude Code | Real (MVP 1) |
| Falha injetada | Retry, fallback, circuito aberto, alerta | Não |
| Ponta a ponta | Demanda sintética completa, por provedor | Real onde houver chave |
| Isolamento | Nenhum import de SDK fora de `adapters/llm/` | Não |
| Segurança | Insumo com instrução embutida não muda caminho, ferramenta nem escopo | Não |

Nada é declarado validado sem execução; o que não foi executado fica marcado como "não validado", como já faz a branch `feat/`.

## 9. Governança de dados (decisão humana pendente)

Cada provedor hospedado recebe o conteúdo da demanda. A classificação abaixo precisa ser decidida e registrada em ADR antes do MVP 4 e do MVP 5; o runtime só aplica o que estiver em `models.yaml`.

| Provedor | Classificação proposta | Justificativa e ressalva |
|---|---|---|
| Anthropic, OpenAI, Gemini | A decidir (provável: aprovado para demanda real) | Confirmar termos de retenção e uso de dados para treino no plano contratado |
| DeepSeek hospedado | A decidir (proposta conservadora: só dados sintéticos) | Confirmar na doc oficial onde a API processa e armazena dados |
| Grok hospedado | A decidir (proposta conservadora: só dados sintéticos) | Confirmar termos de retenção e uso |
| Local (inclui DeepSeek de pesos abertos) | Aprovado para qualquer dado | Dado não sai da máquina |

As propostas conservadoras são minhas e não resultam de pesquisa; a decisão é do dono do OS.

## 10. Suposições e trade-offs (exigidos por CLAUDE.md)

**Suposições**
1. O time aceita manter o Claude Code como adaptador e não apenas migrar.
2. Os provedores continuam oferecendo tool use e saída estruturada nos modelos escolhidos; a matriz da seção 7 confirma ou derruba.
3. Haverá chave de API para ao menos um provedor hospedado por MVP; sem chave, o MVP fecha só com resposta gravada e fica marcado como "não validado contra a API real".
4. O formato OpenAI serve de base para DeepSeek, Grok e local; se algum divergir, deixa de usar o adaptador base.
5. Os preços mudam; o `models.yaml` guarda data e fonte, e nenhum número desta especificação é de preço real.

**Trade-offs**
| Decisão | Ganho | Custo |
|---|---|---|
| Runtime próprio em vez de proxy ou framework | Controle do grafo, do contador e do isolamento; sem dependência de harness | Código a manter; reimplementar o que o `Task` faz |
| Roteamento fixo em vez de dinâmico | Previsível e auditável | Não otimiza custo sozinho |
| Um MVP por provedor | Entrega e risco incrementais | Mais ciclos de revisão |
| Porta mínima | Menos manutenção | Recursos exclusivos de provedor só entram como capacidade opcional |
| Fallback automático | Disponibilidade | Pode mascarar queda de qualidade; mitigado por registro e alerta |

## 11. Riscos consolidados

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Qualidade varia entre modelos na cadeia de arquitetura | Alta | Alto | Golden set (MVP 7); piloto por agente antes de trocar o padrão |
| Dado sensível enviado a provedor não aprovado | Média | Alto | Política no roteador, antes da chamada |
| Fallback silencioso | Média | Médio | RF-10 |
| Adaptador base mal desenhado se replica | Média | Médio | Extrair só depois do MVP 2 verde |
| Convenções OTel mudam | Média | Baixo | Mapeamento isolado em módulo |
| Recurso nativo de provedor contorna as regras de ferramenta | Média | Alto | Desligado por padrão, registrado em política |
| Divergência do isolamento de contexto em relação ao `Task` | Média | Médio | Contexto novo por agente; teste de equivalência |

## 12. Questões em aberto

1. Quais provedores aprovam dado real de demanda (seção 9)?
2. Haverá chave de API para cada provedor desde o início?
3. Onde o runtime roda (máquina local, CI, servidor)?
4. O modelo de cada agente deve ser decidido pelo dono do OS ou pelo agente `trade-offs-e-adr`, com ADR por escolha?
5. Quem preenche e atualiza a tabela de preços do `models.yaml`?

## 13. Referências

- Plano aprovado: `~/.claude/plans/fa-a-uma-an-lise-completa-snuggly-spring.md`
- [LiteLLM Router](https://docs.litellm.ai/docs/routing)
- [A2A 1.0.0](https://a2a-protocol.org/latest/specification/)
- Repositório: `agents/`, `skills/`, `rules/`, `.claude/skills/arquiteto-solucoes/SKILL.md`, `memory.md`, e, na branch `feat/governanca-...` (PR #7), `orquestracao/agent-network.yaml`, `governanca/policies.yaml`, `registry/agent-cards/`, `telemetria/interacoes.jsonl`, `scripts/coletar_telemetria.py`
