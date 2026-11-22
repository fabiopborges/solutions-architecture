const ELK = require(require('path').join(__dirname, 'node_modules/elkjs/lib/elk.bundled.js'));
const fs = require('fs');
const g = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const dir = process.argv[4] || 'DOWN';
const elk = new ELK();
const raiz = {
  id: 'root',
  layoutOptions: {
    'elk.algorithm': 'layered', 'elk.direction': dir,
    'elk.hierarchyHandling': 'INCLUDE_CHILDREN', 'elk.edgeRouting': 'ORTHOGONAL',
    'elk.layered.spacing.edgeEdgeBetweenLayers': '40',
    'elk.spacing.edgeEdge': '30',
    'elk.spacing.edgeNode': '40',
    'elk.layered.spacing.edgeNodeBetweenLayers': '50',
    'elk.portConstraints': 'FREE',
    'elk.spacing.portPort': '25',
    'elk.layered.spacing.nodeNodeBetweenLayers': '140',
    'elk.spacing.nodeNode': '90',
    'elk.layered.nodePlacement.bk.fixedAlignment': 'BALANCED',
    'elk.layered.considerModelOrder.strategy': 'NODES_AND_EDGES',
    'elk.randomSeed': '1', 'elk.json.edgeCoords': 'ROOT', 'elk.json.shapeCoords': 'ROOT',
    'elk.padding': '[top=50,left=50,bottom=50,right=50]'
  },
  children: [], edges: []
};
Object.assign(raiz.layoutOptions, g.opcoes || {});
const espacamentos = () => Object.fromEntries(Object.entries(raiz.layoutOptions).filter(([k]) => k.includes('spacing')));
const porId = {};
for (const b of g.boundaries) {
  porId[b.id] = { id: b.id, children: [], layoutOptions: Object.assign({}, espacamentos(), { 'elk.padding': '[top=50,left=50,bottom=110,right=50]' }, b.camada ? { 'elk.layered.layering.layerConstraint': b.camada } : {}) };
}
for (const n of g.nodes) {
  porId[n.id] = { id: n.id, width: n.w, height: n.h };
  if (n.camada) porId[n.id].layoutOptions = { 'elk.layered.layering.layerConstraint': n.camada };
}
for (const x of [...g.boundaries, ...g.nodes]) {
  const pai = x.parent ? porId[x.parent] : raiz;
  pai.children.push(porId[x.id]);
}
for (const l of g.links) {
  const e = { id: l.id, sources: [l.origem], targets: [l.destino] };
  if (!g.semRotulos && l.lw) e.labels = [{ id: l.id + '_l', text: 'x', width: l.lw, height: l.lh }];
  raiz.edges.push(e);
}
elk.layout(raiz).then(r => fs.writeFileSync(process.argv[3], JSON.stringify(r))).catch(e => { console.error(e); process.exit(1); });
