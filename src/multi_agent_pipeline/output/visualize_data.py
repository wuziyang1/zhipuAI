"""
多智能体 Pipeline 数据可视化脚本

支持以下 4 种 JSON 格式，以"LLM 对话气泡"风格渲染：

  training_data.json         — conversations + _metadata
  training_data_minimal.json — conversations（无 metadata）
  raw_data.json              — 题目为中心，含 student_cases[]
  quality_report.json        — 汇总统计仪表板
"""

import json
import os
import random
import re
import webbrowser
from datetime import datetime

# ==================== 配置 ====================
INPUT_FILE  = 'raw_data.json'        # 改为任意一个文件名即可
OUTPUT_FILE = 'visualization.html'

MAX_DISPLAY = 12        # 超出时随机抽样
RANDOM_SEED = None      # None = 每次随机；整数 = 固定结果
AUTO_OPEN   = True
# ==============================================

# ──────────────────────────────────────────────
# 小工具
# ──────────────────────────────────────────────

LEVEL_MAP = {
    'excellent': ('优秀', '#10b981'),
    'average':   ('中等', '#f59e0b'),
    'weak':      ('薄弱', '#ef4444'),
}

DIFF_COLOR = {
    '容易': '#10b981',
    '中等': '#3b82f6',
    '较难': '#f59e0b',
    '困难': '#ef4444',
}

def _esc(s):
    """最小化 HTML 转义（防止 f-string 中的 < > 破坏结构）。"""
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def badge(text, color, bg=None):
    bg = bg or color + '1a'
    return (f"<span style='display:inline-flex;align-items:center;background:{bg};"
            f"color:{color};border:1px solid {color}44;padding:2px 9px;"
            f"border-radius:20px;font-size:0.76em;font-weight:600;"
            f"white-space:nowrap;line-height:1.6;'>{_esc(text)}</span>")

def level_badge(key):
    text, color = LEVEL_MAP.get(key, (_esc(key) or '?', '#6b7280'))
    return badge(text, color)

def score_badge(score):
    if score is None:
        return ''
    color = '#10b981' if score >= 90 else ('#f59e0b' if score >= 70 else '#ef4444')
    return badge(f"质量 {score:.0f}", color)

def bool_badge(val, t, f):
    if val is None:
        return ''
    return badge(('✓ ' + t) if val else ('✗ ' + f),
                 '#10b981' if val else '#ef4444')

def topic_pills(kps):
    if not kps:
        return ''
    pills = ''.join(
        f"<span style='background:#eff6ff;color:#3b82f6;border:1px solid #bfdbfe;"
        f"padding:2px 9px;border-radius:20px;font-size:0.76em;margin:2px 3px 2px 0;"
        f"display:inline-block;line-height:1.7;'>{_esc(kp)}</span>"
        for kp in kps
    )
    return (f"<div style='margin:0 0 10px;line-height:2;padding:10px 14px;"
            f"background:#f8faff;border-radius:8px;border:1px solid #e0e7ff;'>"
            f"<span style='font-size:0.75em;font-weight:700;color:#6366f1;"
            f"text-transform:uppercase;letter-spacing:.06em;margin-right:8px;'>知识点</span>"
            f"{pills}</div>")

def parse_human(text):
    if '学生的解答：' in text:
        parts = text.split('学生的解答：', 1)
        q = parts[0].split('题目：', 1)[-1].strip() if '题目：' in parts[0] else parts[0].strip()
        return q, parts[1].strip()
    return '', text

# ──────────────────────────────────────────────
# HTML 组件
# ──────────────────────────────────────────────

def system_banner(text):
    if not text:
        return ''
    return (f"<div style='margin:0 0 14px;padding:10px 14px;background:#f5f3ff;"
            f"border:1px solid #ddd6fe;border-radius:8px;font-size:0.82em;"
            f"color:#5b21b6;display:flex;gap:8px;align-items:flex-start;'>"
            f"<span style='flex-shrink:0;'>⚙️</span>"
            f"<span style='white-space:pre-wrap;line-height:1.55;'>{_esc(text)}</span></div>")

def bubble_human(question, student_sol, badges_html=''):
    q_block = ''
    if question:
        q_block = (f"<div style='margin-bottom:12px;padding-bottom:12px;"
                   f"border-bottom:1px solid #e5e7eb;'>"
                   f"<div class='label'>题目</div>"
                   f"<div class='md'>{question}</div></div>")
    s_block = (f"<div><div class='label'>学生解答</div>"
               f"<div class='md'>{student_sol}</div></div>")
    return (f"<div class='msg-row msg-left'>"
            f"<div class='avatar av-student'>🧑‍🎓</div>"
            f"<div class='msg-body'>"
            f"<div class='msg-meta'><span class='msg-name'>学生</span>{badges_html}</div>"
            f"<div class='bubble bubble-student'>{q_block}{s_block}</div>"
            f"</div></div>")

def bubble_teacher(diagnosis, badges_html='', prefix_html=''):
    """prefix_html 是已渲染好的原始 HTML（如常见错误块），diagnosis 是 Markdown 文本。"""
    return (f"<div class='msg-row msg-right'>"
            f"<div class='msg-body'>"
            f"<div class='msg-meta right'>{badges_html}"
            f"<span class='msg-name'>教师诊断</span></div>"
            f"<div class='bubble bubble-teacher'>"
            f"{prefix_html}"
            f"<div class='md'>{diagnosis}</div>"
            f"</div></div>"
            f"<div class='avatar av-teacher'>👩‍🏫</div>"
            f"</div>")

# ──────────────────────────────────────────────
# 格式检测
# ──────────────────────────────────────────────

def detect_format(data):
    if isinstance(data, dict) and 'summary' in data:
        return 'quality_report'
    if isinstance(data, list) and data:
        first = data[0]
        if 'question_id' in first or 'student_cases' in first:
            return 'raw_data'
        if 'conversations' in first:
            return 'conversations'
    return 'unknown'

# ──────────────────────────────────────────────
# 各格式渲染
# ──────────────────────────────────────────────

def render_conversations(records):
    html, nav = '', ''
    for idx, rec in enumerate(records, 1):
        convs = rec.get('conversations', [])
        meta  = rec.get('_metadata', {})

        sys_text = human_msg = gpt_msg = ''
        for turn in convs:
            role, val = turn.get('from', ''), turn.get('value', '')
            if role == 'system':  sys_text  = val
            elif role == 'human': human_msg = val
            elif role == 'gpt':   gpt_msg   = val

        question, student_sol = parse_human(human_msg)
        kps   = meta.get('knowledge_points', [])
        level = meta.get('student_level', '')
        qs    = meta.get('quality_score', None)
        pc    = meta.get('process_correct', None)
        rc    = meta.get('result_correct', None)

        h_badges = ' '.join(filter(None, [
            level_badge(level), score_badge(qs),
            bool_badge(pc, '过程正确', '过程有误'),
            bool_badge(rc, '结果正确', '结果有误'),
        ]))

        html += (f'<div id="r{idx}">'
                 + topic_pills(kps) + system_banner(sys_text)
                 + bubble_human(question, student_sol, h_badges)
                 + bubble_teacher(gpt_msg or '（无诊断）')
                 + '</div>')
        nav += f'<a href="#r{idx}">对话 #{idx}</a>\n'
    return html, nav


def render_raw_data(records):
    html, nav = '', ''
    session = 0
    for rec in records:
        question = rec.get('question', '')
        analysis = rec.get('analysis', {})
        kps  = analysis.get('knowledge_points', [])
        diff = analysis.get('difficulty', None)
        common_errors = analysis.get('common_errors', [])

        for case in rec.get('student_cases', []):
            session += 1
            student_sol = case.get('student_solution', '')
            diagnosis   = case.get('diagnosis', '')
            level = case.get('student_level', '')
            qs    = case.get('quality_score', None)
            pc    = case.get('process_correct', None)
            rc    = case.get('result_correct', None)
            passed = case.get('passed', None)

            diff_badge_html = badge(f'难度 {diff}★', '#6366f1') if diff else ''
            h_badges = ' '.join(filter(None, [
                level_badge(level), score_badge(qs),
                bool_badge(pc, '过程正确', '过程有误'),
                bool_badge(rc, '结果正确', '结果有误'),
            ]))
            t_badges = ' '.join(filter(None, [
                diff_badge_html,
                bool_badge(passed, '审核通过', '审核未通过'),
            ]))

            # 该题常见错误 → 拼在教师诊断最前面
            err_prefix = ''
            if common_errors:
                items = ''.join(
                    f"<li style='font-size:0.85em;color:#92400e;margin:4px 0;'>{_esc(e)}</li>"
                    for e in common_errors
                )
                err_prefix = (
                    f"<div style='margin-bottom:14px;padding-bottom:12px;"
                    f"border-bottom:1px solid #d1fae5;'>"
                    f"<div style='font-weight:700;color:#065f46;margin-bottom:6px;'>"
                    f"【该题常见错误】</div>"
                    f"<ul style='margin:0 0 0 16px;padding:0;list-style:disc;'>{items}</ul>"
                    f"</div>"
                )

            html += (
                f'<div id="r{session}">'
                + topic_pills(kps)
                + bubble_human(question, student_sol, h_badges)
                + bubble_teacher(diagnosis, t_badges, prefix_html=err_prefix)
                + '</div>'
            )
            nav += f'<a href="#r{session}">对话 #{session}</a>\n'
    return html, nav


def render_quality_report(data):
    s = data.get('summary', {})

    def stat_card(label, value, color='#6366f1'):
        return (f"<div style='background:white;border:1px solid #e2e8f0;"
                f"border-radius:14px;padding:20px 24px;text-align:center;"
                f"box-shadow:0 2px 8px #0000000a;'>"
                f"<div style='font-size:2em;font-weight:800;color:{color};'>{value}</div>"
                f"<div style='font-size:0.82em;color:#6b7280;margin-top:4px;'>{label}</div></div>")

    cards_html = (
        f"<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));"
        f"gap:16px;margin:24px 0;'>" +
        stat_card('题目总数',    s.get('总题目数', '-'),    '#6366f1') +
        stat_card('学生案例',    s.get('总学生案例数', '-'), '#8b5cf6') +
        stat_card('通过审核',    s.get('通过审核数', '-'),   '#10b981') +
        stat_card('通过率',      s.get('通过率', '-'),       '#10b981') +
        stat_card('训练数据',    s.get('最终训练数据', '-'), '#3b82f6') +
        stat_card('平均质量分',  s.get('平均质量分', '-'),   '#f59e0b') +
        "</div>"
    )

    details = data.get('per_question_details', [])
    rows = ''
    for d in details:
        kps_str = '、'.join(d.get('knowledge_points', []))
        stars   = '★' * (d.get('difficulty') or 0) or '-'
        rows += (f"<tr>"
                 f"<td style='padding:10px 14px;border-bottom:1px solid #f1f5f9;"
                 f"font-size:0.85em;max-width:280px;'>"
                 f"{_esc(d.get('question_preview','')[:70])}…</td>"
                 f"<td style='padding:10px;border-bottom:1px solid #f1f5f9;"
                 f"text-align:center;color:#f59e0b;'>{stars}</td>"
                 f"<td style='padding:10px 14px;border-bottom:1px solid #f1f5f9;"
                 f"font-size:0.78em;color:#64748b;'>{_esc(kps_str)}</td>"
                 f"<td style='padding:10px;border-bottom:1px solid #f1f5f9;"
                 f"text-align:center;'>{d.get('student_cases_count',0)}</td>"
                 f"<td style='padding:10px;border-bottom:1px solid #f1f5f9;"
                 f"text-align:center;color:#10b981;font-weight:700;'>"
                 f"{d.get('avg_quality_score',0):.1f}</td></tr>")

    table_html = ''
    if rows:
        table_html = (
            f"<div style='background:white;border-radius:14px;overflow:hidden;"
            f"border:1px solid #e2e8f0;box-shadow:0 2px 8px #0000000a;'>"
            f"<div style='padding:16px 20px;border-bottom:1px solid #f1f5f9;"
            f"font-weight:700;color:#374151;'>逐题详情</div>"
            f"<table style='width:100%;border-collapse:collapse;font-size:0.88em;'>"
            f"<thead><tr style='background:#f8fafc;'>"
            f"<th style='padding:10px 14px;text-align:left;color:#475569;font-weight:600;'>题目预览</th>"
            f"<th style='padding:10px;color:#475569;font-weight:600;'>难度</th>"
            f"<th style='padding:10px 14px;text-align:left;color:#475569;font-weight:600;'>知识点</th>"
            f"<th style='padding:10px;color:#475569;font-weight:600;'>案例数</th>"
            f"<th style='padding:10px;color:#475569;font-weight:600;'>均分</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></div>"
        )

    return cards_html + table_html, ''

# ──────────────────────────────────────────────
# CSS / JS
# ──────────────────────────────────────────────

PAGE_CSS = """
*, *::before, *::after { box-sizing: border-box; }

body {
  font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', Arial, sans-serif;
  background: #f1f5f9;
  margin: 0; padding: 0;
  color: #1e293b;
  line-height: 1.7;
  font-size: 15px;
}

/* ── 顶栏 ── */
.topbar {
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
  color: white;
  padding: 0 28px;
  height: 58px;
  display: flex;
  align-items: center;
  gap: 14px;
  box-shadow: 0 2px 16px #4f46e540;
  position: sticky; top: 0; z-index: 200;
}
.topbar h1 { margin: 0; font-size: 1.1em; font-weight: 700; }
.topbar .meta { font-size: 0.78em; opacity: .75; margin-top: 2px; }
.topbar-icon { font-size: 1.5em; }

/* ── 布局 ── */
.layout { display: flex; min-height: calc(100vh - 58px); }

/* ── 侧边导航 ── */
.sidebar {
  width: 200px;
  flex-shrink: 0;
  background: white;
  border-right: 1px solid #e2e8f0;
  position: sticky;
  top: 58px;
  height: calc(100vh - 58px);
  overflow-y: auto;
  padding: 18px 0 24px;
}
.sidebar h4 {
  margin: 0 0 10px 16px;
  font-size: 0.72em;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: #94a3b8;
  font-weight: 700;
}
.sidebar a {
  display: block;
  padding: 7px 18px;
  font-size: 0.83em;
  color: #475569;
  text-decoration: none;
  transition: background .12s, color .12s, border-left .12s;
  border-left: 3px solid transparent;
}
.sidebar a:hover {
  background: #f1f5f9;
  color: #4f46e5;
  border-left-color: #4f46e5;
}

/* ── 主内容区 ── */
.main {
  flex: 1;
  min-width: 0;
  padding: 28px 36px 72px;
  overflow: hidden;
}

/* ── 对话卡片 ── */
.chat-session {
  background: white;
  border-radius: 18px;
  padding: 24px 28px;
  margin-bottom: 24px;
  box-shadow: 0 2px 16px #0000000a;
  border: 1px solid #e2e8f0;
}

/* ── 消息气泡行 ── */
.msg-row {
  display: flex;
  gap: 14px;
  margin: 18px 0;
}
.msg-left  { justify-content: flex-start; }
.msg-right { justify-content: flex-end; }

.avatar {
  flex-shrink: 0;
  width: 40px; height: 40px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.15em;
  box-shadow: 0 2px 8px #00000018;
  align-self: flex-start;
}
.av-student { background: linear-gradient(135deg,#6366f1,#8b5cf6); }
.av-teacher { background: linear-gradient(135deg,#059669,#10b981); }

.msg-body { flex: 1; min-width: 0; max-width: 85%; }
.msg-meta {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 7px;
  flex-wrap: wrap;
}
.msg-meta.right { justify-content: flex-end; }
.msg-name { font-weight: 700; font-size: 0.88em; color: #374151; }

.bubble {
  padding: 16px 20px;
  border-radius: 4px 16px 16px 16px;
  box-shadow: 0 2px 10px #0000000d;
  line-height: 1.75;
}
.bubble-student {
  background: #ffffff;
  border: 1px solid #e5e7eb;
}
.bubble-teacher {
  background: linear-gradient(145deg,#f0fdf4,#ecfdf5);
  border: 1px solid #bbf7d0;
  border-radius: 16px 4px 16px 16px;
}

/* ── 辅助 ── */
.label {
  font-size: 0.72em;
  font-weight: 700;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: .07em;
  margin-bottom: 4px;
}
.section-label {
  font-size: 0.74em;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .07em;
  margin-right: 6px;
}

/* ── Markdown 内容 ── */
.md p  { margin: .4em 0; }
.md ul, .md ol { padding-left: 1.5em; margin: .4em 0; }
.md li { margin: .25em 0; }
.md strong { font-weight: 700; }
.md h1,.md h2,.md h3 { margin: .8em 0 .4em; line-height: 1.3; }
.md h1 { font-size: 1.15em; }
.md h2 { font-size: 1.05em; }
.md h3 { font-size: 0.97em; }
.md code {
  background: #f1f5f9;
  border-radius: 4px;
  padding: 1px 5px;
  font-size: .88em;
  font-family: 'JetBrains Mono', Consolas, monospace;
}
.md pre {
  background: #1e293b;
  color: #e2e8f0;
  padding: 14px 18px;
  border-radius: 10px;
  overflow-x: auto;
  font-size: .85em;
}
.md pre code { background: none; padding: 0; }
.md blockquote {
  border-left: 3px solid #a78bfa;
  margin: .6em 0;
  padding: .2em .8em;
  color: #6b7280;
  background: #faf5ff;
  border-radius: 0 6px 6px 0;
}

@media (max-width: 768px) {
  .sidebar { display: none; }
  .main { padding: 16px; }
  .msg-body { max-width: 95%; }
  .path-track { flex-direction: column; }
  .path-step::after { display: none; }
}
"""

PAGE_JS = """
marked.setOptions({ breaks: true, gfm: true });

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.md').forEach(el => {
    const raw = el.textContent || el.innerText || '';
    el.innerHTML = marked.parse(raw);
  });

  renderMathInElement(document.body, {
    delimiters: [
      {left: '$$', right: '$$', display: true},
      {left: '$',  right: '$',  display: false},
      {left: '\\\\[', right: '\\\\]', display: true},
      {left: '\\\\(', right: '\\\\)', display: false}
    ],
    throwOnError: false
  });

  // 高亮当前导航项
  const links = document.querySelectorAll('.sidebar a');
  const observer = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        links.forEach(a => a.style.borderLeftColor = 'transparent');
        const a = document.querySelector('.sidebar a[href="#' + e.target.id + '"]');
        if (a) a.style.borderLeftColor = '#4f46e5';
      }
    });
  }, { threshold: 0.1, rootMargin: '-60px 0px -60% 0px' });

  document.querySelectorAll('[id^="r"]').forEach(el => observer.observe(el));
});

document.addEventListener('click', function(e) {
  const a = e.target.closest('a[href^="#"]');
  if (!a) return;
  e.preventDefault();
  const t = document.querySelector(a.getAttribute('href'));
  if (t) t.scrollIntoView({ behavior: 'smooth', block: 'start' });
});
"""

# ──────────────────────────────────────────────
# 页面组装
# ──────────────────────────────────────────────

def generate_html(body_html, nav_html, title, records_info):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    nav_block = (f"<div class='sidebar'><h4>快速导航</h4>{nav_html}</div>"
                 if nav_html else '')
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>{_esc(title)}</title>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
  <style>{PAGE_CSS}</style>
</head>
<body>
  <div class="topbar">
    <span class="topbar-icon">💬</span>
    <div>
      <h1>{_esc(title)}</h1>
      <div class="meta">{now} &nbsp;·&nbsp; {_esc(records_info)}</div>
    </div>
  </div>
  <div class="layout">
    {nav_block}
    <div class="main">
      {body_html}
    </div>
  </div>
  <script>{PAGE_JS}</script>
</body>
</html>"""


# ──────────────────────────────────────────────
# 把每段对话包进 chat-session 卡片
# ──────────────────────────────────────────────

def wrap_sessions(raw_html):
    parts = re.split(r'(<div id="r\d+">)', raw_html)
    result = ''
    i = 0
    while i < len(parts):
        if re.match(r'<div id="r\d+">', parts[i]):
            anchor  = parts[i]
            content = parts[i + 1] if i + 1 < len(parts) else ''
            result += f"<div class='chat-session'>{anchor}{content}</div>"
            i += 2
        else:
            result += parts[i]
            i += 1
    return result


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    in_path  = os.path.join(script_dir, INPUT_FILE)
    out_path = os.path.join(script_dir, OUTPUT_FILE)

    print(f"读取文件: {in_path}")
    try:
        with open(in_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[ERR] 找不到文件: {in_path}")
        return

    fmt = detect_format(data)
    print(f"检测到格式: {fmt}")

    if fmt == 'quality_report':
        body_html, nav_html = render_quality_report(data)
        n = len(data.get('per_question_details', []))
        final_html = generate_html(body_html, nav_html,
                                   "质量报告仪表板", f"共 {n} 道题")

    elif fmt == 'raw_data':
        total = sum(len(r.get('student_cases', [])) for r in data)
        if total > MAX_DISPLAY:
            all_pairs = [(r, c) for r in data for c in r.get('student_cases', [])]
            if RANDOM_SEED is not None:
                random.seed(RANDOM_SEED)
            sampled = random.sample(all_pairs, MAX_DISPLAY)
            from collections import defaultdict
            new_data = []
            for r, c in sampled:
                found = next((x for x in new_data if x.get('_oid') == id(r)), None)
                if not found:
                    entry = {k: v for k, v in r.items() if k != 'student_cases'}
                    entry['student_cases'] = []
                    entry['_oid'] = id(r)
                    new_data.append(entry)
                    found = new_data[-1]
                found['student_cases'].append(c)
            data = new_data
            print(f"随机抽样 {MAX_DISPLAY}/{total} 条案例")
        body_html, nav_html = render_raw_data(data)
        body_html = wrap_sessions(body_html)
        info = (f"{total} 条案例" if total <= MAX_DISPLAY
                else f"显示 {MAX_DISPLAY}/{total} 条案例（随机抽样）")
        final_html = generate_html(body_html, nav_html,
                                   "数学诊断训练数据 · 原始格式", info)

    elif fmt == 'conversations':
        total = len(data)
        if total > MAX_DISPLAY:
            if RANDOM_SEED is not None:
                random.seed(RANDOM_SEED)
            data = random.sample(data, MAX_DISPLAY)
            print(f"随机抽样 {MAX_DISPLAY}/{total} 条对话")
        body_html, nav_html = render_conversations(data)
        body_html = wrap_sessions(body_html)
        info = (f"共 {total} 条对话" if total <= MAX_DISPLAY
                else f"显示 {MAX_DISPLAY}/{total} 条（随机抽样）")
        has_meta = any('_metadata' in r for r in data)
        title = "诊断训练数据" + ("（含元数据）" if has_meta else "（Minimal）")
        final_html = generate_html(body_html, nav_html, title, info)

    else:
        print("[WARN] 未能识别数据格式，请检查文件")
        return

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(final_html)
    print(f"[OK] 已生成: {out_path}")

    if AUTO_OPEN:
        try:
            webbrowser.open('file:///' + out_path.replace(os.sep, '/'))
            print("[OK] 已在浏览器打开")
        except Exception:
            print("提示: 请手动打开文件查看")


if __name__ == '__main__':
    main()
