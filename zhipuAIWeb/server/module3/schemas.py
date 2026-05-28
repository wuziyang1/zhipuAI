"""Pydantic 请求/响应模型"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class DiagnoseRequest(BaseModel):
    question: str = Field(..., min_length=1, description="题目全文")
    student_solution: str = Field(..., min_length=1, description="学生作答")
    knowledge_points: Optional[List[str]] = Field(default=None, description="可选知识点")
    include_analysis: bool = Field(default=False, description="是否先进行题目分析")
    correct_solution: Optional[str] = Field(default=None, description="正确解析，供分析参考")

    @field_validator("question", "student_solution")
    @classmethod
    def strip_and_check_non_empty(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("不能为空")
        return stripped


class FormatInfo(BaseModel):
    complete: bool
    missing_sections: List[str] = []
    has_process_judgment: bool = False
    has_result_judgment: bool = False
    completeness_score: float = 0.0


class ParsedDiagnosis(BaseModel):
    process_correct: Optional[bool] = None
    result_correct: Optional[bool] = None
    error_step: Optional[int] = None
    error_type: Optional[str] = None
    format: FormatInfo


class AnalysisResult(BaseModel):
    knowledge_points: List[str] = []
    difficulty: Optional[int] = None
    common_errors: List[str] = []
    key_steps: List[str] = []
    analysis_text: Optional[str] = None


class DiagnoseResponse(BaseModel):
    diagnosis: str
    process_correct: Optional[bool] = None
    result_correct: Optional[bool] = None
    parsed: ParsedDiagnosis
    analysis: Optional[AnalysisResult] = None


class HealthResponse(BaseModel):
    status: str
    model_configured: bool


class ErrorResponse(BaseModel):
    detail: str
