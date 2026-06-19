from pathlib import Path
from text_to_gds.measurement_recipes import run_measurement_recipe

OUT = Path(__file__).resolve().parent / "output"
print(run_measurement_recipe("pump_map", json_path=OUT / "pump_map.json", csv_path=OUT / "pump_map.csv", plot_path=OUT / "pump_map.png"))
