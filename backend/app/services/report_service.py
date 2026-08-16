def generate_report(ai_result):


    imaging = ai_result["results"]["imaging"]

    clinical = ai_result["results"]["clinical"]

    fusion = ai_result["results"]["fusion"]

    agent = ai_result["report_agent"]



    report = {


        "risk_level":
        fusion["risk"],



        "summary":


        f"""
BrainFusion AI完成多模态辅助分析。

MRI模型:
{imaging["model"]}


肿瘤概率:
{imaging["tumor_probability"]}


临床风险模型:
{clinical["model"]}


临床风险评分:
{clinical["risk_score"]}


融合评分:
{fusion["fusion_score"]}


综合风险:
{fusion["risk"]}


AI Agent判断:

{agent["decision"]}

""",



        "recommendation":

        agent["recommendation"]



    }


    return report