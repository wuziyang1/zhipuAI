"""
教师诊断智能体
负责诊断学生解答，给出专业评价和建议
"""

from typing import Dict, Any
from .base_agent import BaseAgent


class TeacherAgent(BaseAgent):
    """教师诊断智能体"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("TeacherAgent", config)
        self.temperature = config.get('AGENT_TEMPERATURES', {}).get('teacher', 0.3)
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        诊断学生解答
        
        Args:
            input_data: {
                'question': 题目内容,
                'student_solution': 学生解答,
                'analysis': 题目分析结果（可选）
            }
        
        Returns:
            {
                'diagnosis': 诊断评价内容,
                'process_correct': 过程是否正确,
                'result_correct': 结果是否正确
            }
        """
        question = input_data.get('question', '')
        student_solution = input_data.get('student_solution', '')
        analysis = input_data.get('analysis', {})
        
        self.log(f"开始诊断学生解答")
        
        # 构造诊断提示词
        prompt = self._build_prompt(question, student_solution, analysis)
        
        # 调用LLM
        response = self.call_llm(prompt, self.temperature)
        
        if not response:
            self.log("诊断生成失败", "ERROR")
            return self._get_empty_result()
        
        # 提取诊断结果
        import re
        process_correct = None
        result_correct = None
        
        # 提取过程判断
        process_match = re.search(r'过程是否正确[：:]\s*[【\[]?(正确|错误)[】\]]?', response)
        if process_match:
            process_correct = (process_match.group(1) == '正确')
        
        # 提取结果判断
        result_match = re.search(r'结果是否正确[：:]\s*[【\[]?(正确|错误)[】\]]?', response)
        if result_match:
            result_correct = (result_match.group(1) == '正确')
        
        self.log(f"诊断完成（过程：{'正确' if process_correct else '错误' if process_correct is not None else '未知'}, "
                f"结果：{'正确' if result_correct else '错误' if result_correct is not None else '未知'}）")
        
        return {
            'diagnosis': response,
            'process_correct': process_correct,
            'result_correct': result_correct
        }
    
    def _build_prompt(self, question: str, student_solution: str, 
                     analysis: Dict[str, Any]) -> str:
        """构造诊断提示词"""
        
        # 基础提示词
        prompt = f"""你是一个专业的数学老师。请诊断以下学生的解答。

                    题目：
                    {question}

                    学生的解答：
                    {student_solution}
                    """
        
        # 如果有题目分析，可以作为参考（但不直接告诉答案）
        knowledge_points = analysis.get('knowledge_points', [])
        if knowledge_points:
            prompt += f"""
                    参考信息（题目涉及的知识点）：
                    {', '.join(knowledge_points)}
                    """
        
        prompt += """
请你作为数学老师，评估这个学生的解答。要求：

1. 首先自己解答这道题，得出正确答案（用于内部判断）
2. 逐步分析学生解答的每一步是否正确
3. 如果有错误，指出最先出错的步骤和具体原因
4. 给出过程和结果是否正确的最终判断
5. 根据错误情况，判断学生在哪些知识点上存在欠缺
6. 给出改进建议（不要直接告诉答案）

请严格按照以下模板输出：

【解题分析】
（你作为老师对这道题的分析和正确解法，用于内部判断）

【诊断过程】
（逐步分析学生的每一步解答，指出哪里对、哪里错）

【诊断结果】
过程是否正确：[正确/错误]
结果是否正确：[正确/错误]
最先出错步骤：[第X步/无错误]
错误类型：[符号计算错误/公式记忆错误/粗心漏解/概念理解错误/其他/无错误]
错误原因：[具体说明]

【知识点欠缺分析】
（根据学生的错误，判断其在哪些知识点上存在欠缺。如果全部掌握则说明"全部掌握"）

【改进建议】
（给学生的建议，帮助其理解错误，但不直接给出答案）
"""
        
        return prompt
    
    def _get_empty_result(self) -> Dict[str, Any]:
        """返回空结果"""
        return {
            'diagnosis': '',
            'process_correct': None,
            'result_correct': None
        }
