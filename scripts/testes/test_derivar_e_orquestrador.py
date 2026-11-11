#!/usr/bin/env python3
"""Testes de derivar_c4.py --formato v2 e do orquestrador gerar_diagramas_demanda.py.

A execução de ponta a ponta (gera as páginas) exige docker e Chrome; sem eles, é pulada.
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(RAIZ))
import spec_para_dsl as sd  # noqa: E402

DEMANDA = AQUI / "fixtures" / "demanda-exemplo"
TEM_FERRAMENTAS = bool(shutil.which("docker") and (shutil.which("google-chrome") or shutil.which("chromium")))


def py(script, *args, timeout=900):
    r = subprocess.run([sys.executable, str(RAIZ / script), *map(str, args)], capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout + r.stderr


def copia_demanda(destino):
    shutil.copytree(DEMANDA, pathlib.Path(destino) / "demanda-exemplo")
    return pathlib.Path(destino) / "demanda-exemplo"


class DerivacaoV2(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dem = copia_demanda(self.tmp)
        self.dd = self.dem / "diagramas"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def deriva(self):
        return py("derivar_c4.py", self.dd / "catalogo-componentes.json", *sorted(self.dd.glob("sequencia-*_spec.json")),
                  "--saida-dir", self.dd, "--formato", "v2")

    def carrega(self, nome):
        return json.loads((self.dd / nome).read_text(encoding="utf-8"))

    def test_gera_specs_v2_sem_contexto(self):
        codigo, _ = self.deriva()
        self.assertEqual(codigo, 0)
        self.assertTrue((self.dd / "c4-container.json").exists())
        self.assertTrue((self.dd / "c4-container-jornada-pedido-confirmado.json").exists())
        self.assertFalse((self.dd / "c4-contexto.json").exists())   # o Contexto sai do gerador (--nivel contexto)

    def test_ignora_retorno_e_self_e_deduplica_entre_jornadas(self):
        self.deriva()
        geral = self.carrega("c4-container.json")
        pares = [(c["de"], c["para"], c.get("acesso")) for c in geral["conexoes"]]
        self.assertEqual(len(pares), 7)
        self.assertIn(("api_ped", "db_ped", "le"), pares)       # lê e grava não se fundem
        self.assertIn(("api_ped", "db_ped", "grava"), pares)
        web_api = [c for c in geral["conexoes"] if (c["de"], c["para"]) == ("web", "api_ped")][0]
        self.assertEqual(sorted(web_api["journey_id"]), ["consulta-pedido", "pedido-confirmado"])

    def test_tecnologia_vem_da_mensagem_ou_do_protocolo(self):
        self.deriva()
        j = {(c["de"], c["para"]): c for c in self.carrega("c4-container-jornada-pedido-confirmado.json")["conexoes"]}
        self.assertEqual(j[("cli", "web")]["tecnologia"], "HTTPS")             # protocolo
        self.assertEqual(j[("api_ped", "t_ped")]["tecnologia"], "Kafka producer")  # tecnologia
        self.assertEqual(j[("api_ped", "pgto")]["condicao"], "Q7")

    def test_campos_de_topo_do_catalogo_e_da_sequencia(self):
        self.deriva()
        s = self.carrega("c4-container-jornada-pedido-confirmado.json")
        self.assertEqual(s["sistema"]["nome"], "Loja Exemplo")
        self.assertEqual(s["titulo_pagina"], "Pedido confirmado")
        self.assertEqual(len(s["leitura"]), 2)
        self.assertIn("Q7", s["nota"])
        self.assertEqual(s["suposicoes"][0]["titulo"], "Pagamento")
        geral = self.carrega("c4-container.json")
        self.assertNotIn("leitura", geral)          # narrativa é da jornada, não da visão geral
        self.assertIn("suposicoes", geral)

    def test_ordem_do_catalogo_e_orfao_reportado(self):
        _, saida = self.deriva()
        geral = self.carrega("c4-container.json")
        self.assertEqual([c["id"] for c in geral["componentes"]], ["web", "api_ped", "db_ped", "t_ped", "ent"])
        self.assertIn("[ORFAO] componente 'legado_orfao'", saida)
        self.assertNotIn("legado_orfao", json.dumps(geral))

    def test_falta_catalogo_nao_importa_e_gerador_recusa(self):
        seq = self.dd / "sequencia-consulta-pedido_spec.json"
        d = json.loads(seq.read_text(encoding="utf-8"))
        d["mensagens"].append({"ordem": 4, "de": "api_ped", "para": "fantasma", "rotulo": "Chama serviço", "protocolo": "HTTPS"})
        seq.write_text(json.dumps(d), encoding="utf-8")
        _, saida = self.deriva()
        self.assertIn("[FALTA-CATALOGO] 'fantasma'", saida)
        spec = self.carrega("c4-container.json")
        self.assertNotIn("fantasma", [c["id"] for c in spec["componentes"] + spec["atores"]])
        self.assertTrue(any(c["para"] == "fantasma" for c in spec["conexoes"]))   # a conexão fica: o gerador recusa
        erros, _ = sd.validar(spec)      # o gerador recusa a conexão até o catálogo/sequência ser corrigido
        self.assertTrue(any("FALTA-CATALOGO" in e for e in erros))

    def test_dono_fora_da_visao_e_omitido_com_aviso(self):
        cat = self.dd / "catalogo-componentes.json"
        d = json.loads(cat.read_text(encoding="utf-8"))
        for c in d["componentes"]:
            if c["id"] == "t_ped":
                c["dono_id"] = "legado_orfao"      # componente que não entra na visão
        cat.write_text(json.dumps(d), encoding="utf-8")
        _, saida = self.deriva()
        self.assertIn("[DONO-FORA-DA-VISAO]", saida)
        t = [c for c in self.carrega("c4-container.json")["componentes"] if c["id"] == "t_ped"][0]
        self.assertNotIn("dono_id", t)

    def test_saida_e_deterministica(self):
        self.deriva()
        a = (self.dd / "c4-container.json").read_text(encoding="utf-8")
        self.deriva()
        self.assertEqual(a, (self.dd / "c4-container.json").read_text(encoding="utf-8"))

    def test_formato_padrao_continua_v1(self):
        codigo, _ = py("derivar_c4.py", self.dd / "catalogo-componentes.json", *sorted(self.dd.glob("sequencia-*_spec.json")), "--saida-dir", self.dd)
        self.assertEqual(codigo, 0)
        self.assertTrue((self.dd / "c4-contexto.json").exists())      # comportamento antigo preservado


class Orquestrador(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dem = copia_demanda(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_recusa_demanda_legada(self):
        (self.dem / "diagramas" / "c4-container.architecture.json").write_text("{}", encoding="utf-8")
        codigo, saida = py("gerar_diagramas_demanda.py", self.dem)
        self.assertEqual(codigo, 1)
        self.assertIn("legada", saida)
        self.assertFalse((self.dem / "diagramas" / "c4-container.html").exists())

    def test_exige_catalogo(self):
        (self.dem / "diagramas" / "catalogo-componentes.json").unlink()
        codigo, saida = py("gerar_diagramas_demanda.py", self.dem)
        self.assertEqual(codigo, 1)
        self.assertIn("catalogo-componentes.json", saida)

    def test_sem_sequencia_exige_container_autorado(self):
        for p in (self.dem / "diagramas").glob("sequencia-*"):
            p.unlink()
        codigo, saida = py("gerar_diagramas_demanda.py", self.dem)
        self.assertEqual(codigo, 1)
        self.assertIn("c4-container.json", saida)

    @unittest.skipUnless(TEM_FERRAMENTAS, "docker e/ou Chrome ausentes")
    def test_ponta_a_ponta(self):
        codigo, saida = py("gerar_diagramas_demanda.py", self.dem)
        self.assertEqual(codigo, 0, saida[-2500:])
        dd = self.dem / "diagramas"
        for nome in ("c4-container.html", "c4-container-jornada-pedido-confirmado.html", "c4-container-jornada-consulta-pedido.html", "c4-contexto.html"):
            self.assertTrue((dd / nome).exists(), nome)
        rel = (dd / "RELATORIO-GERACAO.md").read_text(encoding="utf-8")
        self.assertIn("[ORFAO] componente 'legado_orfao'", rel)
        self.assertIn("4 de 4 diagramas gerados", rel)
        self.assertTrue((dd / "_trabalho" / "contexto" / "workspace.dsl").exists())
        self.assertFalse((dd / "_trabalho" / "contexto" / "site").exists())      # intermediário apagado
        pagina = (dd / "c4-container-jornada-pedido-confirmado.html").read_text(encoding="utf-8")
        self.assertIn("Suposições e trade-offs", pagina)
        self.assertIn("<code>PedidoConfirmado</code>", pagina)
        self.assertIn("Dynamic diagram", pagina)
        ctx = (dd / "c4-contexto.html").read_text(encoding="utf-8")
        self.assertIn("System Context diagram", ctx)
        self.assertIn("Suposições e trade-offs", ctx)       # suposições valem em todos os níveis
        self.assertNotIn("Leitura da jornada", ctx)


if __name__ == "__main__":
    unittest.main()
