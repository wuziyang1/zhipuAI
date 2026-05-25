"""
质量审核智能体
负责审核诊断质量，确保诊断准确、完整、有用
"""

import re
from typing import Dict, Any, List
from .base_agent import BaseAgent


class ReviewerAgent(BaseAgent):
    """质量审核智能体"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("ReviewerAgent", config)
        self.temperature = config.get('AGENT_TEMPERATURES', {}).get('reviewer', 0.1)
        self.quality_threshold = config.get('QUALITY_THRESHOLD', 70)
        self.quality_weights = config.get('QUALITY_WEIGHTS', {
            'completeness': 0.3,
            'accuracy': 0.4,
            'clarity': 0.2,
            'usefulness': 0.1
        })
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        审核诊断质量
        
        Args:
            input_data: {
                'question': 题目内容,
                'student_solution': 学生解答,
                'diagnosis': 诊断内容,
                'target_correct': 学生答案目标正确性（可选）
            }
        
        Returns:
            {
                'quality_score': 质量总分(0-100),
                'quality_details': 各维度评分,
                'passed': 是否通过审核,
                'feedback': 反馈意见,
                'issues': 发现的问题列表
            }
        """
        question = input_data.get('question', '')
        student_solution = input_data.get('student_solution', '')
        diagnosis = input_data.get('diagnosis', '')
        target_correct = input_data.get('target_correct')
        
        self.log("开始质量审核")
        
        # 1. 自动检查（通过正则检查是否所有字段都不缺失）
        auto_check = self._auto_check(diagnosis, target_correct)
        
        # 2. LLM深度审核（慢但准确）
        llm_review = self._llm_review(question, student_solution, diagnosis)
        
        # 3. 综合评分
        quality_details = self._calculate_quality(auto_check, llm_review)
        quality_score = self._calculate_total_score(quality_details)
        
        # 4. 判断是否通过
        passed = quality_score >= self.quality_threshold
        
        # 5. 生成反馈
        feedback = self._generate_feedback(quality_details, auto_check, llm_review)
        
        # 6. 收集问题
        issues = auto_check.get('issues', []) + llm_review.get('issues', [])
        
        self.log(f"审核完成：质量分{quality_score:.1f}, {'通过' if passed else '不通过'}")
        
        return {
            'quality_score': quality_score,
            'quality_details': quality_details,
            'passed': passed,
            'feedback': feedback,
            'issues': issues
        }
    
    def _auto_check(self, diagnosis: str, target_correct: bool = None) -> Dict[str, Any]:
        """自动检查诊断完整性"""
        issues = []
        
        # 检查必需部分
        required_sections = [
            '【解题分析】',
            '【诊断过程】',
            '【诊断结果】',
            '【知识点欠缺分析】',
            '【改进建议】'
        ]
        
        missing_sections = [s for s in required_sections if s not in diagnosis]
        if missing_sections:
            issues.append(f"缺少部分：{', '.join(missing_sections)}")
        
        completeness = (len(required_sections) - len(missing_sections)) / len(required_sections)
        
        # 检查是否有明确的判断结果
        has_process_judgment = '过程是否正确' in diagnosis
        has_result_judgment = '结果是否正确' in diagnosis
        
        if not has_process_judgment:
            issues.append("缺少过程正确性判断")
        if not has_result_judgment:
            issues.append("缺少结果正确性判断")
        
        # 检查长度（太短可能不够详细）
        if len(diagnosis) < 200:
            issues.append("诊断内容过短，可能不够详细")
        
        # 检查是否泄露答案
        if '正确答案是' in diagnosis or '答案应该是' in diagnosis:
            issues.append("可能直接泄露了答案")
        
        return {
            'completeness': completeness,
            'has_process_judgment': has_process_judgment,
            'has_result_judgment': has_result_judgment,
            'length': len(diagnosis),
            'issues': issues
        }
    
    def _llm_review(self, question: str, student_solution: str, 
                   diagnosis: str) -> Dict[str, Any]:
        """使用LLM进行深度审核"""
        
        prompt = f"""你是一个教学质量审核专家。请审核以下数学诊断的质量。

                题目：
                {question}

                学生解答：
                {student_solution}

                教师诊断：
                {diagnosis}

                请从以下维度评估诊断质量（每个维度0-100分）：

                1. 准确性（Accuracy）：诊断的判断是否准确？
                2. 清晰度（Clarity）：表达是否清楚易懂？
                3. 实用性（Usefulness）：建议是否有帮助？

                请按照以下格式输出：

                【准确性评分】
                分数：[0-100]
                说明：（为什么给这个分数）

                【清晰度评分】
                分数：[0-100]
                说明：（为什么给这个分数）

                【实用性评分】
                分数：[0-100]
                说明：（为什么给这个分数）

                【发现的问题】
                （列出发现的主要问题，每个问题一行，格式：- 问题描述）

                【总体评价】
                （简要总结这个诊断的优缺点）
                """
        
        response = self.call_llm(prompt, self.temperature)
        
        if not response:
            return {
                'accuracy': 50,
                'clarity': 50,
                'usefulness': 50,
                'issues': ['LLM审核失败']
            }
        
        # 解析评分
        accuracy = self._extract_score(response, '【准确性评分】')
        clarity = self._extract_score(response, '【清晰度评分】')
        usefulness = self._extract_score(response, '【实用性评分】')
        
        # 提取问题
        issues = self._extract_issues(response)
        
        return {
            'accuracy': accuracy,
            'clarity': clarity,
            'usefulness': usefulness,
            'issues': issues,
            'review_text': response
        }
    
    def _extract_score(self, text: str, section_name: str) -> float:
        """从文本中提取评分"""
        # 查找section
        start_idx = text.find(section_name)
        if start_idx == -1:
            return 50.0  # 默认分数
        
        # 在section后面查找分数
        section_text = text[start_idx:start_idx+200]
        match = re.search(r'分数[：:]\s*(\d+)', section_text)
        
        if match:
            return float(match.group(1))
        
        return 50.0
    
    def _extract_issues(self, text: str) -> List[str]:
        """提取问题列表"""
        issues = []
        
        # 查找【发现的问题】部分
        start_idx = text.find('【发现的问题】')
        if start_idx == -1:
            return issues
        
        end_idx = text.find('【总体评价】', start_idx)
        if end_idx == -1:
            end_idx = len(text)
        
        section_text = text[start_idx:end_idx]
        
        # 提取列表项
        lines = section_text.split('\n')
        for line in lines:
            line = line.strip()
            match = re.match(r'^[-•\d.]+\s*(.+)$', line)
            if match:
                issues.append(match.group(1).strip())
        
        return issues
    
    def _calculate_quality(self, auto_check: Dict[str, Any], 
                          llm_review: Dict[str, Any]) -> Dict[str, float]:
        """计算各维度质量分"""
        return {
            'completeness': auto_check['completeness'] * 100,
            'accuracy': llm_review['accuracy'],
            'clarity': llm_review['clarity'],
            'usefulness': llm_review['usefulness']
        }
    
    def _calculate_total_score(self, quality_details: Dict[str, float]) -> float:
        """计算总分"""
        total = 0.0
        for dimension, score in quality_details.items():
            weight = self.quality_weights.get(dimension, 0)
            total += score * weight
        return total
    
    def _generate_feedback(self, quality_details: Dict[str, float],
                          auto_check: Dict[str, Any],
                          llm_review: Dict[str, Any]) -> str:
        """生成反馈意见"""
        feedback_parts = []
        
        # 各维度反馈
        for dimension, score in quality_details.items():
            if score < 60:
                feedback_parts.append(f"{dimension}较低({score:.1f}分)，需要改进")
        
        # 具体问题
        all_issues = auto_check.get('issues', []) + llm_review.get('issues', [])
        if all_issues:
            feedback_parts.append("发现的问题：" + "; ".join(all_issues[:3]))
        
        if not feedback_parts:
            return "质量良好，无明显问题"
        
        return " | ".join(feedback_parts)
