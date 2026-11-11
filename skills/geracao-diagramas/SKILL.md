# Skill: Geração de Diagramas C4

## Quando usar
Sempre que Desenho de Arquitetura tiver bounded contexts/componentes/integrações decididos, ou Documentação Final precisar consolidar/atualizar diagramas do pacote final — incluindo visões por jornada quando Jornadas do Usuário já tiver rodado.

## Dono
O agente "Geração de Diagramas C4" é o dono desta atividade — nenhum outro agente desenha diagrama de arquitetura por conta própria (regra de [[rules/never]]). ASCII art manual não é o padrão.

## Pipeline (desde 2026-11-11): Structurizr + página HTML
Valem só para **demandas novas**. Demandas com diagramas ArchiFy (`*.architecture.json`) ficam como estão, e o orquestrador recusa regerá-las (`--forcar` só com pedido explícito).

Fluxo: `catalogo-componentes.json` + `sequencia-<id>_spec.json` → `derivar_c4.py --formato v2` → specs v2 → `spec_para_dsl.py` (Structurizr DSL) → `gerar_pagina_c4.py` (Docker + Chrome headless → HTML autocontido) → `validar_diagrama_c4.py`. O comando único é `scripts/gerar_diagramas_demanda.py`. Formato e regras: `docs/diagrams/c4-schema-v2.md`. Uso e pré-requisitos (Docker, Chrome): `scripts/README.md`.

## Regras de autoria

**Nunca inventar tecnologia.** `tecnologia`, `forma`, `armazenamento`, `mensageria`, `broker`, `dono_id`, `retencao` e `sensibilidade` só entram com o que já está em `desenho.md`, `infraestrutura.md` ou `dados.md`. Sem fonte, o campo fica vazio e o gerador avisa. A pergunta volta ao dono do documento (Infraestrutura, Modelagem de Dados ou Desenho), dentro do limite de 3 rodadas de [[rules/always]].

**Limite de 12 palavras** em todo texto visível: `nome` (componente, ator, fronteira), `descricao` de componente, `papel` de ator, `rotulo` de conexão e de mensagem. O gerador recusa (`[limite-palavras]`). Fora do limite: `condicao`, `leitura[]`, `nota`, `suposicoes[]`. Estilo: verbo + objeto direto, sem parênteses explicativos nem citação de fonte no rótulo.

**Mensageria e dados (c4model.com/abstractions):** o container é cada fila ou tópico (`mensageria: fila|topico|stream`), nunca o broker (`broker` é só tecnologia). Microsserviço = API (`forma: api`) + banco (`armazenamento`) agrupados numa fronteira `tipo: servico`. As conexões são sempre escritas na convenção do iniciador (quem publica ou consome aponta para a fila).

**Contexto:** o sistema vira uma caixa, e só aparecem as pessoas e os sistemas diretamente ligados a ele, sem tecnologia nas setas. Quem não tem ligação direta é omitido com `[ATOR-FORA-DO-CONTEXTO]`: isso sinaliza uma decisão de modelagem do Desenho, não do agente.

## Passos

**Primeira execução, acionado por Desenho de Arquitetura (estrutura decidida, jornadas ainda não rodaram):**
1. Leia `desenho.md` (bounded contexts, componentes, integrações, suposições e trade-offs).
2. Traduza para `demandas/<nome-da-demanda>/diagramas/catalogo-componentes.json` (formato v2, **sem conexões**): `sistema` (`nome`, `descricao`), `atores[]`, `fronteiras[]` (a partir dos bounded contexts), `componentes[]` com `status` (`novo`/`alterado`/`reuso`/`existente`) conforme o desenho já sinalizou, `glossario[]` das siglas usadas e `suposicoes[]` copiadas das suposições e trade-offs de `desenho.md` (tradução, nunca conteúdo novo). **Use o `id` canônico que o Desenho atribuiu a cada componente/ator** — [[agents/jornadas-do-usuario/AGENT]] reaproveita o mesmo `id` nas sequências, e IDs divergentes geram falsos `[ORFAO]`/`[FALTA-CATALOGO]`.
3. Se `infraestrutura.md`/`dados.md` já existirem, preencha também `tecnologia` e os campos de dados que eles já decidiram. Se não, deixe vazio: a 2ª execução completa.
4. Se não existir nenhum `sequencia-<id>_spec.json` (Jornadas do Usuário só produz spec quando o veredito é "jornadas identificadas"), autore `c4-container.json` (`nivel: "container"`, `conexoes[]` traduzidas das integrações de `desenho.md`, cada uma com `tecnologia` quando o documento a trouxer) e siga para o passo 7.

**Segunda execução, acionado por Documentação Final (ou depois que Jornadas do Usuário tiver rodado):**
5. Confirme se existem `sequencia-<id>_spec.json` (de [[agents/jornadas-do-usuario/AGENT]]). Eles trazem `tecnologia`/`protocolo`, `acesso`, `via` e `condicao` por mensagem e, opcionalmente, `leitura[]`, `nota` e `titulo_pagina` (texto da jornada, que você apenas exibe).
6. Complete no catálogo o que `infraestrutura.md` e `dados.md` já decidiram (`tecnologia`, `armazenamento`, `mensageria`, `broker`, `dono_id`, `retencao`, `sensibilidade`). Nunca preencha por conta própria.
7. Rode `python3 scripts/gerar_diagramas_demanda.py demandas/<nome-da-demanda>`. Gera `c4-container-jornada-<id>.html` (com Dynamic diagram), `c4-container.html`, `c4-contexto.html` e `c4-fluxo-dados.html` (se houver o spec), valida tudo e grava `RELATORIO-GERACAO.md`.
8. **Leia o relatório inteiro.** Repasse cada aviso como pergunta explícita:
   - `[ORFAO]`, `[FALTA-CATALOGO]`: tensão entre `desenho.md` e `jornadas.md`. Pergunte a quem produziu o documento que parece desatualizado; nunca decida qual está certo.
   - `[SEM-TECNOLOGIA]`, `[SEM-DONO]`, `[BANCO-COMPARTILHADO]`: pergunte a Infraestrutura, Modelagem de Dados ou Desenho.
   - `[BROKER-COMO-CONTAINER]`: o desenho tratou o broker como componente; a regra do C4 pede cada fila/tópico como container. Devolva ao Desenho.
   - `[ATOR-FORA-DO-CONTEXTO]`: devolva ao Desenho (falta uma relação direta, ou o ator não pertence ao Contexto).
   - Falha de validação: corrija o catálogo/spec (nunca o `.html`) e rode de novo. Duas rodadas sem melhora → pare e reporte com honestidade.
9. **Fluxo de dados** (pedido por Documentação Final, a partir de `dados.md`): o orquestrador já gera `c4-fluxo-dados.html` sozinho, como visão **filtrada** do `c4-container.json` (só armazenamentos, filas/tópicos e quem os acessa; `nivel: fluxo-dados`), desde que o Container tenha `armazenamento`/`mensageria` e `acesso` (`le`, `grava`, `publica`, `consome`) preenchidos conforme `dados.md`. Só autore `c4-fluxo-dados.json` à mão se o fluxo de `dados.md` precisar de algo que o Container não tem; ele tem precedência sobre o filtro. Rode o passo 7.
10. **Sequência:** não há mais `sequencia-<id>.html`. O Dynamic diagram numerado dentro de `c4-container-jornada-<id>.html` a substitui; `sequencia-<id>_spec.json` continua sendo a fonte, de Jornadas do Usuário.
11. Se a estrutura em `desenho.md`/`dados.md` for insuficiente ou ambígua para virar diagrama, devolva a pergunta a quem produziu o documento em vez de inventar.

## Componente (C3)
Só quando `desenho.md` já detalha os componentes internos de um container (nunca por palpite; sem detalhe, a pergunta volta ao Desenho). Autore `c4-componente-<container>.json`: `nivel: "componente"`, `foco_id` (id do container), componentes internos com `container_id = foco_id`, mais os vizinhos (containers, atores) e as `conexoes[]` que tocam os internos. Relação entre o container e seu próprio interno é proibida pelo C4. O que não se liga a nenhum interno é omitido com `[FORA-DA-VISAO]`. O orquestrador gera `c4-componente-<container>.html`.

## Lacunas conhecidas
Landscape e Deployment ainda não são gerados. Sinalize a quem pediu; não improvise outro formato. Os `cards[]` e `meta.views` do ArchiFy não existem aqui: a rastreabilidade das suposições vem de `suposicoes[]` e a narrativa da jornada vem de `leitura[]`/`nota`.

## Artefato de saída
Em `demandas/<nome-da-demanda>/diagramas/`: `catalogo-componentes.json` (fonte estática); `c4-container.json` + `c4-container-jornada-<id>.json` (specs v2 derivados); `c4-container.html`, `c4-container-jornada-<id>.html`, `c4-contexto.html` e, se houver, `c4-fluxo-dados.html` (HTML autocontido: SVG vetorial, tema claro/escuro, zoom, tela cheia, legenda, tabelas, avisos, suposições); `_trabalho/<nome>/workspace.dsl` (fonte Structurizr de cada diagrama); `RELATORIO-GERACAO.md`. O relatório vai também na resposta a quem acionou, nunca descartado.

## Como é bem feito
Um diagrama gerado por este agente é sempre rastreável a um catálogo + sequências versionados, e a tensão entre `desenho.md`, `jornadas.md`, `infraestrutura.md` e `dados.md` aparece como aviso explícito na hora de gerar — nunca como divergência silenciosa descoberta depois, nem como tecnologia inventada.
