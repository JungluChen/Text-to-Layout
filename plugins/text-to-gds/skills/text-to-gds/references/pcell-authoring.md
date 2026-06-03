# PCell Authoring

## Rules

- Use `gdsfactory` components and ports as the source of truth.
- Keep dimensions in microns.
- Validate positive geometry parameters before creating polygons.
- Store derived physical data in `component.info`.
- Add electrical ports with explicit orientations and process layers.
- Keep layer constants named and visible.
- Activate a PDK before adding layers; gdsfactory 9 requires this.

## Current Layers

The scaffold uses a placeholder superconducting stack:

| Name | Layer |
| --- | --- |
| bottom electrode | `(3, 0)` |
| junction barrier | `(4, 0)` |
| top electrode | `(5, 0)` |
| marker | `(10, 0)` |

Replace these with a process module once the real stack is fixed.

## Sidecar Requirements

The sidecar should include process layer tuples, not only gdsfactory internal
layer IDs. Use `port.layer_info.layer` and `port.layer_info.datatype` when
available.

