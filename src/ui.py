"""トップページのUI（グラフ可視化 + 検証フォーム）のHTMLを組み立てる。"""

INDEX_HTML = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>AppealGraph</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
  :root {
    --bg: #0f1115;
    --panel: #171a21;
    --border: #2a2f3a;
    --text: #e6e8ec;
    --muted: #9aa3b2;
    --accent: #5b8def;
    --ok: #3ecf8e;
    --bad: #ef5b5b;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: "Hiragino Kaku Gothic ProN", "Yu Gothic", system-ui, sans-serif;
    display: flex;
    height: 100vh;
    overflow: hidden;
  }
  header {
    position: fixed;
    top: 0; left: 0; right: 0;
    padding: 12px 20px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
    z-index: 10;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  header h1 { font-size: 16px; margin: 0; font-weight: 600; }
  header p { margin: 0; color: var(--muted); font-size: 12px; }
  #graph {
    flex: 1;
    margin-top: 52px;
    height: calc(100vh - 52px);
    background: var(--bg);
  }
  #panel {
    width: 420px;
    margin-top: 52px;
    height: calc(100vh - 52px);
    overflow-y: auto;
    background: var(--panel);
    border-left: 1px solid var(--border);
    padding: 20px;
  }
  #panel h2 { font-size: 14px; margin: 0 0 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
  select, button {
    width: 100%;
    padding: 10px;
    margin-bottom: 10px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: #0d0f14;
    color: var(--text);
    font-size: 14px;
  }
  button {
    background: var(--accent);
    border: none;
    color: white;
    font-weight: 600;
    cursor: pointer;
  }
  button:disabled { opacity: 0.5; cursor: wait; }
  .badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
    margin-bottom: 12px;
  }
  .badge.ok { background: rgba(62,207,142,0.15); color: var(--ok); }
  .badge.bad { background: rgba(239,91,91,0.15); color: var(--bad); }
  .card {
    background: #0d0f14;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px;
    margin-bottom: 14px;
    font-size: 13px;
    line-height: 1.7;
    white-space: pre-wrap;
  }
  .label { color: var(--muted); font-size: 11px; text-transform: uppercase; margin-bottom: 4px; }
  .legend { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
  .legend span { font-size: 11px; padding: 4px 8px; border-radius: 6px; }
  #empty { color: var(--muted); font-size: 13px; }
</style>
</head>
<body>
<header>
  <h1>⚖️ AppealGraph</h1>
  <p>Neo4jグラフ × Daytonaサンドボックスによる判例引用検証</p>
</header>
<div id="graph"></div>
<div id="panel">
  <h2>1. 検証したい機関・条文を選択</h2>
  <select id="authoritySelect"></select>
  <select id="articleSelect"></select>
  <button id="verifyBtn">グラフから反論書を生成 → Daytonaで検証</button>

  <div id="result">
    <p id="empty">左のグラフをドラッグ・ズームしながら、機関→非開示条文→反論パターン→反論ロジック/判例の関係を確認できます。上のフォームから検証を実行してください。</p>
  </div>
</div>

<script>
const groupColors = {
  "機関": "#5b8def",
  "非開示条文": "#f2b84b",
  "反論パターン": "#a06cd5",
  "反論ロジック": "#3ecf8e",
  "判例": "#ef5b5b",
};

async function loadGraph() {
  const res = await fetch("/graph");
  const data = await res.json();

  const nodes = new vis.DataSet(data.nodes.map(n => ({
    ...n,
    color: groupColors[n.group] || "#888",
    font: { color: "#e6e8ec", size: 11 },
    shape: n.group === "機関" ? "box" : "dot",
    size: n.group === "機関" ? 18 : 10,
  })));
  const edges = new vis.DataSet(data.edges.map(e => ({ ...e, color: { color: "#2a2f3a" }, arrows: "to" })));

  const network = new vis.Network(document.getElementById("graph"), { nodes, edges }, {
    physics: { stabilization: true, barnesHut: { gravitationalConstant: -4000, springLength: 120 } },
    interaction: { hover: true },
  });
}

async function loadAuthorities() {
  const res = await fetch("/authorities");
  const rows = await res.json();

  const byAuthority = {};
  for (const r of rows) {
    if (!byAuthority[r.key]) byAuthority[r.key] = { name: r.authority, articles: [] };
    byAuthority[r.key].articles.push({ number: r.number, name: r.name });
  }

  const authoritySelect = document.getElementById("authoritySelect");
  for (const [key, info] of Object.entries(byAuthority)) {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = info.name;
    authoritySelect.appendChild(opt);
  }

  function refreshArticles() {
    const articleSelect = document.getElementById("articleSelect");
    articleSelect.innerHTML = "";
    const info = byAuthority[authoritySelect.value];
    for (const a of info.articles) {
      const opt = document.createElement("option");
      opt.value = a.number;
      opt.textContent = `${a.number} ${a.name}`;
      articleSelect.appendChild(opt);
    }
  }

  authoritySelect.addEventListener("change", refreshArticles);
  refreshArticles();
}

document.getElementById("verifyBtn").addEventListener("click", async () => {
  const btn = document.getElementById("verifyBtn");
  const authority_key = document.getElementById("authoritySelect").value;
  const article_number = document.getElementById("articleSelect").value;
  const resultEl = document.getElementById("result");

  btn.disabled = true;
  btn.textContent = "生成・検証中...（Daytonaサンドボックス起動中）";
  resultEl.innerHTML = "<p id='empty'>処理中です。しばらくお待ちください…</p>";

  try {
    const url = `/verify?authority_key=${encodeURIComponent(authority_key)}&article_number=${encodeURIComponent(article_number)}`;
    const res = await fetch(url);
    const data = await res.json();

    if (!res.ok) {
      resultEl.innerHTML = `<p style="color:var(--bad)">エラー: ${data.detail || res.status}</p>`;
      return;
    }

    const ok = data.status === "verified";
    resultEl.innerHTML = `
      <span class="badge ${ok ? "ok" : "bad"}">${ok ? "✓ 引用検証OK" : "✗ 未検証の引用を検出"}</span>
      <div class="label">機関 / 審査会</div>
      <div class="card">${data.authority} / ${data.review_authority}</div>
      <div class="label">生成元 (draft_source)</div>
      <div class="card">${data.draft_source}</div>
      <div class="label">反論書ドラフト</div>
      <div class="card">${data.draft_body}</div>
      <div class="label">グラフ上の実在判例</div>
      <div class="card">${data.citations_in_graph.length ? data.citations_in_graph.join(", ") : "（この条文には判例なし）"}</div>
      <div class="label">Daytonaサンドボックス検証結果</div>
      <div class="card">exit_code=${data.sandbox_exit_code}\n${data.sandbox_result.raw}</div>
    `;
  } catch (e) {
    resultEl.innerHTML = `<p style="color:var(--bad)">通信エラー: ${e}</p>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "グラフから反論書を生成 → Daytonaで検証";
  }
});

loadGraph();
loadAuthorities();
</script>
</body>
</html>
"""
