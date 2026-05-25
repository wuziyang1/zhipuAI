"""
多智能体Pipeline主逻辑
协调各个智能体协作完成数据构造任务
"""

import random
from typing import Dict, Any, List
from agents import (
    AnalyzerAgent,
    StudentAgent,
    TeacherAgent,
    ReviewerAgent,
    IntegratorAgent,
    PlannerAgent,
)


class MultiAgentPipeline:
    """多智能体数据构造Pipeline"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化Pipeline
        
        Args:
            config: 配置字典
        """
        self.config = config
        
        # 初始化各个智能体
        self.planner = PlannerAgent(config)  # 新增：规划智能体
        self.analyzer = AnalyzerAgent(config)
        self.teacher = TeacherAgent(config)
        self.reviewer = ReviewerAgent(config)
        self.integrator = IntegratorAgent(config)
        
        # 初始化多个学生智能体（不同水平）
        self.students = []
        for level_config in config.get('STUDENT_LEVELS', []):
            student = StudentAgent(config, level_config)
            self.students.append(student)
        
        print(f"[Pipeline] 初始化完成，共{len(self.students)}个学生智能体 + Planner智能体")
    
    def process_single_question(self, question_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理单个题目
        
        Args:
            question_data: {
                'id': 题目ID,
                'question': 题目内容,
                'correct_solution': 正确解析（可选）,
                'knowledge_points': 知识点（可选）
            }
        
        Returns:
            {
                'question_id': 题目ID,
                'question': 题目,
                'analysis': 题目分析,
                'student_cases': 所有学生案例,
                'passed_cases': 通过审核的案例,
                'rejected_cases': 被拒绝的案例,
                'training_data': 训练数据
            }
        """
        question_id = question_data.get('id', 'unknown')
        question = question_data.get('question', '')
        correct_solution = question_data.get('correct_solution', '')
        
        print(f"\n{'='*60}")
        print(f"[Pipeline] 处理题目: {question_id}")
        print(f"{'='*60}")
        
        # ========== 步骤1: 题目分析 ==========
        print(f"\n[步骤1] 题目分析")
        analysis = self.analyzer.process({
            'question': question,
            'correct_solution': correct_solution
        })
        
        if not analysis.get('knowledge_points'):
            print(f"[Pipeline] 警告：题目分析失败，使用默认值")
            analysis = {
                'knowledge_points': question_data.get('knowledge_points', []),
                'difficulty': 3,
                'common_errors': [],
                'key_steps': []
            }
        
        # ========== 步骤1.5: 规划生成策略（新增）==========
        print(f"\n[步骤1.5] 规划生成策略")
        strategy = self.planner.plan_generation_strategy(analysis)
        
        print(f"[Pipeline] 策略：{strategy['reasoning']}")
        
        # 根据策略调整配置
        num_students = strategy['num_students']
        quality_threshold = strategy['quality_threshold']
        max_retries = strategy['max_retries']
        
        # ========== 步骤2: 生成学生解答 ==========
        print(f"\n[步骤2] 生成学生解答（策略：{num_students}个学生）")
        
        # 根据策略选择学生智能体
        selected_students = []
        for level_name in strategy['student_levels']:
            # 找到对应水平的学生智能体
            for student in self.students:
                if student.level_config['name'] == level_name:
                    selected_students.append(student)
                    break
        
        student_cases = []
        for student in selected_students:
            student_result = student.process({
                'question': question,
                'analysis': analysis
            })
            
            if student_result.get('student_solution'):
                student_cases.append(student_result)
        
        print(f"[Pipeline] 生成了{len(student_cases)}个学生解答")
        
        # ========== 步骤3: 教师诊断 ==========
        print(f"\n[步骤3] 教师诊断")
        for case in student_cases:
            diagnosis_result = self.teacher.process({
                'question': question,
                'student_solution': case['student_solution'],
                'analysis': analysis
            })
            
            case.update(diagnosis_result)
        
        # ========== 步骤4: 质量审核（带重试） ==========
        print(f"\n[步骤4] 质量审核（阈值：{quality_threshold}，最多重试：{max_retries}次）")
        passed_cases = []
        rejected_cases = []
        
        for case in student_cases:
            # 审核（使用策略中的质量阈值）
            review_result = self.reviewer.process({
                'question': question,
                'student_solution': case['student_solution'],
                'diagnosis': case['diagnosis'],
                'target_correct': case.get('target_correct')
            })
            
            # 临时覆盖质量阈值
            original_threshold = self.reviewer.quality_threshold
            self.reviewer.quality_threshold = quality_threshold
            
            case.update(review_result)
            
            # 如果不通过且允许重试
            retry_count = 0
            while not review_result['passed'] and retry_count < max_retries:
                retry_count += 1
                print(f"  [Pipeline] 质量不合格，重新诊断（第{retry_count}次重试）")
                
                # 重新诊断
                diagnosis_result = self.teacher.process({
                    'question': question,
                    'student_solution': case['student_solution'],
                    'analysis': analysis
                })
                
                case.update(diagnosis_result)
                
                # 重新审核
                review_result = self.reviewer.process({
                    'question': question,
                    'student_solution': case['student_solution'],
                    'diagnosis': case['diagnosis'],
                    'target_correct': case.get('target_correct')
                })
                
                case.update(review_result)
            
            # 恢复原始阈值
            self.reviewer.quality_threshold = original_threshold
            
            # 分类
            if review_result['passed']:
                passed_cases.append(case)
                print(f"  ✓ 通过审核（质量分：{review_result['quality_score']:.1f}）")
            else:
                rejected_cases.append(case)
                print(f"  ✗ 未通过审核（质量分：{review_result['quality_score']:.1f}）")
        
        print(f"[Pipeline] 审核完成：{len(passed_cases)}个通过，{len(rejected_cases)}个被拒绝")
        
        # ========== 步骤5: 数据整合 ==========
        print(f"\n[步骤5] 数据整合")
        integration_result = self.integrator.process({
            'question': question,
            'analysis': analysis,
            'student_cases': student_cases,
            'passed_cases': passed_cases
        })
        
        return {
            'question_id': question_id,
            'question': question,
            'analysis': analysis,
            'student_cases': student_cases,
            'passed_cases': passed_cases,
            'rejected_cases': rejected_cases,
            'training_data': integration_result['training_data'],
            'statistics': integration_result['statistics']
        }
    
    def process_batch(self, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量处理多个题目
        
        Args:
            questions: 题目列表
        
        Returns:
            {
                'all_results': 所有题目的处理结果,
                'all_training_data': 所有训练数据,
                'overall_statistics': 总体统计
            }
        """
        print(f"\n{'='*60}")
        print(f"[Pipeline] 开始批量处理{len(questions)}个题目")
        print(f"{'='*60}")
        
        all_results = []
        all_passed_cases = []
        all_rejected_cases = []
        
        for idx, question_data in enumerate(questions, 1):
            print(f"\n{'#'*60}")
            print(f"# 进度: {idx}/{len(questions)}")
            print(f"{'#'*60}")
            
            result = self.process_single_question(question_data)
            all_results.append(result)
            all_passed_cases.extend(result['passed_cases'])
            all_rejected_cases.extend(result['rejected_cases'])
        
        # 批量整合
        print(f"\n{'='*60}")
        print(f"[Pipeline] 批量整合所有数据")
        print(f"{'='*60}")
        
        integration_data = []
        for result in all_results:
            integration_data.append({
                'question': result['question'],
                'analysis': result['analysis'],
                'passed_cases': result['passed_cases']
            })
        
        final_result = self.integrator.batch_process(integration_data)
        
        # 总体统计
        overall_statistics = final_result['overall_statistics']
        overall_statistics.update({
            'total_student_cases': sum(len(r['student_cases']) for r in all_results),
            'total_passed_cases': len(all_passed_cases),
            'total_rejected_cases': len(all_rejected_cases),
            'pass_rate': len(all_passed_cases) / (len(all_passed_cases) + len(all_rejected_cases)) * 100 
                        if (len(all_passed_cases) + len(all_rejected_cases)) > 0 else 0
        })
        
        print(f"\n{'='*60}")
        print(f"[Pipeline] 批量处理完成")
        print(f"{'='*60}")
        print(f"总题目数: {len(questions)}")
        print(f"总学生案例数: {overall_statistics['total_student_cases']}")
        print(f"通过审核: {overall_statistics['total_passed_cases']}")
        print(f"被拒绝: {overall_statistics['total_rejected_cases']}")
        print(f"通过率: {overall_statistics['pass_rate']:.1f}%")
        print(f"最终训练数据: {overall_statistics['total_training_samples']}条")
        print(f"{'='*60}\n")
        
        return {
            'all_results': all_results,
            'all_training_data': final_result['training_data'],
            'all_rejected_cases': all_rejected_cases,
            'overall_statistics': overall_statistics
        }
