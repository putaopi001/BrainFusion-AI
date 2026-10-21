"""Record actual cohort/split/protocol evidence and unresolved provenance issues."""
import ast
import csv
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.research.dataset import load_dataset, sha256

DATA = Path('E:/BrainFusion-Data/WAW-GliomAI-v3')
OUTPUT = Path('E:/BrainFusion-Runtime/results/stage6/research_registry.json')


def main():
    record = json.loads((DATA / 'zenodo_record.json').read_text(encoding='utf-8'))
    inventory = json.loads((DATA / 'image_archive_inventory.json').read_text(encoding='utf-8'))
    dataset = load_dataset(DATA)
    research = Path('E:/BrainFusion-Runtime/results/research')
    pointer = json.loads((research / 'latest.json').read_text(encoding='utf-8'))
    summary = json.loads((research / pointer['run_id'] / 'summary.json').read_text(encoding='utf-8'))
    assert sha256(research / pointer['run_id'] / 'summary.json') == pointer['summary_sha256']
    with (DATA / 'downloads/4_radiomics_preop.csv').open(encoding='utf-8-sig') as handle:
        rows = list(csv.DictReader(handle, delimiter=';'))
    with (DATA / 'downloads/1_1_clinical_molecular_metadata_dictionary.csv').open(encoding='utf-8-sig') as handle:
        dictionary = list(csv.DictReader(handle))
    profiles = set()
    for row in rows:
        for key, value in row.items():
            if 'Configuration_Settings' in key and value:
                settings = ast.literal_eval(value)
                settings.pop('label', None)
                profiles.add(json.dumps(settings, sort_keys=True))
    subsets = summary['split']['patient_ids']
    assert len(set().union(*map(set, subsets.values()))) == sum(map(len, subsets.values())) == 141
    assert set().union(*map(set, subsets.values())) == set(dataset.ids)
    actual_ids = {str(item['patient_id']) for item in inventory if item['patient_id'] is not None}
    assert set(dataset.ids).issubset(actual_ids)
    target_dictionary = [row for row in dictionary if 'idh' in row['Variable name'].lower()]
    result = {'status': 'passed_with_unresolved_provenance', 'created_utc': datetime.now(timezone.utc).isoformat(),
              'source': {'record_id': record['id'], 'publication_date': record['metadata']['publication_date'],
                         'license': record['metadata']['license'], 'url': 'https://zenodo.org/records/22205631'},
              'input_sha256': dataset.audit['input_sha256'], 'audit': dataset.audit,
              'image_inventory_files': len(inventory), 'image_inventory_patients': len(actual_ids),
              'published_extraction_parameter_variants': [json.loads(value) for value in sorted(profiles)],
              'target_dictionary': target_dictionary, 'actual_target_column': 'idh1/2',
              'target_encoding_note': 'dictionary spells iidh1/2 and does not explicitly specify 0/1 mapping; formal protocol needs confirmation',
              'current_split': summary['split'], 'split_sizes': summary['split_sizes'],
              'unresolved': ['Current split was already inspected: all metrics remain exploratory.',
                             'MONAI checkpoint training patient list is unavailable locally; WAW/BraTS overlap has not been excluded.',
                             'Minmax scaling inferred and numerically verified on five downloaded cases; full MRI cohort not re-extracted.',
                             'Clinical IDH dictionary spelling/encoding requires confirmation before final clinical claims.'],
              'next_protocol': {'status': 'draft_not_final_test_frozen', 'main_endpoint': 'raw IDH label 1',
                                'unit': 'patient', 'clinical_allowlist': ['age', 'female'],
                                'primary_comparisons': ['clinical', 'radiomics', 'average', 'fixed', 'validation TOPSIS'],
                                'final_evaluation_requirement': 'new uninspected holdout or verified independent external cohort'}}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': result['status'], 'patients': len(dataset.ids), 'image_ids': len(actual_ids), 'parameter_variants': len(profiles), 'unresolved': result['unresolved']}, indent=2))


if __name__ == '__main__':
    main()
