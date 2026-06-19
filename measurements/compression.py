from pathlib import Path
from text_to_gds.measurement_recipes import run_measurement_recipe

OUT = Path(__file__).resolve().parent / "output"
print(run_measurement_recipe("compression", json_path=OUT / "compression.json", csv_path=OUT / "compression.csv", plot_path=OUT / "compression.png"))
