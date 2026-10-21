import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('MKL_NUM_THREADS', '2')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.research.experiment import run_experiment

parser = argparse.ArgumentParser(description='Small CPU IDH/fusion/federated experiment, not full training')
parser.add_argument('--data-root', default='E:/BrainFusion-Data/WAW-GliomAI-v3')
parser.add_argument('--output-root', default='E:/BrainFusion-Runtime/results/research')
parser.add_argument('--rounds', type=int, default=3)
parser.add_argument('--local-steps', type=int, default=2)
args = parser.parse_args()
result = run_experiment(args.data_root, args.output_root, args.rounds, args.local_steps)
print(json.dumps({'run_id': result['run_id'], 'patients': result['audit']['cohort_patients'],
                  'split': result['split_sizes'], 'device': result['device'],
                  'branch_models': result['branch_models'], 'fusion': result['fusion'],
                  'verification': result['verification'], 'seconds': result['seconds']}, ensure_ascii=False, indent=2))
