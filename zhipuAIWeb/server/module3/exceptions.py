"""module3 异常定义"""


class DiagnosisError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ServiceUnavailableError(DiagnosisError):
    def __init__(self, message: str = "Gemini API 未配置，请检查环境变量"):
        super().__init__(message, status_code=503)


class LLMUnavailableError(DiagnosisError):
    def __init__(self, message: str = "LLM 调用失败，请稍后重试"):
        super().__init__(message, status_code=502)
