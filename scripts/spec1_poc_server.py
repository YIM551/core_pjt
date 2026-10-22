"""Launch the original Day 1 PoC with recorded input/output limits."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "source/2회차_day1/page47_PoC_서버/PoC_FastAPI서버.py"
spec = importlib.util.spec_from_file_location("spec1_original_poc", path)
poc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(poc)
poc.VLM_MAX_NEW_TOKENS = 80
original_describe = poc._run_vlm_inference


def bounded_describe(image):
    image = image.copy()
    image.thumbnail((448, 448))
    return original_describe(image)


poc._run_vlm_inference = bounded_describe
app = poc.app
