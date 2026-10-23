#!/usr/bin/env python3
"""MVP 7 (docs/refactory/aderencia-agent-fabric-mulesoft/mvp7/mvp7.md) —
MCP Bridge para as operações internas do time, hoje só disparáveis
manualmente via `.claude/skills/arquiteto-solucoes/SKILL.md`
(`argument-hint: "<pedido/SDR> | status <nome-da-demanda> | help"`).

Servidor separado do MVP 5 (servidor/servidor_mcp.py): aquele só lê o
substrato de conhecimento (consulta), este expõe operações que podem
disparar uma cadeia inteira de subagentes (ação) — escopos diferentes,
processos diferentes.

Padrão do MCP Bridge do Agent Fabric: operações de LEITURA ficam ativas por
padrão; operações de ESCRITA ficam DESATIVADAS por padrão e só são ativadas
com autorização explícita do usuário. `iniciar_demanda` (ESCRITA) está
DESATIVADA nesta versão — decisão explícita registrada na sessão que gerou
este arquivo. Para ativar, mude ESCRITA_ATIVADA para True.

NÃO VALIDADO: o pacote `mcp` (SDK oficial) não está instalado neste
ambiente — mesma situação do MVP 5. Rode `python3
servidor/servidor_mcp_operacoes.py --selftest` para exercitar a lógica sem
o SDK, ou `pip install mcp` e depois `python3
servidor/servidor_mcp_operacoes.py` para servir via stdio de verdade.

Este servidor NUNCA despacha um subagente Task diretamente — ele não tem
essa capacidade (é um processo Python isolado, sem acesso à ferramenta
Task do Claude Code). `iniciar_demanda`, quando ativada, só cria/confirma a
pasta da demanda e registra a intenção; quem efetivamente despacha os
subagentes continua sendo a skill `arquiteto-solucoes` de dentro de uma
sessão Claude Code, exatamente como hoje.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEMANDAS_DIR = REPO_ROOT / "demandas"
TELEMETRIA_PATH = REPO_ROOT / "telemetria-agentes.md"
LOG_PATH = REPO_ROOT / "servidor" / "consultas.log"

# Decisão explícita, registrada na sessão que gerou este arquivo: escrita
# (iniciar_demanda) fica desativada até autorização humana futura.
ESCRITA_ATIVADA = False

ETAPAS_DA_CADEIA = [
    "entendimento-e-escopo",
    "desenho-de-arquitetura",
    "modelagem-de-dados",
    "infraestrutura-e-deployment",
    "testes-e-qualidade",
    "jornadas-do-usuario",
    "seguranca-e-compliance",
    "estimativa-de-custo",
    "observabilidade-e-telemetria",
    "documentacao-final",
    "riscos-e-mitigacao",
    "comunicacao-stakeholders",
    "entrega-e-handoff",
]

ARTEFATO_POR_ETAPA = {
    "entendimento-e-escopo": ["entendimento.md"],
    "desenho-de-arquitetura": ["desenho.md"],
    "modelagem-de-dados": ["dados.md"],
    "infraestrutura-e-deployment": ["infraestrutura.md"],
    "testes-e-qualidade": ["qualidade.md"],
    "jornadas-do-usuario": ["jornadas.md"],
    "seguranca-e-compliance": ["seguranca.md"],
    "estimativa-de-custo": ["custo.md"],
    "observabilidade-e-telemetria": ["observabilidade.md"],
    # "pacote-final.md" é o nome real encontrado em demandas anteriores à
    # padronização (ex.: sdr-2026-002-integracao-crm-serasa-mtls-jwt) —
    # documentacao-final.md é o nome documentado em skills/documentacao-final/SKILL.md.
    "documentacao-final": ["documentacao-final.md", "pacote-final.md"],
    "riscos-e-mitigacao": ["riscos.md"],
    # "apresentacao.md" é o nome pré-2026-08-16, documentado como não
    # retroativo em skills/comunicacao-stakeholders/SKILL.md.
    "comunicacao-stakeholders": ["comunicacao.md", "apresentacao.md"],
    "entrega-e-handoff": ["handoff.md"],
}


def _log(tool: str, entrada: dict, resultado: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "entrada": entrada,
        "resultado": str(resultado)[:500],
    }
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _iniciar_demanda(pedido: str) -> dict:
    if not ESCRITA_ATIVADA:
        resultado = {
            "status": "erro",
            "motivo": (
                "iniciar_demanda está desativada por padrão (operação de ESCRITA). "
                "Ative ESCRITA_ATIVADA em servidor/servidor_mcp_operacoes.py com "
                "autorização humana explícita antes de usar esta tool."
            ),
        }
        _log("iniciar_demanda", {"pedido": pedido}, resultado["motivo"])
        return resultado

    # Implementação real fica pendente de ativação explícita: mesmo com
    # ESCRITA_ATIVADA=True, este servidor não tem acesso à ferramenta Task
    # do Claude Code, então não consegue de fato despachar os 19 subagentes
    # — só pode confirmar a intenção e apontar para o fluxo real (a skill
    # arquiteto-solucoes, dentro de uma sessão Claude Code).
    resultado = {
        "status": "não implementado",
        "motivo": (
            "Este servidor MCP roda como processo isolado e não tem acesso à "
            "ferramenta Task — não consegue despachar subagentes de verdade. "
            "Use '/arquiteto-solucoes <pedido>' dentro de uma sessão Claude Code."
        ),
        "caminho": None,
    }
    _log("iniciar_demanda", {"pedido": pedido}, resultado["motivo"])
    return resultado


def _consultar_status_demanda(nome_demanda: str) -> dict:
    demanda_dir = DEMANDAS_DIR / nome_demanda
    if not demanda_dir.exists():
        resultado = {
            "etapas_concluidas": [],
            "etapas_pendentes": ETAPAS_DA_CADEIA,
            "observacao": f"não encontrado: a pasta demandas/{nome_demanda}/ não existe.",
        }
        _log("consultar_status_demanda", {"nome_demanda": nome_demanda}, resultado["observacao"])
        return resultado

    concluidas = []
    pendentes = []
    for etapa in ETAPAS_DA_CADEIA:
        candidatos = ARTEFATO_POR_ETAPA[etapa]
        if any((demanda_dir / nome).exists() for nome in candidatos):
            concluidas.append(etapa)
        else:
            pendentes.append(etapa)

    resultado = {"etapas_concluidas": concluidas, "etapas_pendentes": pendentes}
    _log("consultar_status_demanda", {"nome_demanda": nome_demanda}, json.dumps(resultado, ensure_ascii=False))
    return resultado


def _ajuda() -> dict:
    texto = (
        "Time de agentes de Arquiteto de Soluções. Recebe uma demanda de "
        "arquitetura (SDR, pedido de negócio, etc.), orquestra as atividades da "
        "cadeia (mais especialistas sob demanda) e entrega um pacote de "
        "arquitetura completo e rastreável. Use '/arquiteto-solucoes <pedido>' "
        "para iniciar, '/arquiteto-solucoes status <nome-da-demanda>' para "
        "acompanhar."
    )
    _log("ajuda", {}, texto)
    return {"texto": texto}


def _build_server():
    from mcp.server.fastmcp import FastMCP  # type: ignore

    mcp_server = FastMCP("arquiteto-solucoes-operacoes")

    @mcp_server.tool()
    def iniciar_demanda(pedido: str) -> dict:
        """Inicia uma nova demanda de arquitetura (ESCRITA — desativada por
        padrão). Cobre tanto pedido de negócio novo quanto avaliação de
        arquitetura de terceiros, já que ambos usam o mesmo argumento de
        texto livre na skill real."""
        return _iniciar_demanda(pedido)

    @mcp_server.tool()
    def consultar_status_demanda(nome_demanda: str) -> dict:
        """Consulta quais etapas da cadeia já produziram artefato para uma
        demanda existente em demandas/<nome-da-demanda>/, sem despachar
        nenhum agente novo (LEITURA)."""
        return _consultar_status_demanda(nome_demanda)

    @mcp_server.tool()
    def ajuda() -> dict:
        """Explica brevemente o que este time faz (LEITURA)."""
        return _ajuda()

    return mcp_server


def _selftest() -> int:
    print("== iniciar_demanda('teste') (deve vir desativada) ==")
    print(json.dumps(_iniciar_demanda("teste"), ensure_ascii=False, indent=2))
    print("\n== consultar_status_demanda('demanda-que-nao-existe') ==")
    print(json.dumps(_consultar_status_demanda("demanda-que-nao-existe"), ensure_ascii=False, indent=2))
    print("\n== ajuda() ==")
    print(json.dumps(_ajuda(), ensure_ascii=False, indent=2))
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
            "'python3 servidor/servidor_mcp_operacoes.py --selftest'.",
            file=sys.stderr,
        )
        return 1

    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
