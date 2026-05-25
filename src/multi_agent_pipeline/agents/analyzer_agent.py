"""
题目分析智能体
负责深度分析题目特征、知识点、难度等
"""

import json
import re
from typing import Dict, Any, List
from .base_agent import BaseAgent


class AnalyzerAgent(BaseAgent):
    """题目分析智能体"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__("AnalyzerAgent", config)
        self.temperature = config.get('AGENT_TEMPERATURES', {}).get('analyzer', 0.2)
    
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析题目
        
        Args:
            input_data: {
                'question': 题目内容,
                'correct_solution': 正确解析（可选）
            }
        
        Returns:
            {
                'knowledge_points': 知识点列表,
                'difficulty': 难度等级(1-5),
                'common_errors': 常见错误类型列表,
                'key_steps': 解题关键步骤列表,
                'analysis_text': 完整分析文本
            }
        """
        question = input_data.get('question', '')
        correct_solution = input_data.get('correct_solution', '')
        
        self.log(f"开始分析题目: {question[:50]}...")
        
        # 构造分析提示词
        prompt = self._build_prompt(question, correct_solution)
        
        # 调用LLM
        response = self.call_llm(prompt, self.temperature)
        
        if not response:
            self.log("题目分析失败", "ERROR")
            return self._get_empty_result()
        
        # 解析响应
        result = self._parse_response(response)
        result['analysis_text'] = response
        
        self.log(f"分析完成: 知识点{len(result['knowledge_points'])}个, 难度{result['difficulty']}星")
        
        return result
    
    def _build_prompt(self, question: str, correct_solution: str = '') -> str:
        """构造分析提示词"""
        prompt = f"""你是一个资深数学教师和题目分析专家。请深度分析以下数学题目。

                        题目：
                        {question}
                        """
        
        if correct_solution:
            prompt += f"""
                        正确解析：
                        {correct_solution}
                        """
        
        prompt += """
            请按照以下格式输出分析结果：

            【知识点分析】
            （列出这道题涉及的所有数学知识点，每个知识点一行，格式：- 知识点名称）

            【难度评估】
            难度等级：[1-5星，1星最简单，5星最难]
            难度说明：（简要说明为什么是这个难度）

            【常见错误预测】
            （预测学生在解这道题时可能犯的错误，每个错误一行，格式：- 错误类型：具体描述）

            【解题关键步骤】
            （列出解题的关键步骤，每个步骤一行，格式：- 步骤描述）

            【综合评价】
            （对这道题的综合评价，包括考查重点、适用场景等）
            """
        
        return prompt
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        result = {
            'knowledge_points': [],
            'difficulty': 3,  # 默认中等难度
            'common_errors': [],
            'key_steps': []
        }
        
        # 提取知识点
        knowledge_section = self._extract_section(response, '【知识点分析】', '【难度评估】')
        if knowledge_section:
            result['knowledge_points'] = self._extract_list_items(knowledge_section)
        
        # 提取难度
        difficulty_section = self._extract_section(response, '【难度评估】', '【常见错误预测】')
        if difficulty_section:
            difficulty_match = re.search(r'难度等级[：:]\s*(\d)', difficulty_section)
            if difficulty_match:
                result['difficulty'] = int(difficulty_match.group(1))
        
        # 提取常见错误
        errors_section = self._extract_section(response, '【常见错误预测】', '【解题关键步骤】')
        if errors_section:
            result['common_errors'] = self._extract_list_items(errors_section)
        
        # 提取关键步骤
        steps_section = self._extract_section(response, '【解题关键步骤】', '【综合评价】')
        if steps_section:
            result['key_steps'] = self._extract_list_items(steps_section)
        
        return result
    
    def _extract_section(self, text: str, start_marker: str, end_marker: str) -> str:
        """提取文本中的特定部分"""
        start_idx = text.find(start_marker)
        if start_idx == -1:
            return ''
        
        start_idx += len(start_marker)
        end_idx = text.find(end_marker, start_idx)
        
        if end_idx == -1:
            return text[start_idx:].strip()
        else:
            return text[start_idx:end_idx].strip()
    
    def _extract_list_items(self, text: str) -> List[str]:
        """从文本中提取列表项"""
        items = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            # 匹配 "- 内容" 或 "• 内容" 或 "1. 内容" 格式
            match = re.match(r'^[-•\d.]+\s*(.+)$', line)
            if match:
                items.append(match.group(1).strip())
            elif line and not line.startswith('（') and not line.startswith('【'):
                # 如果不是括号说明，也不是标题，可能是列表项
                items.append(line)
        
        return items
    
    def _get_empty_result(self) -> Dict[str, Any]:
        """返回空结果"""
        return {
            'knowledge_points': [],
            'difficulty': 3,
            'common_errors': [],
            'key_steps': [],
            'analysis_text': ''
        }
