#!/usr/bin/env python3
"""Testes do validador (positivo e negativos). Gera uma página real: exige docker e Chrome, senão pula.

`python3 -m unittest discover scripts/testes`
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ))
import spec_para_dsl as sd  # noqa: E402
import validar_diagrama_c4 as v  # noqa: E402

FIXTURE = AQUI / "fixtures" / "dados-mensageria.v2.json"
TEM_FERRAMENTAS = bool(shutil.which("docker") and (shutil.which("google-chrome") or shutil.which("chromium")))


def falhas(rel, camada=None):
    return [i for i in rel.itens if i["nivel"] == "FAIL" and (camada is None or i["camada"] == camada)]


@unittest.skipUnless(TEM_FERRAMENTAS, "docker e/ou Chrome ausentes")
class Validador(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.chmod(cls.tmp, 0o755)
        cls.html = pathlib.Path(cls.tmp) / "pagina.html"
        r = subprocess.run([sys.executable, str(RAIZ / "gerar_pagina_c4.py"), str(FIXTURE), "--saida", str(cls.html), "--sem-validar"],
                           capture_output=True, text=True, timeout=400)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.pagina = cls.html.read_text(encoding="utf-8")
        cls.spec = json.loads(FIXTURE.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def valida(self, pagina):
        arq = pathlib.Path(self.tmp) / "variante.html"
        arq.write_text(pagina, encoding="utf-8")
        return v.validar_tudo(FIXTURE, arq, pasta=None)

    def test_pagina_gerada_passa_em_tudo(self):
        rel = v.validar_tudo(FIXTURE, self.html, pasta=pathlib.Path(self.tmp) / "pagina.d")
        self.assertEqual(falhas(rel), [])
        self.assertTrue(any(i["camada"] == "dsl" and i["nivel"] == "PASS" for i in rel.itens))

    def test_svg_ausente_reprova(self):
        pagina = re.sub(r'<template id="svg-dynamic-h-dark">.*?</template>', "", self.pagina, flags=re.S)
        self.assertTrue(falhas(self.valida(pagina), "html"))

    def test_elemento_sumido_do_svg_reprova(self):
        pagina = self.pagina.replace("Loja&nbsp;Web", "Loja&nbsp;Wxb")
        self.assertTrue(any("Loja Web" in i["msg"] for i in falhas(self.valida(pagina), "html")))

    def test_tema_nao_aplicado_reprova(self):
        claro = re.search(r'<template id="svg-container-light">(.*?)</template>', self.pagina, re.S).group(1)
        pagina = re.sub(r'(<template id="svg-container-dark">).*?(</template>)', lambda m: m.group(1) + claro + m.group(2), self.pagina, flags=re.S)
        self.assertTrue(any("IGUAL" in i["msg"] for i in falhas(self.valida(pagina), "html")))

    def test_erro_de_javascript_reprova(self):
        pagina = self.pagina.replace("applyTheme(); mount(false);", "applyTheme(); null.boom; mount(false);")
        self.assertTrue(falhas(self.valida(pagina), "runtime"))

    def test_tabela_vazia_reprova(self):
        pagina = self.pagina.replace('$("#tbl-comp tbody").innerHTML =', '$("#tbl-comp tbody").innerHTML = ""; var _x =', 1)
        self.assertTrue(falhas(self.valida(pagina), "runtime"))

    def test_contraste_ruim_reprova(self):
        original = dict(sd.PALETA_TEMA["light"])
        try:
            sd.PALETA_TEMA["light"]["condicional"] = "#b36b00"   # a cor antiga: 4,18:1, abaixo do mínimo
            rel = v.Relatorio()
            v.checa_paleta(rel)
        finally:
            sd.PALETA_TEMA["light"].update(original)
        self.assertTrue(any("condicional" in i["msg"] for i in falhas(rel, "paleta")))

    def test_spec_invalido_reprova_na_camada_spec(self):
        ruim = pathlib.Path(self.tmp) / "ruim.json"
        s = dict(self.spec)
        s["conexoes"] = s["conexoes"] + [{"de": "web", "para": "fantasma", "rotulo": "x"}]
        ruim.write_text(json.dumps(s), encoding="utf-8")
        rel = v.validar_tudo(ruim, self.html, pasta=None)
        self.assertTrue(falhas(rel, "spec"))


@unittest.skipUnless(TEM_FERRAMENTAS, "docker e/ou Chrome ausentes")
class ValidadorContexto(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        os.chmod(cls.tmp, 0o755)
        cls.spec_path = AQUI / "fixtures" / "contexto.v2.json"
        cls.html = pathlib.Path(cls.tmp) / "ctx.html"
        r = subprocess.run([sys.executable, str(RAIZ / "gerar_pagina_c4.py"), str(cls.spec_path), "--saida", str(cls.html), "--sem-validar"],
                           capture_output=True, text=True, timeout=400)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.pagina = cls.html.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_pagina_de_contexto_passa_em_tudo(self):
        rel = v.validar_tudo(self.spec_path, self.html, pasta=pathlib.Path(self.tmp) / "ctx.d")
        self.assertEqual(falhas(rel), [])

    def test_svgs_sao_de_contexto_sem_dynamic(self):
        ids = set(re.findall(r'<template id="svg-([^"]+)"', self.pagina))
        self.assertEqual(ids, {"contexto-light", "contexto-dark", "contexto-h-light", "contexto-h-dark"})

    def test_legenda_sem_fronteira_nem_colchetes(self):
        self.assertNotIn("Fronteira do sistema em escopo", self.pagina)
        self.assertNotIn("Entre colchetes", self.pagina)

    def test_leitura_e_nota_nao_aparecem_no_contexto(self):
        spec = json.loads(self.spec_path.read_text(encoding="utf-8"))
        spec["leitura"] = [{"titulo": "Passo", "texto": "Texto do passo"}]
        spec["nota"] = "Nota de teste"
        arq = pathlib.Path(self.tmp) / "com-leitura.json"
        arq.write_text(json.dumps(spec), encoding="utf-8")
        saida = pathlib.Path(self.tmp) / "com-leitura.html"
        r = subprocess.run([sys.executable, str(RAIZ / "gerar_pagina_c4.py"), str(arq), "--saida", str(saida), "--sem-validar"], capture_output=True, text=True, timeout=400)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        html = saida.read_text(encoding="utf-8")
        self.assertNotIn("Leitura da jornada", html)
        self.assertNotIn("Nota de teste", html)

    def test_ator_omitido_nao_aparece_no_diagrama(self):
        svgs = " ".join(re.findall(r'<template id="svg-[^"]+">(.*?)</template>', self.pagina, re.S))
        self.assertNotIn("Banco&nbsp;emissor", svgs)
        self.assertIn("Transportadora", svgs)

    def test_elemento_sumido_reprova(self):
        pagina = self.pagina.replace("Transportadora", "Transportadxra")
        arq = pathlib.Path(self.tmp) / "var.html"
        arq.write_text(pagina, encoding="utf-8")
        rel = v.validar_tudo(self.spec_path, arq, pasta=None)
        self.assertTrue(falhas(rel, "html"))


if __name__ == "__main__":
    unittest.main()
