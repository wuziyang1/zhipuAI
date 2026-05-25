"""
工具函数
"""

import json
import os
from typing import List, Dict, Any


def load_training_data(file_path: str, num_records: int = None) -> List[Dict[str, Any]]:
    """
    加载训练数据
    
    Args:
        file_path: 数据文件路径（相对于项目根目录）
        num_records: 加载的记录数量（None表示全部）
    
    Returns:
        题目列表
    """
    # 获取项目根目录（multi_agent_pipeline的上上级目录）
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    
    # 构建完整路径
    full_path = os.path.join(project_root, file_path)
    
    print(f"正在加载数据: {file_path}")
    print(f"完整路径: {full_path}")
    
    with open(full_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 提取题目信息
    questions = []
    for idx, record in enumerate(data):
        # 从conversations中提取题目和解答
        conversations = record.get('conversations', [])
        
        question = ''
        correct_solution = ''
        
        for msg in conversations:
            if msg['from'] == 'human':
                question = msg['value']
            elif msg['from'] == 'gpt':
                correct_solution = msg['value']
        
        questions.append({
            'id': record.get('id', f'question_{idx+1}'),
            'question': question,
            'correct_solution': correct_solution,
            'knowledge_points': record.get('knowledgePoints', [])
        })
    
    # 限制数量
    if num_records is not None and num_records < len(questions):
        questions = questions[:num_records]
        print(f"根据配置，只加载前{num_records}条记录")
    
    print(f"成功加载{len(questions)}条题目")
    
    return questions


def save_json(data: Any, file_path: str, indent: int = 2):
    """
    保存JSON文件
    
    Args:
        data: 要保存的数据
        file_path: 文件路径（相对于项目根目录）
        indent: 缩进空格数
    """
    # 获取项目根目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    
    # 构建完整路径
    full_path = os.path.join(project_root, file_path)
    
    # 确保目录存在
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    with open(full_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    
    print(f"✓ 已保存: {file_path}")


def generate_quality_report(results: Dict[str, Any], output_path: str):
    """
    生成质量报告
    
    Args:
        results: Pipeline处理结果
        output_path: 输出路径
    """
    statistics = results['overall_statistics']
    all_results = results['all_results']
    
    report = {
        'summary': {
            '总题目数': statistics['total_questions'],
            '总学生案例数': statistics['total_student_cases'],
            '通过审核数': statistics['total_passed_cases'],
            '被拒绝数': statistics['total_rejected_cases'],
            '通过率': f"{statistics['pass_rate']:.1f}%",
            '最终训练数据': statistics['total_training_samples'],
            '平均质量分': f"{statistics['overall_avg_quality']:.1f}"
        },
        'per_question_details': []
    }
    
    # 每个题目的详细信息
    for result in all_results:
        detail = {
            'question_id': result['question_id'],
            'question_preview': result['question'][:100] + '...',
            'difficulty': result['analysis'].get('difficulty', 'N/A'),
            'knowledge_points': result['analysis'].get('knowledge_points', []),
            'student_cases_count': len(result['student_cases']),
            'passed_count': len(result['passed_cases']),
            'rejected_count': len(result['rejected_cases']),
            'avg_quality_score': result['statistics'].get('avg_quality_score', 0)
        }
        report['per_question_details'].append(detail)
    
    save_json(report, output_path)


def generate_minimal_training_data(training_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    生成纯净版训练数据（移除元数据）
    
    Args:
        training_data: 完整的训练数据
    
    Returns:
        纯净版训练数据（只保留conversations）
    """
    minimal_data = []
    
    for item in training_data:
        minimal_item = {
            'conversations': item['conversations']
        }
        minimal_data.append(minimal_item)
    
    return minimal_data


def print_sample_data(training_data: List[Dict[str, Any]], num_samples: int = 1):
    """
    打印示例数据
    
    Args:
        training_data: 训练数据
        num_samples: 打印的示例数量
    """
    print(f"\n{'='*60}")
    print(f"示例数据（前{num_samples}条）")
    print(f"{'='*60}")
    
    for idx, item in enumerate(training_data[:num_samples], 1):
        print(f"\n--- 示例 {idx} ---")
        
        conversations = item.get('conversations', [])
        
        for msg in conversations:
            role = msg['from']
            content = msg['value']
            
            # 截断显示
            if len(content) > 200:
                content = content[:200] + '...'
            
            print(f"\n[{role.upper()}]")
            print(content)
        
        # 显示元数据
        metadata = item.get('_metadata', {})
        if metadata:
            print(f"\n[元数据]")
            print(f"  知识点: {', '.join(metadata.get('knowledge_points', []))}")
            print(f"  学生水平: {metadata.get('student_level', 'N/A')}")
            print(f"  质量分: {metadata.get('quality_score', 'N/A')}")
    
    print(f"\n{'='*60}\n")
