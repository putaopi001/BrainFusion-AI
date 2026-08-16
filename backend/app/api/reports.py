from fastapi import APIRouter

from app.services.report_service import generate_report


router = APIRouter(
    prefix="/reports",
    tags=["reports"]
)



# 临时保存报告
reports_cache={}




@router.post("/generate/{case_id}")
def create_report(case_id:int):


    from app.services.ai_service import AIService



    # 这里读取一次AI结果

    ai_service=AIService()



    result = ai_service.predict(

        case_id,


        "uploads/case_1/BraTS20_Training_001_flair.nii",


        {

        "age":50,

        "gender":"unknown"

        }

    )



    report = generate_report(result)



    reports_cache[case_id]=report



    return {


        "message":
        "report generated",


        "data":
        report

    }





@router.get("/{case_id}")
def get_report(case_id:int):


    return {


        "data":
        reports_cache.get(

            case_id,

            {}

        )

    }