import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.ai.imaging.monai_segmenter import SegmentationInput, segment
from app.services.segmentation_metrics import evaluate


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.request.read_text(encoding="utf-8"))
    reference = config.pop("reference_mask", None)
    result = segment(SegmentationInput(**config))
    if reference:
        result["evaluation"] = evaluate(Path(result["mask_path"]), Path(reference))
        (Path(result["mask_path"]).parent / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
