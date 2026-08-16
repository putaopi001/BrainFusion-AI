from app.ai.interfaces import BasePredictor, register_predictor


@register_predictor("fusion_layer")
class FusionModel(BasePredictor):
    """多模态融合层：加权融合 MRI 与临床风险评分。"""

    name = "BrainFusion Fusion Layer"
    version = "0.1.0"

    def predict(self, mri_result: dict, tab_result: dict) -> dict:
        mri_score = mri_result.get("tumor_probability", 0)
        clinical_score = tab_result.get("risk_score", 0)
        final_score = 0.6 * mri_score + 0.4 * clinical_score
        return {
            "model": self.name,
            "fusion_score": round(final_score, 3),
            "risk": "high" if final_score >= 0.7 else "low",
        }
