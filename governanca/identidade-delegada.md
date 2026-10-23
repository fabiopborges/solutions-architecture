# Identidade Delegada (Trusted Agent Identity) — MVP 6

Documento de referência para uma futura migração ao MuleSoft Agent Fabric. **Não implementa OAuth** — descreve o modelo de identidade deste fluxo real, para que a configuração no AgentNetwork YAML seja direta quando a migração acontecer.

NÃO VALIDADO: nenhuma integração real com Omni Gateway ou IdP existe hoje. Todo valor de configuração sem base real neste repositório usa placeholder explícito.

## 1. Visão Geral

Trusted Agent Identity é o mecanismo do Agent Fabric que propaga a identidade de quem disparou uma cadeia de agentes através de toda a cadeia, no Omni Gateway, para que cada agente acesse só o que essa pessoa autorizou. Isso importa para este time porque a cadeia inteira só produz um pacote "entregue" depois de aprovação humana explícita (`README.md`, "Por que 'Júnior'") — a identidade de quem aprova, e a garantia de que nenhum agente se autoaprova em nome dela, é o mecanismo central que sustenta essa regra.

*Fonte: especificação de Trusted Agent Identity descrita na conversa; `README.md`, seção "Por que 'Júnior', se as decisões são grandes".*

## 2. O Sujeito (Quem é a Pessoa Operadora)

A Pessoa Operadora é o único ator externo ao time de agentes: dispara a demanda, responde às perguntas de escopo, e aprova o gate de saída. Ela autoriza três coisas específicas, todas documentadas:

- Confirma o nome da demanda antes de qualquer atividade começar (`rules/never.md`).
- Responde perguntas de esclarecimento de Entendimento e Escopo quando a demanda é ambígua.
- Aprova o gate de saída — condição obrigatória mesmo se todos os outros itens do gate passarem (`agents/orquestrador/AGENT.md`, "Gate de saída").

*Fonte: `README.md`, seção "2. Contexto" ("o único ator de fora é a Pessoa Operadora"); `agents/orquestrador/AGENT.md`.*

## 3. Padrões de Autenticação Aplicáveis

### OAuth 2.0 Token Exchange (OBO)
**Quando usar neste fluxo:** no único ponto em que a identidade externa entra no sistema — o disparo da demanda (`trigger: disparo-da-demanda` em `orquestracao/agent-network.yaml`), que despacha `entendimento-e-escopo`. É transparente, sem interação adicional do usuário depois do disparo inicial, exatamente o perfil do OBO.
**Nó do grafo que usaria este padrão:** a aresta de entrada `disparo-da-demanda → entendimento-e-escopo`.
**Por quê:** a Pessoa Operadora não reaparece explicitamente de novo até o gate de saída (ela pode responder perguntas de esclarecimento no meio, mas isso é o mesmo canal conversacional, não uma nova autenticação) — o token trocado no início preserva `sub` (Pessoa Operadora) e troca a audiência (`aud`) para o agente, sem fricção.

### In-Task Authorization Code
**Quando usar neste fluxo:** nos dois pontos onde uma aprovação humana explícita e de alto risco é exigida antes de uma ação irreversível (liberar o pacote; aprovar um ADR como oficial).
**Nós que usariam este padrão:** a aresta `entrega-e-handoff → gate-de-saida` (liberação do pacote); e, fora do grafo de nós/arestas, o gate de revisão interno do agente Trade-offs e ADR (uma pessoa sênior/líder técnico precisa revisar o ADR — `agents/trade-offs-e-adr/AGENT.md`, "Gate de revisão obrigatório").
**Por quê:** ambos são operações de alto risco (liberar arquitetura para o time, oficializar uma decisão) que pedem verificação de segundo fator sem tirar quem aprova do fluxo conversacional — exatamente o perfil de step-up MFA do In-Task Authorization Code.

*Fonte: especificação de Trusted Agent Identity descrita na conversa; `orquestracao/agent-network.yaml` (MVP 2); `agents/orquestrador/AGENT.md`; `agents/trade-offs-e-adr/AGENT.md`.*

## 4. Pontos de Delegação no Grafo

| Nó de Origem | Nó de Destino | Padrão | Justificativa |
|---|---|---|---|
| `disparo-da-demanda` (Pessoa Operadora) | `entendimento-e-escopo` | OBO | Entrada da identidade externa no sistema; preservação transparente de `sub`. |
| `entrega-e-handoff` | `gate-de-saida` | In-Task Authorization Code | Aprovação humana obrigatória antes de liberar "entregue" (`README.md`, `AGENT.md` do Orquestrador). |
| Demais 33 arestas de `orquestracao/agent-network.yaml` (agente-de-atividade → agente-de-atividade, incluindo todos os ramos paralelos, sincronizações e triggers de Trade-offs e ADR / Geração de Diagramas C4) | — | não aplicável | Orquestração interna sob a mesma sessão/autoridade já concedida no disparo; cada agente atua em nome próprio na execução técnica, sem expor um recurso externo com audiência distinta nem exigir nova verificação de identidade. |

*Fonte: `orquestracao/agent-network.yaml` (MVP 2) — as 34 arestas de `edges:` mais o `trigger` inicial (35 transições no total) foram percorridas; só as 2 linhas acima envolvem a Pessoa Operadora diretamente.*

## 5. Configuração de Referência (AgentNetwork YAML)

```yaml
connections:
  disparo-da-demanda:
    kind: agent
    ref:
      name: entendimento-e-escopo
    spec:
      url: "<url-do-endpoint-de-entendimento-e-escopo>"
    authentication:
      kind: oauth2-obo
      flow: oauth2-token-exchange
      tokenEndpoint: "<url-do-endpoint-de-token-do-idp-corporativo>"
      clientId: "<client-id-do-idp>"
      clientSecret: "<client-secret-do-idp>"
      targetType: audience
      targetValue: "<uri-do-recurso-alvo-entendimento-e-escopo>"
      scope: "<escopo-nao-documentado>"
      timeout: 10000

  entrega-e-handoff-para-gate-de-saida:
    kind: agent
    ref:
      name: gate-de-saida
    spec:
      url: "<url-do-endpoint-de-gate-de-saida>"
    authentication:
      kind: in-task-authorization-code
      secondaryAuthProvider: "<idp-secundario-nao-documentado>"
      authorizationEndpoint: "<url-de-autorizacao>"
      tokenEndpoint: "<url-de-token>"
      scopes: "<escopos-nao-documentados>"
      redirectUri: "<uri-de-redirecionamento>"
      responseType: code
      tokenAudience: "<uri-do-recurso-alvo-gate-de-saida>"
      codeChallengeMethod: S256
      bodyEncoding: form
      challengeResponseStatusCode: 200
      tokenTimeout: 300
```

Nenhum `clientId`, `clientSecret`, endpoint ou IdP é documentado em nenhum arquivo-fonte deste repositório — todos ficam como placeholder explícito, nunca inventados.

*Fonte: especificação de configuração de OBO e In-Task Authorization Code descrita na conversa.*

## 6. Onde o Agente Atua em Nome Próprio vs. em Nome do Usuário

**Em nome da Pessoa Operadora:**
- `gate-de-saida` (o Orquestrador segura a liberação até a aprovação explícita da Pessoa Operadora — `agents/orquestrador/AGENT.md`).
- O gate de revisão do Trade-offs e ADR (a pessoa sênior/líder técnico que revisa não é necessariamente a mesma Pessoa Operadora do disparo, mas atua no mesmo papel de autoridade humana final sobre uma decisão).

**Em nome próprio (execução técnica que não exige a identidade do usuário):**
Todos os 17 agentes de atividade restantes (Desenho, Modelagem de Dados, Infraestrutura, Testes e Qualidade, Jornadas do Usuário, Pesquisa e Benchmarking, Especialista IA/ML, Especialista Dados/Analytics, Segurança e Compliance, Estimativa de Custo, Observabilidade e Telemetria, Documentação Final, Riscos e Mitigação, Comunicação com Stakeholders, Entrega e Handoff — na preparação, antes do gate —, Geração de Diagramas C4, Entendimento e Escopo depois do disparo inicial) atuam com a autoridade da própria atividade, sob a mesma sessão, sem precisar da identidade individual da Pessoa Operadora para decidir bounded context, entidade, custo, etc.

*Fonte: `agents/orquestrador/AGENT.md` (Gate de saída); `agents/trade-offs-e-adr/AGENT.md` (Gate de revisão obrigatório); `orquestracao/agent-network.yaml`.*

## 7. Onde a Verificação Secundária (MFA) é Necessária

- **Gate de saída** (`entrega-e-handoff → gate-de-saida`): antes de liberar o pacote como "entregue" — item 4 do gate, obrigatório mesmo se os outros três passarem (`agents/orquestrador/AGENT.md`).
- **Gate de revisão do ADR** (interno ao agente Trade-offs e ADR, não uma aresta do grafo): antes de um ADR valer como decisão oficial, "uma pessoa sênior ou líder técnico precisa revisar" (`agents/trade-offs-e-adr/AGENT.md`) — distinto e adicional ao gate de saída geral.

*Fonte: `agents/orquestrador/AGENT.md`; `agents/trade-offs-e-adr/AGENT.md`.*

## 8. Caminho de Migração

Para este modelo funcionar de verdade no Agent Fabric, precisa existir:
- Omni Gateway configurado com as políticas de OBO Credential Injection e In-Task Authorization Code (nenhuma das duas está ativa hoje — hoje a "aprovação humana" é um passo conversacional dentro da mesma sessão Claude Code, não uma troca de token real).
- Um IdP corporativo integrado ao Gateway, capaz de emitir e trocar tokens (não documentado em nenhum arquivo-fonte — hoje não há IdP nenhum no fluxo).
- As políticas já mapeadas em `governanca/policies.yaml` (MVP 3) aplicadas ao mesmo tráfego A2A, já que Governance e Trusted Agent Identity operam no mesmo Omni Gateway.

*Fonte: especificação de Enterprise Actionability/Governance do Agent Fabric descrita na conversa; `governanca/policies.yaml` (MVP 3).*
