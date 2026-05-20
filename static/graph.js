/* ── Query Map ── */
const QUERY_MAP = {
  'dept-coverage':   { url: '/api/graph/department-coverage', key: 'department_coverage', cat: 'A' },
  'top-technicians': { url: '/api/graph/top-technicians',      key: 'top_technicians',     cat: 'A' },
};

/* ── Category Filter ── */
function filterCat(cat) {
  document.querySelectorAll('.cat-tab').forEach(t => t.classList.toggle('active', t.dataset.cat === cat));
  document.querySelectorAll('.query-card').forEach(c => {
    c.classList.toggle('visible', cat === 'all' || c.dataset.cat === cat);
  });
}

/* ── Run Query ── */
async function runQuery(name, btn) {
  const q = QUERY_MAP[name];
  const el = document.getElementById('res-' + name);
  el.innerHTML = '<div class="empty"><div class="spin">⟳</div><div style="margin-top:6px">Running query…</div></div>';
  btn.disabled = true;

  let url = q.url;
  // Handle parameterized queries
  if (q.params) {
    const params = new URLSearchParams();
    q.params.forEach(p => {
      const input = document.getElementById('param-' + name + '-' + p);
      if (input) params.set(p, input.value);
    });
    url += '?' + params.toString();
  } else if (q.param) {
    const input = document.getElementById('param-' + name);
    if (input) url += '?' + q.param + '=' + encodeURIComponent(input.value);
  }

  try {
    const res = await fetch(url);
    const data = await res.json();
    let rows = data[q.key] || [];

    // Special rendering for shortest-path
    if (name === 'shortest-path' && Array.isArray(rows) && rows.length) {
      el.innerHTML = renderPath(rows);
      btn.disabled = false;
      return;
    }

    // Special rendering for impact-analysis (single object)
    if (name === 'impact-analysis' && !Array.isArray(rows)) {
      rows = [rows];
    }

    if (!rows.length) {
      el.innerHTML = '<div class="empty"><div class="empty-icon">📭</div>No results — seed the database first.</div>';
    } else {
      const cols = Object.keys(rows[0]);
      el.innerHTML =
        '<div class="results-actions"><span class="result-count">' + rows.length + ' row' + (rows.length > 1 ? 's' : '') + '</span></div>' +
        '<table><thead><tr>' + cols.map(c => '<th>' + c.replace(/_/g, ' ') + '</th>').join('') + '</tr></thead>' +
        '<tbody>' + rows.map(r =>
          '<tr>' + cols.map(c => {
            let v = r[c];
            if (Array.isArray(v)) v = v.join(', ');
            return '<td><div class="td-val" title="' + (v ?? '') + '">' + (v ?? '—') + '</div></td>';
          }).join('') + '</tr>'
        ).join('') + '</tbody></table>';
    }
  } catch (e) {
    el.innerHTML = '<div class="empty" style="color:var(--danger)">⚠ Error: ' + e.message + '</div>';
  }
  btn.disabled = false;
}

/* ── Render shortest path as visual nodes ── */
function renderPath(nodes) {
  let html = '<div class="results-actions"><span class="result-count">' + nodes.length + ' nodes in path</span></div><div class="path-viz">';
  nodes.forEach((n, i) => {
    const label = n.name || n.category || n.id || '?';
    const type = n.type || 'Unknown';
    html += '<div class="path-node ' + type + '" title="' + type + '">' + label + '</div>';
    if (i < nodes.length - 1) html += '<div class="path-arrow">→</div>';
  });
  html += '</div>';
  return html;
}

/* ── Load Stats ── */
async function loadStats() {
  const res = await fetch('/api/graph/stats');
  const data = await res.json();
  const nodes = data.nodes || {};
  const rels = data.relationships || 0;
  const colorMap = { Citizen:'#059669', Department:'#1d4ed8', Area:'#d97706', Technician:'#7c3aed', ServiceRequest:'#dc2626' };
  const pills = Object.entries(nodes).map(([label, count]) =>
    '<div class="stat-card"><div class="stat-val" style="color:' + (colorMap[label]||'var(--primary)') + '">' + count + '</div><div class="stat-lbl">' + label + 's</div></div>'
  ).join('');
  document.getElementById('graphStats').innerHTML = pills +
    '<div class="stat-card"><div class="stat-val" style="color:var(--text-lt)">' + rels + '</div><div class="stat-lbl">Relationships</div></div>';
}

/* ── Load Vis.js Graph ── */
async function loadVisGraph() {
  const container = document.getElementById('graphCanvas');
  if (!container) return;
  try {
    const res = await fetch('/api/graph/visual?limit=200');
    const data = await res.json();
    const nodes = new vis.DataSet(data.nodes.map(n => ({
      id: n.id, label: n.label, color: { background: n.color, border: n.color, highlight: { background: n.color, border: '#000' } },
      shape: n.shape, font: { color: '#0f172a', size: 12, face: 'Inter' }, borderWidth: 2, size: n.shape === 'diamond' ? 22 : (n.shape === 'triangle' ? 20 : 16)
    })));
    const edges = new vis.DataSet(data.edges.map((e, i) => ({
      id: i, from: e.from, to: e.to, label: e.label,
      font: { size: 9, color: '#94a3b8', strokeWidth: 0 }, color: { color: '#cbd5e1', highlight: '#1d4ed8' },
      arrows: 'to', smooth: { type: 'curvedCW', roundness: 0.15 }
    })));
    new vis.Network(container, { nodes, edges }, {
      physics: { barnesHut: { gravitationalConstant: -3000, springLength: 150, damping: 0.3 }, stabilization: { iterations: 100 } },
      interaction: { hover: true, tooltipDelay: 100, zoomView: true, dragView: true },
      layout: { improvedLayout: true }
    });
  } catch (e) {
    container.innerHTML = '<div class="empty" style="padding:40px">⚠ Could not load graph: ' + e.message + '</div>';
  }
}

/* ── Init ── */
loadStats().catch(() => {
  document.getElementById('graphStats').innerHTML =
    '<div class="stat-card" style="flex:none"><div class="stat-val" style="color:var(--danger);font-size:1rem">⚠ Neo4j unavailable</div><div class="stat-lbl">Start Docker containers first</div></div>';
});
loadVisGraph();
filterCat('all');
