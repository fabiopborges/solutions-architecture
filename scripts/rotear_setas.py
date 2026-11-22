#!/usr/bin/env python3
"""Roteador de setas dos diagramas C4: segmentos retos, dobras arredondadas, sem sobreposição.

Pós-processa o SVG exportado pelo Structurizr (JointJS). Lê as caixas dos elementos e as pontas de cada seta,
escolhe o lado de saída e de entrada, espalha as portas de um mesmo lado, e roteia cada seta por um grafo
ortogonal (Dijkstra com custo por dobra, sobreposição e cruzamento). Depois reposiciona o rótulo.

Não decide arquitetura: só muda a geometria das setas. A ligação entre elementos é a do SVG original.
"""
import heapq
import itertools
import re

MARGEM = 26          # folga ao redor das caixas
PASSO = 36           # distância entre corredores paralelos
STUB = 44            # trecho reto mínimo ao sair/entrar numa caixa
DOBRA = 160          # custo de cada dobra
SOBREPOE = 3000      # custo por unidade de sobreposição com outra seta
CRUZA = 260          # custo por cruzamento
EXCLUIR = ("diagram", "boundary", "key", "group")


def _lados():
    return {"N": (0, -1), "S": (0, 1), "W": (-1, 0), "E": (1, 0)}


LADOS = _lados()


class No:
    def __init__(self, nid, x, y, w, h, pessoa=False, hy=0):
        self.id, self.x, self.y, self.w, self.h, self.pessoa, self.hy = nid, x, y, w, h, pessoa, hy

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    def caixa(self, m=0):
        return (self.x - m, self.y - m, self.x + self.w + m, self.y + self.h + m)

    def faixa(self, lado):
        """Intervalo (a, b) por onde as portas daquele lado podem ser espalhadas, e a coordenada fixa."""
        if lado in "NS":
            if self.pessoa and lado == "N":
                return (self.x + self.w / 2 - 40, self.x + self.w / 2 + 40), self.y
            return (self.x + 40, self.x + self.w - 40), self.y if lado == "N" else self.y + self.h
        topo = self.y + (self.hy if self.pessoa else 0)
        return (topo + 40, self.y + self.h - 40), self.x if lado == "W" else self.x + self.w


def _cruza_caixa(p, q, caixa):
    x0, y0, x1, y1 = caixa
    if p[0] == q[0]:
        return x0 < p[0] < x1 and min(p[1], q[1]) < y1 and max(p[1], q[1]) > y0
    return y0 < p[1] < y1 and min(p[0], q[0]) < x1 and max(p[0], q[0]) > x0


def _sobreposicao(p, q, seg):
    """Custo de andar de p a q (axial) dado um segmento já usado."""
    a, b = seg
    if p[0] == q[0] == a[0] == b[0] or (p[0] == q[0] and a[0] == b[0] and abs(p[0] - a[0]) < 14):
        lo = max(min(p[1], q[1]), min(a[1], b[1]))
        hi = min(max(p[1], q[1]), max(a[1], b[1]))
        return max(0, hi - lo) * SOBREPOE / 100 * (3 if p[0] == a[0] else 1)
    if (p[1] == q[1] and a[1] == b[1]) and abs(p[1] - a[1]) < 14:
        lo = max(min(p[0], q[0]), min(a[0], b[0]))
        hi = min(max(p[0], q[0]), max(a[0], b[0]))
        return max(0, hi - lo) * SOBREPOE / 100 * (3 if p[1] == a[1] else 1)
    if p[0] == q[0] and a[1] == b[1]:   # vertical x horizontal
        if min(a[0], b[0]) < p[0] < max(a[0], b[0]) and min(p[1], q[1]) < a[1] < max(p[1], q[1]):
            return CRUZA
    if p[1] == q[1] and a[0] == b[0]:
        if min(a[1], b[1]) < p[1] < max(a[1], b[1]) and min(p[0], q[0]) < a[0] < max(p[0], q[0]):
            return CRUZA
    return 0


def _grade(nos, extras):
    xs, ys = set(), set()
    for n in nos:
        for (a, b, eixo) in ((n.x - MARGEM, n.x + n.w + MARGEM, xs), (n.y - MARGEM, n.y + n.h + MARGEM, ys)):
            eixo.update((a, b))
    for x, y in extras:
        xs.add(x)
        ys.add(y)
    for eixo in (xs, ys):
        ordenado = sorted(eixo)
        novos = set()
        for a, b in zip(ordenado, ordenado[1:]):
            k = 1
            while a + k * PASSO < b - PASSO / 2 and k < 18:
                novos.add(a + k * PASSO)
                k += 1
        lo, hi = ordenado[0], ordenado[-1]
        for k in range(1, 6):
            novos.update((lo - k * PASSO, hi + k * PASSO))
        eixo.update(novos)
    return sorted(xs), sorted(ys)


def _dijkstra(xs, ys, ini, dir_ini, fim, dir_fim, caixas, usados):
    ix = {x: i for i, x in enumerate(xs)}
    iy = {y: i for i, y in enumerate(ys)}
    d0 = LADOS_LISTA.index(dir_ini)
    inicio = (ix[ini[0]], iy[ini[1]], d0)
    alvo = (ix[fim[0]], iy[fim[1]])
    dist = {inicio: 0}
    pai = {}
    fila = [(0, inicio)]
    while fila:
        c, est = heapq.heappop(fila)
        if dist.get(est, 1e18) < c:
            continue
        i, j, d = est
        if (i, j) == alvo and LADOS_LISTA[d] == dir_fim:
            cam = []
            while est in pai:
                cam.append((xs[est[0]], ys[est[1]]))
                est = pai[est]
            cam.append((xs[est[0]], ys[est[1]]))
            return c, cam[::-1]
        for nd, (dx, dy) in enumerate(LADOS_LISTA):
            if (dx, dy) == (-LADOS_LISTA[d][0], -LADOS_LISTA[d][1]):
                continue
            ni, nj = i + dx, j + dy
            if not (0 <= ni < len(xs) and 0 <= nj < len(ys)):
                continue
            p, q = (xs[i], ys[j]), (xs[ni], ys[nj])
            if any(_cruza_caixa(p, q, cx) for cx in caixas):
                continue
            custo = c + abs(q[0] - p[0]) + abs(q[1] - p[1]) + (DOBRA if nd != d else 0)
            custo += sum(_sobreposicao(p, q, s) for s in usados)
            nova = (ni, nj, nd)
            if custo < dist.get(nova, 1e18):
                dist[nova] = custo
                pai[nova] = est
                heapq.heappush(fila, (custo, nova))
    return None, None


LADOS_LISTA = [(0, -1), (0, 1), (-1, 0), (1, 0)]
NOME_DIR = {(0, -1): "N", (0, 1): "S", (-1, 0): "W", (1, 0): "E"}


def _porta(no, lado, k, n):
    (a, b), fixo = no.faixa(lado)
    pos = a + (b - a) * (k + 1) / (n + 1)
    return (pos, fixo) if lado in "NS" else (fixo, pos)


def _ponta(no, lado, porta):
    dx, dy = LADOS[lado]
    return (porta[0] + dx * STUB, porta[1] + dy * STUB)


def _simplifica(pts):
    pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
    sai = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = sai[-1], pts[i], pts[i + 1]
        if (a[0] == b[0] == c[0]) or (a[1] == b[1] == c[1]):
            continue
        sai.append(b)
    sai.append(pts[-1])
    return sai


def rotear(nos, ligacoes, lados=None):
    """nos: lista de No. ligacoes: lista de dict(id, origem, destino) (ids de No).
    Devolve {id: [pontos]} com cada seta como polilinha ortogonal."""
    por_id = {n.id: n for n in nos}
    caixas = {n.id: n.caixa(MARGEM) for n in nos}

    def custo_sem_penalidade(l, lo, ld):
        a, b = por_id[l["origem"]], por_id[l["destino"]]
        pa, pb = _porta(a, lo, 0, 1), _porta(b, ld, 0, 1)
        ia, ib = _ponta(a, lo, pa), _ponta(b, ld, pb)
        xs, ys = _grade(nos, [ia, ib])
        c, cam = _dijkstra(xs, ys, ia, LADOS[lo], ib, tuple(-v for v in LADOS[ld]), list(caixas.values()), [])
        return c

    # fase 1: escolhe os lados de cada seta (rota isolada, portas no centro)
    escolha = {}
    for l in ligacoes:
        melhor = None
        if lados and l["id"] in lados:   # lados impostos pelo chamador (ex.: layout em raias)
            escolha[l["id"]] = lados[l["id"]]
            continue
        a, b = por_id[l["origem"]], por_id[l["destino"]]
        dx, dy = b.cx - a.cx, b.cy - a.cy
        def aponta(lado, vx, vy):   # o lado não pode apontar contra o destino
            ux, uy = LADOS[lado]
            return ux * vx + uy * vy >= 0
        for lo, ld in itertools.product("NSWE", repeat=2):
            if not (aponta(lo, dx, dy) and aponta(ld, -dx, -dy)):
                continue
            c = custo_sem_penalidade(l, lo, ld)
            if c is not None and (melhor is None or c < melhor[0]):
                melhor = (c, lo, ld)
        escolha[l["id"]] = melhor[1:]

    # fase 2: espalha as portas de cada (caixa, lado), ordenadas pela posição do outro extremo
    grupos = {}
    for l in ligacoes:
        lo, ld = escolha[l["id"]]
        grupos.setdefault((l["origem"], lo), []).append((l, "o"))
        grupos.setdefault((l["destino"], ld), []).append((l, "d"))
    portas = {}
    for (nid, lado), itens in grupos.items():
        def chave(it):
            l, papel = it
            outro = por_id[l["destino"] if papel == "o" else l["origem"]]
            return outro.cx if lado in "NS" else outro.cy
        itens.sort(key=chave)
        for k, (l, papel) in enumerate(itens):
            portas[(l["id"], papel)] = _porta(por_id[nid], lado, k, len(itens))

    # fase 3: roteia com penalidade de sobreposição/cruzamento (mais curtas primeiro)
    def manhattan(l):
        p, q = portas[(l["id"], "o")], portas[(l["id"], "d")]
        return abs(p[0] - q[0]) + abs(p[1] - q[1])

    usados, rotas = [], {}
    for l in sorted(ligacoes, key=manhattan):
        lo, ld = escolha[l["id"]]
        po, pd = portas[(l["id"], "o")], portas[(l["id"], "d")]
        io, idd = _ponta(por_id[l["origem"]], lo, po), _ponta(por_id[l["destino"]], ld, pd)
        xs, ys = _grade(nos, [io, idd])
        c, cam = _dijkstra(xs, ys, io, LADOS[lo], idd, tuple(-v for v in LADOS[ld]), list(caixas.values()), usados)
        if cam is None:
            rotas[l["id"]] = None
            continue
        pts = _simplifica([po] + cam + [pd])
        rotas[l["id"]] = pts
        usados += list(zip(pts, pts[1:]))
    return rotas


def caminho_arredondado(pts, raio):
    """Polilinha ortogonal -> atributo d com cantos em arco circular de raio limitado pelos segmentos vizinhos."""
    if len(pts) < 2:
        return ""
    d = [f"M {pts[0][0]:g} {pts[0][1]:g}"]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        l1 = abs(b[0] - a[0]) + abs(b[1] - a[1])
        l2 = abs(c[0] - b[0]) + abs(c[1] - b[1])
        r = min(raio, l1 / 2, l2 / 2)
        u1 = ((b[0] - a[0]) / l1, (b[1] - a[1]) / l1)
        u2 = ((c[0] - b[0]) / l2, (c[1] - b[1]) / l2)
        p1 = (b[0] - u1[0] * r, b[1] - u1[1] * r)
        p2 = (b[0] + u2[0] * r, b[1] + u2[1] * r)
        giro = 1 if (u1[0] * u2[1] - u1[1] * u2[0]) > 0 else 0
        d.append(f"L {p1[0]:g} {p1[1]:g} A {r:g} {r:g} 0 0 {giro} {p2[0]:g} {p2[1]:g}")
    d.append(f"L {pts[-1][0]:g} {pts[-1][1]:g}")
    return " ".join(d)


def posicao_rotulo(pts, larg, alt, nos, outros_segs, rotulos_usados):
    """Amostra pontos ao longo da seta e escolhe onde o rótulo menos atrapalha (caixas, outros rótulos, outras setas)."""
    melhor = None
    for a, b in zip(pts, pts[1:]):
        comp = abs(b[0] - a[0]) + abs(b[1] - a[1])
        if comp < 70:
            continue
        passos = max(1, int((comp - 2 * STUB) // 30))
        for k in range(passos + 1):
            t = 0.5 if passos == 0 else (STUB + (comp - 2 * STUB) * k / passos) / comp if comp > 2 * STUB else 0.5
            bx, by = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            vertical = a[0] == b[0]
            deslocs = [(0, 0, 0)] + ([(-(larg / 2 + 12), 0, 150), (larg / 2 + 12, 0, 150)] if vertical else [(0, -(alt / 2 + 10), 150), (0, alt / 2 + 10, 150)])
            for dx, dy, extra in deslocs:
                cx, cy = bx + dx, by + dy
                r = (cx - larg / 2 - 6, cy - alt / 2 - 4, cx + larg / 2 + 6, cy + alt / 2 + 4)
                pena = extra + sum(_area(r, n.caixa(2)) * 120 for n in nos)
                pena += sum(_area(r, u) * 40 for u in rotulos_usados)
                pena += sum(6000 for s in outros_segs if _cruza_caixa(s[0], s[1], r))
                pena += sum(2500 for s in zip(pts, pts[1:]) if (s != (a, b)) and _cruza_caixa(s[0], s[1], r))
                pena += abs(t - 0.5) * comp * 0.3          # prefere o meio do segmento
                pena -= min(comp, 600) * 0.2               # prefere segmentos longos
                if melhor is None or pena < melhor[0]:
                    melhor = (pena, (cx, cy), r)
    if melhor is None:
        a, b = max(zip(pts, pts[1:]), key=lambda s: abs(s[1][0] - s[0][0]) + abs(s[1][1] - s[0][1]))
        cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        return (cx, cy), (cx - larg / 2, cy - alt / 2, cx + larg / 2, cy + alt / 2)
    return melhor[1], melhor[2]


def _area(r, s):
    w = min(r[2], s[2]) - max(r[0], s[0])
    h = min(r[3], s[3]) - max(r[1], s[1])
    return max(0, w) * max(0, h) / 100


# ---------- SVG ----------

def _celulas(svg):
    """Gera (inicio, fim, tag_abertura) de cada <g model-id=...> de primeiro nível de célula."""
    out = []
    for m in re.finditer(r'<g model-id="[^"]+" data-type="([^"]+)"[^>]*>', svg):
        prof, i = 1, m.end()
        while prof:
            a = svg.find("<g", i)
            b = svg.find("</g>", i)
            if a != -1 and a < b and svg[a + 2] in " >":
                prof += 1
                i = a + 2
            else:
                prof -= 1
                i = b + 4
        out.append((m.start(), i, m.group(1), m.group(0)))
    return out


def _nos_do_svg(svg, celulas):
    nos = []
    for ini, fim, tipo, tag in celulas:
        if not tipo.startswith("structurizr.") or any(e in tipo for e in EXCLUIR):
            continue
        t = re.search(r'transform="translate\(([-\d.]+),\s*([-\d.]+)\)"', tag)
        if not t:
            continue
        x, y = float(t.group(1)), float(t.group(2))
        w = h = 0
        hy = 0
        for r in re.finditer(r"<rect\b[^>]*>", svg[ini:fim]):
            at = dict(re.findall(r'([\w-]+)="([^"]*)"', r.group(0)))
            if "width" not in at or "height" not in at:
                continue
            rx, ry = float(at.get("x", 0)), float(at.get("y", 0))
            w = max(w, rx + float(at["width"]))
            h = max(h, ry + float(at["height"]))
            if "structurizrPersonBody" in at.get("class", ""):
                hy = ry
        if w and h:
            nos.append(No(re.search(r'model-id="([^"]+)"', tag).group(1), x, y, w, h, tipo.endswith("person"), hy))
    return nos


def _no_da_ponta(nos, p):
    def dist(n):
        x0, y0, x1, y1 = n.caixa()
        dx = max(x0 - p[0], 0, p[0] - x1)
        dy = max(y0 - p[1], 0, p[1] - y1)
        if dx == 0 and dy == 0:
            return min(p[0] - x0, x1 - p[0], p[1] - y0, y1 - p[1])
        return (dx * dx + dy * dy) ** 0.5
    return min(nos, key=dist)


def rotear_svg(svg, raio=32):
    """Reescreve as setas do SVG do Structurizr. Devolve (svg, avisos)."""
    celulas = _celulas(svg)
    nos = _nos_do_svg(svg, celulas)
    avisos = []
    if not nos:
        return svg, ["[SETAS] nenhum elemento reconhecido; setas mantidas como exportadas"]
    links = []
    for ini, fim, tipo, tag in celulas:
        if tipo != "standard.Link":
            continue
        corpo = svg[ini:fim]
        m = re.search(r'joint-selector="line"[^>]*? d="([^"]+)"', corpo)
        if not m:
            continue
        nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", m.group(1))]
        s, e = (nums[0], nums[1]), (nums[-2], nums[-1])
        lab = re.search(r'class="label" label-idx="0"[^>]*transform="matrix\(1,0,0,1,([-\d.]+),([-\d.]+)\)".*?<rect[^>]*? width="([\d.]+)" height="([\d.]+)"', corpo, flags=re.S)
        links.append({"id": re.search(r'model-id="([^"]+)"', tag).group(1), "ini": ini, "fim": fim,
                      "origem": _no_da_ponta(nos, s).id, "destino": _no_da_ponta(nos, e).id,
                      "larg": float(lab.group(3)) if lab else 0, "alt": float(lab.group(4)) if lab else 0})
    rotas = rotear(nos, links)
    por_id = {l["id"]: l for l in links}
    rot_usados, segs_todos = [], {k: list(zip(v, v[1:])) for k, v in rotas.items() if v}
    novos = []
    for l in links:
        pts = rotas.get(l["id"])
        corpo = svg[l["ini"]:l["fim"]]
        if not pts:
            avisos.append(f"[SETAS] sem rota para uma seta ({l['origem'][:8]} -> {l['destino'][:8]}); mantida como exportada")
            continue
        d = caminho_arredondado(pts, raio)
        corpo = re.sub(r'(joint-selector="(?:line|wrapper)"[^>]*? d=")[^"]+(")', lambda m: m.group(1) + d + m.group(2), corpo)
        if l["larg"]:
            outros = [s for k, v in segs_todos.items() if k != l["id"] for s in v]
            (cx, cy), caixa = posicao_rotulo(pts, l["larg"], l["alt"], nos, outros, rot_usados)
            rot_usados.append(caixa)
            corpo = re.sub(r'(class="label" label-idx="0"[^>]*transform=")matrix\(1,0,0,1,[-\d.]+,[-\d.]+\)(")',
                           lambda m: f'{m.group(1)}matrix(1,0,0,1,{cx:g},{cy:g}){m.group(2)}', corpo, count=1)
        novos.append((l["ini"], l["fim"], corpo))
    for ini, fim, corpo in sorted(novos, reverse=True):
        svg = svg[:ini] + corpo + svg[fim:]
    return svg, avisos
