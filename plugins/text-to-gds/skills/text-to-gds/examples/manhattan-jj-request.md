# Example Request

Use `$text-to-gds` to create a Manhattan Josephson Junction with a 0.22 um by
0.22 um barrier, write the GDS locally, run DRC, and estimate critical current
with `Jc = 2.0 uA/um^2`.

Expected workflow:

```bash
py -3 -m uv run python skills/text-to-gds/scripts/text_to_gds_tool.py toolchain \
  --output-name manhattan_jj.gds \
  --jc-ua-per-um2 2.0
```

