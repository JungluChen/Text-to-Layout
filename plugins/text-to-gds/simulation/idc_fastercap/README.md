# IDC FasterCap / FastCap

This workflow prepares a FastCap-compatible generic panel file and list file from the verified IDC geometry.

```bash
python simulation/idc_fastercap/generate_fastercap_input.py \
  examples/benchmarks/01_idc_0p6pf/layout.json \
  --out examples/benchmarks/01_idc_0p6pf/simulation

python simulation/idc_fastercap/run_fastercap.py \
  examples/benchmarks/01_idc_0p6pf/layout.json \
  --out simulation/idc_fastercap/work
```

The generator reaches readiness Level 2: input files exist, but no result is claimed. The runner exits with code 2 and `status=skipped` when no executable is installed.

The prepared model uses zero-thickness conductor panels and `eps_eff=(1+eps_r)/2`. It is an effective-medium correlation model. It does not explicitly mesh the air/silicon interface, metal thickness, losses, package, parasitic inductance, Q, or self-resonance.

Install FasterCap from [FastFieldSolvers](https://www.fastfieldsolvers.com/fastercap.htm), or build a compatible FastCap implementation. Retain solver version, stdout, stderr, and `simulation_result.json` before calling a result executed.
