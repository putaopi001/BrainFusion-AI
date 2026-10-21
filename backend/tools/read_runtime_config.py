import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.runtime_config import load_runtime_config
print(json.dumps(load_runtime_config(sys.argv[1])))
