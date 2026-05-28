"""诊断业务编排"""

from typing import Any, Dict, Optional

from .config import is_model_configured
from .exceptions import LLMUnavailableError, ServiceUnavailableError
from .pipeline_bridge import (
    get_analyzer_agent,
    get_parse_diagnosis,
    get_teacher_agent,
)
from .schemas import (
    AnalysisResult,
    DiagnoseRequest,
    DiagnoseResponse,
    FormatInfo,
    ParsedDiagnosis,
)


class DiagnosisService:
    def diagnose(self, request: DiagnoseRequest) -> DiagnoseResponse:
        if not is_model_configured():
            raise ServiceUnavailableError()

        analysis: Dict[str, Any] = {}
        analysis_result: Optional[AnalysisResult] = None

        if request.include_analysis:
            analyzer = get_analyzer_agent()
            raw_analysis = analyzer.process({
                "question": request.question,
                "correct_solution": request.correct_solution or "",
            })
            if raw_analysis:
                analysis = raw_analysis
                analysis_result = AnalysisResult(
                    knowledge_points=raw_analysis.get("knowledge_points", []),
                    difficulty=raw_analysis.get("difficulty"),
                    common_errors=raw_analysis.get("common_errors", []),
                    key_steps=raw_analysis.get("key_steps", []),
                    analysis_text=raw_analysis.get("analysis_text"),
                )
        elif request.knowledge_points:
            analysis = {"knowledge_points": request.knowledge_points}

        teacher = get_teacher_agent()
        result = teacher.process({
            "question": request.question,
            "student_solution": request.student_solution,
            "analysis": analysis,
        })

        diagnosis_text = result.get("diagnosis", "")
        if not diagnosis_text:
            raise LLMUnavailableError()

        parse_diagnosis = get_parse_diagnosis()
        parsed_raw = parse_diagnosis(diagnosis_text)

        parsed = ParsedDiagnosis(
            process_correct=parsed_raw.get("process_correct"),
            result_correct=parsed_raw.get("result_correct"),
            error_step=parsed_raw.get("error_step"),
            error_type=parsed_raw.get("error_type"),
            format=FormatInfo(**parsed_raw.get("format", {})),
        )

        return DiagnoseResponse(
            diagnosis=diagnosis_text,
            process_correct=result.get("process_correct"),
            result_correct=result.get("result_correct"),
            parsed=parsed,
            analysis=analysis_result,
        )


diagnosis_service = DiagnosisService()
