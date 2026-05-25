"""
从 raw_data.json 加载评测样本
"""

import json
import os
from typing import Any, Dict, List


def get_project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resolve_path(relative_path: str) -> str:
    return os.path.join(get_project_root(), relative_path)


def load_test_cases(
    raw_data_path: str,
    use_passed_only: bool = True,
    max_samples: int = None,
) -> List[Dict[str, Any]]:
    """
    加载评测样本

    每条样本包含：
        case_id, question_id, question, student_solution, student_level,
        knowledge_points, difficulty,
        gold_diagnosis, gold_labels (结构化 gold 标签)
    """
    full_path = resolve_path(raw_data_path)
    with open(full_path, 'r', encoding='utf-8') as f:
        records = json.load(f)

    cases = []
    for record in records:
        question_id = record['question_id']
        question = record['question']
        analysis = record.get('analysis', {})
        knowledge_points = analysis.get('knowledge_points', [])
        difficulty = analysis.get('difficulty')

        source_cases = record.get('passed_cases' if use_passed_only else 'student_cases', [])

        for idx, case in enumerate(source_cases):
            diagnosis = case.get('diagnosis', '')
            if not diagnosis:
                continue

            cases.append({
                'case_id': f"{question_id}_{case.get('student_level', idx)}",
                'question_id': question_id,
                'question': question,
                'student_solution': case['student_solution'],
                'student_level': case.get('student_level', 'unknown'),
                'target_correct': case.get('target_correct'),
                'knowledge_points': knowledge_points,
                'difficulty': difficulty,
                'gold_diagnosis': diagnosis,
                'gold_labels': {
                    'process_correct': case.get('process_correct'),
                    'result_correct': case.get('result_correct'),
                },
            })

    if max_samples is not None and max_samples < len(cases):
        cases = cases[:max_samples]

    return cases
