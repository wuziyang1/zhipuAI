"""
评测主流程
"""

import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from data_loader import load_test_cases, resolve_path
from metrics import aggregate_results, evaluate_single
from parser import parse_diagnosis
from prompt import build_case_prompt


class DiagnosisEvaluator:
    """数学诊断能力评测器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
        if not config.get('DRY_RUN'):
            from model_client import ModelClient
            self.client = ModelClient(config)

    def run(
        self,
        cases: List[Dict[str, Any]],
        predictions: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        执行评测

        Args:
            cases: 测试样本
            predictions: 可选，{case_id: diagnosis_text}，跳过模型推理
        """
        predictions = predictions or {}
        single_results = []
        raw_predictions = []

        print(f"\n开始评测 {len(cases)} 条样本...")
        print(f"模型: {self.config.get('MODEL_NAME', 'dry-run')}\n")

        for idx, case in enumerate(cases, 1):
            case_id = case['case_id']
            print(f"[{idx}/{len(cases)}] {case_id} ({case['student_level']})")

            if case_id in predictions:
                pred_text = predictions[case_id]
                print("  使用已有预测")
            elif self.config.get('DRY_RUN'):
                pred_text = case['gold_diagnosis']
                print("  [dry-run] 使用 gold 诊断")
            else:
                prompt = build_case_prompt(case)
                pred_text = self.client.generate(prompt)
                interval = self.config.get('REQUEST_INTERVAL', 0)
                if interval > 0:
                    time.sleep(interval)

            if not pred_text:
                print("  X 预测失败，跳过")
                raw_predictions.append({
                    'case_id': case_id,
                    'success': False,
                    'prediction': None,
                })
                continue

            result = evaluate_single(case, pred_text)
            single_results.append(result)
            raw_predictions.append({
                'case_id': case_id,
                'success': True,
                'prediction': pred_text,
                'metrics': result['metrics'],
            })

            flags = []
            flags.append('过程OK' if result['metrics']['process_match'] else '过程X')
            flags.append('结果OK' if result['metrics']['result_match'] else '结果X')
            print(f"  {' | '.join(flags)}")

        summary = aggregate_results(single_results)

        return {
            'meta': {
                'model': self.config.get('MODEL_NAME', 'dry-run'),
                'evaluated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'total_cases': len(cases),
                'successful_cases': len(single_results),
                'input_data': self.config.get('INPUT_RAW_DATA'),
                'dry_run': self.config.get('DRY_RUN', False),
            },
            'summary': summary,
            'details': single_results,
            'predictions': raw_predictions,
        }


def save_report(report: Dict[str, Any], output_dir: str) -> Dict[str, str]:
    """保存评测报告"""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    run_dir = os.path.join(resolve_path(output_dir), timestamp)
    os.makedirs(run_dir, exist_ok=True)

    report_path = os.path.join(run_dir, 'eval_report.json')
    predictions_path = os.path.join(run_dir, 'predictions.json')
    summary_path = os.path.join(run_dir, 'eval_summary.txt')

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    with open(predictions_path, 'w', encoding='utf-8') as f:
        json.dump(report['predictions'], f, ensure_ascii=False, indent=2)

    summary_text = format_summary(report)
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(summary_text)

    return {
        'run_dir': run_dir,
        'report': report_path,
        'predictions': predictions_path,
        'summary': summary_path,
    }


def format_summary(report: Dict[str, Any]) -> str:
    """格式化控制台/文本摘要"""
    meta = report['meta']
    s = report['summary']
    lines = [
        '=' * 60,
        '数学诊断能力评测报告',
        '=' * 60,
        f"模型: {meta['model']}",
        f"评测时间: {meta['evaluated_at']}",
        f"成功样本: {meta['successful_cases']}/{meta['total_cases']}",
        '',
        '--- 核心指标 ---',
    ]

    if s.get('total_samples', 0) == 0:
        lines.append('无有效样本')
        return '\n'.join(lines)

    ja = s['judgment_accuracy']
    el = s['error_localization']
    et = s['error_type_classification']

    lines.extend([
        f"过程判断准确率:     {ja['process_accuracy']}%",
        f"结果判断准确率:     {ja['result_accuracy']}%",
        f"过程+结果联合准确率: {ja['joint_accuracy']}%",
        f"错误步骤定位准确率: {el['exact_step_accuracy']}%  ({el['evaluable_samples']} 条可评)",
        f"错误步骤近似准确率: {el['close_step_accuracy']}%  (±1步)",
        f"错误类型分类准确率: {et['accuracy']}%  ({et['evaluable_samples']} 条可评)",
        f"输出格式完整率:     {s['format_completeness_rate']}%",
        '',
        '--- 过程判断 PRF (以「正确」为正类) ---',
        f"Precision: {s['process_prf']['precision']}%  Recall: {s['process_prf']['recall']}%  F1: {s['process_prf']['f1']}%",
        '',
        '--- 结果判断 PRF (以「正确」为正类) ---',
        f"Precision: {s['result_prf']['precision']}%  Recall: {s['result_prf']['recall']}%  F1: {s['result_prf']['f1']}%",
    ])

    if s.get('by_student_level'):
        lines.extend(['', '--- 按学生水平 ---'])
        for level, stats in s['by_student_level'].items():
            lines.append(
                f"  {level}: n={stats['count']}, "
                f"过程={stats['process_accuracy']}%, "
                f"结果={stats['result_accuracy']}%, "
                f"联合={stats['joint_accuracy']}%"
            )

    if s.get('by_difficulty'):
        lines.extend(['', '--- 按题目难度 ---'])
        for diff, stats in s['by_difficulty'].items():
            lines.append(
                f"  {diff}星: n={stats['count']}, "
                f"过程={stats['process_accuracy']}%, "
                f"结果={stats['result_accuracy']}%"
            )

    lines.append('=' * 60)
    return '\n'.join(lines)
