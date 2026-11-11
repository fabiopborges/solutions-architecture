#!/usr/bin/env python3
"""Gera TODOS os diagramas C4 de uma demanda nova (Structurizr): derivação, páginas HTML, validação e relatório.

Uso:
    python3 scripts/gerar_diagramas_demanda.py demandas/<nome-da-demanda> [--titulo-base TEXTO] [--sem-validar] [--forcar]

Lê, em demandas/<x>/diagramas/:
    catalogo-componentes.json            (obrigatório; formato v2, ver docs/diagrams/c4-schema-v2.md)
    sequencia-<journey_id>_spec.json     (opcional, um por jornada; Jornadas do Usuário)
    c4-container.json                    (só se NÃO houver sequência: Container autorado a partir de desenho.md)
    c4-fluxo-dados.json                  (opcional: Container autorado a partir de dados.md; sem ele, o fluxo é filtrado de c4-container.json)
    c4-componente-<container>.json      (opcional: Component diagram de um container; nivel=componente + foco_id)

Grava na mesma pasta:
    c4-container-jornada-<id>.json/.html (um por jornada; com Dynamic diagram)
    c4-container.json/.html              (união das jornadas)
    c4-contexto.html                     (System Context, do mesmo c4-container.json)
    c4-fluxo-dados.html                  (do spec autorado ou, se o Container tem armazenamento/mensageria, filtrado dele)
    c4-componente-<container>.html       (se houver o spec)
    _trabalho/<nome>/workspace.dsl       (fonte Structurizr de cada diagrama, para rastreabilidade)
    RELATORIO-GERACAO.md                 (derivação, avisos e validação; repassar a quem acionou, nunca descartar)

Recusa demandas legadas (que já têm *.architecture.json do ArchiFy) salvo --forcar.
Requisitos: docker, google-chrome. Código de saída 1 se qualquer diagrama falhar.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

AQUI = pathlib.Path(__file__).resolve().parent
LINHAS_RELEVANTES = re.compile(r"^(aviso:|\[FAIL\]|\[WARN\]|Resumo:|Erros no spec|  \[|ok:)")


def roda(cmd, timeout=1800):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("demanda")
    ap.add_argument("--titulo-base")
    ap.add_argument("--sem-validar", action="store_true")
    ap.add_argument("--forcar", action="store_true", help="permite rodar numa demanda que já tem diagramas ArchiFy")
    a = ap.parse_args()

    dd = pathlib.Path(a.demanda).resolve() / "diagramas"
    if not dd.is_dir():
        sys.exit(f"Pasta não encontrada: {dd}")
    legado = sorted(p.name for p in dd.rglob("*.architecture.json"))
    if legado and not a.forcar:
        sys.exit("Demanda legada: já tem diagramas ArchiFy (" + ", ".join(legado[:3]) + "). O gerador novo vale só para demandas novas; "
                 "não regerar o passado. Use --forcar apenas se o pedido for explícito.")
    catalogo = dd / "catalogo-componentes.json"
    if not catalogo.exists():
        sys.exit(f"Falta {catalogo} (1ª execução do agente: traduzir desenho.md para o catálogo).")

    base = a.titulo_base or pathlib.Path(a.demanda).resolve().name
    relatorio = [f"# Relatório de geração de diagramas — {base}", ""]
    falhas = []

    seqs = sorted(dd.glob("sequencia-*_spec.json"))
    if seqs:
        codigo, saida = roda([sys.executable, str(AQUI / "derivar_c4.py"), str(catalogo), *map(str, seqs), "--saida-dir", str(dd),
                              "--formato", "v2", "--titulo-base", base])
        relatorio += ["## Derivação (catálogo + sequências)", "", "```", saida.strip(), "```", ""]
        print(saida.strip())
        if codigo != 0:
            relatorio_final(dd, relatorio + ["**FALHOU a derivação.**"])
            sys.exit(1)
    elif not (dd / "c4-container.json").exists():
        sys.exit("Sem sequência de jornada e sem c4-container.json: autore o Container (v2) a partir de desenho.md "
                 "(ver skills/geracao-diagramas/SKILL.md, passo 4).")
    else:
        relatorio += ["## Derivação", "", "Sem sequências de jornada: usado `c4-container.json` autorado a partir de desenho.md.", ""]

    alvos = []   # (spec, html, nivel, pasta de trabalho)
    if (dd / "c4-container.json").exists():
        alvos.append((dd / "c4-container.json", dd / "c4-container.html", None, "container"))
    for p in sorted(dd.glob("c4-container-jornada-*.json")):
        alvos.append((p, p.with_suffix(".html"), None, p.stem))
    if (dd / "c4-container.json").exists():
        alvos.append((dd / "c4-container.json", dd / "c4-contexto.html", "contexto", "contexto"))
    for p in sorted(dd.glob("c4-componente-*.json")):   # autorados a partir de desenho.md, um por container em foco
        alvos.append((p, p.with_suffix(".html"), None, p.stem))
    if (dd / "c4-fluxo-dados.json").exists():
        alvos.append((dd / "c4-fluxo-dados.json", dd / "c4-fluxo-dados.html", None, "fluxo-dados"))
    elif (dd / "c4-container.json").exists() and _tem_dados(dd / "c4-container.json"):   # visão filtrada do Container, sem modelagem própria
        alvos.append((dd / "c4-container.json", dd / "c4-fluxo-dados.html", "fluxo-dados", "fluxo-dados"))

    relatorio += ["## Diagramas", ""]
    for spec, html, nivel, nome in alvos:
        cmd = [sys.executable, str(AQUI / "gerar_pagina_c4.py"), str(spec), "--saida", str(html), "--pasta", str(dd / "_trabalho" / nome)]
        if nivel:
            cmd += ["--nivel", nivel]
        if a.sem_validar:
            cmd.append("--sem-validar")
        print(f"\n>>> {html.name}")
        codigo, saida = roda(cmd)
        linhas = [l for l in saida.splitlines() if LINHAS_RELEVANTES.match(l) and "[PASS]" not in l]
        print("\n".join(linhas))
        status = "OK" if codigo == 0 else "FALHOU"
        if codigo != 0:
            falhas.append(html.name)
        relatorio += [f"### {html.name} — {status}", "", "```", "\n".join(linhas) or "(sem linhas relevantes)", "```", ""]
        if codigo != 0 and not linhas:
            relatorio += ["```", saida[-1500:], "```", ""]

    relatorio += ["## Resumo", "", f"{len(alvos) - len(falhas)} de {len(alvos)} diagramas gerados." + (f" Falharam: {', '.join(falhas)}." if falhas else "")]
    relatorio_final(dd, relatorio)
    print(f"\nResumo: {len(alvos) - len(falhas)}/{len(alvos)} diagramas. Relatório: {dd / 'RELATORIO-GERACAO.md'}")
    sys.exit(1 if falhas else 0)


def _tem_dados(spec_path):
    comps = json.loads(spec_path.read_text(encoding="utf-8")).get("componentes", [])
    return any(c.get("armazenamento") or c.get("mensageria") for c in comps)


def relatorio_final(dd, linhas):
    (dd / "RELATORIO-GERACAO.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
