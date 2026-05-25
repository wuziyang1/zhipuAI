"""
诊断数据可视化脚本

功能说明：
- 读取诊断结果JSON文件（V1/V2/V3/V4任意版本）
- 生成HTML可视化页面，支持Markdown和LaTeX渲染
- 自动处理大数据集（超过10条随机抽样）
- 提供右侧导航栏快速跳转

主要特性：
1. 兼容性：自动识别不同版本的字段名
   - student_solution / error_solution
   - diagnosis / realistic_diagnosis
   - diagnosis_correct (V3/V4)
   - diagnosis_quality (V4)
2. Markdown渲染：使用marked.js渲染题目和解答中的Markdown格式
3. LaTeX渲染：使用KaTeX渲染数学公式（支持 $...$ 和 $$...$$ 语法）
4. 智能抽样：数据量大时随机选择展示，避免页面过长
5. 诊断准确性标注：V3/V4版本会显示模型诊断是否准确
6. 诊断质量显示：V4版本会显示诊断完整度评分

输入要求：
- 需要先运行 generate_diagnosis.py / v2 / v3 / v4 生成诊断数据

输出：
- HTML文件，可直接在浏览器中打开
- 包含题目、知识点、正确解析、学生解答、诊断评价、质量评分等完整信息

使用场景：
- 查看和分析诊断结果
- 对比不同版本的诊断效果
- 发现模型的误判case
- 评估诊断质量
"""

import json
import os
import random
from datetime import datetime

# ==================== 配置参数 ====================
# 输入输出路径配置
INPUT_FILE = 'output/diagnosis/diagnosis_v4.json'  # 输入文件路径（可改为v1/v2/v3/v4）
OUTPUT_DIR = 'output/view_html'  # 输出目录
OUTPUT_FILE = 'visualization_v4.html'  # 输出HTML文件名

# 数据处理配置
MAX_DISPLAY_RECORDS = 10  # 最多展示的记录数量（如果数据超过此数量，随机选择）
RANDOM_SEED = None  # 随机种子（None表示每次随机，设置数字如42可固定随机结果）

# 是否自动打开浏览器
AUTO_OPEN_BROWSER = True  # True: 自动打开浏览器, False: 不自动打开
# ==================================================

def generate_html(data, total_records):
    """生成HTML页面"""
    
    # 生成记录HTML和导航链接
    records_html = ""
    navigation_links = ""
    
    for idx, record in enumerate(data, 1):
        record_id = record.get('id', f'record_{idx}')
        question = record.get('question', '无题目')
        correct_solution = record.get('correct_solution', '无正确解析')
        # 兼容新旧字段名
        student_solution = record.get('student_solution') or record.get('error_solution', '无学生解答')
        # 兼容两种字段名：diagnosis 和 realistic_diagnosis
        diagnosis = record.get('diagnosis') or record.get('realistic_diagnosis', '无诊断信息')
        knowledge_points = record.get('knowledge_points', [])
        
        # 获取诊断准确性（V3/V4版本有）
        diagnosis_correct = record.get('diagnosis_correct', None)
        
        # 获取诊断质量（仅V4版本有）
        diagnosis_quality = record.get('diagnosis_quality', None)
        
        # 知识点
        knowledge_points_str = '、'.join(knowledge_points) if knowledge_points else '未指定'
        
        # 诊断准确性标签
        diagnosis_label = ""
        if diagnosis_correct is not None:
            if diagnosis_correct:
                diagnosis_label = "<span style='color: green; font-weight: bold;'>[诊断准确 ✓]</span>"
            else:
                diagnosis_label = "<span style='color: red; font-weight: bold;'>[诊断错误 ✗]</span>"
        
        # 诊断质量信息（V4版本）
        quality_info = ""
        if diagnosis_quality is not None:
            completeness = diagnosis_quality.get('completeness', 0) * 100
            has_all_sections = diagnosis_quality.get('has_all_sections', False)
            quality_color = 'green' if has_all_sections else 'orange'
            quality_icon = '✓' if has_all_sections else '⚠'
            quality_info = f"<span style='color: {quality_color}; font-size: 0.9em;'>[完整度: {completeness:.0f}% {quality_icon}]</span>"
        
        # 生成单条记录HTML
        record_html = f"""
        <div class="record" id="record-{idx}">
            <h2>记录 #{idx} {diagnosis_label} {quality_info}</h2>
            <p><small>ID: {record_id}</small></p>
            
            <h3>题目</h3>
            <div class="markdown-content">{question}</div>
            
            <h3>涉及知识点</h3>
            <p>{knowledge_points_str}</p>
            
            <h3>正确解析</h3>
            <div class="markdown-content">{correct_solution}</div>
            
            <h3>学生解答</h3>
            <div class="markdown-content">{student_solution}</div>
            
            <h3>诊断评价</h3>
            <div class="markdown-content">{diagnosis}</div>
            
            <hr>
        </div>
        """
        
        records_html += record_html
        navigation_links += f'<a href="#record-{idx}">记录 #{idx}</a>\n'
    
    # 生成完整的HTML
    generation_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 显示记录信息
    if len(data) < total_records:
        records_info = f"显示 {len(data)}/{total_records} 条记录（随机抽样）"
    else:
        records_info = f"共 {total_records} 条记录"
    
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>数学题目诊断数据</title>
    
    <!-- Marked.js for Markdown rendering -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    
    <!-- KaTeX for LaTeX rendering -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
    
    <style>
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }}
        
        h1 {{
            border-bottom: 2px solid #333;
            padding-bottom: 10px;
        }}
        
        h2 {{
            margin-top: 30px;
            color: #0066cc;
        }}
        
        h3 {{
            margin-top: 20px;
            color: #333;
        }}
        
        .record {{
            margin-bottom: 40px;
        }}
        
        hr {{
            margin: 40px 0;
            border: none;
            border-top: 1px solid #ccc;
        }}
        
        .markdown-content {{
            background: #f9f9f9;
            padding: 15px;
            border-left: 3px solid #0066cc;
            margin: 10px 0;
        }}
        
        /* 导航栏样式 */
        .navigation {{
            position: fixed;
            right: 20px;
            top: 100px;
            width: 150px;
            background: white;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 15px;
            max-height: 70vh;
            overflow-y: auto;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        
        .navigation h4 {{
            margin-top: 0;
            margin-bottom: 10px;
            font-size: 14px;
            color: #333;
        }}
        
        .navigation a {{
            display: block;
            padding: 5px 10px;
            margin-bottom: 5px;
            color: #0066cc;
            text-decoration: none;
            border-radius: 3px;
            font-size: 13px;
        }}
        
        .navigation a:hover {{
            background: #f0f0f0;
        }}
        
        /* 移动端隐藏导航栏 */
        @media (max-width: 768px) {{
            .navigation {{
                display: none;
            }}
        }}
    </style>
</head>
<body>
    <h1>数学题目诊断数据</h1>
    <p>生成时间: {generation_time} | {records_info}</p>
    
    {records_html}
    
    <!-- 右侧导航栏 -->
    <div class="navigation">
        <h4>快速导航</h4>
        {navigation_links}
    </div>
    
    <script>
        // 配置marked.js
        marked.setOptions({{
            breaks: true,
            gfm: true
        }});
        
        // 页面加载完成后渲染
        document.addEventListener('DOMContentLoaded', function() {{
            // 渲染所有Markdown内容
            const markdownElements = document.querySelectorAll('.markdown-content');
            markdownElements.forEach(element => {{
                const originalText = element.textContent;
                element.innerHTML = marked.parse(originalText);
            }});
            
            // 渲染LaTeX数学公式
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
        
        // 平滑滚动
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {{
            anchor.addEventListener('click', function (e) {{
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {{
                    target.scrollIntoView({{
                        behavior: 'smooth',
                        block: 'start'
                    }});
                }}
            }});
        }});
    </script>
</body>
</html>"""
    
    return html_content

def main():
    # 读取数据
    print(f"正在读取数据: {INPUT_FILE}")
    
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"错误：找不到文件 {INPUT_FILE}")
        print("请先运行 generate_diagnosis.py / v2 / v3 / v4 生成诊断数据")
        return
    
    total_records = len(data)
    print(f"共读取 {total_records} 条记录")
    
    # 如果数据超过最大展示数量，随机选择
    if total_records > MAX_DISPLAY_RECORDS:
        if RANDOM_SEED is not None:
            random.seed(RANDOM_SEED)
        data = random.sample(data, MAX_DISPLAY_RECORDS)
        print(f"随机选择 {MAX_DISPLAY_RECORDS} 条记录进行展示")
    
    # 生成HTML
    print("正在生成HTML...")
    html_content = generate_html(data, total_records)
    
    # 保存HTML文件
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\n✓ 可视化页面已生成: {output_path}")
    
    # 尝试自动打开浏览器
    if AUTO_OPEN_BROWSER:
        try:
            import webbrowser
            abs_path = os.path.abspath(output_path)
            webbrowser.open(f'file://{abs_path}')
            print(f"✓ 已在浏览器中打开")
        except Exception as e:
            print(f"提示：请手动打开文件查看")
    else:
        print(f"提示：请手动打开文件查看")

if __name__ == "__main__":
    main()
