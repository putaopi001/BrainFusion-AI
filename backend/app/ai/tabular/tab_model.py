from app.ai.interfaces import BasePredictor, register_predictor


@register_predictor("tabicl_v2")
class TabularModel(BasePredictor):
    """临床风险模型（TabICL-v2 测试结果占位）。"""

    name = "TabICL-v2"
    version = "0.1.0"

    def predict(self, patient_data: dict) -> dict:
        return {
            "risk_score": 0.78,
            "model": self.name,
        }
