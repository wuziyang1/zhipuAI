"""
学生模拟智能体
模拟不同水平的学生解题
"""

import random
from typing import Dict, Any
from .base_agent import BaseAgent


class StudentAgent(BaseAgent):
    """学生模拟智能体"""
    
    def __init__(self, config: Dict[str, Any], level_config: Dict[str, Any]):
        """
        初始化学生智能体
        
        Args:
            config: 全局配置
            level_config: 学生水平配置 {
                'name': 水平名称,
                'description': 描述,
                'correct_rate': 正确率,
                'temperature': 温度参数,
                'characteristics': 特征描述
            }
        """
        super().__init__(f"StudentAgent-{level_config['name']}", config)
        self.level_config = level_config
        self.temperature = level_config.get('temperature', 0.5)
        self.correct_rate = level_config.get('correct_rate', 0.7)
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        模拟学生解题
        
        Args:
            input_data: {
                'question': 题目内容,
                'analysis': 题目分析结果（可选）
            }
        
        Returns:
            {
                'student_solution': 学生解答,
                'student_level': 学生水平,
                'target_correct': 目标是否正确（用于后续验证）
            }
        """
        question = input_data.get('question', '')
        analysis = input_data.get('analysis', {})
        
        self.log(f"开始模拟{self.level_config['description']}解题")
        
        # 1. 根据正确率决定这次是否要生成正确答案
        target_correct = random.random() < self.correct_rate
        
        # 2. 构造提示词
        prompt = self._build_prompt(question, analysis, target_correct)
        
        # 3. 调用LLM
        response = self.call_llm(prompt, self.temperature)
        
        if not response:
            self.log("学生解答生成失败", "ERROR")
            return self._get_empty_result()
        
        self.log(f"解答生成完成（目标：{'正确' if target_correct else '错误'}）")
        
        #4. 返回结果
        return {
            'student_solution': response,
            'student_level': self.level_config['name'],
            'student_description': self.level_config['description'],
            'target_correct': target_correct
        }
    
    def _build_prompt(self, question: str, analysis: Dict[str, Any], 
                     target_correct: bool) -> str:
        """构造学生解题提示词"""
        
        characteristics = self.level_config.get('characteristics', '')
        common_errors = analysis.get('common_errors', [])
        
        if target_correct:
            # 生成正确解答
            prompt = f"""你是一个{self.level_config['description']}，特点是：{characteristics}。

                请认真解答以下数学题目：

                题目：
                {question}

                要求：
                1. 仔细审题，理解题意
                2. 按照"第一步：... 第二步：..."的格式输出解题步骤
                3. 每一步都要详细说明思路和计算过程
                4. 最后给出明确的答案

                请开始解答："""
                        
        else:
            # 生成错误解答
            error_hints = ""
            if common_errors:
                # 随机选择1-2个常见错误作为提示
                selected_errors = random.sample(common_errors, min(2, len(common_errors)))
                error_hints = "\n可能出现的错误：\n" + "\n".join(f"- {err}" for err in selected_errors)
            
            prompt = f"""你是一个{self.level_config['description']}，特点是：{characteristics}。

                    请解答以下数学题目（注意：你可能会犯一些错误）：

                    题目：
                    {question}
                    {error_hints}

                    要求：
                    1. 按照"第一步：... 第二步：..."的格式输出解题步骤
                    2. 尽力解答，但可能会出现以下情况：
                    - 公式记错或混淆
                    - 符号计算错误
                    - 粗心漏解或多解
                    - 概念理解偏差
                    3. 即使不确定也要给出答案

                    请开始解答："""
        
        return prompt
    
    def _get_empty_result(self) -> Dict[str, Any]:
        """返回空结果"""
        return {
            'student_solution': '',
            'student_level': self.level_config['name'],
            'student_description': self.level_config['description'],
            'target_correct': None
        }
