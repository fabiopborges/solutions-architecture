#!/usr/bin/env python3
"""MVP 5 (docs/refactory/aderencia-agent-fabric-mulesoft/mvp5/mvp5.md) —
servidor MCP interno que expõe substrate/compendium.md e adrs/ como três
ferramentas consultáveis, no espírito da Enterprise Actionability do
MuleSoft Agent Fabric (expor um sistema existente como servidor MCP por
configuração, sem reescrever a fonte).

NÃO VALIDADO: o pacote `mcp` (SDK oficial) não está instalado neste
ambiente (`pip show mcp` não encontrou o pacote), então este servidor não
foi executado/testado de ponta a ponta com um cliente MCP real. A lógica de
extração (`_stack_aprovada`, `_buscar_adr`, `_padroes_da_casa`) foi testada
isoladamente via `python3 servidor/servidor_mcp.py --selftest` (sem
depender do SDK), mas o transporte MCP em si (stdio) não. Rode
`pip install mcp` e depois `python3 servidor/servidor_mcp.py` para servir
via stdio de verdade.

Nenhum conteúdo é inventado: cada tool só retorna trecho literal de
substrate/compendium.md ou de um arquivo em adrs/, ou uma resposta
explícita de "não encontrado" — nunca uma resposta fabricada.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPENDIUM_PATH = REPO_ROOT / "substrate" / "compendium.md"
ADRS_DIR = REPO_ROOT / "adrs"
LOG_PATH = REPO_ROOT / "servidor" / "consultas.log"


def _log(tool: str, entrada: dict, trecho_retornado: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "entrada": entrada,
        "trecho_retornado": trecho_retornado[:500],
    }
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_section(markdown: str, heading_pattern: str) -> str:
    """Extrai o texto de uma seção `## <heading_pattern>` até o próximo `## `."""
    match = re.search(
        rf"^##\s+{heading_pattern}.*?$(.*?)(?=^##\s+|\Z)",
        markdown,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else ""


def _stack_aprovada(tecnologia: str) -> dict:
    markdown = COMPENDIUM_PATH.read_text(encoding="utf-8")
    secao1 = _read_section(markdown, r"1\. Stack aprovada")
    linhas = [l for l in secao1.splitlines() if l.strip().startswith("-")]
    tecnologia_lower = tecnologia.strip().lower()
    encontrados = [l for l in linhas if tecnologia_lower in l.lower()]
    if not encontrados:
        conteudo = f"não encontrado: '{tecnologia}' não aparece na seção 1 (Stack aprovada) do compêndio."
    else:
        conteudo = "\n".join(encontrados)
    resultado = {"conteudo": conteudo, "fonte": "substrate/compendium.md, seção 1 (Stack aprovada)"}
    _log("consultar_stack_aprovada", {"tecnologia": tecnologia}, conteudo)
    return resultado


def _padroes_da_casa() -> dict:
    markdown = COMPENDIUM_PATH.read_text(encoding="utf-8")
    secao2 = _read_section(markdown, r"2\. Padrões e políticas da casa")
    padroes = [l.lstrip("- ").strip() for l in secao2.splitlines() if l.strip().startswith("-")]
    _log("listar_padroes_da_casa", {}, "\n".join(padroes))
    return {"padroes": padroes}


def _buscar_adr(assunto: str) -> dict:
    if not ADRS_DIR.exists():
        return {"adr_id": None, "titulo": None, "conteudo": "não encontrado: pasta adrs/ não existe."}

    assunto_lower = assunto.strip().lower()
    candidatos = []
    for adr_path in sorted(ADRS_DIR.glob("adr-*.md")):
        texto = adr_path.read_text(encoding="utf-8")
        nome_lower = adr_path.stem.lower()
        if assunto_lower in nome_lower or assunto_lower in texto.lower():
            candidatos.append((adr_path, texto))

    if not candidatos:
        conteudo = f"não encontrado: nenhum ADR em adrs/ menciona '{assunto}' no nome do arquivo ou no conteúdo."
        resultado = {"adr_id": None, "titulo": None, "conteudo": conteudo}
        _log("consultar_adr", {"assunto": assunto}, conteudo)
        return resultado

    # Primeiro ADR cujo nome do arquivo já bate é preferido (mais preciso que
    # bater só no corpo do texto); em empate, o de número mais baixo (mais
    # antigo, geralmente o padrão geral, não a exceção pontual).
    candidatos.sort(key=lambda item: (assunto_lower not in item[0].stem.lower(), item[0].name))
    adr_path, texto = candidatos[0]
    primeira_linha = texto.splitlines()[0].lstrip("#").strip() if texto.splitlines() else adr_path.stem
    resultado = {"adr_id": adr_path.stem, "titulo": primeira_linha, "conteudo": texto}
    _log("consultar_adr", {"assunto": assunto}, texto)
    return resultado


def _build_server():
    """Constrói o servidor MCP real via FastMCP (mcp.server.fastmcp), quando
    o pacote `mcp` está instalado. Import feito aqui dentro, não no topo do
    módulo, para que --selftest funcione mesmo sem o SDK instalado."""
    from mcp.server.fastmcp import FastMCP  # type: ignore

    mcp_server = FastMCP("arquiteto-solucoes-substrato")

    @mcp_server.tool()
    def consultar_stack_aprovada(tecnologia: str) -> dict:
        """Retorna o que o compêndio da casa diz sobre uma tecnologia (linguagem,
        banco, mensageria, cloud, borda). Use quando precisar confirmar se uma
        tecnologia já é padrão aprovado antes de propor algo novo."""
        return _stack_aprovada(tecnologia)

    @mcp_server.tool()
    def consultar_adr(assunto: str) -> dict:
        """Retorna o ADR (Architecture Decision Record) mais relevante para um
        assunto, buscando por nome de arquivo e conteúdo em adrs/. Use antes de
        propor uma decisão de arquitetura, para não contradizer o que já foi
        decidido."""
        return _buscar_adr(assunto)

    @mcp_server.tool()
    def listar_padroes_da_casa() -> dict:
        """Lista todos os padrões e políticas da casa registrados na seção 2 do
        compêndio (estilo de arquitetura, integração com legado, frameworks de
        modelagem, critérios de escolha de cloud). Use para ter uma visão geral
        antes de decidir algo novo."""
        return _padroes_da_casa()

    return mcp_server


def _selftest() -> int:
    """Exercita a lógica de extração sem depender do SDK `mcp`."""
    print("== consultar_stack_aprovada('MongoDB') ==")
    print(json.dumps(_stack_aprovada("MongoDB"), ensure_ascii=False, indent=2))
    print("\n== consultar_stack_aprovada('Oracle') (não está na stack aprovada) ==")
    print(json.dumps(_stack_aprovada("Oracle"), ensure_ascii=False, indent=2))
    print("\n== listar_padroes_da_casa() ==")
    print(json.dumps(_padroes_da_casa(), ensure_ascii=False, indent=2))
    print("\n== consultar_adr('cloud agnostica') ==")
    resultado = _buscar_adr("cloud agnostica")
    print(json.dumps({"adr_id": resultado["adr_id"], "titulo": resultado["titulo"]}, ensure_ascii=False, indent=2))
    print("\n== consultar_adr('assunto-que-nao-existe-em-nenhum-adr') ==")
    print(json.dumps(_buscar_adr("assunto-que-nao-existe-em-nenhum-adr"), ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()

    try:
        server = _build_server()
    except ImportError:
        print(
            "[erro] pacote 'mcp' não instalado neste ambiente. "
            "Rode 'pip install mcp' para servir via stdio, ou use "
            "'python3 servidor/servidor_mcp.py --selftest' para testar a "
            "lógica de extração sem o SDK.",
            file=sys.stderr,
        )
        return 1

    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
