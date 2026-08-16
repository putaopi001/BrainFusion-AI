from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import json

from app.database import get_db

from app.models.case import Case
from app.models.patient import Patient
from app.models.mri import MRI

from app.models.prediction import Prediction
from app.models.report import Report

from app.services.ai_service import AIService


# ============================================================
# Router
# ============================================================

router = APIRouter(
    prefix="/predict",
    tags=["predict"]
)


# ============================================================
# AI Service
# ============================================================

ai_service = AIService()


# ============================================================
# 运行 AI 分析
# POST /predict/{case_id}
# ============================================================

@router.post("/{case_id}")
def predict(
    case_id: int,
    db: Session = Depends(get_db)
):

    try:

        # ====================================================
        # 1. 查询病例
        # ====================================================

        case = db.query(Case).filter(
            Case.id == case_id
        ).first()

        if not case:

            raise HTTPException(
                status_code=404,
                detail=f"病例 {case_id} 不存在"
            )


        # ====================================================
        # 2. 查询患者
        # ====================================================

        patient = db.query(Patient).filter(
            Patient.id == case.patient_id
        ).first()


        if not patient:

            raise HTTPException(
                status_code=404,
                detail=f"病例 {case_id} 对应的患者不存在"
            )


        # ====================================================
        # 3. 查询 MRI
        # ====================================================

        mri = db.query(MRI).filter(
            MRI.case_id == case_id
        ).order_by(
            MRI.id.desc()
        ).first()


        if not mri:

            raise HTTPException(
                status_code=404,
                detail=f"病例 {case_id} 暂无 MRI 数据"
            )


        # ====================================================
        # 4. 获取 MRI 文件路径
        # ====================================================

        mri_path = mri.filepath


        if not mri_path:

            raise HTTPException(
                status_code=400,
                detail="MRI 文件路径为空"
            )


        print("")
        print("============================================")
        print("开始 BrainFusion AI 分析")
        print("============================================")

        print("病例 ID:", case_id)
        print("患者 ID:", patient.id)
        print("患者姓名:", patient.name)
        print("患者年龄:", patient.age)
        print("患者性别:", patient.gender)
        print("MRI 文件:", mri.filename)
        print("MRI 路径:", mri_path)

        print("============================================")
        print("")


        # ====================================================
        # 5. 构建临床信息
        # ====================================================

        clinical_data = {

            "age": patient.age,

            "gender": patient.gender

        }


        # ====================================================
        # 6. 调用 AI Service
        # ====================================================

        result = ai_service.predict(

            case_id,

            mri_path,

            clinical_data

        )


        print("")
        print("================ AI RESULT ================")
        print(result)
        print("============================================")
        print("")


        # ====================================================
        # 7. 获取 AI 分析结果
        # ====================================================

        imaging = result["results"]["imaging"]

        clinical = result["results"]["clinical"]

        fusion = result["results"]["fusion"]

        agent = result["report_agent"]


        # ====================================================
        # 8. 打印各模块结果
        # ====================================================

        print("================ MRI RESULT ================")
        print(imaging)
        print("============================================")

        print("================ TAB RESULT ================")
        print(clinical)
        print("============================================")

        print("================ FUSION RESULT =============")
        print(fusion)
        print("============================================")

        print("================ AGENT RESULT ==============")
        print(agent)
        print("============================================")


        # ====================================================
        # 9. 查询该病例以前是否已经有 Prediction
        #
        # 如果有：
        #     更新原来的结果
        #
        # 如果没有：
        #     创建新的 Prediction
        # ====================================================

        prediction = db.query(Prediction).filter(
            Prediction.case_id == case_id
        ).order_by(
            Prediction.id.desc()
        ).first()


        if prediction:

            prediction.tumor_probability = (
                imaging["tumor_probability"]
            )

            prediction.risk_score = (
                clinical["risk_score"]
            )

            prediction.fusion_score = (
                fusion["fusion_score"]
            )

            prediction.risk_level = (
                fusion["risk"]
            )

            prediction.model_version = (
                result["model_version"]
            )

        else:

            prediction = Prediction(

                case_id=case_id,

                tumor_probability=(
                    imaging["tumor_probability"]
                ),

                risk_score=(
                    clinical["risk_score"]
                ),

                fusion_score=(
                    fusion["fusion_score"]
                ),

                risk_level=(
                    fusion["risk"]
                ),

                model_version=(
                    result["model_version"]
                )

            )

            db.add(prediction)


        # ====================================================
        # 10. 查询该病例以前的 Report
        #
        # 同样采用：
        # 有则更新
        # 无则创建
        # ====================================================

        report = db.query(Report).filter(
            Report.case_id == case_id
        ).order_by(
            Report.id.desc()
        ).first()


        # ====================================================
        # 11. 将 Agent 结果转换成 JSON
        # ====================================================

        summary_json = json.dumps(

            agent.get(
                "reason",
                []
            ),

            ensure_ascii=False

        )


        recommendation_json = json.dumps(

            agent.get(
                "recommendation",
                []
            ),

            ensure_ascii=False

        )


        # ====================================================
        # 12. 更新 / 创建 Report
        # ====================================================

        if report:

            report.risk_level = (
                fusion["risk"]
            )

            report.summary = (
                summary_json
            )

            report.recommendation = (
                recommendation_json
            )

        else:

            report = Report(

                case_id=case_id,

                risk_level=(
                    fusion["risk"]
                ),

                summary=summary_json,

                recommendation=recommendation_json

            )

            db.add(report)


        # ====================================================
        # 13. 更新病例状态
        # ====================================================

        case.status = "analyzed"
        mri.status = "analyzed"


        # ====================================================
        # 14. 提交数据库
        # ====================================================

        db.commit()


        # ====================================================
        # 15. 刷新数据库对象
        # ====================================================

        db.refresh(prediction)

        db.refresh(report)

        db.refresh(case)


        # ====================================================
        # 16. 返回结果
        # ====================================================

        return {

            "code": 200,

            "message": "AI 分析成功",

            "prediction_id": prediction.id,

            "report_id": report.id,

            "data": result

        }


    # ========================================================
    # HTTPException
    # ========================================================

    except HTTPException:

        db.rollback()

        raise


    # ========================================================
    # 其他异常
    # ========================================================

    except Exception as e:

        db.rollback()

        print("")
        print("============================================")
        print("PREDICT ERROR")
        print("============================================")
        print(type(e).__name__)
        print(str(e))
        print("============================================")
        print("")


        raise HTTPException(

            status_code=500,

            detail=str(e)

        )