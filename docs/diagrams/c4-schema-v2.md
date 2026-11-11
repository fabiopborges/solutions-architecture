# Schema de diagrama C4 — v2 (Structurizr)

Vale **apenas para demandas novas**. Demandas anteriores continuam no formato v1 (`c4-schema.md`, ArchiFy). A v2 é um superconjunto da v1: todo campo da v1 continua válido. Os campos novos são opcionais, exceto `tecnologia`, que gera aviso quando falta.

Validação formal: `c4-schema-v2.schema.json` (JSON Schema, draft 2020-12).

Fontes oficiais usadas nas regras de dados e mensageria (conferidas em 2026-11-10):
- https://c4model.com/abstractions/microservices
- https://c4model.com/abstractions/queues-and-topics
- https://c4model.com/diagrams/container e https://c4model.com/diagrams/notation (decisões anteriores)

## O que muda em relação à v1

| Onde | Campo novo/alterado | Regra |
|---|---|---|
| `nivel` | + `landscape`, `deployment`, `dinamico` | `dinamico` = jornada numerada (vem das sequências). `codigo` (C4 nível 4) fica fora de escopo. |
| `nivel` | + `fluxo-dados` | Visão **filtrada** do Container: só armazenamentos, filas/tópicos e quem os acessa. Não tem modelagem própria. |
| `atores[].tipo` | `usuario_*` → forma Pessoa; `sistema_externo` → sistema | Sem mudança de valores, muda o desenho. |
| `componentes[].status` | + `existente` | `existente` = já existe e não é tocado (cinza). `reuso` = existente que esta demanda reutiliza (azul claro). |
| `componentes[].tecnologia` | string, **novo** | Obrigatório no C4 (container). Vem de `infraestrutura.md`/`desenho.md`. Ausente → aviso `[SEM-TECNOLOGIA]`; o gerador nunca inventa. |
| `componentes[].forma` | enum, **novo** | `caixa` (padrão) \| `api` \| `app-web` \| `app-movel`. Pessoa vem de `atores[]`. Armazenamento e mensageria têm campos próprios (abaixo) e definem a forma. |
| `componentes[].armazenamento` | enum, **novo** | `relacional` \| `documento` \| `cache` \| `objetos` \| `busca` \| `analitico`. Desenho: cilindro, com o tipo no texto do elemento. |
| `componentes[].mensageria` | enum, **novo** | `fila` \| `topico` \| `stream`. **O elemento é a fila ou o tópico, não o broker.** Desenho: tubo. |
| `componentes[].broker` | string, **novo** | Só com `mensageria`. Tecnologia do broker (ex.: "Azure Service Bus"). Aparece no texto do elemento e no diagrama de deployment, nunca como caixa própria. |
| `componentes[].dono_id` | string, **novo** | `id` de fronteira ou sistema dono do dado/fila. Obrigatório para exibir quando o dono é outro sistema (regra do C4). Decisão de Modelagem de Dados; o gerador só exibe. |
| `componentes[].retencao` | string, **novo** | Texto curto (ex.: "WORM, 5 anos"). Só exibe. |
| `componentes[].sensibilidade` | string, **novo** | Texto curto (ex.: "dado pessoal"). Só exibe. |
| `fronteiras[].pai_id` | string, **novo** | Aninhamento opcional. |
| `fronteiras[].tipo` | enum, **novo** | `bounded-context` (padrão) \| `servico`. `servico` agrupa a API e o banco do mesmo microsserviço numa caixa. |
| `conexoes[].tecnologia` | string, **novo** | Protocolo/mecanismo (ex.: "REST/HTTPS"). Entra no texto da seta. |
| `conexoes[].acesso` | enum, **novo** | `chama` (padrão) \| `le` \| `grava` \| `publica` \| `consome`. Define o estilo da linha (`publica`/`consome` = tracejada). O verbo vem do `rotulo`, que continua obrigatório. |
| `conexoes[].via` | string, **novo** | `id` da fila/tópico usado. Só tem efeito no modo implícito (ver "Mensageria"). |
| `conexoes[].condicao` | string, **novo** | Referência à hipótese em aberto (ex.: "Q5/H1"). Seta marcada como condicional. **Fora** do limite de 12 palavras do `rotulo`. |
| nível superior | `sistema` | `{nome, descricao}`, **novo**. Sistema em escopo. Se ausente, usa o trecho do `titulo` antes de " — ". |
| nível superior | `leitura[]` | `{titulo, texto}`, **novo**. Passos de leitura da jornada, em texto autoral (vem de `jornadas.md`; o gerador só exibe, na ordem). Backticks viram `<code>`. |
| nível superior | `titulo_pagina` | string, **novo**. Título legível da página (ex.: nome da jornada). Se ausente, usa `journey_id`, ou o nome do sistema. |
| nível superior | `nota` | string, **novo**. Aviso destacado (ex.: premissas em aberto). Só exibe. |
| nível superior | `mensageria_modo` | `explicita` (padrão) \| `implicita`. Ver "Mensageria". |
| nível superior | `seta_mensageria` | `iniciador` (padrão) \| `fluxo`. Ver "Mensageria". |
| nível superior | `glossario[]` | `{sigla, significado}`. Gera a tabela de siglas (C4: explicar acrônimos). |
| `mensagens[].condicao`, `.acesso`, `.via` | iguais às de `conexoes[]` | Nas sequências. |

`rotulo` e `nome` continuam com o limite de 12 palavras (verificado no gerador). Com `condicao`, o diagrama mostra `Condicional a <condicao>: <rotulo>`; a 1ª letra do rótulo vira minúscula só quando a 1ª palavra é comum (inicial maiúscula e o resto só letras minúsculas); siglas (`API`, `C6`) e identificadores (`EventoDeConta`) ficam como estão.

## Regras vindas do C4 oficial

### Mensageria (queues-and-topics)

1. **Broker nunca é container.** Cada fila e cada tópico é um container (a página os trata como um *data store*). Por isso o schema tem `mensageria` no componente e `broker` só como tecnologia. Aviso `[BROKER-COMO-CONTAINER]` se um componente tiver `tipo` com palavras como "broker", "message bus" ou "barramento" e não tiver `mensageria`.
2. **Independência de deploy.** O diagrama de Container não mostra a topologia do broker. Quais filas rodam em qual broker ou cluster pertence ao diagrama de `deployment`.
3. **Direção da seta.** O C4 mostra exemplos "sends messages to" da esquerda para a direita e diz que, para destacar publicador/assinante, é possível inverter a direção. O schema aceita as duas:
   - As conexões são sempre **autoradas** na convenção do iniciador (consumidor → fila, `acesso: consome`); `seta_mensageria: fluxo` só muda o desenho.
   - `seta_mensageria: iniciador` (padrão): a seta sai de quem inicia a ação. `publica` e `consome` apontam do serviço para a fila/tópico. O consumo por polling (caso de consumo por polling) fica correto.
   - `seta_mensageria: fluxo`: a seta segue a mensagem. `consome` é desenhado da fila/tópico para o consumidor. Indicado para pub/sub.
4. **Mensagem × chamada de API.** Distinguidas por estilo: `publica`/`consome` usam linha tracejada, como a assíncrona, e `chama` usa linha contínua. O C4 pede outro estilo de linha ou cor, e deixa a escolha à notação do projeto.
5. **Modo implícito (`mensageria_modo: implicita`).** Em relações ponto a ponto a página permite omitir a fila e pôr o nome na seta ("via"). O gerador colapsa publicador → fila → consumidor numa seta rotulada `via <fila>`, só quando a fila tem exatamente 1 publicador e 1 consumidor. Tópicos com vários assinantes continuam explícitos. Nenhuma versão é melhor que a outra; o modo é escolha do autor.
6. **Dono.** Se o serviço é um sistema separado, é preciso dizer quem é dono da fila/tópico (`dono_id`). Componente de `mensageria` sem `dono_id` e sem `fronteira_id`: aviso `[SEM-DONO]` (estar numa fronteira já indica o dono).

### Armazenamento e microsserviços (microservices)

1. **Microsserviço = API + schema de banco.** Dentro de um sistema, o serviço é um grupo de containers: modele a API (`forma: api`, hexágono) e o banco (`armazenamento`, cilindro) e agrupe-os numa fronteira `tipo: servico`. O gerador desenha a caixa em volta do par.
2. **Promoção a sistema.** Quando uma equipe passa a ser dona do serviço, ele deixa de ser grupo e vira sistema próprio com seus diagramas de contexto e container. No schema isso é uma mudança de modelo (`landscape`), feita por Desenho de Arquitetura; o gerador não promove sozinho.
3. **Arquitetura de serviços é detalhe de implementação** enquanto uma única equipe constrói o sistema. Por isso, no Container, `tipo: servico` é opcional: o padrão é só `bounded-context`.
4. **Banco compartilhado.** Se vários serviços acessam o mesmo banco, o gerador emite `[BANCO-COMPARTILHADO]`. Pode ser decisão legítima (monólito em transição); o aviso só torna a escolha visível.
5. **Cor por par.** A página sugere cor para mostrar o pareamento API/banco. Aqui a cor é reservada ao status, então o pareamento é mostrado pela caixa.

## Convenção de cores (status → cor)

Fixas no gerador, nos temas claro e escuro. Cor nunca é o único sinal: a legenda e o texto do elemento trazem o status.

| Status | Preenchimento | Texto | Significado |
|---|---|---|---|
| `novo` | `#1168bd` | branco | Criado por esta demanda |
| `reuso` | `#8ec2f2` | `#0b1f33` | Existente, reutilizado sem alteração |
| `existente` | `#a8a8a8` | `#111` | Já existe, fora do escopo da mudança |
| `alterado` | `#e76f51` | `#111` | Existente, modificado por esta demanda |
| pessoa | `#08427b` | branco | Ator humano |

`alterado` não tinha cor no piloto Structurizr; a cor vem da v1. Texto escuro `#111` porque branco sobre `#e76f51` tem contraste baixo (~3:1). Conferir no tema escuro na fase 2.

## Formas

| Elemento | Forma Structurizr |
|---|---|
| ator humano | Person |
| container comum | RoundedBox |
| `forma: api` | Hexagon |
| `forma: app-web` | WebBrowser |
| `forma: app-movel` | MobileDevicePortrait |
| `armazenamento` | Cylinder |
| `mensageria` | Pipe |

O C4 não prescreve formas. Estas são a convenção deste projeto e devem aparecer na legenda da página.

## Notação das setas

| Atributo | Desenho |
|---|---|
| `chama`, síncrona | linha contínua |
| `assincrona: true`, `publica`, `consome` | linha tracejada |
| `le` / `grava` | linha contínua, verbo no rótulo ("Lê", "Grava em") |
| `condicao` presente | cor de alerta + texto "Condicional" no rótulo |
| rótulo | verbo + tecnologia (`tecnologia` da conexão entre colchetes) |
| numeração | só no diagrama dinâmico |

## Mapa nível → view do Structurizr

| `nivel` | View |
|---|---|
| `contexto` | `systemContext` |
| `container` | `container` |
| `componente` | `component` |
| `landscape` | `systemLandscape` |
| `dinamico` | `dynamic` |
| `deployment` | `deployment` |
| `fluxo-dados` | `container` filtrada por `include` de armazenamentos/mensageria e seus vizinhos |

## Avisos do gerador (relatório sempre exibido, mesmo vazio)

`[ORFAO]`, `[FALTA-CATALOGO]` (herdados da v1) · `[SEM-TECNOLOGIA]` · `[BROKER-COMO-CONTAINER]` · `[SEM-DONO]` · `[BANCO-COMPARTILHADO]` · `[STATUS-SEM-COR]`.
