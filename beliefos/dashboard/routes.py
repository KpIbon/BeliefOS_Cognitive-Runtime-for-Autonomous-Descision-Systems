"""Serve the dashboard at GET / and a small static asset.

The dashboard is intentionally a single page (no bundler) so it boots with
zero build step. It polls the JSON API every second and renders the live
state with Chart.js (loaded from a pinned CDN).
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

router = APIRouter()

_DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>BeliefOS · Live State</title>
  <link rel="icon" href="data:," />
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --bg: #0d0f12;
      --panel: #15191f;
      --line: #232a33;
      --fg: #e6e8ec;
      --muted: #8a94a3;
      --accent: #7dd3fc;
      --good: #4ade80;
      --watch: #facc15;
      --alert: #fb923c;
      --crit: #f87171;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font: 14px/1.5 -apple-system, system-ui, sans-serif;
           background: var(--bg); color: var(--fg); }
    header { padding: 18px 24px; border-bottom: 1px solid var(--line);
             display: flex; justify-content: space-between; align-items: center; }
    header h1 { margin: 0; font-size: 18px; letter-spacing: 0.02em; }
    .pill { padding: 4px 10px; border-radius: 999px; font-size: 12px;
            background: var(--panel); color: var(--muted); border: 1px solid var(--line); }
    main { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 16px 24px 24px; }
    .card { background: var(--panel); border: 1px solid var(--line);
            border-radius: 12px; padding: 16px; }
    .card h2 { margin: 0 0 12px; font-size: 14px; color: var(--muted);
               text-transform: uppercase; letter-spacing: 0.08em; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--line);
             font-size: 13px; }
    th { color: var(--muted); font-weight: 500; }
    .state-stable { color: var(--good); }
    .state-watch { color: var(--watch); }
    .state-alert { color: var(--alert); }
    .state-critical { color: var(--crit); }
    .metric { display: flex; gap: 16px; }
    .metric .box { flex: 1; padding: 14px; background: #0f1217;
                   border: 1px solid var(--line); border-radius: 10px; }
    .metric .box .v { font-size: 24px; font-weight: 600; }
    .metric .box .l { color: var(--muted); font-size: 12px; margin-top: 2px; }
    form { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
    input, select, button { background: #0f1217; color: var(--fg); border: 1px solid var(--line);
                            padding: 8px 10px; border-radius: 8px; font: inherit; }
    button { cursor: pointer; }
    button:hover { border-color: var(--accent); }
    canvas { max-height: 260px; }
    footer { padding: 12px 24px; color: var(--muted); font-size: 12px;
             border-top: 1px solid var(--line); }
  </style>
</head>
<body>
  <header>
    <h1>BeliefOS · Live State</h1>
    <div>
      <span class="pill" id="health">cache: ?</span>
      <span class="pill" id="decision-state">state: ?</span>
    </div>
  </header>

  <main>
    <section class="card">
      <h2>World</h2>
      <div class="metric">
        <div class="box"><div class="v" id="m-fused">—</div><div class="l">fused belief</div></div>
        <div class="box"><div class="v" id="m-conf">—</div><div class="l">confidence</div></div>
        <div class="box"><div class="v" id="m-risk">—</div><div class="l">risk</div></div>
        <div class="box"><div class="v" id="m-vol">—</div><div class="l">volatility</div></div>
      </div>
      <h2 style="margin-top: 18px;">Decision</h2>
      <p id="decision-action" style="margin: 0;">—</p>
    </section>

    <section class="card">
      <h2>Beliefs</h2>
      <table>
        <thead>
          <tr><th>subject</th><th>belief</th><th>conf</th><th>trend</th><th>#obs</th></tr>
        </thead>
        <tbody id="belief-rows">
          <tr><td colspan="5" style="color: var(--muted);">no observations yet</td></tr>
        </tbody>
      </table>
    </section>

    <section class="card" style="grid-column: 1 / -1;">
      <h2>Fused state over time</h2>
      <canvas id="chart"></canvas>
    </section>

    <section class="card" style="grid-column: 1 / -1;">
      <h2>Send an observation</h2>
      <form id="obs-form">
        <input id="obs-subject" placeholder="subject (e.g. cpu_spike)" required />
        <input id="obs-value" type="number" step="0.01" min="0" max="1" value="0.7" required />
        <select id="obs-source">
          <option value="manual">manual</option>
          <option value="openai">openai</option>
          <option value="anthropic">anthropic</option>
          <option value="ros2">ros2</option>
          <option value="drone">drone</option>
        </select>
        <input id="obs-note" placeholder="note (optional)" />
        <button type="submit">POST /observe</button>
      </form>
    </section>
  </main>

  <footer>
    Polling /v1/world-state and /v1/beliefs once per second.
    Drop JSON into <code>/v1/observe</code> from any source.
  </footer>

  <script>
    const chartCtx = document.getElementById('chart').getContext('2d');
    const series = [];
    const chart = new Chart(chartCtx, {
      type: 'line',
      data: { labels: [], datasets: [
        { label: 'fused belief', data: series, borderColor: '#7dd3fc', tension: 0.3, fill: false },
      ]},
      options: {
        animation: false,
        scales: { y: { suggestedMin: 0, suggestedMax: 1 } },
        plugins: { legend: { labels: { color: '#e6e8ec' } } }
      }
    });

    async function pull() {
      try {
        const [ws, beliefs, dec, health] = await Promise.all([
          fetch('/v1/world-state').then(r => r.ok ? r.json() : null),
          fetch('/v1/beliefs').then(r => r.ok ? r.json() : []),
          fetch('/v1/decide').then(r => r.ok ? r.json() : null),
          fetch('/v1/health').then(r => r.ok ? r.json() : null),
        ]);

        if (ws) {
          document.getElementById('m-fused').textContent = ws.fused_belief.toFixed(3);
          document.getElementById('m-conf').textContent = ws.overall_confidence.toFixed(3);
          document.getElementById('m-risk').textContent = ws.risk_score.toFixed(3);
          document.getElementById('m-vol').textContent = ws.volatility.toFixed(3);
          const t = new Date();
          chart.data.labels.push(t.toLocaleTimeString());
          series.push(ws.fused_belief);
          if (chart.data.labels.length > 60) {
            chart.data.labels.shift(); series.shift();
          }
          chart.update('none');
        }
        if (dec) {
          const el = document.getElementById('decision-state');
          el.textContent = 'state: ' + dec.state;
          el.className = 'pill state-' + dec.state;
          document.getElementById('decision-action').textContent = dec.action;
        }
        if (health) {
          document.getElementById('health').textContent =
            'cache: ' + health.cache + (health.cache_alive ? ' · ok' : ' · down');
        }
        const rows = document.getElementById('belief-rows');
        if (beliefs.length === 0) {
          rows.innerHTML = '<tr><td colspan="5" style="color: var(--muted);">no observations yet</td></tr>';
        } else {
          rows.innerHTML = beliefs.map(b => `
            <tr>
              <td>${b.subject}</td>
              <td>${b.value.toFixed(3)}</td>
              <td>${b.confidence.toFixed(3)}</td>
              <td>${b.trend}</td>
              <td>${b.observation_count}</td>
            </tr>`).join('');
        }
      } catch (e) {
        // network blip; try again next tick
      }
    }

    setInterval(pull, 1000);
    pull();

    document.getElementById('obs-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const body = {
        subject: document.getElementById('obs-subject').value,
        value: parseFloat(document.getElementById('obs-value').value),
        source: document.getElementById('obs-source').value,
        note: document.getElementById('obs-note').value,
      };
      const r = await fetch('/v1/observe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!r.ok) alert('observe failed: ' + r.status);
    });
  </script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def index() -> HTMLResponse:
    return HTMLResponse(_DASHBOARD_HTML)
