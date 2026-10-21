"""Pinned MONAI SegResNet inference; reference masks never enter inference."""
import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

import nibabel as nib
import numpy as np


@dataclass
class SegmentationInput:
    sequences: dict[str, str]
    output_dir: str
    model_dir: str
    roi: tuple[int, int, int] = (128, 128, 96)
    gpu_budget_mb: int = 6000
    expected_input_sha256: dict[str, str] | None = None


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def segment(request: SegmentationInput) -> dict:
    import torch
    from monai.inferers import sliding_window_inference
    from monai.networks.nets import SegResNet

    required = ("t1c", "t1n", "t2w", "t2f")
    if set(request.sequences) != set(required):
        raise ValueError("Four aligned sequences are required: t1c, t1n, t2w, t2f")
    expected = request.expected_input_sha256
    if expected is not None and (set(expected) != set(required)
            or any(not isinstance(value, str) or len(value) != 64
                   or any(char not in '0123456789abcdef' for char in value) for value in expected.values())):
        raise ValueError("Reviewed DICOM input hash manifest is invalid")
    weights = Path(request.model_dir) / "models/model.pt"
    if not weights.is_file():
        raise FileNotFoundError("Real pretrained MONAI weights are unavailable")
    if sha256(weights) != "860ccb3f1c21c99d0410ad8a1ac4ef6b8fab60cec0a503b0ba42675741a750ae":
        raise ValueError("Pretrained checkpoint checksum mismatch")
    from app.services.study_validation import validate_sequences
    reference = validate_sequences(request.sequences)
    if not 256 <= request.gpu_budget_mb <= 6000 or len(request.roi) != 3 or any(not 16 <= n <= 128 or n % 16 for n in request.roi):
        raise ValueError("Use a 256–6000 MB GPU budget and ROI multiples of 16 up to 128")
    original_orientation = nib.orientations.io_orientation(reference.affine)
    lps = nib.orientations.axcodes2ornt(("L", "P", "S"))
    to_lps = nib.orientations.ornt_transform(original_orientation, lps)
    channels = []
    fingerprints = {}
    for key in required:
        if expected is not None and sha256(request.sequences[key]) != expected[key]:
            raise ValueError(f"Reviewed DICOM input changed before inference: {key}")
        image = nib.load(request.sequences[key])
        if image.shape != reference.shape or not np.allclose(image.affine, reference.affine, atol=1e-4, rtol=0):
            raise ValueError(f"Sequence geometry mismatch: {key}")
        array = np.asarray(nib.orientations.apply_orientation(image.get_fdata(dtype=np.float32), to_lps))
        if not np.isfinite(array).all():
            raise ValueError(f"Nonfinite MRI values: {key}")
        nonzero = array != 0
        if not nonzero.any():
            raise ValueError(f"Empty sequence: {key}")
        mean, std = float(array[nonzero].mean()), float(array[nonzero].std())
        array = array.copy()
        array[nonzero] = (array[nonzero] - mean) / max(std, 1e-8)
        channels.append(array)
        fingerprints[key] = sha256(request.sequences[key])
        if expected is not None and fingerprints[key] != expected[key]:
            raise ValueError(f"Reviewed DICOM input changed while loading for inference: {key}")
    tensor = torch.from_numpy(np.stack(channels)[None].copy())  # CPU input/output.
    del channels
    device = "cpu"
    if torch.cuda.is_available():
        free, total = torch.cuda.mem_get_info()
        if free >= 3 * 1024**3:
            budget = min(request.gpu_budget_mb * 1024**2, int(free * 0.65))
            torch.cuda.set_per_process_memory_fraction(min(budget / total, 0.55))
            torch.cuda.reset_peak_memory_stats()
            device = "cuda"
    network = SegResNet(blocks_down=[1, 2, 2, 4], blocks_up=[1, 1, 1], init_filters=16,
                        in_channels=4, out_channels=3, dropout_prob=0.2)
    state = torch.load(weights, map_location="cpu", weights_only=True)
    network.load_state_dict(state.get("model", state))
    network.eval()
    start = time.perf_counter()
    roi = request.roi
    fallback = None
    try:
        network.to(device)
        with torch.inference_mode(), torch.autocast("cuda", enabled=device == "cuda"):
            logits = sliding_window_inference(tensor, roi, 1, network, overlap=0.25,
                                              sw_device=device, device="cpu", progress=False)
    except torch.cuda.OutOfMemoryError:
        # One conservative retry on CPU, no GPU batch-size escalation.
        fallback = "GPU allocation budget reached; inference retried on CPU"
        network.to("cpu")
        torch.cuda.empty_cache()
        device = "cpu"
        with torch.inference_mode():
            logits = sliding_window_inference(tensor, roi, 1, network, overlap=0.25,
                                              sw_device="cpu", device="cpu", progress=False)
    binary = (logits[0].float().sigmoid().numpy() >= 0.5)
    # Official output: TC, WT, ET; enforce nesting, encode WAW ET as 3.
    et = binary[2]
    tc = binary[0] | et
    wt = binary[1] | tc
    mask = np.zeros(wt.shape, dtype=np.uint8)
    mask[wt] = 2
    mask[tc] = 1
    mask[et] = 3
    inverse = nib.orientations.ornt_transform(lps, original_orientation)
    mask = nib.orientations.apply_orientation(mask, inverse).copy()
    output = Path(request.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    mask_path = output / "prediction.nii.gz"
    temporary = output / "prediction.part.nii.gz"
    result_image = nib.Nifti1Image(mask, reference.affine)
    result_image.set_qform(reference.get_qform(), int(reference.header["qform_code"]))
    result_image.set_sform(reference.get_sform(), int(reference.header["sform_code"]))
    nib.save(result_image, temporary)
    temporary.replace(mask_path)
    peak = round(torch.cuda.max_memory_allocated() / 1024**2, 2) if torch.cuda.is_available() else 0
    source = json.loads((Path(request.model_dir) / "source.json").read_text(encoding="utf-8"))
    result = {"source": "model", "model": "MONAI BraTS SegResNet", "revision": source["sha"],
              "checkpoint_sha256": sha256(weights), "input_sha256": fingerprints,
              "mask_path": str(mask_path), "mask_sha256": sha256(mask_path),
              "labels": {"1": "core", "2": "FLAIR abnormality", "3": "enhancing"},
              "regions": {"TC": [1, 3], "WT": [1, 2, 3], "ET": [3]},
              "device": device, "roi": list(roi), "gpu_budget_mb": request.gpu_budget_mb,
              "peak_gpu_allocated_mb": peak, "seconds": round(time.perf_counter() - start, 2),
              "fallback": fallback, "preprocessing": "LPS; nonzero channelwise normalization; 1 mm",
              "coordinate_space": "original MRI", "purpose": "research prototype"}
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    del network, logits, tensor
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return result
