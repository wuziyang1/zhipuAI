"""
从诊断文本中解析结构化字段
"""

import re
from typing import Any, Dict, Optional

CN_STEP_NUM = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
}

REQUIRED_SECTIONS = [
    '【解题分析】',
    '【诊断过程】',
    '【诊断结果】',
    '【知识点欠缺分析】',
    '【改进建议】',
]

ERROR_TYPES = [
    '符号计算错误', '公式记忆错误', '粗心漏解',
    '概念理解错误', '其他', '无错误',
]


def parse_bool_judgment(text: str, field: str) -> Optional[bool]:
    """解析「过程/结果是否正确」"""
    pattern = rf'{field}[：:]\s*[【\[]?(正确|错误)[】\]]?'
    match = re.search(pattern, text)
    if match:
        return match.group(1) == '正确'
    return None


def parse_error_step(text: str) -> Optional[int]:
    """
    解析「最先出错步骤」
    返回 0 表示无错误，正整数表示第 N 步，None 表示无法解析
    """
    match = re.search(r'最先出错步骤[：:]\s*(.+)', text)
    if not match:
        return None

    value = match.group(1).strip().split('\n')[0].strip('[]【】 ')

    if not value or '无错误' in value or value == '无':
        return 0

    num_match = re.search(r'第(\d+)步', value)
    if num_match:
        return int(num_match.group(1))

    for cn, num in CN_STEP_NUM.items():
        if f'第{cn}步' in value:
            return num

    return None


def parse_error_type(text: str) -> Optional[str]:
    """解析「错误类型」"""
    match = re.search(r'错误类型[：:]\s*(.+)', text)
    if not match:
        return None

    value = match.group(1).strip().split('\n')[0].strip('[]【】 ')

    if not value or value == '无':
        return '无错误'

    for err_type in ERROR_TYPES:
        if err_type in value:
            return err_type

    return value


def check_format_completeness(text: str) -> Dict[str, Any]:
    """检查诊断格式完整性"""
    missing = [s for s in REQUIRED_SECTIONS if s not in text]
    has_process = '过程是否正确' in text
    has_result = '结果是否正确' in text

    return {
        'complete': len(missing) == 0 and has_process and has_result,
        'missing_sections': missing,
        'has_process_judgment': has_process,
        'has_result_judgment': has_result,
        'completeness_score': (len(REQUIRED_SECTIONS) - len(missing)) / len(REQUIRED_SECTIONS),
    }


def parse_diagnosis(text: str) -> Dict[str, Any]:
    """从诊断文本解析全部结构化字段"""
    fmt = check_format_completeness(text)
    return {
        'process_correct': parse_bool_judgment(text, '过程是否正确'),
        'result_correct': parse_bool_judgment(text, '结果是否正确'),
        'error_step': parse_error_step(text),
        'error_type': parse_error_type(text),
        'format': fmt,
    }
