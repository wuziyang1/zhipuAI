"""
诊断评价生成脚本 - V2版本（真实场景版）

功能说明：
- 读取包含学生解答的数据
- 使用LLM对学生解答进行诊断评价
- 模型看不到正确解析，需要自己解题后判断学生对错
- 模型仍然能看到题目涉及的知识点作为提示

与其他版本的区别：
- V1：模型能看到正确解析 - 用于验证模型能力
- V2（本版本）：模型看不到正确解析，但有知识点提示 - 更真实的场景
- V3：模型完全自主，连知识点都要自己判断 - 最接近实际应用

关键改进：
- 模型需要先自己解题（【解题分析】部分）
- 诊断结果不直接告诉学生正确答案，只指出错误和改进方向
- 增加了【改进建议】部分，更符合教学场景

输入要求：
- 需要先运行 generate_error_data.py 生成学生解答数据

输出字段：
- 保留原有所有字段
- 新增 diagnosis: 诊断评价内容（包含解题分析、诊断过程、结果、改进建议、未掌握的知识点）

使用场景：
- 模拟真实教学场景中的诊断
- 测试模型自主解题和判断的能力
"""

import json
import os
from google import genai
from dotenv import load_dotenv

# ==================== 配置参数 ====================
# 输入输出路径配置
INPUT_FILE = 'output/error_solutions/error_solutionsv2.json'  # 输入文件路径
OUTPUT_DIR = 'output/diagnosis'  # 输出目录
OUTPUT_FILE = 'diagnosis_v2.json'  # 输出文件名

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

def generate_realistic_diagnosis(question, student_solution, knowledge_points):
    """
    调用模型生成真实场景的诊断评价
    模型只能看到题目和学生解答，需要自行判断对错
    """
    knowledge_points_str = '、'.join(knowledge_points) if knowledge_points else '未指定'
    
    prompt = f"""你是一个数学老师评判模型。

题目：
{question}

该题涉及的知识点：
{knowledge_points_str}

学生的解答：
{student_solution}

请你作为数学老师，评估这个学生的解答。要求：
1. 首先自己解答这道题，得出正确答案
2. 逐步分析学生解答的每一步是否正确
3. 指出学生最先出错的步骤和具体原因（如果有错误）
4. 给出过程和结果是否正确的最终判断
5. 根据错误情况，判断学生在上述知识点中哪些没有掌握
6. 注意：不要在诊断结果中直接告诉学生正确答案，只指出错误和改进方向

请严格按照以下模板输出：

【解题分析】
（你作为老师对这道题的分析和正确解法思路，用于内部判断，不展示给学生）

【诊断过程】
（逐步分析学生的每一步解答，指出哪一步开始出错，错误的具体原因是什么）

【诊断结果】
过程是否正确：[正确/错误]
结果是否正确：[正确/错误]
最先出错步骤：[第X步/无错误]
错误类型：[符号计算错误/公式记忆错误/粗心漏解/概念理解错误/其他/无错误]
错误原因：[具体说明，不直接给出正确答案]

【改进建议】
（给学生的建议，帮助其理解错误，但不直接给出答案）

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
    
    # 为每条记录生成真实场景的诊断
    for idx, record in enumerate(data, 1):
        print(f"处理第 {idx}/{len(data)} 条记录...")
        print(f"题目ID: {record.get('id', 'unknown')}")
        
        # 生成真实场景的诊断（不使用正确解析）
        diagnosis = generate_realistic_diagnosis(
            question=record['question'],
            student_solution=record['error_solution'],
            knowledge_points=record.get('knowledge_points', [])
        )
        
        if diagnosis:
            record['diagnosis'] = diagnosis
            print(f"✓ 成功生成真实场景诊断\n")
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
    
    print("\n说明：")
    print("- V2版本：模型只根据题目和学生解答进行判断（真实场景）")
    print("- 模型会自己解题，然后对比学生答案")
    print("- 诊断结果不会直接告诉学生正确答案，只指出错误和改进方向")

if __name__ == "__main__":
    main()
