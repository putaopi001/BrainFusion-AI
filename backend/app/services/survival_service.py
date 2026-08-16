def predict_survival(radiomics: dict, age: int | None = None) -> dict:
    """基于影像组学特征 + 临床信息的生存预测。

    说明：这是科研原型级启发式占位模型（非训练所得），仅用于演示生存预测流程；
    接入真实 CoxPH / 深度学习生存模型可无缝替换。
    """
    intensity = radiomics.get("intensity", {})
    shape = radiomics.get("shape", {})
    tumor_fraction = shape.get("tumor_fraction", 0.0)
    max_intensity = intensity.get("max", 0.0)

    risk = 0.0
    risk += min(0.5, tumor_fraction * 5)              # 肿瘤负荷贡献
    risk += min(0.3, max_intensity / 1000.0)          # 增强强度贡献
    if age is not None:
        risk += min(0.2, max(0.0, (age - 40) / 200.0))  # 年龄贡献

    risk = round(min(1.0, max(0.0, risk)), 3)
    if risk >= 0.6:
        level = "high"
    elif risk >= 0.3:
        level = "medium"
    else:
        level = "low"

    months = round(24 * (1 - risk) + 3, 1) if level != "high" else round(12 * (1 - risk) + 2, 1)

    return {
        "model": "Radiomics-Survival Heuristic (占位)",
        "risk_score": risk,
        "risk_level": level,
        "estimated_survival_months": months,
        "factors": {
            "tumor_fraction": tumor_fraction,
            "max_intensity": round(max_intensity, 1),
            "age": age,
        },
    }
