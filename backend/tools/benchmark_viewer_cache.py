"""Measure repeated metadata and mask validation, not network/GPU throughput."""
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services import mri_service as service

ROOT = Path('E:/BrainFusion-Runtime/results/stage5')
ROOT.mkdir(parents=True, exist_ok=True)
data = Path('E:/BrainFusion-Data/WAW-GliomAI-v3/sample')
rows = []
for patient in (4, 13, 16, 17, 19):
    source = data / f'images/gliomai_preop_scans_renamed/{patient}/{patient}_0_brain_t2f.nii.gz'
    mask = Path(f'E:/BrainFusion-Runtime/results/stage1/{patient}/prediction.nii.gz')
    record = {'source_patient_id': patient, 'requests_each': 3}
    mri = SimpleNamespace(segmentation_path=str(mask))
    for name, method, cache in [('metadata', lambda: service.get_volume_metadata(source), service._metadata_cached),
                                ('mask_validation', lambda: service.ensure_segmentation_mask(mri, source), service._validate_mask_cached)]:
        cache.cache_clear()
        start = time.perf_counter()
        for _ in range(3):
            cache.cache_clear()
            method()
        record[name + '_uncached_seconds'] = round(time.perf_counter() - start, 6)
        # Warm cache; same file fingerprints and same values.
        start = time.perf_counter()
        for _ in range(3):
            method()
        record[name + '_warm_seconds'] = round(time.perf_counter() - start, 6)
    rows.append(record)
result = {'status': 'passed', 'samples': rows, 'scope': '3 repeated calls per sample, warm OS cache, no network; cold values excluded from warm timing',
          'total_uncached_seconds': round(sum(r['metadata_uncached_seconds'] + r['mask_validation_uncached_seconds'] for r in rows), 6),
          'total_warm_seconds': round(sum(r['metadata_warm_seconds'] + r['mask_validation_warm_seconds'] for r in rows), 6)}
(ROOT / 'cache_benchmark.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
