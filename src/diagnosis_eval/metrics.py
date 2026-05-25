"""
评测指标计算
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional

from parser import parse_diagnosis


def _safe_eq(a, b) -> bool:
    return a is not None and b is not None and a == b


def _confusion(labels: List[bool], preds: List[bool]) -> Dict[str, int]:
    tp = fp = tn = fn = 0
    for gold, pred in zip(labels, preds):
        if gold and pred:
            tp += 1
        elif not gold and pred:
            fp += 1
        elif not gold and not pred:
            tn += 1
        else:
            fn += 1
    return {'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn}


def _rate(num: int, denom: int) -> Optional[float]:
    return round(num / denom * 100, 2) if denom > 0 else None


def _precision_recall_f1(cm: Dict[str, int]) -> Dict[str, Optional[float]]:
    tp, fp, fn = cm['tp'], cm['fp'], cm['fn']
    precision = _rate(tp, tp + fp)
    recall = _rate(tp, tp + fn)
    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = round(2 * precision * recall / (precision + recall), 2)
    return {'precision': precision, 'recall': recall, 'f1': f1}


def evaluate_single(gold: Dict[str, Any], pred_text: str) -> Dict[str, Any]:
    """对单条样本计算指标"""
    pred = parse_diagnosis(pred_text)

    # 优先使用 raw_data 中的 gold 标签，缺失时从 gold 诊断文本解析
    gold_process = gold['gold_labels'].get('process_correct')
    gold_result = gold['gold_labels'].get('result_correct')
    gold_parsed = parse_diagnosis(gold['gold_diagnosis'])

    if gold_process is None:
        gold_process = gold_parsed['process_correct']
    if gold_result is None:
        gold_result = gold_parsed['result_correct']

    gold_error_step = gold_parsed['error_step']
    gold_error_type = gold_parsed['error_type']

    pred_process = pred['process_correct']
    pred_result = pred['result_correct']
    pred_error_step = pred['error_step']
    pred_error_type = pred['error_type']

    return {
        'case_id': gold['case_id'],
        'student_level': gold['student_level'],
        'difficulty': gold.get('difficulty'),
        'gold': {
            'process_correct': gold_process,
            'result_correct': gold_result,
            'error_step': gold_error_step,
            'error_type': gold_error_type,
        },
        'pred': {
            'process_correct': pred_process,
            'result_correct': pred_result,
            'error_step': pred_error_step,
            'error_type': pred_error_type,
            'format_complete': pred['format']['complete'],
            'completeness_score': pred['format']['completeness_score'],
        },
        'metrics': {
            'process_match': _safe_eq(gold_process, pred_process),
            'result_match': _safe_eq(gold_result, pred_result),
            'joint_match': (
                _safe_eq(gold_process, pred_process) and _safe_eq(gold_result, pred_result)
            ),
            'error_step_match': (
                gold_error_step is not None
                and pred_error_step is not None
                and gold_error_step == pred_error_step
            ),
            'error_step_close': (
                gold_error_step is not None
                and pred_error_step is not None
                and gold_error_step > 0
                and pred_error_step > 0
                and abs(gold_error_step - pred_error_step) <= 1
            ),
            'error_type_match': (
                gold_error_type is not None
                and pred_error_type is not None
                and gold_error_type == pred_error_type
            ),
            'format_complete': pred['format']['complete'],
        },
    }


def aggregate_results(single_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """汇总全部样本指标"""
    n = len(single_results)
    if n == 0:
        return {'total_samples': 0}

    # --- 过程 / 结果判断 ---
    process_pairs = [
        (r['gold']['process_correct'], r['pred']['process_correct'])
        for r in single_results
        if r['gold']['process_correct'] is not None and r['pred']['process_correct'] is not None
    ]
    result_pairs = [
        (r['gold']['result_correct'], r['pred']['result_correct'])
        for r in single_results
        if r['gold']['result_correct'] is not None and r['pred']['result_correct'] is not None
    ]

    process_cm = _confusion([g for g, _ in process_pairs], [p for _, p in process_pairs])
    result_cm = _confusion([g for g, _ in result_pairs], [p for _, p in result_pairs])

    # --- 错误定位（仅 gold 过程错误样本）---
    error_cases = [
        r for r in single_results
        if r['gold']['process_correct'] is False and r['gold']['error_step'] not in (None, 0)
    ]
    error_step_evaluable = [
        r for r in error_cases
        if r['pred']['error_step'] is not None
    ]
    error_step_exact = sum(1 for r in error_cases if r['metrics']['error_step_match'])
    error_step_close = sum(1 for r in error_cases if r['metrics']['error_step_close'])

    # --- 错误类型（仅 gold 过程错误样本）---
    error_type_cases = [
        r for r in single_results
        if r['gold']['process_correct'] is False
        and r['gold']['error_type'] not in (None, '无错误')
    ]
    error_type_match = sum(1 for r in error_type_cases if r['metrics']['error_type_match'])

    # --- 格式完整率 ---
    format_complete = sum(1 for r in single_results if r['metrics']['format_complete'])

    # --- 联合准确率 ---
    joint_match = sum(1 for r in single_results if r['metrics']['joint_match'])

    # --- 分层统计 ---
    by_level = _group_metrics(single_results, 'student_level')
    by_difficulty = _group_metrics(single_results, 'difficulty')

    return {
        'total_samples': n,
        'parseable_samples': {
            'process': len(process_pairs),
            'result': len(result_pairs),
        },
        'judgment_accuracy': {
            'process_accuracy': _rate(sum(1 for g, p in process_pairs if g == p), len(process_pairs)),
            'result_accuracy': _rate(sum(1 for g, p in result_pairs if g == p), len(result_pairs)),
            'joint_accuracy': _rate(joint_match, n),
        },
        'process_confusion_matrix': process_cm,
        'process_prf': _precision_recall_f1(process_cm),
        'result_confusion_matrix': result_cm,
        'result_prf': _precision_recall_f1(result_cm),
        'error_localization': {
            'evaluable_samples': len(error_cases),
            'exact_step_accuracy': _rate(error_step_exact, len(error_cases)),
            'close_step_accuracy': _rate(error_step_close, len(error_cases)),
            'parsed_step_rate': _rate(len(error_step_evaluable), len(error_cases)),
        },
        'error_type_classification': {
            'evaluable_samples': len(error_type_cases),
            'accuracy': _rate(error_type_match, len(error_type_cases)),
        },
        'format_completeness_rate': _rate(format_complete, n),
        'by_student_level': by_level,
        'by_difficulty': by_difficulty,
    }


def _group_metrics(results: List[Dict], key: str) -> Dict[str, Any]:
    groups = defaultdict(list)
    for r in results:
        groups[str(r.get(key, 'unknown'))].append(r)

    summary = {}
    for group_name, items in sorted(groups.items()):
        process_ok = sum(1 for r in items if r['metrics']['process_match'])
        result_ok = sum(1 for r in items if r['metrics']['result_match'])
        joint_ok = sum(1 for r in items if r['metrics']['joint_match'])
        n = len(items)
        summary[group_name] = {
            'count': n,
            'process_accuracy': _rate(process_ok, n),
            'result_accuracy': _rate(result_ok, n),
            'joint_accuracy': _rate(joint_ok, n),
        }
    return summary
