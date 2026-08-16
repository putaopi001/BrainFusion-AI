from abc import ABC, abstractmethod


class BasePredictor(ABC):
    """AI 预测器统一接口：未来 MedNeXt / nnUNet / Transformer 等模型实现该接口即可插拔替换。"""

    name: str = "base"
    version: str = "0.0.0"

    @abstractmethod
    def predict(self, *args, **kwargs):
        raise NotImplementedError


class BaseSegmenter(ABC):
    """影像分割器统一接口：输出 mask.nii.gz 路径。"""

    name: str = "base-segmenter"

    @abstractmethod
    def segment(self, mri_path: str) -> str:
        raise NotImplementedError


# 可插拔模型注册表
PREDICTOR_REGISTRY: dict[str, type[BasePredictor]] = {}
SEGMENTER_REGISTRY: dict[str, type[BaseSegmenter]] = {}


def register_predictor(name: str):
    def decorator(cls: type[BasePredictor]) -> type[BasePredictor]:
        PREDICTOR_REGISTRY[name] = cls
        return cls

    return decorator


def register_segmenter(name: str):
    def decorator(cls: type[BaseSegmenter]) -> type[BaseSegmenter]:
        SEGMENTER_REGISTRY[name] = cls
        return cls

    return decorator
