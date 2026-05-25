"""
多智能体训练数据可视化脚本

数据格式说明（batch_training_data.json）：
每条记录包含：
  - conversations: 对话列表
      [0] from="system"  : 系统提示词
      [1] from="human"   : 题目 + 学生解答（以"学生的解答："分隔）
      [2] from="gpt"     : 教师诊断回复
  - _metadata:
      knowledge_points : 知识点列表
      student_level    : 学生水平 (excellent / average / weak)
      quality_score    : 质量分数 (0~100)
      process_correct  : 过程是否正确
      result_correct   : 结果是否正确
"""

import json
import os
import random
import webbrowser
from datetime import datetime

# ==================== 配置参数 ====================
INPUT_FILE = 'examples/batch_training_data.json'
OUTPUT_FILE = 'visualization_training_data.html'

MAX_DISPLAY_RECORDS = 15    # 超过此数量时随机抽样
RANDOM_SEED = None          # None 表示每次随机；设为整数可固定结果
AUTO_OPEN_BROWSER = True
# ==================================================

LEVEL_LABEL = {
    'excellent': ('优秀', '#27ae60'),
    'average':   ('一般', '#f39c12'),
    'weak':      ('薄弱', '#e74c3c'),
}


def parse_human_message(text: str):
    """从 human 消息中拆分出题目和学生解答。"""
    question, student_solution = '', text
    if '学生的解答：' in text:
        parts = text.split('学生的解答：', 1)
        question_part = parts[0]
        student_solution = parts[1].strip()
        # 去掉前缀 "题目：\n"
        if '题目：' in question_part:
            question = question_part.split('题目：', 1)[1].strip()
        else:
            question = question_part.strip()
    return question, student_solution


def build_records_html(data):
    records_html = ''
    nav_links = ''

    for idx, record in enumerate(data, 1):
        conversations = record.get('conversations', [])
        metadata = record.get('_metadata', {})

        # 从对话中提取各部分
        system_prompt, human_msg, gpt_msg = '', '', ''
        for turn in conversations:
            role = turn.get('from', '')
            value = turn.get('value', '')
            if role == 'system':
                system_prompt = value
            elif role == 'human':
                human_msg = value
            elif role == 'gpt':
                gpt_msg = value

        question, student_solution = parse_human_message(human_msg)

        # 元数据
        knowledge_points = metadata.get('knowledge_points', [])
        student_level_key = metadata.get('student_level', '')
        quality_score = metadata.get('quality_score', None)
        process_correct = metadata.get('process_correct', None)
        result_correct = metadata.get('result_correct', None)

        kp_str = '、'.join(knowledge_points) if knowledge_points else '未指定'

        # 学生水平标签
        level_text, level_color = LEVEL_LABEL.get(
            student_level_key, (student_level_key or '未知', '#95a5a6')
        )
        level_badge = (
            f"<span style='background:{level_color};color:white;"
            f"padding:2px 8px;border-radius:3px;font-size:0.85em;'>"
            f"学生水平：{level_text}</span>"
        )

        # 质量分数
        score_html = ''
        if quality_score is not None:
            score_color = '#27ae60' if quality_score >= 90 else (
                '#f39c12' if quality_score >= 70 else '#e74c3c'
            )
            score_html = (
                f"<span style='color:{score_color};font-weight:bold;margin-left:10px;'>"
                f"质量分：{quality_score:.1f}</span>"
            )

        # 过程/结果正确性
        def bool_badge(val, true_text, false_text):
            if val is None:
                return ''
            color = '#27ae60' if val else '#e74c3c'
            icon = '✓' if val else '✗'
            text = true_text if val else false_text
            return (
                f"<span style='color:{color};margin-left:8px;font-size:0.9em;'>"
                f"[{icon} {text}]</span>"
            )

        process_badge = bool_badge(process_correct, '过程正确', '过程有误')
        result_badge = bool_badge(result_correct, '结果正确', '结果有误')

        records_html += f"""
        <div class="record" id="record-{idx}">
            <h2>记录 #{idx} &nbsp; {level_badge}{score_html}{process_badge}{result_badge}</h2>

            <h3>涉及知识点</h3>
            <p>{kp_str}</p>

            <h3>题目</h3>
            <div class="markdown-content">{question or human_msg}</div>

            <h3>学生解答</h3>
            <div class="markdown-content">{student_solution}</div>

            <h3>教师诊断</h3>
            <div class="markdown-content">{gpt_msg}</div>

            <details style="margin-top:10px;">
                <summary style="cursor:pointer;color:#888;font-size:0.9em;">系统提示词</summary>
                <pre style="background:#f0f0f0;padding:10px;font-size:0.85em;white-space:pre-wrap;">{system_prompt}</pre>
            </details>

            <hr>
        </div>
        """
        nav_links += f'<a href="#record-{idx}">记录 #{idx}</a>\n'

    return records_html, nav_links


def generate_html(data, total_records):
    records_html, nav_links = build_records_html(data)
    generation_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if len(data) < total_records:
        records_info = f"显示 {len(data)}/{total_records} 条记录（随机抽样）"
    else:
        records_info = f"共 {total_records} 条记录"

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>多智能体训练数据可视化</title>

    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>

    <style>
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px 20px 60px;
            line-height: 1.7;
        }}
        h1 {{ border-bottom: 2px solid #333; padding-bottom: 10px; }}
        h2 {{ margin-top: 30px; color: #0066cc; font-size: 1.1em; }}
        h3 {{ margin-top: 18px; color: #444; font-size: 1em; }}
        .record {{ margin-bottom: 40px; }}
        hr {{ margin: 40px 0; border: none; border-top: 1px solid #ddd; }}
        .markdown-content {{
            background: #f9f9f9;
            padding: 14px 16px;
            border-left: 3px solid #0066cc;
            margin: 8px 0;
            border-radius: 0 4px 4px 0;
        }}
        .navigation {{
            position: fixed;
            right: 20px;
            top: 100px;
            width: 150px;
            background: white;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 12px;
            max-height: 70vh;
            overflow-y: auto;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .navigation h4 {{ margin: 0 0 8px; font-size: 13px; color: #333; }}
        .navigation a {{
            display: block;
            padding: 4px 8px;
            margin-bottom: 4px;
            color: #0066cc;
            text-decoration: none;
            border-radius: 3px;
            font-size: 12px;
        }}
        .navigation a:hover {{ background: #f0f0f0; }}
        @media (max-width: 768px) {{ .navigation {{ display: none; }} }}
    </style>
</head>
<body>
    <h1>多智能体训练数据可视化</h1>
    <p>生成时间：{generation_time} &nbsp;|&nbsp; {records_info}</p>

    {records_html}

    <div class="navigation">
        <h4>快速导航</h4>
        {nav_links}
    </div>

    <script>
        marked.setOptions({{ breaks: true, gfm: true }});

        document.addEventListener('DOMContentLoaded', function() {{
            document.querySelectorAll('.markdown-content').forEach(el => {{
                el.innerHTML = marked.parse(el.textContent);
            }});

            renderMathInElement(document.body, {{
                delimiters: [
                    {{left: '$$', right: '$$', display: true}},
                    {{left: '$', right: '$', display: false}},
                    {{left: '\\\\[', right: '\\\\]', display: true}},
                    {{left: '\\\\(', right: '\\\\)', display: false}}
                ],
                throwOnError: false
            }});
        }});

        document.querySelectorAll('a[href^="#"]').forEach(a => {{
            a.addEventListener('click', function(e) {{
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
            }});
        }});
    </script>
</body>
</html>"""


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, INPUT_FILE)
    output_path = os.path.join(script_dir, OUTPUT_FILE)

    print(f"正在读取数据：{input_path}")
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"错误：找不到文件 {input_path}")
        return

    total_records = len(data)
    print(f"共读取 {total_records} 条记录")

    if total_records > MAX_DISPLAY_RECORDS:
        if RANDOM_SEED is not None:
            random.seed(RANDOM_SEED)
        data = random.sample(data, MAX_DISPLAY_RECORDS)
        print(f"随机抽取 {MAX_DISPLAY_RECORDS} 条记录展示")

    print("正在生成 HTML...")
    html = generate_html(data, total_records)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\n[OK] 可视化页面已生成：{output_path}")

    if AUTO_OPEN_BROWSER:
        try:
            webbrowser.open(f'file:///{output_path.replace(os.sep, "/")}')
            print("[OK] 已在浏览器中打开")
        except Exception:
            print("提示：请手动打开文件查看")
    else:
        print("提示：请手动打开文件查看")


if __name__ == '__main__':
    main()
