#!/usr/bin/env python3
"""Layout ELK (layered) para os SVGs do Structurizr: posiciona caixas e fronteiras e roteia as setas.

Pós-processa o SVG exportado: lê elementos, fronteiras e setas, calcula o layout com o elkjs (scripts/elk/elk_run.cjs,
via Node) e reescreve posições, tamanhos de fronteira, caminhos das setas (retas, dobras arredondadas) e rótulos.
Não decide arquitetura: a ligação entre elementos é a do SVG original.

Requisitos: node e `npm install` em scripts/elk (elkjs 0.9.3).
Pessoas ficam na primeira camada; no nível Contexto, os sistemas externos ficam na última.
"""
import json
import pathlib
import re
import shutil
import subprocess
import tempfile

import rotear_setas as r
import spec_para_dsl as sd

AQUI = pathlib.Path(__file__).resolve().parent
RUNNER = AQUI / "elk" / "elk_run.cjs"


def verifica_ambiente():
    if not shutil.which("node"):
        raise SystemExit("node não encontrado no PATH (necessário para --layout elk).")
    if not (AQUI / "elk" / "node_modules" / "elkjs").exists():
        raise SystemExit("elkjs ausente: rode `npm install` em scripts/elk.")


def _rect_abs(tag, corpo):
    t = re.search(r"translate\(([-\d.]+),\s*([-\d.]+)\)", tag)
    rc = re.search(r"<rect[^>]*>", corpo).group(0)
    return (float(t.group(1)), float(t.group(2)), float(re.search(r' width="([\d.]+)"', rc).group(1)),
            float(re.search(r' height="([\d.]+)"', rc).group(1)))


def aplicar_elk(svg, direcao="DOWN", nivel="container", raio=32):
    """Devolve o SVG com layout e rotas do ELK. direcao: DOWN (vertical) ou RIGHT (horizontal)."""
    cel = r._celulas(svg)
    nos = r._nos_do_svg(svg, cel)
    if not nos:
        return svg
    bounds = []
    for ini, fim, tipo, tag in cel:
        if tipo == "structurizr.boundary":
            x, y, w, h = _rect_abs(tag, svg[ini:fim])
            bounds.append(dict(id=re.search(r'model-id="([^"]+)"', tag).group(1), x=x, y=y, w=w, h=h))
    for b in bounds:
        pais = [p for p in bounds if p is not b and p["x"] <= b["x"] and p["y"] <= b["y"]
                and p["x"] + p["w"] >= b["x"] + b["w"] and p["y"] + p["h"] >= b["y"] + b["h"]]
        b["parent"] = min(pais, key=lambda p: p["w"] * p["h"])["id"] if pais else None
    for n in nos:
        pais = [p for p in bounds if p["x"] <= n.cx <= p["x"] + p["w"] and p["y"] <= n.cy <= p["y"] + p["h"]]
        n.parent = min(pais, key=lambda p: p["w"] * p["h"])["id"] if pais else None
    links = []
    for ini, fim, tipo, tag in cel:
        if tipo != "standard.Link":
            continue
        corpo = svg[ini:fim]
        m = re.search(r'joint-selector="line"[^>]*? d="([^"]+)"', corpo)
        if not m:
            continue
        nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", m.group(1))]
        lab = re.search(r'class="label" label-idx="0"[^>]*transform="matrix\(1,0,0,1,([-\d.]+),([-\d.]+)\)".*?<rect[^>]*? width="([\d.]+)" height="([\d.]+)"', corpo, flags=re.S)
        links.append(dict(id=re.search(r'model-id="([^"]+)"', tag).group(1), ini=ini, fim=fim,
                          origem=r._no_da_ponta(nos, (nums[0], nums[1])).id, destino=r._no_da_ponta(nos, (nums[-2], nums[-1])).id,
                          lw=float(lab.group(3)) if lab else 0, lh=float(lab.group(4)) if lab else 0))
    grau = {n.id: 0 for n in nos}
    for l in links:
        grau[l["origem"]] += 1
        grau[l["destino"]] += 1
    foco = max(nos, key=lambda n: grau[n.id]).id
    existentes = set()
    cor_existente = sd.PALETA_ELEMENTOS["Existente"][0].lower()
    for ini, fim, tipo, tag in cel:
        mid = re.search(r'model-id="([^"]+)"', tag).group(1)
        forma = re.search(r'<(?:rect|path)\b[^>]*? fill="(#[0-9a-fA-F]{6})"', svg[ini:fim])   # rect (caixa) ou path (cilindro, tubo)
        if tipo.startswith("structurizr.") and forma and forma.group(1).lower() == cor_existente:
            existentes.add(mid)
    camada = {}
    for n in nos:
        if n.pessoa:
            camada[n.id] = "FIRST"
    # sem fronteira: o nó existente vai para a última camada; com fronteira: a fronteira cujo conteúdo é só existente
    for n in nos:
        if n.id in existentes and not n.parent and not n.pessoa and n.id != foco:
            camada[n.id] = "LAST"
    if nivel == "contexto":
        for n in nos:
            if not n.pessoa and n.id != foco:
                camada[n.id] = "LAST"

    def so_existentes(bid):
        filhos = [n for n in nos if n.parent == bid]
        subs = [b["id"] for b in bounds if b["parent"] == bid]
        return bool(filhos or subs) and all(f.id in existentes for f in filhos) and all(so_existentes(x) for x in subs)
    camada_b = {b["id"]: "LAST" for b in bounds if so_existentes(b["id"])}
    ids = {b["id"]: b for b in bounds}
    ordem = []

    def add(b):
        if b in ordem:
            return
        if b["parent"]:
            add(ids[b["parent"]])
        ordem.append(b)
    for b in bounds:
        add(b)
    opcoes = {}
    if nivel == "contexto":
        opcoes = {"elk.spacing.nodeNode": "110", "elk.spacing.edgeEdge": "44", "elk.layered.spacing.edgeEdgeBetweenLayers": "44",
                  "elk.layered.spacing.nodeNodeBetweenLayers": "150"}
    g = dict(semRotulos=False, opcoes=opcoes, boundaries=[dict(id=b["id"], parent=b["parent"], camada=camada_b.get(b["id"])) for b in ordem],
             nodes=[dict(id=n.id, w=n.w, h=n.h, parent=n.parent, camada=camada.get(n.id)) for n in nos], links=links)
    with tempfile.TemporaryDirectory() as d:
        entrada, saida = pathlib.Path(d) / "g.json", pathlib.Path(d) / "out.json"
        entrada.write_text(json.dumps(g))
        subprocess.run(["node", str(RUNNER), str(entrada), str(saida), direcao], check=True)
        out = json.loads(saida.read_text())
    pos = {}

    def walk(c, ox, oy):
        for k in c.get("children", []):
            k["x"] += ox
            k["y"] += oy
            pos[k["id"]] = k
            walk(k, k["x"], k["y"])
    walk(out, 0, 0)
    edits = []
    titulos = []
    for ini, fim, tipo, tag in cel:
        mid = re.search(r'model-id="([^"]+)"', tag)
        if not mid or mid.group(1) not in pos:
            continue
        p = pos[mid.group(1)]
        corpo = svg[ini:fim]
        corpo = re.sub(r"translate\([^)]*\)", f"translate({p['x']:g},{p['y']:g})", tag, count=1) + corpo[len(tag):]
        if tipo == "structurizr.boundary":
            fundo = (re.search(r'<rect class="structurizrBoundary[^>]*? fill="([^"]+)"', corpo) or [None, "#ffffff"])[1]
            titulo = "".join(re.findall(r'<text class="structurizr(?:Name|MetaData)".*?</text>', corpo, flags=re.S))
            corpo = re.sub(r'<text class="structurizr(?:Name|MetaData)".*?</text>', "", corpo, flags=re.S)
            for cls, off in (("structurizrName", 39), ("structurizrMetaData", 15)):   # y relativo à altura nova
                titulo = re.sub(rf'(class="{cls}"[^>]*? )y="[\d.]+"', lambda m: f"{m.group(1)}y=\"{p['height'] - off:g}\"", titulo, count=1)
            titulos.append(f'<g transform="translate({p["x"]:g},{p["y"]:g})" pointer-events="none" stroke="{fundo}" stroke-width="10" '
                           f'stroke-linejoin="round" paint-order="stroke">{titulo}</g>')
            corpo = re.sub(r'(<rect class="structurizrBoundary[^>]*? )width="[\d.]+" height="[\d.]+"',
                           lambda m: f"{m.group(1)}width=\"{p['width']:g}\" height=\"{p['height']:g}\"", corpo, count=1)
        edits.append((ini, fim, corpo))
    maxy = max(p["y"] + p["height"] for p in pos.values())
    pai = {n.id: n.parent for n in nos}
    pai.update({b["id"]: b["parent"] for b in bounds})

    def ancestrais(i):
        c = []
        while pai.get(i):
            i = pai[i]
            c.append(i)
        return c
    por_link = {e["id"]: e for e in out["edges"]}
    rotas = {}
    for l in links:
        e = por_link.get(l["id"])
        if not (e and e.get("sections")):
            continue
        a, b = ancestrais(l["origem"]), set(ancestrais(l["destino"]))
        lca = next((x for x in a if x in b), None)
        ox, oy = (pos[lca]["x"], pos[lca]["y"]) if lca else (0, 0)
        s = e["sections"][0]
        pts = [(s["startPoint"]["x"] + ox, s["startPoint"]["y"] + oy)] + [(q["x"] + ox, q["y"] + oy) for q in s.get("bendPoints", [])] \
            + [(s["endPoint"]["x"] + ox, s["endPoint"]["y"] + oy)]
        rotas[l["id"]] = r._simplifica(pts)
    for n in nos:   # posições novas, para o rótulo evitar as caixas
        n.x, n.y = pos[n.id]["x"], pos[n.id]["y"]
    segs = {k: list(zip(v, v[1:])) for k, v in rotas.items()}
    usados = []
    for l in sorted(links, key=lambda l: len(rotas.get(l["id"], []))):
        pts = rotas.get(l["id"])
        if not pts:
            continue
        corpo = svg[l["ini"]:l["fim"]]
        corpo = re.sub(r'(joint-selector="(?:line|wrapper)"[^>]*? d=")[^"]+(")',
                       lambda m: m.group(1) + r.caminho_arredondado(pts, raio) + m.group(2), corpo)
        if l["lw"]:
            outros = [sg for k, v in segs.items() if k != l["id"] for sg in v]
            (cx, cy), caixa = r.posicao_rotulo(pts, l["lw"], l["lh"], nos, outros, usados)
            usados.append(caixa)
            corpo = re.sub(r'(class="label" label-idx="0"[^>]*transform=")matrix\(1,0,0,1,[-\d.]+,[-\d.]+\)(")',
                           lambda m: f"{m.group(1)}matrix(1,0,0,1,{cx:g},{cy:g}){m.group(2)}", corpo, count=1)
        edits.append((l["ini"], l["fim"], corpo))
    for ini, fim, tipo, tag in cel:
        if "diagram" in tipo:
            dy = {"diagramTitle": 0, "diagramDescription": 46, "diagramMetadata": 80}[tipo.split(".")[1]]
            edits.append((ini, fim, re.sub(r"translate\([^)]*\)", f"translate(20,{maxy + 60 + dy:g})", svg[ini:fim], count=1)))
    if titulos:   # títulos das fronteiras acima das setas (os originais ficam sob elas)
        fim_total = max(c[1] for c in cel)
        edits.append((fim_total, fim_total, "".join(titulos)))
    for ini, fim, corpo in sorted(edits, reverse=True):
        svg = svg[:ini] + corpo + svg[fim:]
    return svg
