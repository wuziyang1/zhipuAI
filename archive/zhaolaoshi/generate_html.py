import json, re

with open("test.json", encoding="utf-8") as f:
    items = json.load(f)[:2]

data_json = json.dumps(items, ensure_ascii=False, indent=2)

html = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>数学题库可视化</title>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script>
    MathJax = {
      tex: {
        inlineMath: [['$', '$'], ['\\(', '\\)']],
        displayMath: [['$$', '$$'], ['\\[', '\\]']],
        processEscapes: true
      },
      options: { skipHtmlTags: ['script','noscript','style','textarea','pre'] }
    };
  </script>
  <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js" async></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'PingFang SC', 'Microsoft YaHei', 'Segoe UI', sans-serif;
      background: #f8fafc;
      min-height: 100vh;
      padding: 40px 20px;
      color: #1e293b;
    }

    h1.page-title {
      text-align: center;
      font-size: 2rem;
      font-weight: 700;
      margin-bottom: 8px;
      background: linear-gradient(90deg, #6d28d9, #2563eb, #059669);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
    }
    .page-subtitle {
      text-align: center;
      color: #64748b;
      margin-bottom: 48px;
      font-size: 0.95rem;
      letter-spacing: 0.05em;
    }

    .cards-container {
      max-width: 960px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 36px;
    }

    .card {
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 20px;
      overflow: hidden;
      box-shadow: 0 4px 24px rgba(0,0,0,0.08);
      animation: fadeUp 0.5s ease both;
    }
    .card:nth-child(1) { animation-delay: 0.1s; }
    .card:nth-child(2) { animation-delay: 0.25s; }

    @keyframes fadeUp {
      from { opacity: 0; transform: translateY(24px); }
      to   { opacity: 1; transform: translateY(0); }
    }

    .card-header {
      padding: 20px 28px;
      display: flex;
      align-items: center;
      gap: 14px;
      border-bottom: 1px solid #f1f5f9;
    }
    .card:nth-child(1) .card-header { background: linear-gradient(135deg, #ede9fe, #dbeafe); }
    .card:nth-child(2) .card-header { background: linear-gradient(135deg, #ccfbf1, #dbeafe); }

    .card-num {
      width: 42px; height: 42px;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 1.1rem; font-weight: 700; flex-shrink: 0;
      color: #ffffff;
    }
    .card:nth-child(1) .card-num { background: #7c3aed; }
    .card:nth-child(2) .card-num { background: #0d9488; }

    .card-meta { flex: 1; }
    .card-meta h2 { font-size: 1rem; font-weight: 600; color: #0f172a; margin-bottom: 6px; }
    .badges { display: flex; gap: 8px; flex-wrap: wrap; }

    .badge {
      padding: 3px 12px;
      border-radius: 999px;
      font-size: 0.75rem;
      font-weight: 600;
      letter-spacing: 0.04em;
    }
    .badge-type  { background: #ede9fe; color: #6d28d9; border: 1px solid #c4b5fd; }
    .badge-level { background: #ccfbf1; color: #0f766e; border: 1px solid #99f6e4; }

    .answer-pill {
      padding: 6px 18px;
      border-radius: 999px;
      font-size: 0.85rem;
      font-weight: 700;
      background: #dcfce7;
      border: 1px solid #86efac;
      color: #15803d;
      white-space: nowrap;
    }

    .card-body { padding: 0 28px 28px; }

    .section-label {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.78rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin: 24px 0 12px;
    }
    .section-label::before {
      content: '';
      display: block;
      width: 4px; height: 16px;
      border-radius: 2px;
    }
    .label-question { color: #2563eb; }
    .label-question::before { background: #3b82f6; }
    .label-solution { color: #059669; }
    .label-solution::before { background: #10b981; }

    .question-box {
      background: #eff6ff;
      border: 1px solid #bfdbfe;
      border-radius: 12px;
      padding: 18px 20px;
      font-size: 1rem;
      line-height: 1.8;
      color: #1e3a5f;
    }

    .solution-box {
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 20px 22px;
      font-size: 0.88rem;
      line-height: 1.75;
      color: #334155;
      max-height: 520px;
      overflow-y: auto;
      transition: max-height 0.3s ease, padding 0.3s ease;
    }
    .solution-box::-webkit-scrollbar { width: 5px; }
    .solution-box::-webkit-scrollbar-track { background: #f1f5f9; }
    .solution-box::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }

    .solution-box h2 {
      font-size: 1rem; color: #6d28d9;
      margin: 18px 0 8px; border-bottom: 1px solid #e9d5ff; padding-bottom: 4px;
    }
    .solution-box h3 { font-size: 0.92rem; color: #1d4ed8; margin: 14px 0 6px; }
    .solution-box h4 { font-size: 0.88rem; color: #0f766e; margin: 10px 0 4px; }
    .solution-box p  { margin-bottom: 8px; }
    .solution-box ul, .solution-box ol { padding-left: 20px; margin-bottom: 8px; }
    .solution-box li { margin-bottom: 4px; }
    .solution-box strong { color: #92400e; }
    .solution-box em    { color: #9d174d; }
    .solution-box code  {
      background: #f1f5f9; color: #0f172a;
      padding: 1px 6px; border-radius: 4px;
      font-size: 0.84rem; border: 1px solid #e2e8f0;
    }
    .solution-box blockquote {
      border-left: 3px solid #818cf8;
      margin: 8px 0; padding-left: 12px;
      color: #64748b;
    }
    .solution-box hr { border: none; border-top: 1px solid #e2e8f0; margin: 14px 0; }
    .solution-box table {
      border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 0.85rem;
    }
    .solution-box th, .solution-box td {
      border: 1px solid #e2e8f0; padding: 6px 12px; text-align: left;
    }
    .solution-box th { background: #f1f5f9; font-weight: 600; color: #1e293b; }

    .toggle-btn {
      display: inline-flex; align-items: center; gap: 6px;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      color: #64748b;
      padding: 6px 16px;
      border-radius: 999px;
      cursor: pointer;
      font-size: 0.8rem;
      margin-top: 10px;
      transition: all .2s;
    }
    .toggle-btn:hover { background: #f1f5f9; color: #1e293b; border-color: #cbd5e1; }
    .toggle-btn.collapsed .arrow { transform: rotate(-90deg); }
    .arrow { display: inline-block; transition: transform .25s; }

    .page-footer {
      text-align: center;
      margin-top: 52px;
      color: #94a3b8;
      font-size: 0.8rem;
    }
  </style>
</head>
<body>

<h1 class="page-title">数学题库解析可视化</h1>
<p class="page-subtitle">共展示 2 道题目 · 数据直接来源于 test.json · 内容完整未删减</p>

<div class="cards-container" id="cards"></div>

<div class="page-footer">数据来源：test.json · 渲染引擎：MathJax 3 + Marked.js</div>

<script type="application/json" id="raw-data">
__DATA_PLACEHOLDER__
</script>

<script>
const items = JSON.parse(document.getElementById('raw-data').textContent);

const colors = [
  { header: 'linear-gradient(135deg,#ede9fe,#dbeafe)', num: '#7c3aed' },
  { header: 'linear-gradient(135deg,#ccfbf1,#dbeafe)', num: '#0d9488' }
];

function renderAnswer(raw) {
  // strip html tags for display
  return raw.replace(/<[^>]+>/g, '').trim();
}

function render() {
  const container = document.getElementById('cards');
  items.forEach((item, idx) => {
    const human = item.conversations.find(c => c.from === 'human');
    const gpt   = item.conversations.find(c => c.from === 'gpt');
    const id    = 'sol-' + idx;
    const c     = colors[idx] || colors[0];

    const card = document.createElement('div');
    card.className = 'card';

    card.innerHTML = `
      <div class="card-header" style="background:${c.header}">
        <div class="card-num" style="background:${c.num}">${idx + 1}</div>
        <div class="card-meta">
          <h2>第 ${idx + 1} 题</h2>
          <div class="badges">
            <span class="badge badge-type">${item.quesType}</span>
            <span class="badge badge-level">难度：${item.level}</span>
          </div>
        </div>
        <div class="answer-pill">答案：${renderAnswer(item.quesAnswer)}</div>
      </div>
      <div class="card-body">
        <div class="section-label label-question">题目</div>
        <div class="question-box">${human ? human.value : ''}</div>

        <div class="section-label label-solution">解题过程（GPT 完整原文）</div>
        <div class="solution-box" id="${id}">
          ${gpt ? marked.parse(gpt.value) : ''}
        </div>
        <button class="toggle-btn" onclick="toggle('${id}',this)">
          <span class="arrow">&#9660;</span>&nbsp;收起解析
        </button>
      </div>
    `;
    container.appendChild(card);
  });

  if (window.MathJax) MathJax.typesetPromise();
}

function toggle(id, btn) {
  const box = document.getElementById(id);
  const isCollapsed = btn.classList.toggle('collapsed');
  if (isCollapsed) {
    box.style.maxHeight = '0';
    box.style.overflow  = 'hidden';
    box.style.padding   = '0 22px';
    btn.innerHTML = '<span class="arrow" style="transform:rotate(-90deg);display:inline-block">&#9660;</span>&nbsp;展开解析';
  } else {
    box.style.maxHeight = '520px';
    box.style.overflow  = 'auto';
    box.style.padding   = '20px 22px';
    btn.innerHTML = '<span class="arrow" style="display:inline-block">&#9660;</span>&nbsp;收起解析';
  }
}

render();
</script>
</body>
</html>
"""

html = html.replace('__DATA_PLACEHOLDER__', data_json)

with open("visualize.html", "w", encoding="utf-8") as f:
    f.write(html)

print("visualize.html 已生成，包含前2条完整原始数据。")
