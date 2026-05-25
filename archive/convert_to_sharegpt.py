"""
诊断数据转换为ShareGPT格式脚本

功能说明：
- 读取V4版本的诊断结果JSON文件
- 将诊断数据转换为ShareGPT格式的训练数据
- 用于微调LLM模型进行数学题目诊断

ShareGPT格式说明：
{
  "conversations": [
    {"from": "human", "value": "题目 + 学生解答"},
    {"from": "gpt", "value": "诊断评价"}
  ],
  "id": "记录ID",
  "knowledgePoints": ["知识点列表"]
}

输入要求：
- 需要先运行 generate_diagnosisv4.py 生成诊断数据

输出：
- ShareGPT格式的训练数据JSON文件
- 可用于LLM微调训练

使用场景：
- 准备模型微调数据
- 训练专门的数学诊断模型
"""

import json
import os

# ==================== 配置参数 ====================
# 输入输出路径配置
INPUT_FILE = 'output/diagnosis/diagnosis_v4.json'  # 输入文件路径
OUTPUT_DIR = 'output/training_data'  # 输出目录
OUTPUT_FILE = 'diagnosis_sharegpt.json'  # 输出文件名

# 数据过滤配置
ONLY_CORRECT_DIAGNOSIS = False  # 是否只保留诊断正确的数据（True=只要准确的，False=全部保留）
MIN_QUALITY_SCORE = 0.0  # 最低质量分数（0.0-1.0，0表示不过滤）

# 提示词配置
INCLUDE_QUESTION_IN_PROMPT = True  # 是否在human部分包含题目
INCLUDE_CORRECT_SOLUTION = False  # 是否在human部分包含正确解析（不建议，会泄露答案）
INCLUDE_INSTRUCTION = True  # 是否包含任务指令（推荐，让模型明确知道要做什么）
USE_SHORT_INSTRUCTION = False  # True: 使用简短指令, False: 使用详细指令

# 输出格式配置
MINIMAL_FORMAT = True  # True: 只保留conversations字段（纯净版，用于微调）
                       # False: 保留所有字段（完整版，便于追踪）
USE_SYSTEM_MESSAGE = True  # True: 使用system消息（推荐，避免重复）
                           # False: 指令放在human消息中
# ==================================================

def get_system_instruction():
    """
    获取系统指令（用于system消息）
    """
    if not INCLUDE_INSTRUCTION:
        return None
    
    if USE_SHORT_INSTRUCTION:
        # 简短指令
        return "你是一个数学老师。请诊断以下学生的解答，指出错误并给出改进建议。"
    else:
        # 详细指令（与V4生成诊断时使用的prompt完全一致）
        return """你是一个数学老师评判模型。请评估以下学生的解答，要求：
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
（根据学生的错误，判断其在哪些知识点上存在欠缺。如果全部掌握则说明"全部掌握"）"""

def create_human_prompt(record):
    """
    构造human部分的提示词
    包含题目和学生解答
    """
    question = record.get('question', '')
    student_solution = record.get('student_solution') or record.get('error_solution', '')
    correct_solution = record.get('correct_solution', '')
    
    # 构造提示词
    prompt_parts = []
    
    # 如果不使用system消息，则需要在human消息中包含指令
    if INCLUDE_INSTRUCTION and not USE_SYSTEM_MESSAGE:
        if USE_SHORT_INSTRUCTION:
            # 简短指令
            instruction = "你是一个数学老师。请诊断以下学生的解答，指出错误并给出改进建议。"
        else:
            # 详细指令
            instruction = get_system_instruction()
        
        prompt_parts.append(instruction)
    
    if INCLUDE_QUESTION_IN_PROMPT:
        prompt_parts.append(f"\n题目：\n{question}")
    
    # 学生解答（必须包含）
    prompt_parts.append(f"\n学生的解答：\n{student_solution}")
    
    # 可选：包含正确解析（不建议，会让模型看到答案）
    if INCLUDE_CORRECT_SOLUTION:
        prompt_parts.append(f"\n正确解析：\n{correct_solution}")
    
    return "\n".join(prompt_parts)

def create_gpt_response(record):
    """
    构造gpt部分的回复
    即模型的诊断评价
    """
    diagnosis = record.get('diagnosis', '')
    return diagnosis

def should_include_record(record):
    """
    判断是否应该包含这条记录
    根据配置的过滤条件
    """
    # 检查诊断准确性
    if ONLY_CORRECT_DIAGNOSIS:
        diagnosis_correct = record.get('diagnosis_correct')
        if diagnosis_correct is not True:
            return False
    
    # 检查诊断质量
    if MIN_QUALITY_SCORE > 0:
        quality = record.get('diagnosis_quality')
        if quality is None:
            return False
        completeness = quality.get('completeness', 0)
        if completeness < MIN_QUALITY_SCORE:
            return False
    
    # 检查必需字段
    if not record.get('diagnosis'):
        return False
    
    student_solution = record.get('student_solution') or record.get('error_solution')
    if not student_solution:
        return False
    
    return True

def convert_to_sharegpt(data):
    """
    将诊断数据转换为ShareGPT格式
    """
    sharegpt_data = []
    filtered_count = 0
    
    # 获取系统指令（如果使用system消息）
    system_instruction = get_system_instruction() if USE_SYSTEM_MESSAGE else None
    
    for record in data:
        # 检查是否应该包含这条记录
        if not should_include_record(record):
            filtered_count += 1
            continue
        
        # 构造conversations
        conversations = []
        
        # 添加system消息（如果启用）
        if system_instruction:
            conversations.append({
                "from": "system",
                "value": system_instruction
            })
        
        # 添加human消息
        conversations.append({
            "from": "human",
            "value": create_human_prompt(record)
        })
        
        # 添加gpt消息
        conversations.append({
            "from": "gpt",
            "value": create_gpt_response(record)
        })
        
        # 根据配置选择输出格式
        if MINIMAL_FORMAT:
            # 纯净版：只保留conversations字段（用于微调）
            sharegpt_record = {
                "conversations": conversations
            }
        else:
            # 完整版：保留所有字段（便于追踪和分析）
            sharegpt_record = {
                "conversations": conversations,
                "id": record.get('id', ''),
                "knowledgePoints": record.get('knowledge_points', [])
            }
            
            # 可选：添加元数据（用于追踪，但不影响训练）
            if record.get('diagnosis_correct') is not None:
                sharegpt_record['_metadata'] = {
                    'diagnosis_correct': record.get('diagnosis_correct'),
                    'diagnosis_quality': record.get('diagnosis_quality')
                }
        
        sharegpt_data.append(sharegpt_record)
    
    return sharegpt_data, filtered_count

def main():
    # 读取诊断数据
    print(f"正在读取数据: {INPUT_FILE}")
    
    try:
        with open(INPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"错误：找不到文件 {INPUT_FILE}")
        print("请先运行 generate_diagnosisv4.py 生成诊断数据")
        return
    
    print(f"共读取 {len(data)} 条记录\n")
    
    # 转换为ShareGPT格式
    print("正在转换为ShareGPT格式...")
    sharegpt_data, filtered_count = convert_to_sharegpt(data)
    
    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 保存结果
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sharegpt_data, f, ensure_ascii=False, indent=2)
    
    # 统计报告
    print(f"\n{'='*60}")
    print("转换完成")
    print(f"{'='*60}")
    print(f"原始记录数: {len(data)}")
    print(f"过滤记录数: {filtered_count}")
    print(f"输出记录数: {len(sharegpt_data)}")
    print(f"保留比例: {len(sharegpt_data)/len(data)*100:.1f}%")
    print(f"\n结果已保存到: {output_path}")
    
    # 配置说明
    print(f"\n{'='*60}")
    print("配置说明")
    print(f"{'='*60}")
    print(f"输出格式: {'纯净版（只保留conversations）' if MINIMAL_FORMAT else '完整版（包含所有字段）'}")
    print(f"使用system消息: {'是' if USE_SYSTEM_MESSAGE else '否（指令在human消息中）'}")
    print(f"只保留诊断正确的数据: {'是' if ONLY_CORRECT_DIAGNOSIS else '否'}")
    print(f"最低质量分数: {MIN_QUALITY_SCORE}")
    print(f"包含题目: {'是' if INCLUDE_QUESTION_IN_PROMPT else '否'}")
    print(f"包含正确解析: {'是' if INCLUDE_CORRECT_SOLUTION else '否（推荐）'}")
    print(f"包含任务指令: {'是' if INCLUDE_INSTRUCTION else '否'}")
    if INCLUDE_INSTRUCTION:
        print(f"指令类型: {'简短指令' if USE_SHORT_INSTRUCTION else '详细指令'}")
    
    # 示例展示
    if sharegpt_data:
        print(f"\n{'='*60}")
        print("示例数据（第1条）")
        print(f"{'='*60}")
        example = sharegpt_data[0]
        
        if not MINIMAL_FORMAT:
            print(f"ID: {example.get('id', 'N/A')}")
            print(f"知识点: {', '.join(example.get('knowledgePoints', []))}")
        
        # 显示conversations结构
        print(f"\nConversations结构:")
        for i, msg in enumerate(example['conversations']):
            print(f"  [{i}] from: {msg['from']}")
            content_preview = msg['value'][:150].replace('\n', ' ')
            print(f"      value: {content_preview}...")
        
        # 如果有system消息，单独展示
        if USE_SYSTEM_MESSAGE and example['conversations'][0]['from'] == 'system':
            print(f"\nSystem消息（前200字符）:")
            print(example['conversations'][0]['value'][:200] + "...")
            print(f"\nHuman输入（前200字符）:")
            print(example['conversations'][1]['value'][:200] + "...")
            print(f"\nGPT回复（前200字符）:")
            print(example['conversations'][2]['value'][:200] + "...")
        else:
            print(f"\nHuman输入（前200字符）:")
            print(example['conversations'][0]['value'][:200] + "...")
            print(f"\nGPT回复（前200字符）:")
            print(example['conversations'][1]['value'][:200] + "...")
    
    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    main()
