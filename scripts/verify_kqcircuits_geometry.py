"""Execute the packaged external KQCircuits worker in this isolated interpreter."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "src/textlayout/external/_kqcircuits_worker.py"), run_name="__main__")
