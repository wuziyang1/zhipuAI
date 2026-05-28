"""module3 HTTP 路由（Flask Blueprint）"""

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from .config import is_model_configured
from .schemas import DiagnoseRequest, HealthResponse
from .service import diagnosis_service

bp = Blueprint("module3", __name__)


@bp.route("/health", methods=["GET"])
def health():
    resp = HealthResponse(
        status="ok",
        model_configured=is_model_configured(),
    )
    return jsonify(resp.model_dump())


@bp.route("/diagnose", methods=["POST"])
def diagnose():
    if not request.is_json:
        return jsonify({"detail": "Content-Type 必须为 application/json"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"detail": "请求体必须是合法的 JSON"}), 400

    try:
        req = DiagnoseRequest.model_validate(data)
    except ValidationError as exc:
        return jsonify({"detail": exc.errors()}), 422

    result = diagnosis_service.diagnose(req)
    return jsonify(result.model_dump())
