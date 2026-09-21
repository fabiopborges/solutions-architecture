#!/usr/bin/env python3
"""MVP 4 (docs/refactory/aderencia-agent-fabric-mulesoft/mvp4/mvp4.md) — lê
telemetria/interacoes.jsonl (log de interações no formato que o Agent
Visualizer usa) e gera um resumo agregado por demanda no MESMO FORMATO
NARRATIVO de telemetria-agentes.md (uma entrada por demanda, "Por agente: ...",
paralelo vs sequencial) — não um formato tabular, porque telemetria-agentes.md
nunca foi tabular; ver seção "Formato de uma entrada" do próprio arquivo.

Limitação conhecida, não escondida: o log JSONL só guarda o que é
estruturalmente real (origem, destino, tokens, resultado, artefato). Comentário
qualitativo por agente ("achou 1 requisito não atendido", "identificou 1
tensão") e a descrição de paralelo vs sequencial não fazem parte do schema do
MVP 4 — este script não inventa esse texto, só resume o que o JSONL contém.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JSONL_PATH = REPO_ROOT / "telemetria" / "interacoes.jsonl"


def load_interactions(path: Path) -> list[dict]:
    interactions = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                interactions.append(json.loads(line))
    return interactions


def format_demanda(demanda: str, interactions: list[dict]) -> str:
    lines = [f"### {demanda}", "", "**Por agente (origem → destino), status e tokens (extraído de telemetria/interacoes.jsonl):**"]
    total_tokens = 0
    total_sucesso = 0
    total_erro = 0
    for it in interactions:
        tokens = it["tokens_consumidos"]
        if tokens is not None:
            total_tokens += tokens
        if it["resultado"] == "sucesso":
            total_sucesso += 1
        elif it["resultado"] == "erro":
            total_erro += 1
        artefato = it["artefato_gerado"] or "(nenhum artefato registrado)"
        tokens_str = f"{tokens:,}".replace(",", ".") if tokens is not None else "não registrado"
        lines.append(
            f"- {it['agente_origem']} → {it['agente_destino']}: "
            f"{it['resultado']}, {tokens_str} tokens, artefato: {artefato}."
        )
    lines.append("")
    lines.append(
        f"**Total medido: {total_tokens:,} tokens**".replace(",", ".")
        + f" em {total_sucesso} interação(ões) bem-sucedida(s)"
        + (f" (mais {total_erro} tentativa(s) sem custo registrado)" if total_erro else "")
        + "."
    )
    bottlenecks = [f"{it['agente_origem']} → {it['agente_destino']}" for it in interactions if it["bottleneck_flag"]]
    if bottlenecks:
        lines.append("")
        lines.append("**Interações acima da duração média da demanda (bottleneck_flag):** " + ", ".join(bottlenecks) + ".")
    lines.append("")
    lines.append(
        "**Loops de dúvida / paralelo vs sequencial:** não reconstruído aqui — "
        "esses dados não fazem parte do schema de telemetria/interacoes.jsonl (MVP 4); "
        "continuam registrados em prosa na entrada correspondente de telemetria-agentes.md."
    )
    return "\n".join(lines)


def main() -> int:
    if not JSONL_PATH.exists():
        print(f"[erro] arquivo não encontrado: {JSONL_PATH}", file=sys.stderr)
        return 1

    interactions = load_interactions(JSONL_PATH)
    by_demanda: dict[str, list[dict]] = defaultdict(list)
    for it in interactions:
        by_demanda[it["demanda"]].append(it)

    print("# Resumo agregado (gerado por scripts/coletar_telemetria.py a partir de telemetria/interacoes.jsonl)\n")
    for demanda in sorted(by_demanda):
        print(format_demanda(demanda, by_demanda[demanda]))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
