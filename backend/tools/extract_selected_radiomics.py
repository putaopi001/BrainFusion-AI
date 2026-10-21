"""Run only with the isolated PyRadiomics interpreter; no torch/CUDA imports."""
import argparse
import hashlib
import json
import logging
from pathlib import Path
import sys
import time
import numpy as np
import SimpleITK as sitk
import radiomics
from radiomics import featureextractor


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def extract(request):
    start = time.perf_counter()
    logging.getLogger('radiomics').setLevel(logging.ERROR)
    sitk.ProcessObject.SetGlobalDefaultNumberOfThreads(2)
    paths, wanted = request['sequences'], request['selected_features']
    if set(paths) != {'t1c', 't1n', 't2w', 't2f'}:
        raise ValueError('Exactly four MRI sequences required')
    if len(wanted) != len(set(wanted)) or not wanted:
        raise ValueError('Invalid selected feature schema')
    mask = sitk.ReadImage(request['mask_path'])
    mask_array = sitk.GetArrayFromImage(mask)
    if not np.isin(mask_array, [0, 1, 2, 3, 4]).all():
        raise ValueError('Mask labels must be 0..4')
    values, grouped, counts = {}, {}, {}
    for key in wanted:
        label, feature = key.split(':', 1)
        name, sequence = feature.split('.brain_') if '.brain_' in feature else (feature, 't1c')
        prefix, category, feature_name = name.split('_', 2)
        if prefix != 'original' or label not in ('1', '2', '3') or sequence not in paths:
            raise ValueError('Unsupported feature key')
        counts[label] = int(np.count_nonzero(mask_array == int(label)))
        if counts[label] == 0:
            values[key] = None
        else:
            grouped.setdefault(sequence, {}).setdefault(label, {}).setdefault(category, []).append((key, feature_name))
    for sequence, regions in grouped.items():
        image = sitk.ReadImage(paths[sequence])
        if image.GetDimension() != 3 or image.GetSize() != mask.GetSize() or np.prod(image.GetSize()) > 32_000_000:
            raise ValueError('Unsupported MRI dimensions')
        for first, second in [(image.GetOrigin(), mask.GetOrigin()), (image.GetSpacing(), mask.GetSpacing()), (image.GetDirection(), mask.GetDirection())]:
            if not np.allclose(first, second, atol=1e-4, rtol=0):
                raise ValueError('Image and mask geometry differ')
        data = sitk.GetArrayFromImage(image).astype(np.float64)
        if not np.isfinite(data).all() or data.max() <= data.min():
            raise ValueError('Invalid or constant MRI intensity')
        data -= data.min()
        data /= data.max()
        scaled = sitk.GetImageFromArray(data)
        scaled.CopyInformation(image)
        for label, classes in regions.items():
            extractor = featureextractor.RadiomicsFeatureExtractor(**request['protocol']['radiomics_settings'])
            extractor.disableAllFeatures()
            extractor.enableFeaturesByName(**{name: [feature for _, feature in entries] for name, entries in classes.items()})
            computed = extractor.execute(scaled, mask, label=int(label))
            for name, entries in classes.items():
                for key, feature in entries:
                    value = float(computed['original_' + name + '_' + feature])
                    if not np.isfinite(value):
                        raise ValueError('Nonfinite radiomics output: ' + key)
                    values[key] = value
        del image, scaled, data
    return {'status': 'succeeded', 'contract_sha256': request['contract_sha256'], 'features': values,
            'region_voxel_counts': counts, 'input_sha256': {key: digest(path) for key, path in paths.items()},
            'mask_sha256': digest(request['mask_path']), 'seconds': round(time.perf_counter() - start, 3),
            'versions': {'python': sys.version.split()[0], 'pyradiomics': radiomics.__version__,
                         'numpy': np.__version__, 'simpleitk': sitk.Version_VersionString()},
            'device': 'cpu', 'gpu_used': False, 'feature_source': request['feature_source']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = extract(json.loads(args.request.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(args.output)
    print('Selected radiomics extraction succeeded on CPU', flush=True)
