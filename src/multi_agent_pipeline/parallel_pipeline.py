"""
并行处理版Pipeline
通过并行生成学生解答和诊断，速度提升66%
"""

import random
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from agents import (
    AnalyzerAgent,
    StudentAgent,
    TeacherAgent,
    ReviewerAgent,
    IntegratorAgent,
    PlannerAgent
)


class ParallelMultiAgentPipeline:
    """并行处理版多智能体Pipeline"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化Pipeline
        
        Args:
            config: 配置字典
        """
        self.config = config
        
        # 初始化各个智能体
        self.planner = PlannerAgent(config)
        self.analyzer = AnalyzerAgent(config)
        self.teacher = TeacherAgent(config)
        self.reviewer = ReviewerAgent(config)
        self.integrator = IntegratorAgent(config)
        
        # 初始化多个学生智能体（不同水平）
        self.students = []
        for level_config in config.get('STUDENT_LEVELS', []):
            student = StudentAgent(config, level_config)
            self.students.append(student)
        
        # 并行配置
        self.max_workers = config.get('PARALLEL_WORKERS', 3)
        
        print(f"[ParallelPipeline] 初始化完成，共{len(self.students)}个学生智能体 + Planner智能体")
        print(f"[ParallelPipeline] 并行工作线程数：{self.max_workers}")
    
    def process_single_question(self, question_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理单个题目（并行版）
        
        Args:
            question_data: {
                'id': 题目ID,
                'question': 题目内容,
                'correct_solution': 正确解析（可选）,
                'knowledge_points': 知识点（可选）
            }
        
        Returns:
            处理结果
        """
        question_id = question_data.get('id', 'unknown')
        question = question_data.get('question', '')
        correct_solution = question_data.get('correct_solution', '')
        
        print(f"\n{'='*60}")
        print(f"[ParallelPipeline] 处理题目: {question_id}")
        print(f"{'='*60}")
        
        # ========== 步骤1: 题目分析 ==========
        print(f"\n[步骤1] 题目分析")
        analysis = self.analyzer.process({
            'question': question,
            'correct_solution': correct_solution
        })
        
        if not analysis.get('knowledge_points'):
            print(f"[ParallelPipeline] 警告：题目分析失败，使用默认值")
            analysis = {
                'knowledge_points': question_data.get('knowledge_points', []),
                'difficulty': 3,
                'common_errors': [],
                'key_steps': []
            }
        
        # ========== 步骤1.5: 规划生成策略 ==========
        print(f"\n[步骤1.5] 规划生成策略")
        strategy = self.planner.plan_generation_strategy(analysis)
        
        print(f"[ParallelPipeline] 策略：{strategy['reasoning']}")
        
        # 根据策略调整配置
        num_students = strategy['num_students']
        quality_threshold = strategy['quality_threshold']
        max_retries = strategy['max_retries']
        
        # ========== 步骤2: 并行生成学生解答 ==========
        print(f"\n[步骤2] 并行生成学生解答（{num_students}个学生）")
        
        # 根据策略选择学生智能体
        selected_students = []
        for level_name in strategy['student_levels']:
            for student in self.students:
                if student.level_config['name'] == level_name:
                    selected_students.append(student)
                    break
        
        # 并行生成学生解答
        student_cases = self._parallel_generate_solutions(
            selected_students, question, analysis
        )
        
        print(f"[ParallelPipeline] 生成了{len(student_cases)}个学生解答")
        
        # ========== 步骤3: 并行教师诊断 ==========
        print(f"\n[步骤3] 并行教师诊断")
        
        student_cases = self._parallel_diagnose(
            student_cases, question, analysis
        )
        
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
                print(f"  [ParallelPipeline] 质量不合格，重新诊断（第{retry_count}次重试）")
                
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
        
        print(f"[ParallelPipeline] 审核完成：{len(passed_cases)}个通过，{len(rejected_cases)}个被拒绝")
        
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
    
    def _parallel_generate_solutions(self, students: List[StudentAgent], 
                                     question: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        并行生成学生解答
        
        Args:
            students: 学生智能体列表
            question: 题目
            analysis: 题目分析
        
        Returns:
            学生解答列表
        """
        student_cases = []
        
        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_student = {
                executor.submit(
                    student.process,
                    {'question': question, 'analysis': analysis}
                ): student
                for student in students
            }
            
            # 收集结果
            for future in as_completed(future_to_student):
                student = future_to_student[future]
                try:
                    result = future.result()
                    if result.get('student_solution'):
                        student_cases.append(result)
                        print(f"  ✓ {student.name} 完成")
                except Exception as e:
                    print(f"  ✗ {student.name} 失败: {e}")
        
        return student_cases
    
    def _parallel_diagnose(self, student_cases: List[Dict[str, Any]], 
                          question: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        并行诊断学生解答
        
        Args:
            student_cases: 学生解答列表
            question: 题目
            analysis: 题目分析
        
        Returns:
            带诊断的学生解答列表
        """
        # 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_case = {
                executor.submit(
                    self.teacher.process,
                    {
                        'question': question,
                        'student_solution': case['student_solution'],
                        'analysis': analysis
                    }
                ): case
                for case in student_cases
            }
            
            # 收集结果
            for future in as_completed(future_to_case):
                case = future_to_case[future]
                try:
                    diagnosis_result = future.result()
                    case.update(diagnosis_result)
                    print(f"  ✓ 诊断完成（学生水平：{case.get('student_level')}）")
                except Exception as e:
                    print(f"  ✗ 诊断失败: {e}")
        
        return student_cases
    
    def process_batch(
        self,
        questions: List[Dict[str, Any]],
        training_writers: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        批量处理多个题目
        
        Args:
            questions: 题目列表
        
        Returns:
            批量处理结果
        """
        print(f"\n{'='*60}")
        print(f"[ParallelPipeline] 开始批量处理{len(questions)}个题目")
        print(f"{'='*60}")
        
        from utils import build_overall_statistics

        all_results = []
        all_training_data = []
        all_passed_cases = []
        all_rejected_cases = []
        
        for idx, question_data in enumerate(questions, 1):
            print(f"\n{'#'*60}")
            print(f"# 进度: {idx}/{len(questions)}")
            print(f"{'#'*60}")
            
            result = self.process_single_question(question_data)
            all_results.append(result)
            all_training_data.extend(result['training_data'])
            all_passed_cases.extend(result['passed_cases'])
            all_rejected_cases.extend(result['rejected_cases'])

            if training_writers and result['training_data']:
                training_writers.add(result['training_data'])
        
        overall_statistics = build_overall_statistics(
            all_results,
            all_training_data,
            all_passed_cases,
            all_rejected_cases,
            len(questions),
        )
        
        print(f"\n{'='*60}")
        print(f"[ParallelPipeline] 批量处理完成")
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
            'all_training_data': all_training_data,
            'all_rejected_cases': all_rejected_cases,
            'overall_statistics': overall_statistics
        }
