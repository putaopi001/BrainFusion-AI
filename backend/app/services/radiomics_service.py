from pathlib import Path

import nibabel as nib
import numpy as np
import scipy.stats


def extract_radiomics(filepath: Path) -> dict:
    """从 MRI 体数据提取影像组学特征（强度 + 形态 + 纹理）。

    说明：这是科研原型级特征提取（numpy/scipy 实现），用于演示影像组学流程；
    接入真实 PyRadiomics 可无缝替换。
    """
    image = nib.load(str(filepath))
    data = np.asanyarray(image.dataobj).astype(np.float32)

    # 只关注脑实质（强度 > 0），聚焦组织/肿瘤信号
    brain = data[data > 0]

    def safe_stat(fn, default=0.0):
        return float(fn(brain)) if brain.size else default

    intensity = {
        "mean": safe_stat(np.mean),
        "std": safe_stat(np.std),
        "min": safe_stat(np.min),
        "max": safe_stat(np.max),
        "median": safe_stat(np.median),
        "p10": safe_stat(lambda x: np.percentile(x, 10)),
        "p90": safe_stat(lambda x: np.percentile(x, 90)),
        "skewness": float(scipy.stats.skew(brain)) if brain.size > 1 else 0.0,
        "kurtosis": float(scipy.stats.kurtosis(brain)) if brain.size > 3 else 0.0,
    }

    # 肿瘤负荷：高强度区域（> mean + 1.5*std）占比，模拟增强/肿瘤区域
    high_threshold = safe_stat(np.mean) + 1.5 * safe_stat(np.std)
    tumor_voxels = int(np.sum(brain > high_threshold)) if brain.size else 0
    total_voxels = int(brain.size) if brain.size else 1

    shape = {
        "shape": list(data.shape),
        "spacing": [float(value) for value in image.header.get_zooms()[:3]],
        "brain_volume_voxels": int(brain.size),
        "tumor_volume_voxels": tumor_voxels,
        "tumor_fraction": round(tumor_voxels / total_voxels, 6),
    }

    # 纹理：灰度直方图熵
    if brain.size:
        hist, _ = np.histogram(brain, bins=64)
        hist = hist.astype(np.float64)
        hist = hist / (hist.sum() + 1e-9)
        entropy = float(-np.sum(hist * np.log(hist + 1e-9)))
    else:
        entropy = 0.0

    return {
        "intensity": intensity,
        "shape": shape,
        "entropy": round(entropy, 4),
    }
