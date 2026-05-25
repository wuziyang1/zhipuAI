"""
诊断评价生成脚本 - V3版本（完全自主版）

功能说明：
- 读取包含学生解答的数据（包含正确和错误解答）
- 使用LLM对学生解答进行完全自主的诊断评价
- 模型只能看到题目和学生解答，需要自己判断一切
- 自动评估模型的诊断准确性

与其他版本的区别：
- V1：模型能看到正确解析 - 用于验证模型能力
- V2：模型看不到正确解析，但有知识点提示 - 更真实的场景
- V3（本版本）：模型完全自主，连知识点都要自己判断 - 最接近实际应用

关键特性：
1. 完全自主：模型需要自己分析题目涉及的知识点
2. 自我验证：通过正则表达式提取模型的判断结果
3. 准确率统计：对比模型判断与真实标签，计算诊断准确率
4. 隐藏真实标签：输出文件中不包含 is_correct 字段（仅内部使用）

输入要求：
- 需要先运行 generate_error_data.py 生成学生解答数据
- 输入数据必须包含 is_correct 字段（用于验证诊断准确性）

输出字段：
- 保留原有字段（除了 is_correct）
- 新增 diagnosis: 诊断评价内容
- 新增 diagnosis_correct: 模型诊断是否准确（True/False/None）

使用场景：
- 最接近实际应用的诊断场景
- 评估模型的完全自主诊断能力
- 发现模型的误判模式，用于优化prompt
"""

import json
import os
import re
from google import genai
from dotenv import load_dotenv

# ==================== 配置参数 ====================
# 输入输出路径配置
INPUT_FILE = 'output/error_solutions/error_solutionsv2.json'  # 输入文件路径
OUTPUT_DIR = 'output/diagnosis'  # 输出目录
OUTPUT_FILE = 'diagnosis_v3.json'  # 输出文件名

# 数据处理配置
NUM_RECORDS = 10  # 处理的记录数量（None表示处理全部，或指定数字如10）

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

def extract_diagnosis_result(diagnosis_text):
    """
    从诊断文本中提取模型的判断结果
    返回：(过程是否正确, 结果是否正确)
    """
    if not diagnosis_text:
        return None, None
    
    # 使用正则表达式提取"过程是否正确"和"结果是否正确"
    process_pattern = r'过程是否正确[：:]\s*[【\[]?(正确|错误)[】\]]?'
    result_pattern = r'结果是否正确[：:]\s*[【\[]?(正确|错误)[】\]]?'
    
    process_match = re.search(process_pattern, diagnosis_text)
    result_match = re.search(result_pattern, diagnosis_text)
    
    process_correct = None
    result_correct = None
    
    if process_match:
        process_correct = (process_match.group(1) == '正确')
    
    if result_match:
        result_correct = (result_match.group(1) == '正确')
    
    return process_correct, result_correct

def check_diagnosis_accuracy(student_is_correct, process_correct, result_correct):
    """
    检查模型的诊断是否准确
    
    参数：
    - student_is_correct: 学生答案是否正确（真实标签）
    - process_correct: 模型判断过程是否正确
    - result_correct: 模型判断结果是否正确
    
    返回：
    - diagnosis_correct: 模型诊断是否准确
    """
    # 如果无法提取模型的判断，返回None
    if process_correct is None and result_correct is None:
        return None
    
    # 优先使用结果判断，如果没有则使用过程判断
    model_judgment = result_correct if result_correct is not None else process_correct
    
    # 模型的判断与真实标签一致，则诊断正确
    return model_judgment == student_is_correct

def generate_fully_autonomous_diagnosis(question, student_solution):
    """
    调用模型生成完全自主的诊断评价
    模型只能看到题目和学生解答，需要：
    1. 自己解题
    2. 自己判断题目涉及的知识点
    3. 自己判断学生未掌握的知识点
    """
    
    prompt = f"""你是一个数学老师评判模型。

题目：
{question}

学生的解答：
{student_solution}

请你作为数学老师，评估这个学生的解答。要求：
1. 首先分析这道题目涉及哪些数学知识点
2. 自己解答这道题，得出正确答案
3. 逐步分析学生解答的每一步是否正确
4. 指出学生最先出错的步骤和具体原因（如果有错误）
5. 给出过程和结果是否正确的最终判断
6. 根据错误情况，判断学生在哪些知识点上存在欠缺
7. 注意：不要在诊断结果中直接告诉学生正确答案，只指出错误和改进方向

请严格按照以下模板输出：

【题目知识点分析】
（分析这道题目涉及哪些数学知识点，列出3-5个主要知识点）

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
（根据学生的错误，判断其在哪些知识点上存在欠缺。如果全部掌握则说明"全部掌握"）
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
    
    # 为每条记录生成完全自主的诊断
    correct_diagnosis_count = 0  # 统计诊断正确的数量
    
    for idx, record in enumerate(data, 1):
        print(f"处理第 {idx}/{len(data)} 条记录...")
        print(f"题目ID: {record.get('id', 'unknown')}")
        
        # 获取学生答案的真实标签
        student_is_correct = record.get('is_correct', None)
        if student_is_correct is not None:
            print(f"学生答案: {'正确' if student_is_correct else '错误'}")
        
        # 生成完全自主的诊断（不使用任何知识点提示）
        diagnosis = generate_fully_autonomous_diagnosis(
            question=record['question'],
            student_solution=record.get('student_solution') or record.get('error_solution', '')
        )
        
        if diagnosis:
            record['diagnosis'] = diagnosis
            
            # 提取模型的判断结果
            process_correct, result_correct = extract_diagnosis_result(diagnosis)
            
            # 检查诊断准确性
            if student_is_correct is not None:
                diagnosis_correct = check_diagnosis_accuracy(student_is_correct, process_correct, result_correct)
                record['diagnosis_correct'] = diagnosis_correct
                
                if diagnosis_correct is not None:
                    if diagnosis_correct:
                        correct_diagnosis_count += 1
                        print(f"模型判断: {'正确' if result_correct else '错误'} - ✓ 诊断准确")
                    else:
                        print(f"模型判断: {'正确' if result_correct else '错误'} - ✗ 诊断错误")
                else:
                    print(f"⚠ 无法从诊断中提取判断结果")
            else:
                record['diagnosis_correct'] = None
            
            print(f"✓ 成功生成完全自主诊断\n")
        else:
            record['diagnosis'] = None
            record['diagnosis_correct'] = None
            print(f"✗ 诊断生成失败\n")
    
    # 保存结果前，移除is_correct字段（这是用于验证的真实标签，不应该在输出中暴露）
    for record in data:
        if 'is_correct' in record:
            del record['is_correct']
    
    # 保存结果
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n完成！共处理 {len(data)} 条数据")
    print(f"结果已保存到: {output_path}")
    
    # 统计成功率
    success_count = sum(1 for record in data if record.get('diagnosis'))
    print(f"成功生成诊断: {success_count}/{len(data)} 条")
    
    # 统计诊断准确率
    valid_diagnosis = [r for r in data if r.get('diagnosis_correct') is not None]
    if valid_diagnosis:
        accuracy = correct_diagnosis_count / len(valid_diagnosis) * 100
        print(f"\n诊断准确率: {correct_diagnosis_count}/{len(valid_diagnosis)} ({accuracy:.1f}%)")
        print(f"  - 正确诊断: {correct_diagnosis_count} 条")
        print(f"  - 错误诊断: {len(valid_diagnosis) - correct_diagnosis_count} 条")
    
    print("\n说明：")
    print("- V3版本：完全自主诊断，模型只看题目和学生解答")
    print("- 模型自己判断题目涉及的知识点")
    print("- 模型自己解题，然后对比学生答案")
    print("- 模型自己判断学生未掌握的知识点")
    print("- 诊断结果不会直接告诉学生正确答案")
    print("- diagnosis_correct字段表示模型的诊断是否准确")
    print("- 最接近真实应用场景")

if __name__ == "__main__":
    main()
