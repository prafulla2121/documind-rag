import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from evals.run_evals import isolate_storage  # noqa: E402

# Must happen before anything imports `app`: all tests write to a temp data dir.
isolate_storage()
