"""
规划智能体（Planner Agent）
负责根据题目特征和中间结果，动态规划处理策略
"""

from typing import Dict, Any, List
from .base_agent import BaseAgent


class PlannerAgent(BaseAgent):
    """规划智能体 - 动态规划数据生成策略"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("PlannerAgent", config)
        self.temperature = 0.1  # 规划需要确定性
    
    def plan_generation_strategy(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据题目分析结果，规划生成策略
        
        Args:
            analysis: 题目分析结果 {
                'knowledge_points': 知识点列表,
                'difficulty': 难度等级(1-5),
                'common_errors': 常见错误列表,
                'key_steps': 关键步骤列表
            }
        
        Returns:
            strategy: 生成策略 {
                'num_students': 学生数量,
                'student_levels': 选择的学生水平列表,
                'quality_threshold': 质量阈值,
                'max_retries': 最大重试次数,
                'use_expert': 是否使用专家智能体,
                'expert_type': 专家类型（如果需要）,
                'reasoning': 规划理由
            }
        """
        difficulty = analysis.get('difficulty', 3)
        knowledge_points = analysis.get('knowledge_points', [])
        common_errors = analysis.get('common_errors', [])
        
        self.log(f"开始规划策略（难度：{difficulty}星）")
        
        # 1. 根据难度决定学生数量和水平
        student_config = self._plan_students(difficulty, common_errors)
        
        # 2. 根据知识点决定是否需要专家
        expert_config = self._plan_expert(knowledge_points)
        
        # 3. 根据难度调整质量控制
        quality_config = self._plan_quality_control(difficulty)
        
        # 4. 综合策略
        strategy = {
            **student_config,
            **expert_config,
            **quality_config,
            'reasoning': self._generate_reasoning(
                difficulty, knowledge_points, student_config, expert_config, quality_config
            )
        }
        
        self.log(f"规划完成：{strategy['num_students']}个学生，"
                f"质量阈值{strategy['quality_threshold']}，"
                f"最多重试{strategy['max_retries']}次")
        
        return strategy
    
    def _plan_students(self, difficulty: int, common_errors: List[str]) -> Dict[str, Any]:
        """规划学生配置"""
        
        # 根据难度决定学生数量
        if difficulty <= 2:
            # 简单题：2个学生（优秀+中等）
            num_students = 2
            student_levels = ['excellent', 'average']
        elif difficulty == 3:
            # 中等题：3个学生（优秀+中等+薄弱）
            num_students = 3
            student_levels = ['excellent', 'average', 'weak']
        else:
            # 困难题：4个学生（覆盖更多错误模式）
            num_students = 4
            student_levels = ['excellent', 'average', 'weak', 'weak']
        
        # 如果预测的常见错误很多，增加薄弱学生
        if len(common_errors) >= 3:
            if 'weak' not in student_levels:
                student_levels.append('weak')
            num_students = len(student_levels)
        
        return {
            'num_students': num_students,
            'student_levels': student_levels
        }
    
    def _plan_expert(self, knowledge_points: List[str]) -> Dict[str, Any]:
        """规划是否需要专家智能体"""
        
        # 定义专家领域
        expert_domains = {
            'function': ['函数', '二次函数', '反比例函数', '一次函数'],
            'geometry': ['几何', '三角形', '圆', '相似', '全等'],
            'algebra': ['方程', '不等式', '因式分解', '代数式'],
            'probability': ['概率', '统计', '排列组合']
        }
        
        # 检查是否需要专家
        for expert_type, keywords in expert_domains.items():
            for kp in knowledge_points:
                if any(keyword in kp for keyword in keywords):
                    return {
                        'use_expert': True,
                        'expert_type': expert_type
                    }
        
        return {
            'use_expert': False,
            'expert_type': None
        }
    
    def _plan_quality_control(self, difficulty: int) -> Dict[str, Any]:
        """规划质量控制策略"""
        
        if difficulty <= 2:
            # 简单题：要求更高质量，但重试少
            quality_threshold = 75
            max_retries = 1
        elif difficulty == 3:
            # 中等题：平衡质量和重试
            quality_threshold = 70
            max_retries = 2
        else:
            # 困难题：适当降低阈值，增加重试
            quality_threshold = 65
            max_retries = 3
        
        return {
            'quality_threshold': quality_threshold,
            'max_retries': max_retries
        }
    
    def _generate_reasoning(self, difficulty: int, knowledge_points: List[str],
                           student_config: Dict, expert_config: Dict,
                           quality_config: Dict) -> str:
        """生成规划理由"""
        
        reasons = []
        
        # 难度理由
        if difficulty <= 2:
            reasons.append(f"简单题（{difficulty}星），使用{student_config['num_students']}个学生")
        elif difficulty == 3:
            reasons.append(f"中等题（{difficulty}星），使用{student_config['num_students']}个学生覆盖常见错误")
        else:
            reasons.append(f"困难题（{difficulty}星），使用{student_config['num_students']}个学生覆盖多种错误模式")
        
        # 专家理由
        if expert_config['use_expert']:
            reasons.append(f"涉及{expert_config['expert_type']}领域，建议使用专家智能体")
        
        # 质量理由
        reasons.append(f"质量阈值{quality_config['quality_threshold']}，最多重试{quality_config['max_retries']}次")
        
        return " | ".join(reasons)
    
    def adjust_strategy_based_on_results(self, 
                                        current_strategy: Dict[str, Any],
                                        results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        根据中间结果调整策略
        
        Args:
            current_strategy: 当前策略
            results: 已生成的结果列表（包含质量分）
        
        Returns:
            adjusted_strategy: 调整后的策略
        """
        if not results:
            return current_strategy
        
        # 计算平均质量分
        quality_scores = [r.get('quality_score', 0) for r in results if r.get('quality_score')]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        
        self.log(f"当前平均质量分：{avg_quality:.1f}")
        
        adjusted = current_strategy.copy()
        
        # 如果质量普遍很低，调整策略
        if avg_quality < 50:
            self.log("质量过低，调整策略：增加学生数量，降低质量阈值")
            adjusted['num_students'] = min(adjusted['num_students'] + 1, 5)
            adjusted['quality_threshold'] = max(adjusted['quality_threshold'] - 5, 60)
            adjusted['max_retries'] = min(adjusted['max_retries'] + 1, 3)
        
        # 如果质量普遍很高，可以优化成本
        elif avg_quality > 85:
            self.log("质量很高，优化策略：减少重试次数")
            adjusted['max_retries'] = max(adjusted['max_retries'] - 1, 1)
        
        return adjusted
    
    def should_continue_generation(self, 
                                  passed_cases: List[Dict[str, Any]],
                                  target_count: int) -> bool:
        """
        判断是否应该继续生成
        
        Args:
            passed_cases: 已通过的案例
            target_count: 目标数量
        
        Returns:
            是否继续生成
        """
        current_count = len(passed_cases)
        
        if current_count >= target_count:
            self.log(f"已达到目标数量（{current_count}/{target_count}），停止生成")
            return False
        
        # 检查质量分布
        if current_count > 0:
            quality_scores = [c.get('quality_score', 0) for c in passed_cases]
            avg_quality = sum(quality_scores) / len(quality_scores)
            
            # 如果质量很高且数量接近目标，可以提前停止
            if avg_quality > 90 and current_count >= target_count * 0.8:
                self.log(f"质量优秀（{avg_quality:.1f}）且接近目标，可以停止")
                return False
        
        self.log(f"继续生成（{current_count}/{target_count}）")
        return True
    
    def plan_batch_strategy(self, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        规划批量处理策略
        
        Args:
            questions: 题目列表
        
        Returns:
            batch_strategy: 批量策略 {
                'processing_order': 处理顺序,
                'parallel_groups': 并行分组,
                'priority_questions': 优先题目,
                'reasoning': 规划理由
            }
        """
        self.log(f"规划批量处理策略（共{len(questions)}题）")
        
        # 简单策略：按难度排序（简单题先处理，快速验证流程）
        # 实际可以更复杂：考虑知识点分布、预估处理时间等
        
        return {
            'processing_order': 'sequential',  # 顺序处理
            'parallel_groups': None,  # 暂不支持并行
            'priority_questions': [],  # 无优先级
            'reasoning': '顺序处理所有题目，确保稳定性'
        }
