"""
桥接 multi_agent_pipeline Agent，集中管理 sys.path 注入与单例
"""

from typing import Any, Dict, Optional

from .config import build_agent_config, ensure_pipeline_imports, is_model_configured


_config: Optional[Dict[str, Any]] = None
_teacher_agent = None
_analyzer_agent = None


def get_agent_config() -> Dict[str, Any]:
    global _config
    if _config is None:
        ensure_pipeline_imports()
        _config = build_agent_config()
    return _config


def get_teacher_agent():
    global _teacher_agent
    if _teacher_agent is None:
        if not is_model_configured():
            raise RuntimeError("Gemini API 未配置，请检查 .env 中的 Gemini_API_KEY / Gemini_BASE_URL / Gemini_MODEL_NAME")
        ensure_pipeline_imports()
        from agents.teacher_agent import TeacherAgent
        _teacher_agent = TeacherAgent(get_agent_config())
    return _teacher_agent


def get_analyzer_agent():
    global _analyzer_agent
    if _analyzer_agent is None:
        if not is_model_configured():
            raise RuntimeError("Gemini API 未配置，请检查 .env 中的 Gemini_API_KEY / Gemini_BASE_URL / Gemini_MODEL_NAME")
        ensure_pipeline_imports()
        from agents.analyzer_agent import AnalyzerAgent
        _analyzer_agent = AnalyzerAgent(get_agent_config())
    return _analyzer_agent


def get_parse_diagnosis():
    ensure_pipeline_imports()
    from diagnosis_eval.parser import parse_diagnosis
    return parse_diagnosis
