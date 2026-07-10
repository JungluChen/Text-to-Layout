# Palace full-tile preparation

This optional path lowers verified `textlayout` geometry into a simplified
three-dimensional Gmsh extrusion, writes a Palace eigenmode configuration, and
runs Palace only when its executable is available.

It is not a full-chip verification claim. The model still needs reviewed
dielectric loss, metal thickness, enclosure, package, wirebond, port, mesh
convergence, and boundary assumptions.

Use `textlayout doctor --strict-fullchip` to require Palace, Gmsh, and meshio.
