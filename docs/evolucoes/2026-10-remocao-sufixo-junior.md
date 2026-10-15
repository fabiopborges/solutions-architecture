# Plano de evolução: remover o sufixo "Júnior" do nome do projeto

## Contexto

O projeto deixa de se chamar "Arquiteto de Soluções Júnior" e passa a se chamar **"Arquiteto de Soluções"**. O repositório no GitHub também será renomeado. Este plano lista tudo que referencia o nome antigo (código, agentes, documentação, diagramas e remote) e a ordem de execução, para aprovação antes de qualquer edição.

**Decisões já tomadas com o Fabio:**
- Novo nome do repo no GitHub: `solutions-architecture-agents` (hoje o remote é `solutions-architecture-jr`).
- A seção do README "Por que 'Júnior', se as decisões são grandes" será **reescrita**, mantendo os mecanismos de aprovação humana e removendo o argumento sobre o termo "júnior".

**Mapa de substituição**

| De | Para |
|---|---|
| `Arquiteto de Soluções Júnior` / `Junior IA` / `Arquiteto de Soluções Junior IA` | `Arquiteto de Soluções` (README: `Arquiteto de Soluções IA`) |
| `arquiteto júnior` / `pessoa júnior` (texto livre) | `arquiteto de soluções` / reescrita caso a caso |
| `solutions-architecture-jr-agents` (README, CONTRIBUTING) | `solutions-architecture-agents` |
| `git@github.com:fabiopborges/solutions-architecture-jr.git` | `git@github.com:fabiopborges/solutions-architecture-agents.git` |

**Não muda (de propósito):** o slash command e skill `/arquiteto-solucoes` (já não tem sufixo) e o nome da pasta local `agentes-arquiteto-de-solucoes`.

## Inventário (levantado por busca, 60 ocorrências em 32 arquivos)

**A. Identidade e instruções (versionado)**
- `CLAUDE.md:3`, "OS do time de Arquiteto de Soluções Júnior". É a linha de identidade, tem o maior impacto.
- `.claude/skills/arquiteto-solucoes/SKILL.md`: `description` (linha 3), título (linha 8) e corpo (linha 10), 3 ocorrências.
- `.claude/agents/*.md`: 18 arquivos, 1 ocorrência cada na linha 7, "Você é o agente X do time de Arquiteto de Soluções Júnior (skill `arquiteto-solucoes`)". Padrão único, substituição mecânica.
- `rules/always.md:14,16`, `memory.md` (cabeçalho e 3 linhas de objetivo/próxima ação) e `telemetria-agentes.md`.

**B. Documentação pública (versionado)**
- `README.md`, 19 linhas: título H1 (linha 3), subtítulo (linha 5), seção "Por que Júnior" (linhas 17 a 39), item do sumário (linha 50) e a âncora `#por-que-júnior-...`, títulos "1." e "2." mais o sumário (linhas 57, 58, 131, 141), textos e alt text das imagens (133, 135, 139, 145, 487) e o quickstart (linha 248, `cd solutions-architecture-jr-agents`).
- `CONTRIBUTING.md:3,45`, nome do repositório (`solutions-architecture-jr-agents`) na definição legal de "Projeto" do CLA.
- `LICENSE.md`, `.github/pull_request_template.md` e `.github/workflows/cla-check.yml`: busca sem ocorrências do nome antigo. **Verificar** na execução se citam o repo por URL.

**C. Diagramas gerados (versionado)**
- `docs/diagrams/archify/`: `c4-contexto`, `c4-container` e `c4-fluxo-dados`, cada um com `.architecture.json` (campo `title`) e `.svg` (`<title>`), mais `README.md`.
- `docs/diagrams/01-camadas.svg` e `03-execucao-referencia.svg`: sem a palavra no texto. **Conferir visualmente** os rótulos renderizados.

**D. Fora do git ou histórico (decisão de tratamento abaixo)**
- `demandas/projeto-agentes-arquitetura-de-solucoes-junior-16-08-2026/`: pasta e ~25 arquivos. Está no `.gitignore`.
- `servidor/consultas.log`: log de execução, untracked, 2 ocorrências.
- `memory.md` e `telemetria-agentes.md`: entradas datadas de agosto/2026 que citam caminhos antigos, por exemplo `/home/fabioborges/projetos/agentes-arquiteto-de-solucoes-junior/`.

## Tratamento proposto

1. **Renomear** tudo o que é identidade viva (blocos A, B e C).
2. **Não renomear** o histórico: entradas datadas de `memory.md`/`telemetria-agentes.md` e caminhos antigos descritos como fato do passado. Reescrever isso falsifica o registro. Só atualizar o **cabeçalho** de `memory.md` e o **objetivo** (linhas 1 a 5).
3. **Não renomear** a pasta `demandas/projeto-agentes-arquitetura-de-solucoes-junior-16-08-2026/`. É o identificador de uma demanda real já registrada (citada em `docs/diagrams/archify/README.md`, `telemetria-agentes.md` e na pasta `adrs/`). Renomear quebra as referências sem ganho. Se o Fabio preferir renomear, vira um item extra (pasta, 4 referências e o `custo-processamento.md`).
4. **Não editar** `servidor/consultas.log` (log append-only de runtime).

## Reescrita da seção do README (linhas 17 a 39)

Novo título sugerido: **"Por que a palavra final é sempre humana"**. Mantém:
- a lista de mecanismos (agente não decide fora do escopo, ADR só oficial com aprovação humana, Entrega e Handoff não se autoaprova, risco com mitigação ou aceite explícito, escalada na 4ª rodada);
- a frase "IA que faz o trabalho inteiro para que a decisão seja sua, e mais bem informada".

Remove o argumento do "selo de júnior" e o texto "o nome engana de propósito". Atualizar o item do sumário (linha 50) e a âncora para `#por-que-a-palavra-final-é-sempre-humana`. Nenhum outro arquivo aponta para a âncora antiga (checado por busca).

## Passos de execução (ordem)

1. **Salvar este plano** no repo como `docs/evolucoes/2026-10-remocao-sufixo-junior.md` (arquivo isolado da evolução) e criar a branch `chore/remove-sufixo-junior`.
2. **Bloco A**: `sed` no padrão de uma linha dos 18 agentes (`Arquiteto de Soluções Júnior` → `Arquiteto de Soluções`), depois edição manual de `CLAUDE.md`, `SKILL.md`, `rules/always.md` e do cabeçalho/objetivo de `memory.md`.
3. **Bloco B**: edição do `README.md` (título, subtítulo, seção reescrita, sumário e âncora, alt texts, quickstart) e do `CONTRIBUTING.md` (nome do repo).
4. **Bloco C**: substituir o `title` nos 3 `.architecture.json` e o `<title>` nos 3 `.svg` (substituição textual simples do título, sem re-renderizar o pipeline ArchiFy). Atualizar `docs/diagrams/archify/README.md`.
5. **Commit** (um commit por bloco, mensagens em português, seguindo o histórico) e **push** da branch.
6. **Renomear no GitHub** (Settings → Repository name → `solutions-architecture-agents`). O GitHub redireciona o nome antigo, mas deve-se atualizar o remote local:
   `git remote set-url origin git@github.com:fabiopborges/solutions-architecture-agents.git`
7. **Merge** na `main` após a revisão do Fabio. A renomeação do repo no GitHub fica por conta do Fabio (ação externa, não será executada sem confirmação).

## Riscos e suposições

- **Suposição:** "Júnior" aparece como nome do projeto na grande maioria dos casos; casos de texto livre ("arquiteto júnior competente") estão concentrados na seção do README que será reescrita. Se sobrar algum, será tratado caso a caso.
- **Risco, links externos:** quem tem o repo clonado com o remote antigo continua funcionando pelo redirect do GitHub, mas o redirect some se o nome antigo for reutilizado. Mitigação: atualizar o remote local (passo 6).
- **Risco, CLA:** `CONTRIBUTING.md:45` está numa cláusula legal que define "Projeto". A troca do nome do repo ali é só nominal, mas por ser texto contratual será destacada no commit para revisão.
- **Risco, SVGs:** edição textual do `<title>` evita regerar o diagrama, mas precisa de conferência visual após o commit.
- **Trade-off, histórico:** preservar entradas datadas deixa algumas ocorrências de "Júnior" no `memory.md`/`telemetria-agentes.md`. É deliberado, a busca final de verificação vai tolerar apenas esses arquivos e a pasta da demanda.

## Verificação

1. `grep -rIiE 'j[uú]nior' --exclude-dir=.git --exclude-dir=.venv --exclude-dir=demandas --exclude=consultas.log .` deve retornar **apenas** as entradas históricas datadas de `memory.md` e `telemetria-agentes.md`.
2. `grep -rIn 'solutions-architecture-jr' .` deve retornar vazio, exceto o histórico.
3. Abrir o README renderizado: título, sumário, âncora da seção nova e quickstart funcionando.
4. Abrir os 3 SVGs de `docs/diagrams/archify/` no navegador e conferir o título e os rótulos.
5. Rodar `/arquiteto-solucoes` e `/arquiteto-solucoes status` em uma sessão nova a partir da raiz e confirmar que skill e subagentes carregam (o `name` dos agentes não muda, só a descrição).
6. `git remote -v` aponta para o novo nome e `git push` funciona após a renomeação no GitHub.

## Nota de execução (2026-10-15)

O repositório foi renomeado no GitHub para `solutions-architecture` (e não `solutions-architecture-agents`, como previsto acima). README e CONTRIBUTING foram ajustados e o remote local agora é `git@github.com:fabiopborges/solutions-architecture.git`. O `memory.md` cita `solutions-architecture-agents` como outro repositório (público desde 2026-07-21), por isso não foi alterado.
