#!/usr/bin/env python3
"""Validação determinística dos diagramas C4 gerados (substitui `archify validate/deliver`).

Camadas, todas com saída PASS/FAIL/WARN e código de saída 1 se houver FAIL:
  1. spec    : validar() de spec_para_dsl (referências, limite de 12 palavras, schema, avisos).
  2. dsl     : `structurizr validate` no workspace.dsl (Docker).
  3. paleta  : contraste WCAG da paleta aplicada (texto >= 4,5:1; setas e bordas >= 3:1).
  4. html    : os SVGs embutidos existem (visões x temas), claro != escuro, todo elemento e todo rótulo
               de seta aparecem no texto de cada SVG.
  5. runtime : a página abre no Chrome headless em cada combinação visão x layout x tema, monta o SVG
               (viewBox definido), preenche as tabelas e não lança erro de JavaScript.

Uso:
    python3 scripts/validar_diagrama_c4.py spec.json pagina.html [--pasta dir-com-workspace.dsl] [--json]
"""
import argparse
import html as htmllib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import spec_para_dsl as sd  # noqa: E402

LIMIAR_TEXTO = 4.5
LIMIAR_GRAFICO = 3.0


class Relatorio:
    def __init__(self):
        self.itens = []

    def add(self, nivel, camada, msg):
        self.itens.append({"nivel": nivel, "camada": camada, "msg": msg})

    @property
    def falhou(self):
        return any(i["nivel"] == "FAIL" for i in self.itens)

    def imprime(self):
        for i in self.itens:
            print(f"[{i['nivel']}] {i['camada']}: {i['msg']}")
        n = {k: sum(1 for i in self.itens if i["nivel"] == k) for k in ("PASS", "WARN", "FAIL")}
        print(f"\nResumo: {n['PASS']} PASS, {n['WARN']} WARN, {n['FAIL']} FAIL")


# ----------------------------------------------------------------------------- 3. paleta
def luminancia(hexa):
    r, g, b = (int(hexa[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contraste(a, b):
    la, lb = luminancia(a), luminancia(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def checa_paleta(rel):
    for tag, (bg, fg) in sd.PALETA_ELEMENTOS.items():
        c = contraste(bg, fg)
        rel.add("PASS" if c >= LIMIAR_TEXTO else "FAIL", "paleta", f"elemento {tag}: texto {fg} sobre {bg} = {c:.2f}:1 (mín. {LIMIAR_TEXTO}:1)")
    for tema, pt in sd.PALETA_TEMA.items():
        for chave, limiar, rotulo in (("seta", LIMIAR_TEXTO, "texto da seta"), ("condicional", LIMIAR_TEXTO, "texto da seta condicional"),
                                      ("grupo_txt", LIMIAR_TEXTO, "texto do grupo"), ("grupo_borda", LIMIAR_GRAFICO, "borda do grupo")):
            c = contraste(pt[chave], pt["canvas"])
            rel.add("PASS" if c >= limiar else "FAIL", "paleta", f"tema {tema}, {rotulo}: {pt[chave]} sobre {pt['canvas']} = {c:.2f}:1 (mín. {limiar}:1)")


# ----------------------------------------------------------------------------- 2. dsl
def checa_dsl(rel, pasta):
    dsl = pathlib.Path(pasta) / "workspace.dsl"
    if not dsl.exists():
        rel.add("WARN", "dsl", f"{dsl} não encontrado; validação do Structurizr pulada")
        return
    if not shutil.which("docker"):
        rel.add("WARN", "dsl", "docker ausente; `structurizr validate` pulado")
        return
    r = subprocess.run(["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}", "-v", f"{pathlib.Path(pasta).resolve()}:/w", "-w", "/w",
                        "structurizr/structurizr", "validate", "-workspace", "workspace.dsl"], capture_output=True, text=True, timeout=180)
    if r.returncode == 0:
        rel.add("PASS", "dsl", "structurizr validate sem erros")
    else:
        rel.add("FAIL", "dsl", "structurizr validate: " + (r.stdout + r.stderr).strip().splitlines()[-1][:300])


# ----------------------------------------------------------------------------- 4. html
def padrao_texto(texto):
    """Regex que casa o texto mesmo quebrado em várias linhas/tspans do SVG."""
    palavras = [re.escape(htmllib.escape(p, quote=False)) for p in texto.split()]
    if not palavras:
        return re.compile("$^")
    sep = r"(?:<[^>]*>|\s|&nbsp;|&#160;|\u00a0)+"   # o viewer separa palavras com &nbsp; e quebra linhas em tspans
    return re.compile(r"(?<![\wÀ-ÿ])" + sep.join(palavras) + r"(?![\wÀ-ÿ])")


def checa_html(rel, spec, pagina_html):
    templ = {m.group(1): m.group(2) for m in re.finditer(r'<template id="svg-([^"]+)">(.*?)</template>', pagina_html, re.S)}
    tem_din = bool(spec.get("journey_id"))
    base = sd.base_view(spec)
    tem_din = tem_din and base == "container"
    esperados = [f"{v}-{t}" for v in ([base, base + "-h"] + (["dynamic", "dynamic-h"] if tem_din else [])) for t in ("light", "dark")]
    faltam = [e for e in esperados if e not in templ]
    rel.add("FAIL" if faltam else "PASS", "html", f"{len(esperados)} SVGs esperados (visões x layouts x temas)" + (f"; faltam: {faltam}" if faltam else ": todos presentes"))
    if faltam:
        return
    for chave in esperados:
        if "<svg" not in templ[chave] or "joint-layers" not in templ[chave]:
            rel.add("FAIL", "html", f"svg-{chave}: SVG sem camada de desenho")
    for v in {e.rsplit("-", 1)[0] for e in esperados}:
        igual = templ[f"{v}-light"] == templ[f"{v}-dark"]
        rel.add("FAIL" if igual else "PASS", "html", f"{v}: SVG claro {'IGUAL ao' if igual else 'difere do'} escuro (tema aplicado)")

    ef = sd.modelo_efetivo(spec)
    nomes = [x["nome"] for x in ef.get("atores", []) + ef.get("componentes", [])]
    rotulos = [sd.rotulo_exibido(c) for c in ef.get("conexoes", [])]
    # o Structurizr exibe a descrição do elemento/seta dentro do SVG; confere elementos e rótulos em cada visão
    for chave in esperados:
        svg = templ[chave]
        sem = [n for n in nomes if not padrao_texto(n).search(svg)]
        sem_r = [r for r in rotulos if not padrao_texto(r).search(svg)]
        if sem or sem_r:
            rel.add("FAIL", "html", f"svg-{chave}: ausentes — elementos {sem[:3]} rótulos {[r[:40] for r in sem_r[:3]]}")
        else:
            rel.add("PASS", "html", f"svg-{chave}: {len(nomes)} elementos e {len(rotulos)} rótulos presentes")
    return templ


# ----------------------------------------------------------------------------- 5. runtime
ESTADO_INICIAL_RE = re.compile(r'let view = "(\w+)", layout = "v", theme = "light"')


def chrome():
    for n in ("google-chrome", "chromium", "chromium-browser"):
        if shutil.which(n):
            return n
    return None


def checa_runtime(rel, spec, pagina_html):
    cr = chrome()
    if not cr:
        rel.add("WARN", "runtime", "Chrome/Chromium ausente; teste de abertura pulado")
        return
    achou = ESTADO_INICIAL_RE.search(pagina_html)
    if not achou:
        rel.add("FAIL", "runtime", "contrato do template quebrado: linha de estado inicial não encontrada")
        return
    ESTADO_INICIAL = achou.group(0)
    n_comp = len(sd.modelo_efetivo(spec).get("componentes", []))
    views = [achou.group(1)] + (["dynamic"] if spec.get("journey_id") and sd.base_view(spec) == "container" else [])
    with tempfile.TemporaryDirectory() as d:
        os.chmod(d, 0o755)
        for v in views:
            for lay in ("v", "h"):
                for tema in ("light", "dark"):
                    arq = pathlib.Path(d) / f"{v}-{lay}-{tema}.html"
                    arq.write_text(pagina_html.replace(ESTADO_INICIAL, f'let view = "{v}", layout = "{lay}", theme = "{tema}"', 1), encoding="utf-8")
                    r = subprocess.run([cr, "--headless=new", "--no-sandbox", "--disable-gpu", "--allow-file-access-from-files", "--virtual-time-budget=8000",
                                        "--window-size=1500,950", "--enable-logging=stderr", "--v=0", "--dump-dom", f"file://{arq}"],
                                       capture_output=True, text=True, timeout=120)
                    dom, log = r.stdout, r.stderr
                    rotulo = f"{v}/{lay}/{tema}"
                    erros_js = [l for l in log.splitlines() if "Uncaught" in l or ("CONSOLE" in l and "ERROR" in l.upper())]
                    vb = re.search(r'<div id="viewport"[^>]*>\s*<svg[^>]*viewBox="[^"]+"', dom)
                    linhas = len(re.findall(r"<tr>", re.search(r'<table id="tbl-comp".*?</table>', dom, re.S).group(0))) - 1 if 'id="tbl-comp"' in dom else -1
                    problemas = []
                    if erros_js:
                        problemas.append("erro de JS: " + erros_js[0][:160])
                    if not vb:
                        problemas.append("SVG não montado (sem viewBox)")
                    if linhas < n_comp:
                        problemas.append(f"tabela de componentes com {max(linhas, 0)} linhas (esperado ≥ {n_comp})")
                    if f'data-theme="{tema}"' not in dom:
                        problemas.append("tema não aplicado ao documento")
                    rel.add("FAIL" if problemas else "PASS", "runtime", f"{rotulo}: " + ("; ".join(problemas) if problemas else "abre, monta o SVG e preenche as tabelas, sem erro de JS"))


def validar_tudo(spec_path, html_path, pasta=None, nivel=None):
    rel = Relatorio()
    spec = json.loads(pathlib.Path(spec_path).read_text(encoding="utf-8"))
    if nivel:
        spec["nivel"] = nivel   # mesmo override do gerador (--nivel)
    erros, avisos = sd.validar(spec)
    for e in erros:
        rel.add("FAIL", "spec", e)
    for a in avisos:
        rel.add("WARN", "spec", a)
    if not erros:
        rel.add("PASS", "spec", "spec sem erros")
    if pasta:
        checa_dsl(rel, pasta)
    checa_paleta(rel)
    pagina = pathlib.Path(html_path).read_text(encoding="utf-8")
    if not erros:
        checa_html(rel, spec, pagina)
        checa_runtime(rel, spec, pagina)
    return rel


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("html")
    ap.add_argument("--pasta", help="pasta com workspace.dsl (padrão: <html>.d)")
    ap.add_argument("--nivel", choices=["container", "contexto", "componente"])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    pasta = a.pasta or str(pathlib.Path(a.html).with_suffix(".d"))
    rel = validar_tudo(a.spec, a.html, pasta if pathlib.Path(pasta).exists() else None, nivel=a.nivel)
    if a.json:
        print(json.dumps(rel.itens, ensure_ascii=False, indent=1))
    else:
        rel.imprime()
    sys.exit(1 if rel.falhou else 0)


if __name__ == "__main__":
    main()
