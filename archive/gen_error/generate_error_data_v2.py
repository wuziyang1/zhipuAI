"""
生成学生错误解答数据脚本 - V2版本（后验证法）

功能说明：
- 读取训练集中的数学题目和正确解析
- 使用LLM生成模拟学生的解答（不给正确解析，更自然）
- 通过后验证确保生成符合预期的正确/错误解答
- 按照配置的比例生成错误/正确解答（默认7:3）

与V1的区别：
- V1：给模型看正确解析，让它"故意犯错" → 错误不自然
- V2：不给正确解析，让模型自然解题，然后验证结果 → 错误更真实

改进点：
1. 移除正确解析输入（更真实）
2. 添加答案验证机制（确保符合预期）
3. 添加重试机制（最多5次）
4. 随机分配正确/错误（避免位置偏见）
5. 不固定错误位置（让错误自然发生）

输出字段：
- id: 题目ID
- question: 题目内容
- correct_solution: 正确解析
- knowledge_points: 涉及的知识点列表
- student_solution: 学生的解答（可能正确或错误）
- is_correct: 标记学生解答是否正确
- generation_attempts: 生成尝试次数（用于分析）
"""

import json
import os
import random
import re
from google import genai
from dotenv import load_dotenv

# ==================== 配置参数 ====================
# 输入输出路径配置
INPUT_TRAIN_DATA = 'data/train_sharegpt.json'  # 训练集路径
OUTPUT_DIR = 'output/error_solutions'  # 输出目录
OUTPUT_FILE = 'error_solutions_v2.json'  # 输出文件名

# 数据处理配置
NUM_RECORDS = 10  # 处理的记录数量（前N条）
ERROR_RATIO = 0.7  # 错误解答的比例（0-1之间，0.7表示70%错误，30%正确）
RANDOM_SEED = 42  # 随机种子（None表示每次随机，设置数字可固定结果）

# 生成配置
MAX_ATTEMPTS = 5  # 每条数据最多尝试生成次数
ENABLE_RETRY = True  # 是否启用重试（如果生成结果不符合预期）

# 验证配置
VERIFICATION_METHOD = 'llm'  # 验证方法：'llm'（使用LLM判断）或 'extract'（提取答案对比）

# 模型参数配置
TEMPERATURE_CORRECT = 0.3  # 生成正确解答的温度（较低，更确定）
TEMPERATURE_ERROR = 0.8  # 生成错误解答的温度（较高，更随机）
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

def extract_question_info(conversation):
    """从对话中提取题目、解答过程和知识点"""
    question = ""
    solution = ""
    
    for msg in conversation:
        if msg["from"] == "human":
            question = msg["value"]
        elif msg["from"] == "gpt":
            solution = msg["value"]
    
    return question, solution

def call_llm(prompt, temperature):
    """调用LLM生成内容"""
    try:
        response = client.models.generate_content(
            model=os.getenv("Gemini_MODEL_NAME"),
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=MAX_OUTPUT_TOKENS
            )
        )
        return response.text
    except Exception as e:
        print(f"    ⚠ API调用失败: {str(e)[:100]}")
        return None

def extract_final_answer(text):
    """
    从文本中提取最终答案
    支持多种格式：\\boxed{...}, 答案：..., 选X等
    """
    if not text:
        return None
    
    # 方法1：匹配 \boxed{答案}
    boxed_match = re.search(r'\\boxed\{([^}]+)\}', text)
    if boxed_match:
        return boxed_match.group(1).strip()
    
    # 方法2：匹配 答案：XXX 或 最终答案：XXX
    answer_patterns = [
        r'(?:最终)?答案[：:]\s*([^\n]+)',
        r'(?:所以|因此|故)(?:答案)?[是为]?\s*[：:]?\s*([^\n]+)',
    ]
    for pattern in answer_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    
    # 方法3：匹配选择题答案（选A、选B等）
    choice_match = re.search(r'选\s*([A-D])', text)
    if choice_match:
        return choice_match.group(1)
    
    # 方法4：如果都没匹配到，返回最后一行（可能是答案）
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if lines:
        return lines[-1]
    
    return None

def verify_solution_by_llm(student_solution, correct_solution):
    """
    使用LLM判断学生答案是否正确
    返回：True（正确）或 False（错误）
    """
    prompt = f"""请判断学生的解答是否正确。

正确解析：
{correct_solution}

学生解答：
{student_solution}

判断标准：
1. 如果学生的最终答案与正确答案一致，判断为"正确"
2. 如果学生的解题过程有错误，或最终答案不一致，判断为"错误"
3. 只需要回答"正确"或"错误"，不要解释

你的判断："""
    
    response = call_llm(prompt, temperature=0.0)
    
    if response:
        # 判断回复中是否包含"正确"
        return "正确" in response and "错误" not in response
    else:
        # 如果API调用失败，返回None表示无法判断
        return None

def verify_solution_by_extract(student_solution, correct_solution):
    """
    通过提取答案对比判断是否正确
    返回：True（正确）或 False（错误）
    """
    student_answer = extract_final_answer(student_solution)
    correct_answer = extract_final_answer(correct_solution)
    
    if not student_answer or not correct_answer:
        # 如果无法提取答案，返回None表示无法判断
        return None
    
    # 简单的字符串对比（可以根据需要增强）
    # 去除空格、标点符号等
    student_clean = re.sub(r'[^\w]', '', student_answer.lower())
    correct_clean = re.sub(r'[^\w]', '', correct_answer.lower())
    
    return student_clean == correct_clean

def verify_solution(student_solution, correct_solution):
    """
    验证学生解答是否正确
    根据配置选择验证方法
    """
    if VERIFICATION_METHOD == 'llm':
        return verify_solution_by_llm(student_solution, correct_solution)
    elif VERIFICATION_METHOD == 'extract':
        return verify_solution_by_extract(student_solution, correct_solution)
    else:
        print(f"    ⚠ 未知的验证方法: {VERIFICATION_METHOD}")
        return None

def generate_student_solution(question, correct_solution, target_is_correct):
    """
    生成学生解答（带验证和重试）
    
    参数：
    - question: 题目
    - correct_solution: 正确解析（仅用于验证，不给模型看）
    - target_is_correct: True表示需要正确答案，False表示需要错误答案
    
    返回：
    - student_solution: 学生解答
    - is_actually_correct: 实际是否正确
    - attempts: 尝试次数
    """
    max_attempts = MAX_ATTEMPTS if ENABLE_RETRY else 1
    
    for attempt in range(max_attempts):
        # 根据目标调整prompt和温度
        if target_is_correct:
            # 生成正确解答
            prompt = f"""你是一个数学成绩优秀的高中生。请认真解答以下题目：

题目：
{question}

要求：
1. 仔细审题，确保理解题意
2. 按照'第一步：... 第二步：...'的格式输出解题步骤
3. 每一步都要仔细计算，确保准确
4. 最后给出明确的答案

请开始解答："""
            temperature = TEMPERATURE_CORRECT
        else:
            # 生成错误解答
            prompt = f"""你是一个数学基础一般的高中生，有时会粗心或记错公式。请解答以下题目：

题目：
{question}

要求：
1. 按照'第一步：... 第二步：...'的格式输出解题步骤
2. 尽力解答，但可能会出现以下情况：
   - 公式记错（如 i² = 1 而不是 -1）
   - 符号算错（如正负号搞混）
   - 粗心漏解（如只求出一个解）
   - 概念混淆（如奇函数和偶函数搞混）
3. 即使不确定也要给出答案

请开始解答："""
            temperature = TEMPERATURE_ERROR
        
        # 调用LLM生成
        student_solution = call_llm(prompt, temperature)
        
        if not student_solution:
            print(f"    ⚠ 第{attempt+1}次生成失败（API错误）")
            continue
        
        # 验证答案是否正确
        is_actually_correct = verify_solution(student_solution, correct_solution)
        
        if is_actually_correct is None:
            print(f"    ⚠ 第{attempt+1}次验证失败（无法判断正确性）")
            # 如果无法验证，假设符合预期
            return student_solution, target_is_correct, attempt + 1
        
        # 检查是否符合预期
        if is_actually_correct == target_is_correct:
            print(f"    ✓ 第{attempt+1}次尝试成功（需要{'正确' if target_is_correct else '错误'}，实际{'正确' if is_actually_correct else '错误'}）")
            return student_solution, is_actually_correct, attempt + 1
        else:
            print(f"    ⚠ 第{attempt+1}次不符合预期（需要{'正确' if target_is_correct else '错误'}，实际{'正确' if is_actually_correct else '错误'}），重试...")
    
    # 如果多次尝试都失败，返回最后一次的结果
    print(f"    ⚠ 经过{max_attempts}次尝试未能生成符合预期的解答，使用最后一次结果")
    return student_solution, is_actually_correct, max_attempts

def main():
    # 设置随机种子
    if RANDOM_SEED is not None:
        random.seed(RANDOM_SEED)
    
    # 读取训练集
    print("正在读取训练集...")
    with open(INPUT_TRAIN_DATA, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 只处理前N条记录
    records = data[:NUM_RECORDS]
    
    # 计算错误和正确的数量
    num_errors = int(NUM_RECORDS * ERROR_RATIO)
    num_correct = NUM_RECORDS - num_errors
    
    # 创建随机分配列表（True=正确，False=错误）
    target_list = [False] * num_errors + [True] * num_correct
    random.shuffle(target_list)  # 随机打乱
    
    # 存储生成的数据
    generated_data = []
    
    # 统计信息
    stats = {
        'total': NUM_RECORDS,
        'target_correct': num_correct,
        'target_error': num_errors,
        'actual_correct': 0,
        'actual_error': 0,
        'match_target': 0,
        'total_attempts': 0
    }
    
    print(f"开始处理前 {len(records)} 条记录...")
    print(f"目标分布: {num_errors} 条错误 ({ERROR_RATIO*100:.0f}%), {num_correct} 条正确 ({(1-ERROR_RATIO)*100:.0f}%)")
    print(f"验证方法: {VERIFICATION_METHOD}")
    print(f"重试机制: {'启用（最多{MAX_ATTEMPTS}次）' if ENABLE_RETRY else '禁用'}\n")
    
    for idx, record in enumerate(records, 1):
        print(f"{'='*60}")
        print(f"处理第 {idx}/{len(records)} 条记录")
        
        # 提取信息
        question, correct_solution = extract_question_info(record["conversations"])
        knowledge_points = record.get("knowledgePoints", [])
        
        print(f"题目: {question[:50]}...")
        print(f"知识点: {', '.join(knowledge_points)}")
        
        # 获取目标（正确/错误）
        target_is_correct = target_list[idx - 1]
        print(f"目标: {'正确解答' if target_is_correct else '错误解答'}")
        
        # 生成学生解答
        student_solution, is_actually_correct, attempts = generate_student_solution(
            question, correct_solution, target_is_correct
        )
        
        if student_solution:
            # 更新统计
            stats['total_attempts'] += attempts
            if is_actually_correct:
                stats['actual_correct'] += 1
            else:
                stats['actual_error'] += 1
            if is_actually_correct == target_is_correct:
                stats['match_target'] += 1
            
            generated_data.append({
                "id": record.get("id", f"record_{idx}"),
                "question": question,
                "correct_solution": correct_solution,
                "knowledge_points": knowledge_points,
                "student_solution": student_solution,
                "is_correct": is_actually_correct,
                "generation_attempts": attempts
            })
            print(f"✓ 成功生成{'正确' if is_actually_correct else '错误'}解答（尝试{attempts}次）\n")
        else:
            print(f"✗ 生成失败\n")
    
    # 保存结果
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(generated_data, f, ensure_ascii=False, indent=2)
    
    # 输出统计报告
    print(f"\n{'='*60}")
    print("生成完成 - 统计报告")
    print(f"{'='*60}")
    print(f"总记录数: {len(generated_data)}/{stats['total']}")
    print(f"\n【目标分布】")
    print(f"目标正确: {stats['target_correct']} 条")
    print(f"目标错误: {stats['target_error']} 条")
    print(f"\n【实际分布】")
    print(f"实际正确: {stats['actual_correct']} 条")
    print(f"实际错误: {stats['actual_error']} 条")
    print(f"\n【匹配度】")
    print(f"符合目标: {stats['match_target']}/{len(generated_data)} ({stats['match_target']/len(generated_data)*100:.1f}%)")
    print(f"平均尝试次数: {stats['total_attempts']/len(generated_data):.1f} 次")
    print(f"\n结果已保存到: {output_path}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
