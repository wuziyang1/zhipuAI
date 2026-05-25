"""
诊断评价生成脚本 - V1版本（验证版）

功能说明：
- 读取包含学生解答的数据
- 使用LLM对学生解答进行诊断评价
- 模型可以看到正确解析和知识点（用于验证模型诊断能力）

与其他版本的区别：
- V1（本版本）：模型能看到正确解析 - 用于验证模型能力
- V2：模型看不到正确解析，但有知识点提示 - 更真实的场景
- V3：模型完全自主，连知识点都要自己判断 - 最接近实际应用

输入要求：
- 需要先运行 generate_error_data.py 生成学生解答数据

输出字段：
- 保留原有所有字段
- 新增 diagnosis: 诊断评价内容（包含诊断过程、结果、未掌握的知识点）

使用场景：
- 验证模型的诊断能力
- 作为baseline对比其他版本的效果
"""

import json
import os
from google import genai
from dotenv import load_dotenv

# ==================== 配置参数 ====================
# 输入输出路径配置
INPUT_FILE = 'output/error_solutions/error_solutionsv2.json'  # 输入文件路径
OUTPUT_DIR = 'output/diagnosis'  # 输出目录
OUTPUT_FILE = 'diagnosis_v1.json'  # 输出文件名

# 数据处理配置
NUM_RECORDS = None  # 处理的记录数量（None表示处理全部，或指定数字如10）

# 模型参数配置
TEMPERATURE = 0.3  # 温度参数，控制生成的随机性（0-1，越高越随机）
MAX_OUTPUT_TOKENS = 8192  # 最大输出token数
# ==================================================

# 加载环境变量
load_dotenv()

# 初始化客户端
client = genai.Client(
    api_key=os.getenv("Gemini_API_KEY"),
    http_options=genai.types.HttpOptions(
        base_url=os.getenv("Gemini_BASE_URL")
    )
)

def generate_diagnosis(question, correct_solution, student_solution, knowledge_points):
    """调用模型生成诊断评价"""
    knowledge_points_str = '、'.join(knowledge_points) if knowledge_points else '未指定'
    
    prompt = f"""你是一个数学老师评判模型。

已知题目：
{question}

正确解析：
{correct_solution}

涉及的知识点：
{knowledge_points_str}

请评估以下学生的解答：
{student_solution}

要求：
1. 逐步分析学生解答的对错
2. 指出最先出错的步骤和具体原因
3. 给出过程和结果是否正确的最终判断
4. 根据错误情况，判断学生在上述知识点中哪些没有掌握

请严格按照以下模板输出：

【诊断过程】
（逐步分析学生的每一步解答，指出哪一步开始出错，错误的具体原因是什么）

【诊断结果】
过程是否正确：[正确/错误]
结果是否正确：[正确/错误]
最先出错步骤：[第X步]
错误类型：[符号计算错误/公式记忆错误/粗心漏解/其他]
错误原因：[具体说明]

【未掌握的知识点】
（列出学生未掌握的知识点，从上述涉及的知识点中选择，如果全部掌握则说明"全部掌握"）
"""

    try:
        response = client.models.generate_content(
            model=os.getenv("Gemini_MODEL_NAME"),
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=TEMPERATURE,
                max_output_tokens=MAX_OUTPUT_TOKENS
            )
        )
        return response.text
    except Exception as e:
        print(f"API调用失败: {e}")
        return None

def main():
    # 读取之前生成的错误解答数据
    print(f"正在读取数据: {INPUT_FILE}")
    
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"错误：找不到文件 {INPUT_FILE}")
        print("请先运行 generate_error_data.py 生成错误解答数据")
        return
    
    print(f"共读取 {len(data)} 条记录\n")
    
    # 如果设置了NUM_RECORDS，只处理前N条
    if NUM_RECORDS is not None and NUM_RECORDS < len(data):
        data = data[:NUM_RECORDS]
        print(f"根据配置，只处理前 {NUM_RECORDS} 条记录\n")
    
    # 为每条记录生成诊断
    for idx, record in enumerate(data, 1):
        print(f"处理第 {idx}/{len(data)} 条记录...")
        print(f"题目ID: {record.get('id', 'unknown')}")
        
        # 生成诊断
        diagnosis = generate_diagnosis(
            question=record['question'],
            correct_solution=record['correct_solution'],
            student_solution=record['error_solution'],
            knowledge_points=record.get('knowledge_points', [])
        )
        
        if diagnosis:
            record['diagnosis'] = diagnosis
            print(f"✓ 成功生成诊断\n")
        else:
            record['diagnosis'] = None
            print(f"✗ 诊断生成失败\n")
    
    # 保存结果
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n完成！共处理 {len(data)} 条数据")
    print(f"结果已保存到: {output_path}")
    
    # 统计成功率
    success_count = sum(1 for record in data if record.get('diagnosis'))
    print(f"成功生成诊断: {success_count}/{len(data)} 条")

if __name__ == "__main__":
    main()
