from pathlib import Path
from text_to_gds.measurement_recipes import run_measurement_recipe

OUT = Path(__file__).resolve().parent / "output"
print(run_measurement_recipe("noise_temperature", json_path=OUT / "noise_temperature.json", csv_path=OUT / "noise_temperature.csv", plot_path=OUT / "noise_temperature.png"))
