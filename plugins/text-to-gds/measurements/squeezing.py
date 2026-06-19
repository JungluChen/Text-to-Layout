from pathlib import Path
from text_to_gds.measurement_recipes import run_measurement_recipe

OUT = Path(__file__).resolve().parent / "output"
print(run_measurement_recipe("squeezing", json_path=OUT / "squeezing.json", csv_path=OUT / "squeezing.csv", plot_path=OUT / "squeezing.png"))
