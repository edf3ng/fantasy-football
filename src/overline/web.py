"""Local board: players over the line, and the context window that put them there."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def serve(payload: dict, port: int) -> None:
    page = render_page(payload).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.split("?", 1)[0] not in ("/", "/index.html"):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def log_message(self, fmt: str, *args) -> None:
            print("%s - %s" % (self.address_string(), fmt % args))

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Overline board at http://127.0.0.1:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


def render_page(payload: dict) -> str:
    data = json.dumps(payload).replace("<", "\\u003c")
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Overline</title>
<style>
:root {
  color-scheme: light;
  --bg: #f3f0e8;
  --ink: #1c1b17;
  --muted: #5e5a52;
  --line: #d9d3c6;
  --panel: #fffdf8;
  --mark: #8a5a12;
  --good: #1f6b45;
  --bad: #8d2f2f;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 15px/1.45 "Iowan Old Style", Palatino, Georgia, serif;
}
main { max-width: 1180px; margin: 0 auto; padding: 28px 20px 48px; }
header h1 { font-size: 32px; font-weight: 500; margin: 0 0 6px; letter-spacing: -0.03em; }
header p { margin: 0; max-width: 62ch; color: var(--muted); }
.toolbar { display: flex; flex-wrap: wrap; gap: 16px 28px; align-items: end; margin: 22px 0; }
label { display: flex; flex-direction: column; gap: 4px; font-family: ui-sans-serif, system-ui, sans-serif; font-size: 12px; color: var(--muted); }
select {
  font: 14px/1.2 ui-sans-serif, system-ui, sans-serif;
  color: var(--ink);
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 8px 10px;
}
.rates { display: flex; gap: 22px; font-family: ui-sans-serif, system-ui, sans-serif; font-size: 13px; }
.rates strong { display: block; font-size: 18px; font-weight: 600; color: var(--ink); }
.layout { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.8fr); gap: 22px; align-items: start; }
@media (max-width: 860px) { .layout { grid-template-columns: 1fr; } }
table { width: 100%; border-collapse: collapse; background: var(--panel); font-family: ui-sans-serif, system-ui, sans-serif; font-size: 13px; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { font-size: 11px; font-weight: 600; color: var(--muted); letter-spacing: 0.02em; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
tbody tr { cursor: pointer; }
tbody tr[aria-selected="true"] { background: #efe6d4; }
.edge { color: var(--mark); font-weight: 600; }
.hit { color: var(--good); }
.miss { color: var(--bad); }
aside { background: var(--panel); border: 1px solid var(--line); padding: 16px 16px 20px; position: sticky; top: 12px; }
aside h2 { font-size: 13px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; margin: 0 0 4px; font-family: ui-sans-serif, system-ui, sans-serif; }
.who { font-size: 22px; margin: 0 0 2px; }
.meta { color: var(--muted); margin: 0 0 14px; font-family: ui-sans-serif, system-ui, sans-serif; font-size: 13px; }
.equation { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 14px; font-family: ui-sans-serif, system-ui, sans-serif; }
.equation span { display: block; color: var(--muted); font-size: 11px; }
.equation strong { font-size: 18px; font-weight: 600; }
.slot { display: grid; grid-template-columns: minmax(0, 1.3fr) 52px 1fr; gap: 8px; align-items: center; margin: 7px 0; font-family: ui-sans-serif, system-ui, sans-serif; font-size: 12px; }
.slot .name { color: var(--ink); }
.slot .raw { text-align: right; font-variant-numeric: tabular-nums; color: var(--muted); }
.track { position: relative; height: 8px; background: transparent; }
.track i {
  position: absolute;
  top: 0;
  height: 8px;
  background: var(--mark);
  border-radius: 2px;
}
.track i.neg { background: var(--ink); }
.zero { position: absolute; left: 50%; top: -2px; bottom: -2px; width: 1px; background: var(--line); }
.line-bits { margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--line); }
.line-bits h3 { margin: 0 0 8px; font-size: 13px; font-weight: 600; font-family: ui-sans-serif, system-ui, sans-serif; }
.bits { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 12px; font-family: ui-sans-serif, system-ui, sans-serif; font-size: 12px; }
.bits span { color: var(--muted); }
footer { margin-top: 18px; color: var(--muted); font-size: 13px; max-width: 78ch; }
.empty { padding: 18px 10px; font-family: ui-sans-serif, system-ui, sans-serif; }
</style>
</head>
<body>
<main>
  <header>
    <h1>Overline</h1>
    <p id="note"></p>
  </header>
  <div class="toolbar">
    <label>Week
      <select id="week"></select>
    </label>
    <div class="rates">
      <div><strong id="listed">—</strong>On the board</div>
      <div><strong id="board-rate">—</strong>Board hit rate</div>
      <div><strong id="base-rate">—</strong><span id="base-label">Base rate</span></div>
    </div>
  </div>
  <div class="layout">
    <div>
      <table>
        <caption class="visually-hidden" style="position:absolute;left:-999px">Players the model expects to score above their form line</caption>
        <thead>
          <tr>
            <th class="num">#</th>
            <th>Player</th>
            <th>Pos</th>
            <th>Opp</th>
            <th class="num">Line</th>
            <th class="num">Model</th>
            <th class="num">Edge</th>
            <th class="num">P(over)</th>
            <th>Actual</th>
          </tr>
        </thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
    <aside id="context" aria-live="polite"></aside>
  </div>
  <footer id="foot"></footer>
</main>
<script id="board" type="application/json">""" + data + """</script>
<script>
const data = JSON.parse(document.getElementById("board").textContent);
const weekSelect = document.getElementById("week");
const rowsEl = document.getElementById("rows");
const contextEl = document.getElementById("context");
let selected = 0;

document.getElementById("note").textContent = data.note;
document.getElementById("base-label").textContent = "Base rate, line at least " + data.min_projection;

data.weeks.forEach((week, index) => {
  const option = document.createElement("option");
  option.value = String(index);
  option.textContent = week.season + " week " + week.week;
  weekSelect.appendChild(option);
});
if (data.weeks.length) weekSelect.value = String(data.featured || 0);

weekSelect.addEventListener("change", () => {
  selected = 0;
  render();
});

function points(value) {
  return Number(value).toFixed(1);
}

function signed(value) {
  const number = Number(value);
  return (number > 0 ? "+" : "") + number.toFixed(1);
}

function pct(value) {
  return Math.round(Number(value) * 100) + "%";
}

function rate(hits, trials) {
  if (!trials) return "—";
  return Math.round(100 * hits / trials) + "%";
}

function opponent(player) {
  if (player.site === "away") return "@ " + player.opponent;
  return "vs " + player.opponent;
}

function render() {
  const week = data.weeks[Number(weekSelect.value)];
  const partial = week && week.partial ? " This week is only partly posted, so the list is whoever has a stat line so far." : "";
  document.getElementById("note").textContent = data.note + partial;
  document.getElementById("listed").textContent = week ? String(week.players.length) : "0";
  document.getElementById("board-rate").textContent = week ? rate(week.hits, week.players.length) : "—";
  document.getElementById("base-rate").textContent = week ? rate(week.eligible_hits, week.eligible) : "—";
  rowsEl.replaceChildren();
  if (!week || !week.players.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 9;
    cell.className = "empty";
    cell.textContent = "No player cleared the line this week.";
    row.appendChild(cell);
    rowsEl.appendChild(row);
    contextEl.replaceChildren();
    return;
  }
  if (selected >= week.players.length) selected = 0;
  week.players.forEach((player, index) => {
    const row = document.createElement("tr");
    row.setAttribute("aria-selected", index === selected ? "true" : "false");
    const actual = document.createElement("td");
    actual.textContent = points(player.actual);
    actual.className = player.beat ? "hit" : "miss";
    const cells = [
      ["num", String(index + 1)],
      ["", player.name],
      ["", player.position],
      ["", opponent(player)],
      ["num", points(player.projection)],
      ["num", points(player.expected)],
      ["num edge", signed(player.edge)],
      ["num", pct(player.p_beat)],
    ];
    cells.forEach(([className, text]) => {
      const cell = document.createElement("td");
      if (className) cell.className = className;
      cell.textContent = text;
      row.appendChild(cell);
    });
    row.appendChild(actual);
    row.addEventListener("click", () => {
      selected = index;
      render();
    });
    rowsEl.appendChild(row);
  });
  renderContext(week.players[selected]);
}

function renderContext(player) {
  contextEl.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = "Context window";
  const who = document.createElement("p");
  who.className = "who";
  who.textContent = player.name;
  const meta = document.createElement("p");
  meta.className = "meta";
  meta.textContent = player.position + " · " + player.team + " " + opponent(player) + " · position error " + points(player.sigma) + " PPR";
  const equation = document.createElement("div");
  equation.className = "equation";
  [["Line", points(player.projection)], ["Surplus", signed(player.edge)], ["Model", points(player.expected)]].forEach(([label, value]) => {
    const block = document.createElement("div");
    const span = document.createElement("span");
    span.textContent = label;
    const strong = document.createElement("strong");
    strong.textContent = value;
    block.appendChild(span);
    block.appendChild(strong);
    equation.appendChild(block);
  });
  contextEl.append(title, who, meta, equation);

  const maxPull = Math.max(0.25, ...player.slots.map((slot) => Math.abs(slot.pull)));
  player.slots.forEach((slot) => contextEl.appendChild(slotRow(slot.label, slot.raw, slot.pull, maxPull)));
  contextEl.appendChild(slotRow("Intercept", null, player.intercept, Math.max(maxPull, Math.abs(player.intercept))));

  const lineBits = document.createElement("div");
  lineBits.className = "line-bits";
  const heading = document.createElement("h3");
  heading.textContent = "How the line was built";
  const bits = document.createElement("div");
  bits.className = "bits";
  [
    ["Last game", points(player.line.last_points)],
    ["Last three", points(player.line.avg_3)],
    ["Season average", points(player.line.season_avg)],
    ["Games this season", String(Math.round(player.line.games_played))],
  ].forEach(([label, value]) => {
    const span = document.createElement("span");
    span.textContent = label;
    const strong = document.createElement("strong");
    strong.textContent = value;
    bits.append(span, strong);
  });
  lineBits.append(heading, bits);
  contextEl.appendChild(lineBits);
}

function slotRow(label, raw, pull, maxPull) {
  const row = document.createElement("div");
  row.className = "slot";
  const name = document.createElement("div");
  name.className = "name";
  name.textContent = label;
  const rawEl = document.createElement("div");
  rawEl.className = "raw";
  rawEl.textContent = raw == null ? "" : Number(raw).toFixed(1);
  const track = document.createElement("div");
  track.className = "track";
  const zero = document.createElement("div");
  zero.className = "zero";
  const bar = document.createElement("i");
  const width = Math.abs(pull) / maxPull * 50;
  if (pull >= 0) {
    bar.style.left = "50%";
    bar.style.width = width + "%";
  } else {
    bar.className = "neg";
    bar.style.left = (50 - width) + "%";
    bar.style.width = width + "%";
  }
  track.append(zero, bar);
  track.title = signed(pull) + " PPR";
  row.append(name, rawEl, track);
  return row;
}

document.getElementById("foot").textContent = "Each pull is that slot's share of the surplus after the week was fit on earlier games only. Actual points were not an input. Hit rate is how often the listed players scored above the form line.";
render();
</script>
</body>
</html>
"""
