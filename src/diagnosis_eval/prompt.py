"""
诊断提示词（与 TeacherAgent 保持一致，确保评测与训练任务对齐）
"""

from typing import Any, Dict, List


def build_diagnosis_prompt(
    question: str,
    student_solution: str,
    knowledge_points: List[str] = None,
) -> str:
    prompt = f"""你是一个专业的数学老师。请诊断以下学生的解答。

题目：
{question}

学生的解答：
{student_solution}
"""

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


def build_case_prompt(case: Dict[str, Any]) -> str:
    return build_diagnosis_prompt(
        question=case['question'],
        student_solution=case['student_solution'],
        knowledge_points=case.get('knowledge_points'),
    )
