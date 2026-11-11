#!/usr/bin/env python3
"""Spec C4 v2 (JSON) -> Structurizr DSL.

Só traduz o que o spec diz (nunca decide arquitetura nem inventa tecnologia).
Schema e regras: docs/diagrams/c4-schema-v2.md. Só para demandas novas.

Uso:
    python3 scripts/spec_para_dsl.py spec.json -o workspace.dsl [--sem-horizontal]

Saída: workspace.dsl + relatório de avisos (sempre exibido, mesmo vazio).
Código de saída 1 se houver erro (referência inválida, limite de palavras, nível não suportado).

Suporte atual (Fase 1): nivel "container". Com journey_id, gera também o Dynamic diagram
(numerado, na ordem de conexoes[]). Os demais níveis entram na Fase 4.
"""
import argparse
import copy
import json
import pathlib
import re
import sys
import unicodedata

LIMITE_PALAVRAS = 12
NIVEIS_SUPORTADOS = ("container",)
STATUS_TAG = {"novo": "Novo", "alterado": "Alterado", "reuso": "Reuso", "existente": "Existente"}
FORMA_TAG = {"api": "Api", "app-web": "App Web", "app-movel": "App Móvel"}
ARMAZ_ROTULO = {"relacional": "banco relacional", "documento": "banco de documentos", "cache": "cache",
                "objetos": "armazenamento de objetos", "busca": "índice de busca", "analitico": "armazenamento analítico"}
MENS_ROTULO = {"fila": "fila", "topico": "tópico", "stream": "stream"}
PALAVRAS_BROKER = ("broker", "message bus", "barramento")
ACESSOS_ASSINCRONOS = ("publica", "consome")


# ----------------------------------------------------------------------------- utilidades
def ident(texto):
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    s = re.sub(r"\W+", "_", s).strip("_") or "x"
    return "e_" + s if s[0].isdigit() else s


def slug(texto):
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "geral"


def q(texto):
    """Literal de string do DSL."""
    return '"' + str(texto).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def palavras(texto):
    return len((texto or "").split())


# ----------------------------------------------------------------------------- validação
def validar(spec):
    """Retorna (erros, avisos). Erros impedem a geração; avisos entram no relatório."""
    erros, avisos = [], []
    try:
        import jsonschema  # opcional: o schema formal é checado quando a biblioteca existe
        esquema = json.loads((pathlib.Path(__file__).resolve().parent.parent / "docs" / "diagrams" / "c4-schema-v2.schema.json").read_text(encoding="utf-8"))
        for e in sorted(jsonschema.Draft202012Validator(esquema).iter_errors(spec), key=lambda e: list(e.path)):
            erros.append(f"[schema] {'/'.join(map(str, e.path)) or '(raiz)'}: {e.message}")
    except ImportError:
        avisos.append("[SCHEMA-NAO-VALIDADO] biblioteca jsonschema ausente: só as checagens internas rodaram")

    nivel = spec.get("nivel")
    if nivel not in NIVEIS_SUPORTADOS:
        erros.append(f"[nivel] '{nivel}' ainda não é gerado (suportado: {', '.join(NIVEIS_SUPORTADOS)})")

    atores = spec.get("atores", []) or []
    comps = spec.get("componentes", []) or []
    fronts = spec.get("fronteiras", []) or []
    conx = spec.get("conexoes", []) or []

    ids = {}
    for tipo, lista in (("ator", atores), ("componente", comps), ("fronteira", fronts)):
        for item in lista:
            i = item.get("id")
            if i is None:
                continue
            if i in ids:
                erros.append(f"[id-duplicado] '{i}' ({tipo}) já usado como {ids[i]}")
            ids[i] = tipo
    ids_fr = {f["id"] for f in fronts if "id" in f}
    ids_node = {x["id"] for x in atores + comps if "id" in x}
    mens = {c["id"] for c in comps if c.get("mensageria") and "id" in c}
    nome_de = {x["id"]: x.get("nome", x["id"]) for x in atores + comps + fronts if "id" in x}

    for f in fronts:
        if f.get("pai_id") and f["pai_id"] not in ids_fr:
            erros.append(f"[ref] fronteira '{f.get('id')}': pai_id '{f['pai_id']}' não existe")
    for f in fronts:  # ciclo em pai_id
        visto, cur = set(), f.get("id")
        pais = {x["id"]: x.get("pai_id") for x in fronts if "id" in x}
        while cur:
            if cur in visto:
                erros.append(f"[ref] ciclo em pai_id envolvendo fronteira '{f.get('id')}'"); break
            visto.add(cur); cur = pais.get(cur)
    for c in comps:
        if c.get("fronteira_id") and c["fronteira_id"] not in ids_fr:
            erros.append(f"[ref] componente '{c.get('id')}': fronteira_id '{c['fronteira_id']}' não existe")
        d = c.get("dono_id")
        if d and d not in ids_fr and d not in ids_node:
            erros.append(f"[ref] componente '{c.get('id')}': dono_id '{d}' não existe")
    for i, c in enumerate(conx):
        for campo in ("de", "para"):
            if c.get(campo) not in ids_node:
                erros.append(f"[FALTA-CATALOGO] conexão #{i + 1}: '{c.get(campo)}' ({campo}) não existe em atores/componentes")
        if c.get("via") and c["via"] not in mens:
            erros.append(f"[ref] conexão #{i + 1}: via '{c['via']}' não é um componente com mensageria")

    # limite de palavras (campos que aparecem na figura). `condicao` fica fora do limite.
    for chave, campos in (("componentes", ("nome", "descricao")), ("atores", ("nome", "papel")), ("conexoes", ("rotulo",))):
        for item in spec.get(chave, []) or []:
            for campo in campos:
                n = palavras(item.get(campo))
                if n > LIMITE_PALAVRAS:
                    erros.append(f"[limite-palavras] {chave}.{campo} '{item.get('id', item.get('de', '?'))}' tem {n} palavras (limite {LIMITE_PALAVRAS})")

    # ----- avisos
    ligados = {c.get("de") for c in conx} | {c.get("para") for c in conx} | {c.get("via") for c in conx}
    for x in atores + comps:
        if x.get("id") not in ligados:
            avisos.append(f"[ORFAO] '{x.get('id')}' não aparece em nenhuma conexão")
    for c in comps:
        if not c.get("tecnologia") and not (c.get("mensageria") and c.get("broker")):
            avisos.append(f"[SEM-TECNOLOGIA] componente '{c.get('id')}' sem tecnologia (o gerador não inventa)")
        tipo = (c.get("tipo") or "").lower()
        if any(p in tipo for p in PALAVRAS_BROKER) and not c.get("mensageria"):
            avisos.append(f"[BROKER-COMO-CONTAINER] '{c.get('id')}' parece um broker; o C4 modela cada fila/tópico como container (campo mensageria) e o broker como tecnologia")
        if c.get("mensageria") and not c.get("dono_id") and not c.get("fronteira_id"):
            avisos.append(f"[SEM-DONO] '{c.get('id')}' (mensageria) sem dono_id e sem fronteira_id")
    for c in conx:
        if c.get("de") in ids_node and c.get("para") in ids_node and not c.get("tecnologia"):
            avisos.append(f"[SEM-TECNOLOGIA] conexão {c['de']} -> {c['para']} sem tecnologia")
    # banco compartilhado: armazenamento acessado por componentes de fronteiras diferentes
    fr_de = {c["id"]: c.get("fronteira_id") for c in comps if "id" in c}
    for c in comps:
        if not c.get("armazenamento"):
            continue
        acessos = {fr_de.get(x["de"]) for x in conx if x.get("para") == c["id"] and x.get("de") in fr_de}
        if len(acessos) > 1:
            avisos.append(f"[BANCO-COMPARTILHADO] '{c['id']}' é acessado por componentes de {len(acessos)} fronteiras diferentes")
    _ = nome_de
    return erros, avisos


# ----------------------------------------------------------------------------- modelo efetivo
def modelo_efetivo(spec):
    """Aplica mensageria_modo (implícita) e seta_mensageria (fluxo) sobre uma cópia do spec."""
    s = copy.deepcopy(spec)
    comps = {c["id"]: c for c in s.get("componentes", [])}
    conx = list(s.get("conexoes", []))
    if s.get("mensageria_modo") == "implicita":
        for qid in [i for i, c in comps.items() if c.get("mensageria")]:
            pubs = [c for c in conx if c["para"] == qid and c.get("acesso") == "publica"]
            cons = [c for c in conx if c["para"] == qid and c.get("acesso") == "consome"]
            outros = [c for c in conx if qid in (c["de"], c["para"]) and c not in pubs and c not in cons]
            if len(pubs) == 1 and len(cons) == 1 and not outros and not any(c.get("via") == qid for c in conx):
                fila = comps[qid]
                pub, con = pubs[0], cons[0]
                via = f"via {fila.get('nome', qid)}" + (f" ({fila['broker']})" if fila.get("broker") else "")
                novo = {"de": pub["de"], "para": con["de"], "rotulo": pub["rotulo"], "assincrona": True,
                        "acesso": "chama", "tecnologia": (pub.get("tecnologia") + ", " if pub.get("tecnologia") else "") + via}
                cond = pub.get("condicao") or con.get("condicao")
                if cond:
                    novo["condicao"] = cond
                if pub.get("journey_id"):
                    novo["journey_id"] = pub["journey_id"]
                conx[conx.index(pub)] = novo
                conx.remove(con)
                del comps[qid]
    if s.get("seta_mensageria") == "fluxo":
        for c in conx:
            if c.get("acesso") == "consome" and comps.get(c["para"], {}).get("mensageria"):
                c["de"], c["para"] = c["para"], c["de"]
    s["componentes"] = list(comps.values())
    s["conexoes"] = conx
    return s


# ----------------------------------------------------------------------------- DSL
def _tecnologia(c):
    if c.get("mensageria"):
        base = c.get("broker") or c.get("tecnologia") or ""
        return (base + " · " if base else "") + MENS_ROTULO[c["mensageria"]]
    if c.get("armazenamento"):
        base = c.get("tecnologia") or ""
        return (base + " · " if base else "") + ARMAZ_ROTULO[c["armazenamento"]]
    return c.get("tecnologia") or ""


def _tags_comp(c):
    tags = [STATUS_TAG[c["status"]]]
    if c.get("forma") in FORMA_TAG:
        tags.append(FORMA_TAG[c["forma"]])
    if c.get("armazenamento"):
        tags.append("Armazenamento")
    if c.get("mensageria"):
        tags.append("Mensageria")
    return ",".join(tags)


def _descricao(c, nome_de):
    partes = [c.get("descricao", "").rstrip(".")]
    if c.get("dono_id"):
        partes.append(f"Dono: {nome_de.get(c['dono_id'], c['dono_id'])}")
    if c.get("retencao"):
        partes.append(f"Retenção: {c['retencao']}")
    if c.get("sensibilidade"):
        partes.append(f"Sensibilidade: {c['sensibilidade']}")
    return ". ".join(p for p in partes if p)


def _caminho_fronteira(fid, fronts):
    por_id = {f["id"]: f for f in fronts}
    nomes = []
    while fid:
        nomes.append(por_id[fid]["nome"]); fid = por_id[fid].get("pai_id")
    return " / ".join(reversed(nomes))


# Paleta única: o gerador a aplica e o validador (validar_diagrama_c4.py) mede o contraste dela.
# (fundo, texto) por tag de elemento. Mesmas cores nos dois temas, como no piloto aprovado.
PALETA_ELEMENTOS = {
    "Person": ("#08427b", "#ffffff"), "Software System": ("#1168bd", "#ffffff"), "Container": ("#1168bd", "#ffffff"),
    "Novo": ("#1168bd", "#ffffff"), "Reuso": ("#8ec2f2", "#0b1f33"),
    "Existente": ("#a8a8a8", "#111111"), "Alterado": ("#e76f51", "#111111"),
}
# por tema: cor da seta, cor da seta condicional, texto e borda do grupo, fundo do canvas (o da página)
PALETA_TEMA = {
    "light": {"seta": "#444444", "condicional": "#a35f00", "grupo_txt": "#444444", "grupo_borda": "#888888", "canvas": "#ffffff"},
    "dark": {"seta": "#d0d7e2", "condicional": "#f0a940", "grupo_txt": "#d0d7e2", "grupo_borda": "#8a94a6", "canvas": "#111111"},
}
FORMAS_TAG = (("Api", "Hexagon"), ("App Web", "WebBrowser"), ("App Móvel", "MobileDevicePortrait"),
              ("Armazenamento", "Cylinder"), ("Mensageria", "Pipe"))


def _estilos(modo):
    pt = PALETA_TEMA[modo]
    s = f"            {modo} {{\n"
    for tag, (bg, fg) in PALETA_ELEMENTOS.items():
        forma = "                    shape Person\n" if tag == "Person" else ""
        s += f'                element "{tag}" {{\n{forma}                    background {bg}\n                    color {fg}\n                }}\n'
    for tag, forma in FORMAS_TAG:
        s += f'                element "{tag}" {{\n                    shape {forma}\n                }}\n'
    s += f'                element "Group" {{\n                    color {pt["grupo_txt"]}\n                    stroke {pt["grupo_borda"]}\n                    strokeWidth 2\n                }}\n'
    s += f'                relationship "Relationship" {{\n                    thickness 3\n                    dashed false\n                    color {pt["seta"]}\n                    routing Curved\n                    fontSize 22\n                    width 420\n                }}\n'
    s += '                relationship "Assíncrono" {\n                    dashed true\n                }\n'
    s += f'                relationship "Condicional" {{\n                    color {pt["condicional"]}\n                }}\n'
    s += "            }\n"
    return s


def _rel(c, ref):
    desc = c["rotulo"]
    if c.get("condicao"):
        desc = f"Condicional a {c['condicao']}: {desc}"
    tags = []
    if c.get("assincrona") or c.get("acesso") in ACESSOS_ASSINCRONOS:
        tags.append("Assíncrono")
    if c.get("condicao"):
        tags.append("Condicional")
    return ref(c["de"]), ref(c["para"]), desc, c.get("tecnologia", ""), ",".join(tags)


def nome_sistema(spec):
    sis = spec.get("sistema") or {}
    return sis.get("nome") or spec["titulo"].split(" — ")[0].strip()


def titulos_views(spec, ef):
    sis = nome_sistema(spec)
    jid = spec.get("journey_id")
    escopo = f" (jornada {jid})" if jid else ""
    conds = sorted({c["condicao"] for c in ef["conexoes"] if c.get("condicao")})
    legenda = "Tracejado = assíncrono."
    if conds:
        legenda += f" 'Condicional' no texto = depende de hipótese em aberto ({', '.join(conds)})."
    base = (spec.get("subtitulo", "").rstrip(".") + ". ") if spec.get("subtitulo") else ""
    t = {"container": {"title": f"Container diagram for {sis}{escopo}", "desc": base + legenda}}
    if jid:
        t["dynamic"] = {"title": f"Dynamic diagram for {sis}{escopo}", "desc": "Ordem das interações, numeradas. " + legenda}
    return t


def gerar_dsl(spec, horizontal=True):
    ef = modelo_efetivo(spec)
    atores, comps, fronts, conx = ef.get("atores", []), ef.get("componentes", []), ef.get("fronteiras", []), ef.get("conexoes", [])
    sis = nome_sistema(spec)
    sis_desc = (spec.get("sistema") or {}).get("descricao", "")
    nome_de = {x["id"]: x.get("nome", x["id"]) for x in atores + comps + fronts}
    ids_node = {x["id"] for x in comps}
    jid = spec.get("journey_id")
    sl = slug(jid) if jid else "geral"
    pessoas = [a for a in atores if a["tipo"] != "sistema_externo"]

    def ref(i):
        return ("sis." if i in ids_node else "") + ident(i)

    L = [f"workspace {q(spec['titulo'])} {q(spec.get('subtitulo', ''))} {{", "", "    !identifiers hierarchical"]
    L += ["", "    model {"]
    if any(f.get("pai_id") for f in fronts):  # grupos aninhados exigem a propriedade no model
        L += ["        properties {", '            "structurizr.groupSeparator" "/"', "        }", ""]
    for a in atores:
        tag = STATUS_TAG.get(a.get("status", ""), "")
        if a["tipo"] == "sistema_externo":
            L.append(f'        {ident(a["id"])} = softwareSystem {q(a["nome"])} {q(a.get("papel", ""))} {q(tag or "Existente")}')
        else:
            L.append(f'        {ident(a["id"])} = person {q(a["nome"])} {q(a.get("papel", ""))}' + (f" {q(tag)}" if tag else ""))
    L += ["", f"        sis = softwareSystem {q(sis)} {q(sis_desc)} {{"]

    usados = {c.get("fronteira_id") for c in comps}
    filhos = {}
    for f in fronts:
        filhos.setdefault(f.get("pai_id"), []).append(f)

    def tem_conteudo(f):
        return f["id"] in usados or any(tem_conteudo(x) for x in filhos.get(f["id"], []))

    def emite_comp(c, ind):
        L.append(f'{ind}{ident(c["id"])} = container {q(c["nome"])} {q(_descricao(c, nome_de))} {q(_tecnologia(c))} {q(_tags_comp(c))}')

    def emite_grupo(f, ind):
        L.append(f'{ind}group {q(f["nome"].replace("/", "-"))} {{')
        for c in comps:
            if c.get("fronteira_id") == f["id"]:
                emite_comp(c, ind + "    ")
        for x in filhos.get(f["id"], []):
            if tem_conteudo(x):
                emite_grupo(x, ind + "    ")
        L.append(f"{ind}}}")

    for f in filhos.get(None, []):
        if tem_conteudo(f):
            emite_grupo(f, "            ")
    for c in comps:
        if not c.get("fronteira_id"):
            emite_comp(c, "            ")
    L += ["        }", "", "        # Relações: uma seta = uma relação unidirecional. Descrição e tecnologia vêm do spec."]
    for c in conx:
        o, d, desc, tec, tags = _rel(c, ref)
        L.append(f"        {o} -> {d} {q(desc)} {q(tec)}" + (f" {q(tags)}" if tags else ""))
    L += ["    }", "", "    views {"]

    tit = titulos_views(spec, ef)
    inc_pessoas = "".join(f"            include {ident(a['id'])}\n" for a in pessoas)
    variantes = [("", "tb 130 100", "tb 140 110")] + ([("-h", "lr 120 110", "lr 120 110")] if horizontal else [])
    for suf, lay_c, lay_d in variantes:
        L.append(f'        container sis "container{suf}-{sl}" {{')
        L.append(f'            title {q(tit["container"]["title"])}\n            description {q(tit["container"]["desc"])}\n            include *')
        if inc_pessoas:
            L.append(inc_pessoas.rstrip("\n"))
        L += [f"            autolayout {lay_c}", "        }", ""]
        if jid:
            L.append(f'        dynamic sis "dynamic{suf}-{sl}" {{')
            L.append(f'            title {q(tit["dynamic"]["title"])}\n            description {q(tit["dynamic"]["desc"])}')
            for c in conx:
                o, d, desc, _, _ = _rel(c, ref)
                L.append(f"            {o} -> {d} {q(desc)}")
            L += [f"            autolayout {lay_d}", "        }", ""]
    L += ["        # Cores = status do componente. Formas = tipo de elemento. Tema escuro repete os estilos de elemento.", "        styles {"]
    L.append(_estilos("light").rstrip("\n"))
    L.append(_estilos("dark").rstrip("\n"))
    L += ["        }", "    }", "}", ""]
    return "\n".join(L)


# ----------------------------------------------------------------------------- dados para a página
def modelo_pagina(spec, avisos):
    ef = modelo_efetivo(spec)
    atores, comps, fronts, conx = ef.get("atores", []), ef.get("componentes", []), ef.get("fronteiras", []), ef.get("conexoes", [])
    nome_de = {x["id"]: x.get("nome", x["id"]) for x in atores + comps + fronts}
    jid = spec.get("journey_id")
    return {
        "sistema": nome_sistema(spec),
        "slug": slug(jid) if jid else "geral",
        "journey": jid or "",
        "titles": titulos_views(spec, ef),
        "atores": [{"nome": a["nome"], "status": STATUS_TAG.get(a.get("status", ""), "Pessoa" if a["tipo"] != "sistema_externo" else "Existente"),
                    "tec": "Pessoa" if a["tipo"] != "sistema_externo" else "Sistema externo", "papel": a.get("papel", "")} for a in atores],
        "componentes": [{"nome": c["nome"], "status": STATUS_TAG[c["status"]], "tec": _tecnologia(c),
                         "grupo": _caminho_fronteira(c["fronteira_id"], fronts) if c.get("fronteira_id") else "—",
                         "descr": _descricao(c, nome_de)} for c in comps],
        "conexoes": [{"de": nome_de[c["de"]], "para": nome_de[c["para"]], "rotulo": c["rotulo"], "tec": c.get("tecnologia", ""),
                      "assinc": bool(c.get("assincrona") or c.get("acesso") in ACESSOS_ASSINCRONOS), "cond": c.get("condicao", "")}
                     for c in conx],
        "formas": sorted({FORMA_TAG[c["forma"]] for c in comps if c.get("forma") in FORMA_TAG}
                         | ({"Armazenamento"} if any(c.get("armazenamento") for c in comps) else set())
                         | ({"Mensageria"} if any(c.get("mensageria") for c in comps) else set())),
        "tem_pessoa": any(a["tipo"] != "sistema_externo" for a in atores),
        "tem_grupo": any(c.get("fronteira_id") for c in comps),
        "glossario": spec.get("glossario", []),
        "avisos": avisos,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("-o", "--saida", required=True)
    ap.add_argument("--sem-horizontal", action="store_true")
    a = ap.parse_args()
    spec = json.loads(pathlib.Path(a.spec).read_text(encoding="utf-8"))
    erros, avisos = validar(spec)
    print("Avisos:" if avisos else "Avisos: nenhum.")
    for x in avisos:
        print("  " + x)
    if erros:
        print("Erros:")
        for x in erros:
            print("  " + x)
        sys.exit(1)
    pathlib.Path(a.saida).write_text(gerar_dsl(spec, horizontal=not a.sem_horizontal), encoding="utf-8")
    print("ok:", a.saida)


if __name__ == "__main__":
    main()
