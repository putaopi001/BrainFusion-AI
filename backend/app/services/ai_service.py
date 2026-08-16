from app.ai.imaging.mri_model import MRIModel
from app.ai.tabular.tab_model import TabularModel
from app.ai.fusion.fusion_model import FusionModel
from app.ai.agent.clinical_agent import ClinicalAgent

from app.services.feature_service import extract_mri_feature



class AIService:


    def __init__(self):


        """
        BrainFusion AI核心服务

        模型初始化一次
        """


        self.mri_model = MRIModel()


        self.tab_model = TabularModel()


        self.fusion_model = FusionModel()


        self.agent = ClinicalAgent()





    def predict(
        self,
        case_id:int,
        mri_path:str,
        clinical_data:dict
    ):


        try:



            # =================================================
            # 1. MRI Analysis
            # =================================================


            mri_feature = extract_mri_feature(
                mri_path
            )


            mri_result = self.mri_model.predict(
                mri_feature
            )


            print("================ MRI RESULT ================")
            print(mri_result)
            print("============================================")





            # =================================================
            # 2. Clinical / Tabular Analysis
            # =================================================


            tab_result = self.tab_model.predict(
                clinical_data
            )


            print("================ TAB RESULT ================")
            print(tab_result)
            print("============================================")






            # =================================================
            # 3. Multi-modal Fusion
            # =================================================


            fusion_result = self.fusion_model.predict(

                mri_result,

                tab_result

            )


            print("================ FUSION RESULT ================")
            print(fusion_result)
            print("================================================")






            # =================================================
            # 4. Clinical Agent Report Generation
            # =================================================


            agent_result = self.agent.analyze(

                mri_result,

                tab_result,

                fusion_result

            )


            print("================ AGENT RESULT ================")
            print(agent_result)
            print("================================================")






            # =================================================
            # Final Response
            # =================================================


            return {


                "case_id":
                case_id,


                "model_version":
                "BrainFusion-v0.4",



                "results":{


                    "imaging":mri_result,


                    "clinical":
                    tab_result,


                    "fusion":
                    fusion_result
                },



                "report_agent":
                 agent_result
}





        except Exception as e:



            print(
                "AI SERVICE ERROR:",
                e
            )



            return {


                "case_id":case_id,


                "error":str(e),


                "status":"failed"

            }