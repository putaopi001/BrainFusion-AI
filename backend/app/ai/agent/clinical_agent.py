class ClinicalAgent:


    def analyze(
        self,
        mri_result,
        tab_result,
        fusion_result
    ):


        tumor_probability = (
            mri_result.get(
                "tumor_probability",
                0
            )
        )


        risk_score = (
            tab_result.get(
                "risk_score",
                0
            )
        )


        fusion_score = (
            fusion_result.get(
                "fusion_score",
                0
            )
        )



        if fusion_score>=0.7:

            decision="high risk"


            recommendation=[

                "建议神经外科进一步评估",

                "建议增强MRI检查",

                "建议病理检查"

            ]



        else:


            decision="low risk"


            recommendation=[

                "定期MRI随访"

            ]





        return {


            "decision":
            decision,


            "reason":[

                f"MRI肿瘤概率:{tumor_probability}",

                f"临床风险评分:{risk_score}",

                f"融合评分:{fusion_score}"

            ],


            "recommendation":
            recommendation

        }