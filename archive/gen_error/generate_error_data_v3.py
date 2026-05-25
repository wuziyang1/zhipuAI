"""
    生成学生错误解答数据脚本 - V3版本（优化版）

    功能说明：
    - 读取训练集中的数学题目和正确解析
    - 使用CoT（思维链）让模型自然地犯错，而不是指定错误类型
    - 按照配置的比例生成错误/正确解答（默认7:3）

    版本演进：
    - V1：固定错误位置（第2步），固定错误类型（3种）
    - V2：随机错误位置，随机错误类型（6种），但仍然指定错误类型
    - V3（本版本）：使用CoT让模型自然犯错，不固定错误类型和位置

    核心特性：
    1. 使用CoT引导模型思考如何犯错（更自然）
    2. 不固定错误类型（让模型自己决定）
    3. 不固定错误位置（可以在任何步骤）
    4. 随机分配正确/错误（避免位置偏见）
    5. 高温度参数（0.9）增加错误多样性

    优化特性：
    6. API重试机制（最多3次，指数退避）
    7. 错误验证（确保错误解答真的不同于正确答案）
    8. 增量保存（每10条保存一次结果）
    9. 失败记录单独保存
    10. 改进的CoT prompt（明确要求参考正确解析故意犯错）

    设计理念：
    - 让模型"扮演"一个真实的学生，而不是"执行"犯错指令
    - 通过内心思考引导，让错误更自然地发生
    - 不限制错误类型，允许各种可能的错误
    - 确保数据质量和生成成功率

    适用场景：
    - 需要高质量、自然的错误数据
    - 希望错误类型多样化
    - 追求真实学生的错误分布
    - 需要稳定的批量数据生成

    备注：
    - 如需完全不给答案的版本，可使用 generate_error_data_v2.py
    - V3是目前推荐使用的版本
"""

import json
import os
import random
import time
from google import genai
from dotenv import load_dotenv

# ==================== 配置参数 ====================
# 输入输出路径配置
INPUT_TRAIN_DATA = 'data/train_sharegpt.json'  # 训练集路径
OUTPUT_DIR = 'output/error_solutions'  # 输出目录
OUTPUT_FILE = 'error_solutionsv3.json'  # 输出文件名
FAILED_FILE = 'error_solutions_v3_failed.json'  # 失败记录文件名

# 数据处理配置
NUM_RECORDS = 10  # 处理的记录数量（前N条）
ERROR_RATIO = 0.7  # 错误解答的比例（0-1之间，0.7表示70%错误，30%正确）
RANDOM_SEED = 42  # 随机种子（None表示每次随机，设置数字可固定结果）
SAVE_INTERVAL = 10  # 每处理多少条记录保存一次结果

# 模型参数配置
TEMPERATURE_CORRECT = 0.3  # 生成正确解答的温度（较低，更确定）
TEMPERATURE_ERROR = 0.9  # 生成错误解答的温度（较高，更随机，增加多样性）
MAX_OUTPUT_TOKENS = 8192  # 最大输出token数

# API重试配置
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 1  # 初始重试延迟（秒）
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

def call_api_with_retry(prompt, temperature, max_retries=MAX_RETRIES):
    """带重试机制的API调用"""
    for attempt in range(max_retries):
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
            if attempt < max_retries - 1:
                delay = RETRY_DELAY * (2 ** attempt)  # 指数退避
                print(f"  ⚠ API调用失败 (尝试 {attempt + 1}/{max_retries}): {str(e)[:100]}")
                print(f"  等待 {delay} 秒后重试...")
                time.sleep(delay)
            else:
                print(f"  ✗ API调用失败，已达最大重试次数: {str(e)[:100]}")
                return None
    return None

def verify_solution_difference(student_solution, correct_solution):
    """
    验证学生解答与正确解答是否有实质性差异
    简单的启发式检查：比较文本相似度
    """
    if not student_solution or not correct_solution:
        return False
    
    # 移除空格和换行符进行比较
    student_clean = ''.join(student_solution.split())
    correct_clean = ''.join(correct_solution.split())
    
    # 如果完全相同，说明没有错误
    if student_clean == correct_clean:
        return False
    
    # 如果长度差异很大，说明有实质性不同
    len_diff = abs(len(student_clean) - len(correct_clean))
    if len_diff > len(correct_clean) * 0.3:  # 差异超过30%
        return True
    
    # 简单的字符差异检查
    diff_count = sum(1 for a, b in zip(student_clean, correct_clean) if a != b)
    similarity = 1 - (diff_count / max(len(student_clean), len(correct_clean)))
    
    # 如果相似度低于95%，认为有差异
    return similarity < 0.95

def generate_correct_solution(question, correct_solution):
    """调用模型生成正确的学生解答（模仿学生的解题风格）"""
    prompt = f"""给定以下数学题目和正确解析，请你扮演一个认真学习的高中生，生成一个完全正确的解答。

要求：
1. 使用学生的语言风格，不要完全照搬标准答案
2. 解题步骤要清晰完整
3. 每一步都要正确
4. 请按照'第一步：... 第二步：...'的格式输出

题目：
{question}

正确解析（供参考）：
{correct_solution}

请生成一个完全正确的学生解答："""

    return call_api_with_retry(prompt, TEMPERATURE_CORRECT)

def generate_error_solution(question, correct_solution, max_attempts=3):
    """
    调用模型生成包含错误的解答
    使用CoT（思维链）让模型自然地犯错，不固定错误类型
    包含错误验证机制
    """
    prompt = f"""你是一个正在学习数学的高中生，但你经常会犯一些错误。现在请你解答下面这道题。

题目：
{question}

正确解析（供你参考，但你要故意在某个步骤犯错）：
{correct_solution}

请按照以下思路完成：

【内心思考】（这部分不要输出，只是引导你的思考）
- 我看到了正确解析，知道正确的解题思路和步骤
- 但我要模拟一个容易犯错的学生，所以我要参考正确解析，但故意在某个步骤犯错
- 我可能会犯这些错误：
  * 记错公式或定理（比如把平方差公式记混）
  * 计算时粗心大意（符号弄错、数字算错）
  * 理解题意有偏差（漏掉条件、误解题意）
  * 概念混淆（把相似的概念搞混）
  * 漏掉某些情况（忘记讨论某些情况）
- 我会在某个步骤自然地犯错，然后继续按错误结果往下算
- 我不知道自己犯了错，所以不会说"这里我犯了个错误"

【解答过程】（请输出这部分）
请按照'第一步：... 第二步：...'的格式输出你的解题步骤。
要求：
1. 参考正确解析的解题思路，但在某个步骤故意犯错
2. 犯错后继续计算，得出最终答案
3. 错误要像真实学生会犯的，不要太刻意
4. 不要说明"这里犯错"，要像真的不知道自己错了
5. 用学生的语气，不要太正式

现在开始解题："""

    # 尝试多次生成，直到生成的解答确实包含错误
    for attempt in range(max_attempts):
        student_solution = call_api_with_retry(prompt, TEMPERATURE_ERROR)
        
        if student_solution:
            # 验证是否真的包含错误
            if verify_solution_difference(student_solution, correct_solution):
                return student_solution
            else:
                print(f"  ⚠ 生成的解答与正确答案过于相似，重新生成 (尝试 {attempt + 1}/{max_attempts})")
        else:
            return None
    
    print(f"  ⚠ 多次尝试后仍无法生成有效的错误解答")
    return None

def save_results(data, output_path):
    """保存结果到JSON文件"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
    failed_records = []
    
    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    
    print(f"开始处理前 {len(records)} 条记录...")
    print(f"目标分布: {num_errors} 条错误 ({ERROR_RATIO*100:.0f}%), {num_correct} 条正确 ({(1-ERROR_RATIO)*100:.0f}%)")
    print(f"生成策略: 使用CoT让模型参考正确解析故意犯错")
    print(f"优化特性: API重试、错误验证、每{SAVE_INTERVAL}条保存一次")
    print(f"随机种子: {RANDOM_SEED}\n")
    
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
        if target_is_correct:
            student_solution = generate_correct_solution(question, correct_solution)
        else:
            student_solution = generate_error_solution(question, correct_solution)
        
        if student_solution:
            generated_data.append({
                "id": record.get("id", f"record_{idx}"),
                "question": question,
                "correct_solution": correct_solution,
                "knowledge_points": knowledge_points,
                "student_solution": student_solution,
                "is_correct": target_is_correct  # 标记是否为正确解答
            })
            print(f"✓ 成功生成{'正确' if target_is_correct else '错误'}解答")
        else:
            failed_records.append({
                "id": record.get("id", f"record_{idx}"),
                "question": question,
                "target": "正确" if target_is_correct else "错误",
                "reason": "API调用失败或生成失败"
            })
            print(f"✗ 生成失败")
        
        # 每处理SAVE_INTERVAL条记录，保存一次结果
        if idx % SAVE_INTERVAL == 0:
            save_results(generated_data, output_path)
            print(f"  💾 已保存前 {len(generated_data)} 条结果")
        
        print()
    
    # 保存最终结果
    save_results(generated_data, output_path)
    
    # 保存失败记录
    if failed_records:
        failed_path = os.path.join(OUTPUT_DIR, FAILED_FILE)
        with open(failed_path, 'w', encoding='utf-8') as f:
            json.dump(failed_records, f, ensure_ascii=False, indent=2)
    
    # 统计实际分布
    actual_correct = sum(1 for d in generated_data if d['is_correct'])
    actual_error = len(generated_data) - actual_correct
    
    # 输出统计报告
    print(f"\n{'='*60}")
    print("生成完成 - 统计报告")
    print(f"{'='*60}")
    print(f"总记录数: {len(generated_data)}/{NUM_RECORDS}")
    
    if len(generated_data) > 0:
        print(f"成功率: {len(generated_data)/NUM_RECORDS*100:.1f}%")
        print(f"\n实际分布:")
        print(f"  正确解答: {actual_correct} 条 ({actual_correct/len(generated_data)*100:.1f}%)")
        print(f"  错误解答: {actual_error} 条 ({actual_error/len(generated_data)*100:.1f}%)")
    else:
        print(f"成功率: 0.0%")
        print(f"\n⚠ 警告：所有记录生成失败！")
    
    print(f"\n目标分布:")
    print(f"  正确解答: {num_correct} 条 ({(1-ERROR_RATIO)*100:.0f}%)")
    print(f"  错误解答: {num_errors} 条 ({ERROR_RATIO*100:.0f}%)")
    
    if failed_records:
        print(f"\n失败记录: {len(failed_records)} 条")
        print(f"  详情已保存到: {os.path.join(OUTPUT_DIR, FAILED_FILE)}")
    
    print(f"\n结果已保存到: {output_path}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
