#!/usr/bin/env python3
"""Spec C4 v2 (JSON) -> página HTML autocontida (SVG vetorial, tema claro/escuro, zoom, tela cheia).

Passos: (1) spec_para_dsl.py gera o workspace.dsl; (2) Structurizr (Docker) exporta o site estático;
(3) Chrome headless renderiza cada visão nos temas claro e escuro; (4) o SVG renderizado é extraído
e embutido no template skills/geracao-diagramas/templates/pagina.template.html.

Requisitos: python3, docker (imagem structurizr/structurizr), google-chrome (ou chromium).
Uso:
    python3 scripts/gerar_pagina_c4.py spec.json --saida c4-container-<x>.html [--pasta trabalho/]
A pasta de trabalho (padrão: <saida>.d/) guarda workspace.dsl e o site intermediário (descartável).
"""
import argparse
import html
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import spec_para_dsl as sd  # noqa: E402

TEMPLATE = AQUI.parent / "skills" / "geracao-diagramas" / "templates" / "pagina.template.html"


def run(cmd, **kw):
    try:
        return subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300, **kw)
    except subprocess.CalledProcessError as e:
        sys.exit(f"Falhou: {' '.join(cmd[:6])} ...\n{(e.stderr or e.stdout or '')[-1500:]}")


def achar_chrome():
    for nome in ("google-chrome", "chromium", "chromium-browser"):
        if shutil.which(nome):
            return nome
    sys.exit("Chrome/Chromium não encontrado no PATH (necessário para renderizar o SVG).")


def extrai_svg(dom):
    i = dom.index('<svg width="100%"')
    j = dom.index("</svg>", i) + 6
    svg = re.sub(r"<!--.*?-->", "", dom[i:j], flags=re.S)
    svg = re.sub(r"^<svg [^>]*>", '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" style="width:100%;height:100%">', svg, count=1)
    # o viewer aplica zoom/ajuste via transform em .joint-layers; a página usa o próprio viewBox
    svg, n = re.subn(r'(class="joint-layers")\s+transform="[^"]*"', r"\1", svg, count=1)
    if n != 1:
        sys.exit("transform do viewer não encontrado no SVG renderizado")
    return svg


def json_script(obj):
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def legenda(m):
    usados = {c["status"] for c in m["componentes"]} | {a["status"] for a in m["atores"]}
    status = [("Novo", "novo", "azul"), ("Alterado", "alt", "laranja"), ("Reuso", "reuso", "azul claro"), ("Existente", "exist", "cinza")]
    li = ""
    for nome, cls, cor in status:
        nomes = [x["nome"] for x in m["componentes"] + m["atores"] if x["status"] == nome]
        nota = f"nesta visão: {html.escape(', '.join(nomes))}" if nomes else "nenhum nesta visão"
        li += f'<li><i class="sw {cls}"></i><span><b>{nome}</b> — {cor} <small>· {nota}</small></span></li>\n'
    if m["tem_pessoa"]:
        li += '<li><i class="sw pessoa"></i><span><b>Pessoa</b> — azul escuro, forma de pessoa</span></li>\n'
    out = f"      <div>\n        <h3>Status do componente (cor)</h3>\n        <ul>\n{li}        </ul>\n      </div>\n"
    formas = {"Api": ("f-api", "API (hexágono)"), "App Web": ("f-web", "Aplicação web (janela)"), "App Móvel": ("f-mov", "Aplicação móvel"),
              "Armazenamento": ("f-armaz", "Armazenamento de dados (cilindro)"), "Mensageria": ("f-mens", "Fila, tópico ou stream (tubo)")}
    if m["formas"]:
        out += "      <div>\n        <h3>Formas</h3>\n        <ul>\n" + "".join(
            f'<li><i class="sw {formas[f][0]}"></i><span>{formas[f][1]}</span></li>\n' for f in m["formas"]) + "        </ul>\n      </div>\n"
    lim = ""
    if m["tem_grupo"]:
        lim += '<li><i class="sw bc"></i><span>Grupo tracejado = fronteira (bounded context ou serviço)</span></li>\n'
    lim += '<li><i class="sw fr"></i><span>Fronteira do sistema em escopo</span></li>\n'
    out += f"      <div>\n        <h3>Limites</h3>\n        <ul>\n{lim}        </ul>\n      </div>\n"
    setas = '<li><i class="ln"></i><span>Síncrono</span></li>\n<li><i class="ln as"></i><span>Assíncrono (inclui publica e consome mensagem)</span></li>\n'
    if any(c["cond"] for c in m["conexoes"]):
        setas += '<li><i class="ln cond"></i><span>Marrom + “Condicional” no texto: depende de hipótese em aberto</span></li>\n'
    setas += "<li><span>Entre colchetes: tecnologia ou protocolo.</span></li>\n"
    out += f"      <div>\n        <h3>Setas (unidirecionais)</h3>\n        <ul>\n{setas}        </ul>\n      </div>"
    return out


def aderencia(m):
    comps, conx = m["componentes"], m["conexoes"]
    com_tec = sum(1 for c in comps if c["tec"])
    con_tec = sum(1 for c in conx if c["tec"])
    usados = sorted({c["status"] for c in comps} | {a["status"] for a in m["atores"] if a["status"] != "Pessoa"})
    sem_tec = [a for a in m["avisos"] if a.startswith("[SEM-TECNOLOGIA]")]
    itens = [
        f"<li><b>Título com tipo e escopo:</b> sim — “{html.escape(m['titles']['container']['title'])}”.</li>",
        f"<li><b>Tecnologia nos containers:</b> {com_tec} de {len(comps)}.</li>",
        f"<li><b>Tecnologia/protocolo nas setas:</b> {con_tec} de {len(conx)}. Setas unidirecionais: sim (uma por conexão).</li>",
        f"<li><b>Status por cor:</b> usados nesta visão: {html.escape(', '.join(usados)) or 'nenhum'}. Os demais têm cor reservada.</li>",
        "<li><b>Cor não é o único sinal:</b> status e “Condicional” aparecem em texto; síncrono e assíncrono se distinguem por linha contínua e tracejada.</li>",
        "<li><b>Numeração só no Dynamic diagram:</b> sim; o Container diagram é estático.</li>"
        if "dynamic" in m["titles"] else "<li><b>Numeração:</b> sem journey_id, não há Dynamic diagram.</li>",
        "<li><b>Siglas explicadas:</b> " + (f"{len(m['glossario'])} no glossário desta página." if m["glossario"] else "o spec não traz glossário (campo glossario[]).") + "</li>",
    ]
    if sem_tec:
        itens.append(f"<li><b>Atenção:</b> {len(sem_tec)} item(ns) sem tecnologia (ver avisos); o gerador não inventa.</li>")
    return "\n".join(itens)


def glossario(m):
    if not m["glossario"]:
        return ""
    linhas = "".join(f"<tr><td><b>{html.escape(g['sigla'])}</b></td><td>{html.escape(g['significado'])}</td></tr>" for g in m["glossario"])
    return ('  <section>\n    <h2>Siglas e códigos</h2>\n    <p class="sub">A notação oficial pede que siglas sejam explicadas no próprio material.</p>\n'
            f'    <div class="scroll"><table><tbody>{linhas}</tbody></table></div>\n  </section>\n')


def avisos_html(avisos):
    if not avisos:
        return "    <p>Nenhum aviso.</p>"
    return "    <ul class=\"chk\">" + "".join(f"<li><code>{html.escape(a)}</code></li>" for a in avisos) + "</ul>"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--saida", required=True)
    ap.add_argument("--pasta")
    ap.add_argument("--sem-validar", action="store_true", help="não roda validar_diagrama_c4 ao final")
    a = ap.parse_args()

    spec_path = pathlib.Path(a.spec).resolve()
    saida = pathlib.Path(a.saida).resolve()
    pasta = pathlib.Path(a.pasta).resolve() if a.pasta else saida.with_suffix(".d")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    erros, avisos = sd.validar(spec)
    for x in avisos:
        print("aviso:", x)
    if erros:
        sys.exit("Erros no spec:\n  " + "\n  ".join(erros))
    if not shutil.which("docker"):
        sys.exit("docker não encontrado no PATH (necessário para o Structurizr).")
    chrome = achar_chrome()

    pasta.mkdir(parents=True, exist_ok=True)
    dsl = sd.gerar_dsl(spec, horizontal=True)
    (pasta / "workspace.dsl").write_text(dsl, encoding="utf-8")
    m = sd.modelo_pagina(spec, avisos)
    sl = m["slug"]

    site = pasta / "site"
    shutil.rmtree(site, ignore_errors=True)
    site.mkdir()
    run(["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{pasta}:/w", "-w", "/w",
         "structurizr/structurizr", "export", "-workspace", "workspace.dsl", "-format", "static", "-output", "site"])

    tipos = ["container", "container-h"] + (["dynamic", "dynamic-h"] if "dynamic" in m["titles"] else [])
    variantes = {}
    for v in tipos:
        for esquema in (0, 1):   # o tema real é lido de data-bs-theme (o flag só induz o viewer)
            dom = run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--allow-file-access-from-files",
                       f"--blink-settings=preferredColorScheme={esquema}", "--virtual-time-budget=20000",
                       "--window-size=1600,1200", "--dump-dom", f"file://{site}/index.html#{v}-{sl}"]).stdout
            tema = "dark" if 'data-bs-theme="dark"' in dom else "light"
            variantes[(v, tema)] = extrai_svg(dom)
    faltando = [(v, t) for v in tipos for t in ("light", "dark") if (v, t) not in variantes]
    if faltando:
        sys.exit(f"Falhou ao obter variantes: {faltando}")

    titulo = f"{m['sistema']}" + (f" · {m['journey']}" if m["journey"] else "")
    valores = {
        "TITULO_PAGINA": html.escape(f"{titulo} · C4 Container"),
        "H1": html.escape(m["journey"] or m["sistema"]),
        "CRUMB": html.escape(f"{m['sistema']} · C4 nível Container"),
        "LEGENDA": legenda(m),
        "CONTEXTO": html.escape(spec.get("subtitulo", "")) + (" " if spec.get("subtitulo") else "") +
                    "O <b>Container diagram</b> mostra a estrutura (sem ordem)" + ("; o <b>Dynamic diagram</b> mostra a mesma jornada numerada." if "dynamic" in m["titles"] else "."),
        "GLOSSARIO": glossario(m),
        "AVISOS": avisos_html(avisos),
        "ADERENCIA": aderencia(m),
        "DSL": html.escape(dsl, quote=False),
        "ORIGEM": html.escape(spec_path.name),
        "SLUG": sl,
        "SPEC_JSON": json_script({k: m[k] for k in ("atores", "componentes", "conexoes")}),
        "TITLES": json_script(m["titles"]),
        "SVGS": "\n".join(f'<template id="svg-{v}-{t}">{variantes[(v, t)]}</template>' for v in tipos for t in ("light", "dark")),
    }
    tpl = TEMPLATE.read_text(encoding="utf-8")
    out = re.sub(r"\{\{([A-Z0-9_]+)\}\}", lambda mo: valores[mo.group(1)], tpl)   # passe único: valores nunca são re-expandidos
    saida.write_text(out, encoding="utf-8")
    print("ok:", saida, f"({len(out) // 1024} KB)")
    if not a.sem_validar:
        import validar_diagrama_c4 as vd
        rel = vd.validar_tudo(spec_path, saida, pasta)
        rel.imprime()
        if rel.falhou:
            sys.exit(1)


if __name__ == "__main__":
    main()
