# Diagramas C4 do README (Structurizr)

SVGs standalone, claro e escuro, extraídos das páginas HTML da demanda **PTI0001 - Agentes Arquiteto de Soluções** (estado atual; a pasta `demandas/` é git-ignored). Gerados em 2026-11-22 com o layout padrão (`dagre`, setas curvas), orientação horizontal.

| Arquivo | Visão |
| --- | --- |
| `contexto-*.svg` | System Context |
| `container-*.svg` | Container **reduzido** (operador + C1, C2, C3, C6, C8, só o caminho principal), derivado de `c4-container.json` sem alterar rótulos |
| `pedir-demanda-receber-pacote-*.svg` | Dynamic diagram da jornada principal |
| `aprovar-adr-*.svg`, `responder-duvida-so-humano-*.svg` | Dynamic diagram das jornadas de governança |

## Como regerar

```bash
python3 scripts/gerar_diagramas_demanda.py "demandas/PTI0001 - Agentes Arquiteto de Soluções"
python3 scripts/exportar_svg_da_pagina_c4.py "demandas/PTI0001 - Agentes Arquiteto de Soluções/diagramas/c4-container.html" docs/diagrams/c4 container --horizontal --visoes container
```

O exportador acrescenta o nome da visão ao prefixo, exceto quando o prefixo já termina nele. Requisitos: Python 3, Docker, Chrome. Detalhes em [`scripts/README.md`](../../../scripts/README.md).

## Limites conhecidos

- O tema segue `prefers-color-scheme` do GitHub via `<picture>` no README; aberto direto, o SVG usa o tema do sistema.
- Sem interação (zoom, legenda, alternância Container/Dynamic): isso só existe na página HTML.
- Os diagramas são largos e o texto fica pequeno no README; abra o SVG em tamanho real.
- Contexto, Container reduzido e Sequência (Dynamic) são exemplificados aqui; o Container completo e as demais vistas ficam na demanda.
