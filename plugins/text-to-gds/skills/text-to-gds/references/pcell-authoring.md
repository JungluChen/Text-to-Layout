# PCell Authoring

## Rules

- Use `gdsfactory` components and ports as the source of truth.
- Keep dimensions in microns.
- Validate positive geometry parameters before creating polygons.
- Store derived physical data in `component.info`.
- Add electrical ports with explicit orientations and process layers.
- Import layer constants and validation helpers from `text_to_gds.process`.
- Activate a PDK before adding layers; gdsfactory 9 requires this.
- Include performance-relevant dimensions in `component.info`: width, length,
  height/thickness, angle, gap, pitch, turns, area, and layer roles when present.

## Current Layers

The scaffold uses a placeholder superconducting stack:

| Name | Layer | Purpose |
| --- | --- | --- |
| M1 | `(3, 0)` | bottom electrode and local interconnect |
| JJ | `(4, 0)` | Josephson tunnel barrier |
| M2 | `(5, 0)` | top electrode and local routing |
| M3 | `(6, 0)` | global microwave routing |
| VIA12 | `(7, 0)` | M1/M2 via |
| VIA23 | `(8, 0)` | M2/M3 via |
| MARKER | `(10, 0)` | labels and non-fab annotations |

Replace `text_to_gds.process.DEFAULT_PROCESS` with a real process file once the
stack is fixed.

## Sidecar Requirements

The sidecar should include process layer tuples, not only gdsfactory internal
layer IDs. Use `port.layer_info.layer` and `port.layer_info.datatype` when
available.
