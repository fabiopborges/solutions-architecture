#!/usr/bin/env python3
"""Lê o bloco `agent_card` YAML anexado ao final de cada agents/<atividade>/AGENT.md
(MVP 1 de docs/refactory/aderencia-agent-fabric-mulesoft/) e gera um JSON A2A Agent
Card por agente em registry/agent-cards/<atividade>.json.

Parser dedicado ao formato fixo do bloco agent_card definido em
docs/refactory/aderencia-agent-fabric-mulesoft/mvp1/mvp1.md — não é um parser YAML
genérico. Só stdlib, sem PyYAML (não está instalado neste ambiente).
"""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
OUTPUT_DIR = REPO_ROOT / "registry" / "agent-cards"


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _parse_scalar(value: str):
    value = value.strip()
    if value == "true":
        return True
    if value == "false":
        return False
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_strip_quotes(item) for item in inner.split(",")]
    return _strip_quotes(value)


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def parse_agent_card_block(lines: list[str]) -> dict:
    """`lines` começa em `agent_card:` (indentação 0) até o fim do arquivo."""
    root: dict = {}
    # pilha de (indentação, container)
    stack = [(-1, root)]
    i = 1  # pula a própria linha "agent_card:"
    current_list_item = None
    current_list_item_indent = None

    while i < len(lines):
        raw = lines[i]
        if not raw.strip():
            i += 1
            continue
        indent = _indent_of(raw)
        stripped = raw.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if stripped.startswith("- "):
            item_content = stripped[2:]
            if not isinstance(parent, list):
                raise ValueError(f"Item de lista fora de uma lista: {raw!r}")
            new_item: dict = {}
            parent.append(new_item)
            key, _, value = item_content.partition(":")
            key = key.strip()
            value = value.strip()
            if value:
                new_item[key] = _parse_scalar(value)
            # o próprio "- id: x" fica na mesma indentação dos campos irmãos
            # seguintes ("name:", "description:" etc.), então empilha o dict
            # do item nessa indentação para que eles sejam absorvidos como
            # chaves de new_item, não de um novo item de lista.
            stack.append((indent, new_item))
            i += 1
            continue

        key, sep, value = stripped.partition(":")
        if not sep:
            raise ValueError(f"Linha inesperada no bloco agent_card: {raw!r}")
        key = key.strip()
        value = value.strip()

        if value == "":
            # Bloco aninhado (dict ou lista) — decide pelo próximo item não vazio.
            next_indent = None
            next_is_list = False
            for j in range(i + 1, len(lines)):
                if lines[j].strip():
                    next_indent = _indent_of(lines[j])
                    next_is_list = lines[j].strip().startswith("- ")
                    break
            if next_indent is not None and next_indent > indent:
                child = [] if next_is_list else {}
            else:
                child = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(value)
        i += 1

    return root["agent_card"] if "agent_card" in root else root


def extract_agent_card(agent_md_path: Path) -> dict:
    text = agent_md_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line.strip() == "agent_card:":
            start = idx
    if start is None:
        raise ValueError(f"Nenhum bloco agent_card encontrado em {agent_md_path}")
    block_lines = lines[start:]
    # Envolve num dict raiz "agent_card" para reaproveitar o parser genérico.
    wrapped = ["agent_card:"] + block_lines[1:]
    return parse_agent_card_block(wrapped)


def main() -> int:
    if not AGENTS_DIR.exists():
        print(f"[erro] pasta não encontrada: {AGENTS_DIR}", file=sys.stderr)
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generated = []
    failed = []
    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir():
            continue
        agent_md = agent_dir / "AGENT.md"
        if not agent_md.exists():
            continue
        try:
            card = extract_agent_card(agent_md)
        except ValueError as exc:
            failed.append((agent_dir.name, str(exc)))
            continue

        out_path = OUTPUT_DIR / f"{agent_dir.name}.json"
        out_path.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        generated.append(agent_dir.name)

    print(f"Gerados {len(generated)} agent cards em {OUTPUT_DIR}:")
    for name in generated:
        print(f"  - {name}.json")
    if failed:
        print(f"\n[erro] {len(failed)} agente(s) sem bloco agent_card válido:", file=sys.stderr)
        for name, reason in failed:
            print(f"  - {name}: {reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
