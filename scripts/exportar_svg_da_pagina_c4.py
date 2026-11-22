#!/usr/bin/env python3
"""Extrai os SVGs embutidos numa página C4 (gerar_pagina_c4.py) para arquivos standalone, claro e escuro.

Uso:
    python3 scripts/exportar_svg_da_pagina_c4.py <pagina.html> <pasta-saida> <prefixo> [--visoes container,dynamic] [--horizontal]

Grava <pasta-saida>/<prefixo>-<visao>-light.svg e -dark.svg (a página guarda um SVG por visão, orientação e tema).
No README, use <picture> com prefers-color-scheme para escolher o par. Só extrai e valida XML; não altera o desenho.
"""
import argparse
import pathlib
import re
import sys
import xml.dom.minidom
import html as htmllib

import json
import shutil
import subprocess
import tempfile

CANVAS = {"light": "#ffffff", "dark": "#111111"}   # mesmos fundos da página
OCULTA = ".structurizrNavigation,.structurizrZoom{display:none}"
PAD = 40


def achar_chrome():
    for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if shutil.which(n):
            return shutil.which(n)
    sys.exit("Chrome/Chromium não encontrado no PATH (necessário para medir o desenho).")


def mede(svgs):
    """Devolve {nome: (x, y, w, h)} com a caixa do desenho, medida no Chrome como a página mede (getBBox + folga)."""
    corpo = "".join(f'<div data-n="{n}">{svg}</div>' for n, svg in svgs.items())
    pagina = (f"<!doctype html><meta charset=utf-8><style>{OCULTA}</style>{corpo}<pre id=r></pre><script>"
              "const r={};document.querySelectorAll('div[data-n]').forEach(d=>{const b=d.querySelector('.joint-layers').getBBox();"
              "r[d.dataset.n]=[b.x,b.y,b.width,b.height]});document.getElementById('r').textContent=JSON.stringify(r)</script>")
    with tempfile.TemporaryDirectory() as t:
        f = pathlib.Path(t) / "m.html"
        f.write_text(pagina, encoding="utf-8")
        dom = subprocess.run([achar_chrome(), "--headless=new", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=10000",
                              "--dump-dom", f"file://{f}"], capture_output=True, text=True).stdout
    m = re.search(r'<pre id="r">(.*?)</pre>', dom, re.S)
    if not m:
        sys.exit("Não consegui medir o desenho no Chrome.")
    return json.loads(htmllib.unescape(m.group(1)))


def com_caixa(svg, caixa, tema):
    x, y, w, h = caixa
    x, y, w, h = x - PAD, y - PAD, w + 2 * PAD, h + 2 * PAD
    svg = svg.replace("<svg ", f'<svg viewBox="{x:.1f} {y:.1f} {w:.1f} {h:.1f}" width="{w:.0f}" height="{h:.0f}" ', 1)
    svg = re.sub(r"(<svg[^>]*>)", rf'\1<style>{OCULTA}</style><rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{CANVAS[tema]}"/>', svg, count=1)
    return svg


def extrai(pagina):
    return {m.group(1): m.group(2) for m in re.finditer(r'<template id="svg-([a-z0-9-]+-(?:light|dark))">(.*?)</template>', pagina, re.S)}


def normaliza(svg):
    svg = re.sub(r'\sstyle="width:100%;height:100%"', "", svg, count=1)   # tamanho vem do viewBox
    svg = re.sub(r"<(br|hr|img|input)([^>/]*)(?<!/)>", r"<\1\2/>", svg)
    svg = svg.replace("&nbsp;", "&#160;")
    return svg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pagina")
    ap.add_argument("saida")
    ap.add_argument("prefixo")
    ap.add_argument("--visoes", default="", help="lista separada por vírgula (padrão: todas as presentes)")
    ap.add_argument("--horizontal", action="store_true", help="usa a orientação horizontal (sufixo -h)")
    a = ap.parse_args()
    svgs = extrai(pathlib.Path(a.pagina).read_text(encoding="utf-8"))
    if not svgs:
        sys.exit("Nenhum SVG embutido encontrado.")
    visoes = {re.sub(r"-(light|dark)$", "", k) for k in svgs}
    visoes = {v for v in visoes if v.endswith("-h") == a.horizontal}
    if a.visoes:
        pedidas = {v + ("-h" if a.horizontal else "") for v in a.visoes.split(",")}
        visoes &= pedidas
    out = pathlib.Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)
    limpos = {f"{v}-{t}": normaliza(svgs[f"{v}-{t}"]) for v in visoes for t in ("light", "dark")}
    caixas = mede(limpos)
    for v in sorted(visoes):
        for tema in ("light", "dark"):
            svg = com_caixa(limpos[f"{v}-{tema}"], caixas[f"{v}-{tema}"], tema)
            xml.dom.minidom.parseString(svg)   # falha alto se não for XML válido
            nome = out / f"{a.prefixo}-{v.removesuffix('-h')}-{tema}.svg"
            nome.write_text(svg, encoding="utf-8")
            print("ok:", nome, f"({len(svg) // 1024} KB)")


if __name__ == "__main__":
    main()
