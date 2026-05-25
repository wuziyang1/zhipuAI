"""
诊断评价生成脚本 - V4版本（完全自主增强版）

功能说明：
- 在V3基础上进行全面优化
- 更精确的诊断准确性判断逻辑
- 更鲁棒的结果提取机制
- 完善的错误处理和重试机制
- 详细的统计分析（假阳性/假阴性）
- 自动保存检查点和误判案例

与V3的改进：
1. 更精细的准确性判断（区分过程和结果）
2. 多模式正则匹配（提高提取成功率）
3. API调用重试机制（指数退避）
4. 诊断质量评估（完整性检查）
5. 详细统计（假阳性、假阴性、按知识点统计）
6. 检查点保存（防止数据丢失）
7. 误判案例单独保存（便于分析）
8. 扩展配置参数（更灵活的控制）

输入要求：
- 需要先运行 generate_error_data.py 生成学生解答数据
- 输入数据必须包含 is_correct 字段（用于验证诊断准确性）

输出字段：
- 保留原有字段（除了 is_correct）
- 新增 diagnosis: 诊断评价内容
- 新增 diagnosis_correct: 模型诊断是否准确（True/False/None）
- 新增 diagnosis_quality: 诊断质量评分（可选）

使用场景：
- 生产环境的诊断应用
- 大规模数据处理
- 深度分析和优化
"""

import json
import os
import re
import time
import glob
from google import genai
from dotenv import load_dotenv

# ==================== 配置参数 ====================
# 输入输出路径配置
INPUT_FILE = 'output/error_solutions/error_solutionsv3.json'  # 输入文件路径
OUTPUT_DIR = 'output/diagnosis'  # 输出目录
OUTPUT_FILE = 'diagnosis_v4.json'  # 输出文件名

# 数据处理配置
NUM_RECORDS = None  # 处理的记录数量（None表示处理全部，或指定数字如10）

# 模型参数配置
TEMPERATURE = 0.3  # 温度参数，控制生成的随机性（0-1，越高越随机）
MAX_OUTPUT_TOKENS = 8192  # 最大输出token数

# 诊断配置
ENABLE_RETRY = True  # 是否启用重试
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 2  # 重试延迟基数（秒），使用指数退避
CHECKPOINT_INTERVAL = 10  # 检查点保存间隔（每N条保存一次）
ENABLE_QUALITY_CHECK = True  # 是否检查诊断质量

# 统计配置
SAVE_ERROR_CASES = True  # 是否单独保存误判案例
ERROR_CASES_FILE = 'diagnosis_v4_errors.json'  # 误判案例文件名
SAVE_CHECKPOINTS = True  # 是否保存检查点
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
    从诊断文本中提取模型的判断结果（增强版）
    使用多种模式匹配，提高提取成功率
    
    返回：(过程是否正确, 结果是否正确)
    """
    if not diagnosis_text:
        return None, None
    
    # 多种模式匹配 - 过程判断
    process_patterns = [
        r'过程是否正确[：:]\s*[【\[]?(正确|错误|是|否)[】\]]?',
        r'过程[：:]\s*[【\[]?(正确|错误|是|否)[】\]]?',
        r'解题过程[：:]\s*[【\[]?(正确|错误|是|否)[】\]]?',
    ]
    
    # 多种模式匹配 - 结果判断
    result_patterns = [
        r'结果是否正确[：:]\s*[【\[]?(正确|错误|是|否)[】\]]?',
        r'结果[：:]\s*[【\[]?(正确|错误|是|否)[】\]]?',
        r'最终结果[：:]\s*[【\[]?(正确|错误|是|否)[】\]]?',
    ]
    
    process_correct = None
    result_correct = None
    
    # 尝试提取过程判断
    for pattern in process_patterns:
        match = re.search(pattern, diagnosis_text)
        if match:
            word = match.group(1)
            process_correct = word in ['正确', '是']
            break
    
    # 尝试提取结果判断
    for pattern in result_patterns:
        match = re.search(pattern, diagnosis_text)
        if match:
            word = match.group(1)
            result_correct = word in ['正确', '是']
            break
    
    return process_correct, result_correct

def check_diagnosis_accuracy(student_is_correct, process_correct, result_correct):
    """
    检查模型的诊断是否准确（优化版）
    更精细的判断逻辑，区分过程和结果
    
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
    
    # 学生完全正确：结果应该被判为正确，过程也应该正确（如果有判断的话）
    if student_is_correct:
        # 优先看结果判断
        if result_correct is not None:
            # 结果判断正确，且过程判断（如果有）也正确或未判断
            if result_correct and (process_correct is None or process_correct):
                return True
            else:
                return False
        # 如果没有结果判断，只看过程判断
        elif process_correct is not None:
            return process_correct
        else:
            return None
    
    # 学生有错误：至少结果或过程应该被判为错误
    else:
        # 优先看结果判断
        if result_correct is not None:
            # 结果判断为错误，则诊断正确
            if not result_correct:
                return True
            # 结果判断为正确，但过程判断为错误，也算诊断正确（发现了过程错误）
            elif process_correct is not None and not process_correct:
                return True
            else:
                return False
        # 如果没有结果判断，只看过程判断
        elif process_correct is not None:
            return not process_correct
        else:
            return None

def evaluate_diagnosis_quality(diagnosis_text):
    """
    评估诊断的完整性和质量
    
    返回：质量评分字典
    """
    if not diagnosis_text:
        return {
            'completeness': 0.0,
            'has_process': False,
            'has_result': False,
            'length': 0,
            'has_all_sections': False
        }
    
    required_sections = [
        '【题目知识点分析】',
        '【解题分析】',
        '【诊断过程】',
        '【诊断结果】',
        '【改进建议】',
        '【未掌握的知识点】'
    ]
    
    sections_found = sum(1 for s in required_sections if s in diagnosis_text)
    
    quality_score = {
        'completeness': sections_found / len(required_sections),
        'has_process': '过程是否正确' in diagnosis_text,
        'has_result': '结果是否正确' in diagnosis_text,
        'length': len(diagnosis_text),
        'has_all_sections': sections_found == len(required_sections)
    }
    
    return quality_score

def generate_fully_autonomous_diagnosis(question, student_solution, max_retries=None):
    """
    调用模型生成完全自主的诊断评价（增强版）
    添加重试机制和错误处理
    
    模型只能看到题目和学生解答，需要：
    1. 自己解题
    2. 自己判断题目涉及的知识点
    3. 自己判断学生未掌握的知识点
    """
    
    if max_retries is None:
        max_retries = MAX_RETRIES if ENABLE_RETRY else 1
    
    prompt = f"""你是一个数学老师评判模型。

题目：
{question}

学生的解答：
{student_solution}

请你作为数学老师，评估这个学生的解答。要求：
1. 首先分析这道题目涉及哪些数学知识点
2. 自己解答这道题，得出正确答案
3. 逐步分析学生解答的每一步是否正确
4. 如果解答有错误，指出学生最先出错的步骤和具体原因
5. 给出过程和结果是否正确的最终判断
6. 根据错误情况，判断学生在哪些知识点上存在欠缺
7. 注意：不要在诊断结果中直接告诉学生正确答案，只指出错误和改进方向

请严格按照以下模板输出：

【题目知识点分析】
（分析这道题目涉及哪些数学知识点，列出3-5个主要知识点）

【解题分析】
（你作为老师对这道题的分析和正确解法思路，用于内部判断，不展示给学生）

【诊断过程】
（逐步分析学生的每一步解答，如有错误指出哪一步开始出错，错误的具体原因是什么）

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

    for attempt in range(max_retries):
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
            print(f"  ⚠ API调用失败 (尝试 {attempt+1}/{max_retries}): {str(e)[:100]}")
            if attempt < max_retries - 1:
                delay = RETRY_DELAY ** attempt  # 指数退避
                print(f"  等待 {delay} 秒后重试...")
                time.sleep(delay)
            else:
                print(f"  ✗ 达到最大重试次数，放弃")
                return None
    
    return None

def save_checkpoint(data, idx, output_dir):
    """保存检查点"""
    if not SAVE_CHECKPOINTS:
        return
    
    checkpoint_path = os.path.join(output_dir, f'diagnosis_v4_checkpoint_{idx}.json')
    # 临时保存，不删除is_correct字段
    with open(checkpoint_path, 'w', encoding='utf-8') as f:
        json.dump(data[:idx], f, ensure_ascii=False, indent=2)
    print(f"  💾 已保存检查点: {checkpoint_path}")

def cleanup_checkpoints(output_dir):
    """清理所有检查点文件"""
    if not SAVE_CHECKPOINTS:
        return
    
    checkpoint_pattern = os.path.join(output_dir, 'diagnosis_v4_checkpoint_*.json')
    checkpoint_files = glob.glob(checkpoint_pattern)
    
    if checkpoint_files:
        print(f"\n正在清理 {len(checkpoint_files)} 个检查点文件...")
        for checkpoint_file in checkpoint_files:
            try:
                os.remove(checkpoint_file)
                print(f"  ✓ 已删除: {os.path.basename(checkpoint_file)}")
            except Exception as e:
                print(f"  ✗ 删除失败 {os.path.basename(checkpoint_file)}: {e}")
        print("✓ 检查点清理完成")

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
    
    # 统计变量
    correct_diagnosis_count = 0  # 诊断正确的数量
    false_positive_count = 0  # 假阳性：把错的判成对的
    false_negative_count = 0  # 假阴性：把对的判成错的
    extraction_failed_count = 0  # 无法提取判断结果的数量
    quality_issues_count = 0  # 质量问题的数量
    error_cases = []  # 误判案例
    
    # 为每条记录生成完全自主的诊断
    for idx, record in enumerate(data, 1):
        print(f"\n{'='*60}")
        print(f"处理第 {idx}/{len(data)} 条记录")
        print(f"题目ID: {record.get('id', 'unknown')}")
        
        # 获取学生答案的真实标签
        student_is_correct = record.get('is_correct', None)
        if student_is_correct is not None:
            print(f"学生答案: {'✓ 正确' if student_is_correct else '✗ 错误'}")
        
        # 生成完全自主的诊断（不使用任何知识点提示）
        diagnosis = generate_fully_autonomous_diagnosis(
            question=record['question'],
            student_solution=record.get('student_solution') or record.get('error_solution', '')
        )
        
        if diagnosis:
            record['diagnosis'] = diagnosis
            
            # 评估诊断质量
            if ENABLE_QUALITY_CHECK:
                quality = evaluate_diagnosis_quality(diagnosis)
                record['diagnosis_quality'] = quality
                
                if not quality['has_all_sections']:
                    quality_issues_count += 1
                    print(f"  ⚠ 诊断不完整 (完整度: {quality['completeness']*100:.0f}%)")
            
            # 提取模型的判断结果
            process_correct, result_correct = extract_diagnosis_result(diagnosis)
            
            if process_correct is None and result_correct is None:
                extraction_failed_count += 1
                print(f"  ⚠ 无法从诊断中提取判断结果")
            
            # 检查诊断准确性
            if student_is_correct is not None:
                diagnosis_correct = check_diagnosis_accuracy(student_is_correct, process_correct, result_correct)
                record['diagnosis_correct'] = diagnosis_correct
                
                if diagnosis_correct is not None:
                    model_judgment = result_correct if result_correct is not None else process_correct
                    
                    if diagnosis_correct:
                        correct_diagnosis_count += 1
                        print(f"  模型判断: {'✓ 正确' if model_judgment else '✗ 错误'}")
                        print(f"  诊断结果: ✓ 准确")
                    else:
                        # 区分假阳性和假阴性
                        if not student_is_correct and model_judgment:
                            false_positive_count += 1
                            error_type = "假阳性（把错的判成对的）"
                        elif student_is_correct and not model_judgment:
                            false_negative_count += 1
                            error_type = "假阴性（把对的判成错的）"
                        else:
                            error_type = "其他误判"
                        
                        print(f"  模型判断: {'✓ 正确' if model_judgment else '✗ 错误'}")
                        print(f"  诊断结果: ✗ 错误 ({error_type})")
                        
                        # 保存误判案例
                        if SAVE_ERROR_CASES:
                            error_cases.append({
                                'id': record.get('id'),
                                'student_is_correct': student_is_correct,
                                'model_judgment': model_judgment,
                                'error_type': error_type,
                                'question': record['question'][:100] + '...',
                                'diagnosis': diagnosis[:200] + '...'
                            })
            else:
                record['diagnosis_correct'] = None
            
            print(f"  ✓ 成功生成完全自主诊断")
        else:
            record['diagnosis'] = None
            record['diagnosis_correct'] = None
            if ENABLE_QUALITY_CHECK:
                record['diagnosis_quality'] = None
            print(f"  ✗ 诊断生成失败")
        
        # 定期保存检查点
        if SAVE_CHECKPOINTS and idx % CHECKPOINT_INTERVAL == 0:
            save_checkpoint(data, idx, OUTPUT_DIR)
    
    print(f"\n{'='*60}")
    print("处理完成，正在保存结果...")
    
    # 保存误判案例
    if SAVE_ERROR_CASES and error_cases:
        error_cases_path = os.path.join(OUTPUT_DIR, ERROR_CASES_FILE)
        with open(error_cases_path, 'w', encoding='utf-8') as f:
            json.dump(error_cases, f, ensure_ascii=False, indent=2)
        print(f"✓ 误判案例已保存到: {error_cases_path}")
    
    # 保存结果前，移除is_correct字段（这是用于验证的真实标签，不应该在输出中暴露）
    for record in data:
        if 'is_correct' in record:
            del record['is_correct']
    
    # 保存最终结果
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 最终结果已保存到: {output_path}")
    
    # 清理检查点文件
    cleanup_checkpoints(OUTPUT_DIR)
    
    # 详细统计报告
    print(f"\n{'='*60}")
    print("统计报告")
    print(f"{'='*60}")
    
    # 基本统计
    print(f"\n【基本统计】")
    print(f"总处理记录数: {len(data)}")
    success_count = sum(1 for record in data if record.get('diagnosis'))
    print(f"成功生成诊断: {success_count}/{len(data)} ({success_count/len(data)*100:.1f}%)")
    
    # 诊断准确率统计
    valid_diagnosis = [r for r in data if r.get('diagnosis_correct') is not None]
    if valid_diagnosis:
        accuracy = correct_diagnosis_count / len(valid_diagnosis) * 100
        print(f"\n【诊断准确率】")
        print(f"有效诊断数: {len(valid_diagnosis)}")
        print(f"准确诊断数: {correct_diagnosis_count}")
        print(f"错误诊断数: {len(valid_diagnosis) - correct_diagnosis_count}")
        print(f"准确率: {accuracy:.1f}%")
        
        # 误判类型统计
        if false_positive_count > 0 or false_negative_count > 0:
            print(f"\n【误判类型分析】")
            print(f"假阳性（把错的判成对的）: {false_positive_count} 条")
            print(f"假阴性（把对的判成错的）: {false_negative_count} 条")
            if false_positive_count > 0:
                print(f"  → 假阳性率: {false_positive_count/(false_positive_count+false_negative_count)*100:.1f}%")
            if false_negative_count > 0:
                print(f"  → 假阴性率: {false_negative_count/(false_positive_count+false_negative_count)*100:.1f}%")
    
    # 质量统计
    if ENABLE_QUALITY_CHECK:
        quality_records = [r for r in data if r.get('diagnosis_quality')]
        if quality_records:
            avg_completeness = sum(r['diagnosis_quality']['completeness'] for r in quality_records) / len(quality_records)
            print(f"\n【诊断质量】")
            print(f"平均完整度: {avg_completeness*100:.1f}%")
            print(f"完全符合格式: {sum(1 for r in quality_records if r['diagnosis_quality']['has_all_sections'])}/{len(quality_records)}")
            print(f"质量问题数: {quality_issues_count}")
    
    # 提取失败统计
    if extraction_failed_count > 0:
        print(f"\n【提取失败】")
        print(f"无法提取判断结果: {extraction_failed_count} 条")
        print(f"提取成功率: {(len(data)-extraction_failed_count)/len(data)*100:.1f}%")
    
    print(f"\n{'='*60}")
    print("V4版本特性说明")
    print(f"{'='*60}")
    print("✓ 完全自主诊断（模型只看题目和学生解答）")
    print("✓ 精细的准确性判断（区分过程和结果）")
    print("✓ 鲁棒的结果提取（多模式匹配）")
    print("✓ API重试机制（指数退避）")
    print("✓ 诊断质量评估（完整性检查）")
    print("✓ 详细统计分析（假阳性/假阴性）")
    print("✓ 检查点保存（防止数据丢失）")
    print("✓ 误判案例保存（便于分析优化）")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
