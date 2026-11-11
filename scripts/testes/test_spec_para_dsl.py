#!/usr/bin/env python3
"""Testes do tradutor spec C4 v2 -> Structurizr DSL (só stdlib; `python3 -m unittest discover scripts/testes`).

O teste de integração com o Structurizr (docker validate) é pulado se o Docker não existir.
"""
import copy
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

AQUI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
import spec_para_dsl as sd  # noqa: E402

FIXTURE = json.loads((AQUI / "fixtures" / "dados-mensageria.v2.json").read_text(encoding="utf-8"))
CONTEXTO = json.loads((AQUI / "fixtures" / "contexto.v2.json").read_text(encoding="utf-8"))


def spec(**mudancas):
    s = copy.deepcopy(FIXTURE)
    s.update(mudancas)
    return s


class Validacao(unittest.TestCase):
    def test_fixture_valida_sem_erros(self):
        erros, _ = sd.validar(spec())
        self.assertEqual(erros, [])

    def test_nivel_nao_suportado(self):
        erros, _ = sd.validar(spec(nivel="deployment"))
        self.assertTrue(any("[nivel]" in e for e in erros))

    def test_referencia_inexistente_e_erro(self):
        s = spec()
        s["conexoes"].append({"de": "web", "para": "nao_existe", "rotulo": "x", "tecnologia": "t"})
        erros, _ = sd.validar(s)
        self.assertTrue(any("FALTA-CATALOGO" in e for e in erros))

    def test_limite_de_12_palavras(self):
        s = spec()
        s["conexoes"][0]["rotulo"] = " ".join(["palavra"] * 13)
        erros, _ = sd.validar(s)
        self.assertTrue(any("limite-palavras" in e for e in erros))

    def test_nome_de_fronteira_tambem_tem_limite(self):
        s = spec()
        s["fronteiras"][0]["nome"] = " ".join(["palavra"] * 13)
        erros, _ = sd.validar(s)
        self.assertTrue(any("limite-palavras" in e and "fronteiras.nome" in e for e in erros))

    def test_condicao_fica_fora_do_limite(self):
        s = spec()
        s["conexoes"][0]["condicao"] = " ".join(["x"] * 30)
        erros, _ = sd.validar(s)
        self.assertFalse(any("limite-palavras" in e for e in erros))

    def test_avisos_tecnologia_broker_dono_banco_compartilhado(self):
        s = spec()
        s["componentes"].append({"id": "bus", "nome": "Barramento", "status": "novo", "tipo": "message bus", "tecnologia": "X"})
        s["componentes"].append({"id": "t2", "nome": "Fila solta", "status": "novo", "mensageria": "fila", "tecnologia": "X"})
        s["componentes"].append({"id": "sem", "nome": "Sem tec", "status": "novo"})
        s["conexoes"].append({"de": "ent", "para": "db_ped", "rotulo": "Lê pedido", "tecnologia": "SQL"})
        s["conexoes"] += [{"de": "web", "para": x, "rotulo": "r", "tecnologia": "t"} for x in ("bus", "t2", "sem")]
        _, av = sd.validar(s)
        texto = "\n".join(av)
        for chave in ("[BROKER-COMO-CONTAINER]", "[SEM-DONO]", "[SEM-TECNOLOGIA]", "[BANCO-COMPARTILHADO]"):
            self.assertIn(chave, texto)

    def test_orfao(self):
        s = spec()
        s["componentes"].append({"id": "solto", "nome": "Solto", "status": "novo", "tecnologia": "t"})
        _, av = sd.validar(s)
        self.assertTrue(any("[ORFAO] 'solto'" in a for a in av))

    def test_ids_duplicados(self):
        s = spec()
        s["componentes"].append({"id": "web", "nome": "Outra", "status": "novo", "tecnologia": "t"})
        erros, _ = sd.validar(s)
        self.assertTrue(any("id-duplicado" in e for e in erros))


class GeracaoDsl(unittest.TestCase):
    def test_formas_status_e_tags(self):
        dsl = sd.gerar_dsl(spec())
        self.assertIn('"Novo,Api"', dsl)
        self.assertIn('"Novo,Armazenamento"', dsl)
        self.assertIn('"Novo,Mensageria"', dsl)
        self.assertIn('"Alterado"', dsl)
        self.assertIn('"Reuso,Armazenamento"', dsl)
        self.assertIn("shape Cylinder", dsl)
        self.assertIn("shape Pipe", dsl)
        self.assertIn("shape Hexagon", dsl)

    def test_broker_nao_vira_container(self):
        dsl = sd.gerar_dsl(spec())
        self.assertNotIn('container "Kafka"', dsl)
        self.assertIn('"Kafka · tópico"', dsl)

    def test_assincrono_e_condicional(self):
        dsl = sd.gerar_dsl(spec())
        self.assertIn('"Condicional a Q7: cobra pedido"', dsl)
        self.assertIn('"Condicional"', dsl)
        relacoes_assincronas = [l for l in dsl.splitlines() if "->" in l and l.rstrip().endswith('"Assíncrono"')]
        self.assertEqual(len(relacoes_assincronas), 2)  # publica + consome

    def test_grupos_aninhados_exigem_separador(self):
        self.assertIn("structurizr.groupSeparator", sd.gerar_dsl(spec()))
        s = spec()
        for f in s["fronteiras"]:
            f.pop("pai_id", None)
        self.assertNotIn("structurizr.groupSeparator", sd.gerar_dsl(s))

    def test_views_vertical_horizontal_e_dinamica(self):
        dsl = sd.gerar_dsl(spec())
        for chave in ("container-pedido-confirmado", "container-h-pedido-confirmado", "dynamic-pedido-confirmado", "dynamic-h-pedido-confirmado"):
            self.assertIn(f'"{chave}"', dsl)
        self.assertNotIn("dynamic-h-", sd.gerar_dsl(spec(), horizontal=False))

    def test_sem_journey_nao_gera_dynamic(self):
        s = spec()
        s.pop("journey_id")
        dsl = sd.gerar_dsl(s)
        self.assertNotIn("dynamic sis", dsl)
        self.assertIn('"container-geral"', dsl)

    def test_escape_de_aspas(self):
        s = spec()
        s["conexoes"][0]["rotulo"] = 'Diz "oi"'
        self.assertIn('"Diz \\"oi\\""', sd.gerar_dsl(s))

    def test_extras_de_dado_na_descricao(self):
        dsl = sd.gerar_dsl(spec())
        self.assertIn("Retenção: 5 anos", dsl)
        self.assertIn("Sensibilidade: dado pessoal", dsl)
        self.assertIn("Dono: BC Pedidos", dsl)


class Fidelidade(unittest.TestCase):
    def test_descricao_sem_extras_preserva_ponto_final(self):
        s = spec()
        s["componentes"][1]["descricao"] = "Recebe e confirma pedidos."
        self.assertIn('"Recebe e confirma pedidos."', sd.gerar_dsl(s))

    def test_rotulo_condicional_minuscula_so_palavra_comum(self):
        f = lambda r: sd.rotulo_exibido({"rotulo": r, "condicao": "Q1"})
        self.assertEqual(f("Pede snapshot"), "Condicional a Q1: pede snapshot")
        self.assertEqual(f("EventoDeConta publicado"), "Condicional a Q1: EventoDeConta publicado")   # identificador preservado
        self.assertEqual(f("API chamada"), "Condicional a Q1: API chamada")                             # sigla preservada
        self.assertEqual(f("C6 recusa pedido"), "Condicional a Q1: C6 recusa pedido")                   # código com dígito preservado
        self.assertEqual(sd.rotulo_exibido({"rotulo": "Pede snapshot"}), "Pede snapshot")              # sem condição, intacto


class Contexto(unittest.TestCase):
    def setUp(self):
        self.spec = copy.deepcopy(CONTEXTO)
        self.ctx = sd.colapsar_contexto(self.spec)

    def test_valida_sem_erros_e_avisa_ator_fora(self):
        erros, av = sd.validar(self.spec)
        self.assertEqual(erros, [])
        self.assertTrue(any("[ATOR-FORA-DO-CONTEXTO] 'banco'" in a for a in av))
        self.assertTrue(any("[ATOR-FORA-DO-CONTEXTO] 'adm'" in a for a in av))

    def test_ator_omitido_nao_gera_aviso_duplicado_de_orfao(self):
        _, av = sd.validar(self.spec)
        self.assertFalse(any(a.startswith("[ORFAO] 'adm'") for a in av))

    def test_sem_avisos_de_container(self):
        _, av = sd.validar(self.spec)
        self.assertFalse(any(a.startswith(("[SEM-TECNOLOGIA]", "[SEM-DONO]")) for a in av))

    def test_so_atores_diretamente_ligados(self):
        self.assertEqual({a["id"] for a in self.ctx["atores"]}, {"cli", "pgto", "transp"})
        self.assertEqual(set(self.ctx["omitidos"]), {"adm", "banco"})

    def test_conexao_interna_some_e_pares_se_fundem(self):
        conx = {(c["de"], c["para"]): c for c in self.ctx["spec"]["conexoes"]}
        self.assertNotIn((sd.SIS_CTX, sd.SIS_CTX), conx)
        self.assertEqual(conx[("cli", sd.SIS_CTX)]["rotulo"], "2 interações")           # web + api
        self.assertEqual(conx[(sd.SIS_CTX, "pgto")]["rotulo"], "Cobra pedido")           # única: mantém
        self.assertEqual(conx[("transp", sd.SIS_CTX)]["rotulo"], "2 interações")
        self.assertEqual(len(conx), 4)   # cli->sis, sis->pgto, sis->transp, transp->sis (pgto->banco some: banco omitido)

    def test_assincrona_e_condicional_so_se_todas_forem(self):
        conx = {(c["de"], c["para"]): c for c in self.ctx["spec"]["conexoes"]}
        self.assertTrue(conx[("transp", sd.SIS_CTX)]["assincrona"])
        self.assertFalse(conx[("cli", sd.SIS_CTX)]["assincrona"])
        self.assertEqual(conx[(sd.SIS_CTX, "pgto")]["condicao"], "Q7")
        self.assertNotIn("condicao", conx[("cli", sd.SIS_CTX)])

    def test_status_do_sistema_misto_e_alterado(self):
        self.assertEqual(self.ctx["spec"]["componentes"][0]["status"], "alterado")
        s = copy.deepcopy(self.spec)
        for c in s["componentes"]:
            c["status"] = "novo"
        self.assertEqual(sd.colapsar_contexto(s)["spec"]["componentes"][0]["status"], "novo")

    def test_dsl_sem_containers_sem_tecnologia_e_com_view_de_contexto(self):
        dsl = sd.gerar_dsl(self.spec)
        self.assertNotIn("container ", dsl.split("views {")[0])
        self.assertIn('systemContext sis "contexto-geral"', dsl)
        self.assertIn('systemContext sis "contexto-h-geral"', dsl)
        self.assertIn('"Condicional a Q7: cobra pedido" ""', dsl)   # tecnologia vazia
        self.assertNotIn("HTTPS", dsl)
        self.assertNotIn("Banco emissor", dsl)                      # ator omitido não vira elemento
        self.assertNotIn("dynamic sis", dsl)

    def test_sem_ator_ligado_e_erro(self):
        s = copy.deepcopy(self.spec)
        s["conexoes"] = [c for c in s["conexoes"] if c["de"] in ("web", "api") and c["para"] in ("web", "api")]
        erros, _ = sd.validar(s)
        self.assertTrue(any("[contexto]" in e for e in erros))

    def test_titulo_e_chave_da_visao(self):
        t = sd.titulos_views(self.spec, sd.modelo_efetivo(self.spec))
        self.assertEqual(list(t), ["contexto"])
        self.assertTrue(t["contexto"]["title"].startswith("System Context diagram for Loja Exemplo"))
        self.assertEqual(sd.base_view(self.spec), "contexto")
        self.assertEqual(sd.base_view(FIXTURE), "container")


class Mensageria(unittest.TestCase):
    def test_modo_implicito_colapsa_fila_ponto_a_ponto(self):
        dsl = sd.gerar_dsl(spec(mensageria_modo="implicita"))
        self.assertNotIn("t_ped = container", dsl)
        self.assertIn("via Tópico PedidoConfirmado (Kafka)", dsl)

    def test_modo_implicito_preserva_topico_com_varios_consumidores(self):
        s = spec(mensageria_modo="implicita")
        s["conexoes"].append({"de": "web", "para": "t_ped", "rotulo": "Também consome", "tecnologia": "t", "acesso": "consome"})
        self.assertIn("t_ped = container", sd.gerar_dsl(s))

    def test_seta_fluxo_inverte_consome(self):
        iniciador = sd.gerar_dsl(spec())
        fluxo = sd.gerar_dsl(spec(seta_mensageria="fluxo"))
        self.assertIn('sis.ent -> sis.t_ped "Consome pedido confirmado"', iniciador)
        self.assertIn('sis.t_ped -> sis.ent "Consome pedido confirmado"', fluxo)


@unittest.skipUnless(shutil.which("docker"), "docker ausente")
class IntegracaoStructurizr(unittest.TestCase):
    def test_dsl_de_contexto_passa_no_validate(self):
        with tempfile.TemporaryDirectory() as d:
            os.chmod(d, 0o755)
            arq = pathlib.Path(d, "workspace.dsl")
            arq.write_text(sd.gerar_dsl(CONTEXTO), encoding="utf-8")
            os.chmod(arq, 0o644)
            r = subprocess.run(["docker", "run", "--rm", "-v", f"{d}:/w", "-w", "/w", "structurizr/structurizr", "validate", "-workspace", "workspace.dsl"],
                               capture_output=True, text=True, timeout=180)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_dsl_gerado_passa_no_validate(self):
        with tempfile.TemporaryDirectory() as d:
            os.chmod(d, 0o755)   # o contêiner roda como usuário não-root e precisa ler a pasta
            arq = pathlib.Path(d, "workspace.dsl")
            arq.write_text(sd.gerar_dsl(spec()), encoding="utf-8")
            os.chmod(arq, 0o644)
            r = subprocess.run(["docker", "run", "--rm", "-v", f"{d}:/w", "-w", "/w", "structurizr/structurizr", "validate", "-workspace", "workspace.dsl"],
                               capture_output=True, text=True, timeout=180)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
