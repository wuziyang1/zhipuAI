"""
多智能体Pipeline运行脚本
"""

import os
import sys
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from pipeline import MultiAgentPipeline
from parallel_pipeline import ParallelMultiAgentPipeline
from utils import (
    load_training_data,
    save_json,
    generate_quality_report,
    generate_minimal_training_data,
    print_sample_data
)


def main():
    """主函数"""
    print(f"\n{'='*60}")
    print("多智能体数据构造Pipeline")
    print(f"{'='*60}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # 转换config模块为字典
    config_dict = {
        key: getattr(config, key)
        for key in dir(config)
        if not key.startswith('_') and key.isupper()
    }
    
    # 显示配置
    print("\n配置信息:")
    print(f"  输入文件: {config.INPUT_TRAIN_DATA}")
    print(f"  输出目录: {config.OUTPUT_DIR}")
    print(f"  处理数量: {config.NUM_RECORDS or '全部'}")
    print(f"  学生水平数: {len(config.STUDENT_LEVELS)}")
    print(f"  每题学生数: {config.NUM_STUDENTS_PER_QUESTION}")
    print(f"  质量阈值: {config.QUALITY_THRESHOLD}")
    print(f"  最大重试: {config.MAX_RETRY_ATTEMPTS}")
    print(f"  启用并行: {config.ENABLE_PARALLEL}")
    print()
    
    # 加载数据
    try:
        questions = load_training_data(
            config.INPUT_TRAIN_DATA,
            config.NUM_RECORDS
        )
    except FileNotFoundError:
        print(f"错误：找不到文件 {config.INPUT_TRAIN_DATA}")
        print("请确保数据文件存在")
        return
    except Exception as e:
        print(f"错误：加载数据失败 - {e}")
        return
    
    if not questions:
        print("错误：没有加载到任何题目")
        return
    
    # 初始化Pipeline
    print("\n初始化Pipeline...")
    if config.ENABLE_PARALLEL:
        pipeline = ParallelMultiAgentPipeline(config_dict)
    else:
        pipeline = MultiAgentPipeline(config_dict)
    
    # 运行Pipeline
    print("\n开始处理数据...")
    results = pipeline.process_batch(questions)
    
    # 每次运行创建独立的日期时间子目录
    run_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    run_output_dir = os.path.join(config.OUTPUT_DIR, run_timestamp)
    os.makedirs(run_output_dir, exist_ok=True)
    print(f"\n本次输出目录: {run_output_dir}")
    
    # 保存原始数据（包含所有中间结果）
    if config.SAVE_INTERMEDIATE_RESULTS:
        raw_data_path = os.path.join(run_output_dir, config.OUTPUT_FILES['raw_data'])
        save_json(results['all_results'], raw_data_path)
    
    # 保存训练数据（完整版，包含元数据）
    training_data_path = os.path.join(run_output_dir, config.OUTPUT_FILES['training_data'])
    save_json(results['all_training_data'], training_data_path)
    
    # 保存训练数据（纯净版，只保留conversations）
    minimal_data = generate_minimal_training_data(results['all_training_data'])
    minimal_data_path = os.path.join(run_output_dir, 'training_data_minimal.json')
    save_json(minimal_data, minimal_data_path)
    
    # 保存质量报告
    quality_report_path = os.path.join(run_output_dir, config.OUTPUT_FILES['quality_report'])
    generate_quality_report(results, quality_report_path)
    
    # 保存被拒绝的案例
    if config.SAVE_REJECTED_CASES and results['all_rejected_cases']:
        rejected_cases_path = os.path.join(run_output_dir, config.OUTPUT_FILES['rejected_cases'])
        save_json(results['all_rejected_cases'], rejected_cases_path)
    
    # 打印示例数据
    if results['all_training_data']:
        print_sample_data(results['all_training_data'], num_samples=2)
    
    # 最终统计
    print(f"\n{'='*60}")
    print("处理完成 - 最终统计")
    print(f"{'='*60}")
    stats = results['overall_statistics']
    print(f"总题目数: {stats['total_questions']}")
    print(f"总学生案例数: {stats['total_student_cases']}")
    print(f"通过审核: {stats['total_passed_cases']}")
    print(f"被拒绝: {stats['total_rejected_cases']}")
    print(f"通过率: {stats['pass_rate']:.1f}%")
    print(f"最终训练数据: {stats['total_training_samples']}条")
    print(f"平均质量分: {stats['overall_avg_quality']:.1f}")
    print(f"\n输出目录: {run_output_dir}")
    print(f"输出文件:")
    print(f"  - 训练数据（完整版）: {training_data_path}")
    print(f"  - 训练数据（纯净版）: {minimal_data_path}")
    print(f"  - 质量报告: {quality_report_path}")
    if config.SAVE_INTERMEDIATE_RESULTS:
        print(f"  - 原始数据: {raw_data_path}")
    if config.SAVE_REJECTED_CASES and results['all_rejected_cases']:
        print(f"  - 被拒绝案例: {rejected_cases_path}")
    
    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断执行")
    except Exception as e:
        print(f"\n\n错误：{e}")
        import traceback
        traceback.print_exc()
