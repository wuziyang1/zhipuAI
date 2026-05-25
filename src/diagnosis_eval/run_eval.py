"""
诊断能力评测入口

用法:
  # 1. 先用 dry-run 验证指标计算（不调用 API，gold=pred，指标应接近 100%）
  python run_eval.py --dry-run

  # 2. 调用 GLM-5.1 进行真实评测
  python run_eval.py

  # 3. 指定测试数据和模型
  python run_eval.py --input ../multi_agent_pipeline/output/2026-05-25_18-40-44/raw_data.json --model glm-5.1

  # 4. 使用已有预测文件（跳过推理）
  python run_eval.py --predictions path/to/predictions.json
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from data_loader import load_test_cases, resolve_path
from evaluator import DiagnosisEvaluator, format_summary, save_report
from model_utils import normalize_model_name


def build_config(args) -> dict:
    cfg = {
        key: getattr(config, key)
        for key in dir(config)
        if not key.startswith('_') and key.isupper()
    }
    if args.input:
        cfg['INPUT_RAW_DATA'] = args.input
    if args.model:
        cfg['MODEL_NAME'] = args.model
    if args.max_samples is not None:
        cfg['MAX_SAMPLES'] = args.max_samples
    cfg['DRY_RUN'] = args.dry_run
    return cfg


def load_predictions(path: str) -> dict:
    full_path = resolve_path(path) if not os.path.isabs(path) else path
    with open(full_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, dict):
        return data

    preds = {}
    for item in data:
        if item.get('success') and item.get('prediction'):
            preds[item['case_id']] = item['prediction']
    return preds


def main():
    parser = argparse.ArgumentParser(description='数学诊断能力评测')
    parser.add_argument('--input', type=str, help='raw_data.json 路径')
    parser.add_argument('--model', type=str, help='被测模型名称，如 glm-5.1')
    parser.add_argument('--max-samples', type=int, help='限制评测样本数')
    parser.add_argument('--dry-run', action='store_true',
                        help='不调用 API，用 gold 诊断作为预测，验证指标流程')
    parser.add_argument('--predictions', type=str,
                        help='已有预测 JSON 文件（跳过模型推理）')
    parser.add_argument('--all-cases', action='store_true',
                        help='评测全部 student_cases（默认只用 passed_cases）')
    args = parser.parse_args()

    cfg = build_config(args)
    resolved_model = normalize_model_name(cfg['MODEL_NAME'])
    from model_utils import detect_api_backend
    cfg['RESOLVED_MODEL_NAME'] = resolved_model

    print(f"\n{'=' * 60}")
    print("数学诊断能力评测")
    print(f"{'=' * 60}")
    print(f"测试数据: {cfg['INPUT_RAW_DATA']}")
    print(f"配置模型: {cfg['MODEL_NAME']}")
    if resolved_model != cfg['MODEL_NAME']:
        print(f"实际请求: {resolved_model}")
    print(f"API 协议: {detect_api_backend(resolved_model)}")
    print(f"Dry-run: {cfg['DRY_RUN']}")
    print(f"{'=' * 60}")

    cases = load_test_cases(
        cfg['INPUT_RAW_DATA'],
        use_passed_only=not args.all_cases,
        max_samples=cfg['MAX_SAMPLES'],
    )

    if not cases:
        print("错误：未加载到任何测试样本")
        return

    print(f"加载 {len(cases)} 条测试样本")

    predictions = load_predictions(args.predictions) if args.predictions else None

    if not cfg['DRY_RUN'] and not predictions:
        if not cfg.get('API_KEY') or not cfg.get('BASE_URL'):
            print("错误：请在 .env 中配置 EVAL_API_KEY / EVAL_BASE_URL（或 Gemini_API_KEY / Gemini_BASE_URL）")
            return

    evaluator = DiagnosisEvaluator(cfg)
    report = evaluator.run(cases, predictions=predictions)

    paths = save_report(report, cfg['OUTPUT_DIR'])

    print(f"\n{format_summary(report)}")
    print(f"\n报告已保存:")
    print(f"  目录: {paths['run_dir']}")
    print(f"  完整报告: {paths['report']}")
    print(f"  预测结果: {paths['predictions']}")
    print(f"  文本摘要: {paths['summary']}")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback
        traceback.print_exc()
