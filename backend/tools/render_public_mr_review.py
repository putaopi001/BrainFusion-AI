"""Render all supported public MR instances with byte-bound review evidence."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.public_mr_preparation import render_review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-dir', 'source-record', 'output-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    manifest = render_review(args.source_dir, args.source_record, args.output_dir)
    print('Rendered', len(manifest['source_snapshot']['files']), 'instances in', len(manifest['sheets']),
          'sheets. Review template is incomplete; no derivative or archive was created.')


if __name__ == '__main__':
    main()
