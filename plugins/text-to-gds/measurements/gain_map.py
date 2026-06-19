from pathlib import Path
from text_to_gds.measurement_recipes import run_measurement_recipe

OUT = Path(__file__).resolve().parent / "output"
print(run_measurement_recipe("gain_map", json_path=OUT / "gain_map.json", csv_path=OUT / "gain_map.csv", plot_path=OUT / "gain_map.png"))
