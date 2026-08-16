from app.ai.interfaces import BasePredictor, register_predictor


@register_predictor("mri_baseline")
class MRIModel(BasePredictor):
    """MRI 影像基线模型（占位，可替换为 MedNeXt / nnUNet）。"""

    name = "MRI Baseline Model"
    version = "0.1.0"

    def predict(self, feature: dict) -> dict:
        voxel_number = feature.get("voxel_number", 0)
        probability = 0.85 if voxel_number > 1000000 else 0.65
        return {
            "model": self.name,
            "task": "tumor_detection",
            "tumor_probability": probability,
            "feature": feature,
            "status": "baseline",
        }
