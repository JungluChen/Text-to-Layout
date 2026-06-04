# KLayout DRC Adapter

Text-to-GDS has two local DRC paths:

1. `run_drc`: always available when the Python `klayout` module is installed.
   It scans GDS shape bounding boxes and emits `text-to-gds.drc.v0`.
2. `run_process_drc`: process-rule adapter. It tries KLayout in batch mode when
   the `klayout` executable is on PATH or installed under `.tools/`:

```powershell
klayout -b -rd input=workspace\artifacts\layout.gds -rd report=workspace\artifacts\layout.lyrdb -r drc\superconducting_min_width.drc
```

The sample deck uses:

```ruby
source($input)
report("Text-to-GDS superconducting starter DRC", $report)
```

`run_process_drc` parses `.lyrdb` or JSON reports into the same
`text-to-gds.drc.v0` schema. If the executable is missing or the Windows GUI
distribution cannot execute the Ruby deck, it falls back to the Python
`klayout.db` module and runs starter process min-width/min-spacing rules from
`text_to_gds.process.DEFAULT_PROCESS`. The JSON report keeps the external
command, return code, and warnings so the fallback is auditable.

The KLayout documentation notes that batch/standalone DRC scripts need an
explicit `source` input and can be run with `klayout -b -r deck.drc`; KLayout
forum guidance shows passing `input` and `report` through `-rd` variables. The
Python fallback is for local agent iteration only; it is not foundry signoff.
