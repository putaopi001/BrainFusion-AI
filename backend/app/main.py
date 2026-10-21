from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.core.dependencies import require_dicom_parser

require_dicom_parser()

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import get_logger, setup_logging
from app.database import Base, engine

# API routers
from app.api import cases
from app.api import debug
from app.api import mri as mri_api
from app.api import patients
from app.api import predict
from app.api import predictions
from app.api import preprocess
from app.api import reports
from app.api import upload
from app.api import analysis
from app.api import research
from app.api import pacs
from app.api import local_auth

# models（import 以便 create_all 注册表结构）
from app.models import annotation
from app.models import case
from app.models import clinical
from app.models import doctor_opinion
from app.models import feature
from app.models import mri
from app.models import patient
from app.models import prediction
from app.models import report
from app.models import analysis_run
from app.models import case_research_input


setup_logging(settings.LOG_LEVEL)
logger = get_logger("app.main")

# 创建数据库表
Base.metadata.create_all(bind=engine)


def _ensure_column(table: str, column: str, ddl: str) -> None:
    """守卫式补列：仅当列不存在时执行 ALTER TABLE（幂等）。"""
    columns = {item["name"] for item in inspect(engine).get_columns(table)}
    if column not in columns:
        with engine.begin() as connection:
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
        logger.info("schema migrated: %s.%s", table, column)


def apply_schema_updates() -> None:
    # mris
    _ensure_column("mris", "preview_error", "preview_error VARCHAR")
    _ensure_column("mris", "processed_path", "processed_path VARCHAR")
    for column in ("sequences_json", "segmentation_path", "analysis_run_id", "verified_run_id"):
        _ensure_column("mris", column, column + " VARCHAR")
    _ensure_column("mris", "input_source", "input_source VARCHAR(40)")
    _ensure_column("mris", "source_provenance_json", "source_provenance_json TEXT")
    _ensure_column("mri_annotations", "coordinate_contract", "coordinate_contract VARCHAR DEFAULT 'legacy-array-v0'")
    _ensure_column("mris", "doctor_verified", "doctor_verified BOOLEAN DEFAULT 0")
    _ensure_column("mris", "segmentation_source", "segmentation_source VARCHAR DEFAULT 'mock'")
    _ensure_column("mris", "created_time", "created_time DATETIME")
    _ensure_column("mris", "updated_time", "updated_time DATETIME")

    # mri_annotations
    _ensure_column("mri_annotations", "color", "color VARCHAR DEFAULT '#f97316'")
    _ensure_column("mri_annotations", "case_id", "case_id INTEGER")
    _ensure_column("mri_annotations", "annotation_type", "annotation_type VARCHAR DEFAULT 'other'")
    _ensure_column("mri_annotations", "voxel_coordinate", "voxel_coordinate TEXT")
    _ensure_column("mri_annotations", "points", "points TEXT")
    _ensure_column("mri_annotations", "updated_time", "updated_time DATETIME")

    # 其余实体统一补充时间戳
    _ensure_column("cases", "created_time", "created_time DATETIME")
    _ensure_column("cases", "updated_time", "updated_time DATETIME")
    _ensure_column("patients", "created_time", "created_time DATETIME")
    _ensure_column("patients", "updated_time", "updated_time DATETIME")
    _ensure_column("predictions", "updated_time", "updated_time DATETIME")
    _ensure_column("reports", "updated_time", "updated_time DATETIME")
    _ensure_column("reports", "analysis_run_id", "analysis_run_id VARCHAR")
    _ensure_column("doctor_opinions", "created_time", "created_time DATETIME")

    # 数据迁移：历史状态对齐新的 MRI 状态机语义
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE mris SET status='preview_ready' "
                "WHERE status='uploaded' AND slice_path IS NOT NULL AND slice_path != ''"
            )
        )
        connection.execute(text("UPDATE mris SET status='failed' WHERE status='preview_failed'"))


apply_schema_updates()


app = FastAPI(
    title=f"{settings.PROJECT_NAME} API",
    version=settings.VERSION,
)

# ======================
# MRI 文件静态访问
# ======================
from app.core.storage import upload_root
UPLOAD_DIR = upload_root()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ======================
# 统一异常处理（{code, message, data}）
# ======================
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "detail": exc.message, "data": None},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={"code": exc.status_code, "message": str(exc.detail), "detail": exc.detail, "data": None},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"code": 422, "message": "参数校验失败", "detail": exc.errors(), "data": None},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("未处理异常: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务器内部错误", "detail": str(exc), "data": None},
    )


# ======================
# 注册 API
# ======================
app.include_router(upload.router)
app.include_router(analysis.router)
app.include_router(research.router)
app.include_router(pacs.router)
app.include_router(local_auth.router)

@app.on_event("startup")
def recover_analysis():
    from app.services.analysis_jobs import recover_interrupted_jobs
    recover_interrupted_jobs()
    from app.services.feature_jobs import recover_interrupted
    recover_interrupted()
    from app.services.pacs_import import recover_interrupted as recover_pacs_imports
    recover_pacs_imports()
app.include_router(patients.router)
app.include_router(cases.router)
app.include_router(debug.router)
app.include_router(mri_api.router)
app.include_router(preprocess.router)
app.include_router(predict.router)
app.include_router(reports.router)
app.include_router(predictions.router)


@app.get("/")
def root():
    return {
        "code": 200,
        "message": "BrainFusion-AI Backend Running",
        "data": {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "status": "healthy",
        },
    }
