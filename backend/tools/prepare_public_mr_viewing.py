"""Prepare a public classic-MR derivative after explicit source-bound review."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.public_mr_preparation import prepare_reviewed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-dir', 'source-record', 'review-dir', 'review-record', 'output-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--patient-id', required=True)
    args = parser.parse_args()
    report = prepare_reviewed(args.source_dir, args.source_record, args.review_dir,
                              args.review_record, args.output_dir, args.patient_id)
    print('Public MR derivative verified:', report['instance_count'], 'instances; no PACS write or AI activation.')


if __name__ == '__main__':
    main()
