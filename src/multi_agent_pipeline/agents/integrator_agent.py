"""
数据整合智能体
负责整合所有智能体的输出，生成最终的训练数据
"""

from typing import Dict, Any, List
from .base_agent import BaseAgent


class IntegratorAgent(BaseAgent):
    """数据整合智能体"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("IntegratorAgent", config)
        self.temperature = config.get('AGENT_TEMPERATURES', {}).get('integrator', 0.0)
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        整合数据
        
        Args:
            input_data: {
                'question': 题目,
                'analysis': 题目分析,
                'student_cases': [学生解答案例列表],
                'passed_cases': [通过审核的案例]
            }
        
        Returns:
            {
                'training_data': ShareGPT格式的训练数据列表,
                'statistics': 统计信息
            }
        """
        question = input_data.get('question', '')
        analysis = input_data.get('analysis', {})
        passed_cases = input_data.get('passed_cases', [])
        
        self.log(f"开始整合数据，通过审核的案例数：{len(passed_cases)}")
        
        training_data = []
        
        for case in passed_cases:
            # 转换为ShareGPT格式
            sharegpt_item = self._convert_to_sharegpt(
                question=question,
                student_solution=case.get('student_solution', ''),
                diagnosis=case.get('diagnosis', ''),
                knowledge_points=analysis.get('knowledge_points', []),
                metadata=case
            )
            
            training_data.append(sharegpt_item)
        
        # 统计信息
        statistics = {
            'total_cases': len(passed_cases),
            'student_levels': self._count_levels(passed_cases),
            'avg_quality_score': self._avg_quality(passed_cases)
        }
        
        self.log(f"整合完成，生成{len(training_data)}条训练数据")
        
        return {
            'training_data': training_data,
            'statistics': statistics
        }
    
    def _convert_to_sharegpt(self, question: str, student_solution: str,
                            diagnosis: str, knowledge_points: List[str],
                            metadata: Dict[str, Any]) -> Dict[str, Any]:
        """转换为ShareGPT格式"""
        
        # 构造system消息
        system_message = """你是一个数学老师。请诊断以下学生的解答，指出错误并给出改进建议。

        要求：
        1. 首先自己解答这道题
        2. 逐步分析学生解答的每一步
        3. 指出错误和改进方向
        4. 不要直接告诉学生正确答案"""
        
        # 构造human消息
        human_message = f"""题目：
                        {question}

                        学生的解答：
                        {student_solution}"""
        
        # 构造gpt消息
        gpt_message = diagnosis
        
        # ShareGPT格式
        sharegpt_item = {
            'conversations': [
                {'from': 'system', 'value': system_message},
                {'from': 'human', 'value': human_message},
                {'from': 'gpt', 'value': gpt_message}
            ]
        }
        
        # 添加元数据（可选，用于追踪）
        sharegpt_item['_metadata'] = {
            'knowledge_points': knowledge_points,
            'student_level': metadata.get('student_level'),
            'quality_score': metadata.get('quality_score'),
            'process_correct': metadata.get('process_correct'),
            'result_correct': metadata.get('result_correct')
        }
        
        return sharegpt_item
    
    def _count_levels(self, cases: List[Dict[str, Any]]) -> Dict[str, int]:
        """统计各水平学生的数量"""
        level_counts = {}
        for case in cases:
            level = case.get('student_level', 'unknown')
            level_counts[level] = level_counts.get(level, 0) + 1
        return level_counts
    
    def _avg_quality(self, cases: List[Dict[str, Any]]) -> float:
        """计算平均质量分"""
        if not cases:
            return 0.0
        
        total = sum(case.get('quality_score', 0) for case in cases)
        return total / len(cases)
    
    def batch_process(self, all_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量处理多个题目的数据
        
        Args:
            all_data: 所有题目的数据列表
        
        Returns:
            {
                'training_data': 所有训练数据,
                'overall_statistics': 总体统计
            }
        """
        self.log(f"开始批量整合{len(all_data)}个题目的数据")
        
        all_training_data = []
        all_statistics = []
        
        for item in all_data:
            result = self.process(item)
            all_training_data.extend(result['training_data'])
            all_statistics.append(result['statistics'])
        
        # 总体统计
        overall_statistics = {
            'total_questions': len(all_data),
            'total_training_samples': len(all_training_data),
            'avg_samples_per_question': len(all_training_data) / len(all_data) if all_data else 0,
            'overall_avg_quality': sum(s['avg_quality_score'] for s in all_statistics) / len(all_statistics) if all_statistics else 0
        }
        
        self.log(f"批量整合完成，共生成{len(all_training_data)}条训练数据")
        
        return {
            'training_data': all_training_data,
            'overall_statistics': overall_statistics
        }

