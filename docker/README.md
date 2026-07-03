# Solver containers

Build the RF-capable image:

```bash
docker build -f docker/solver-full.Dockerfile -t textlayout-solver-full .
docker run --rm -v "$PWD:/work" textlayout-solver-full textlayout doctor --strict-em
```

The image builds openEMS and CSXCAD from their official recursive source tree
and installs Octave, scikit-rf, Gmsh, meshio, KLayout, and the Python project.

FasterCap, FastHenry, JoSIM, and Palace remain optional external binaries. Use
the repository installers or mount known-good binaries and set
`TEXTLAYOUT_FASTERCAP`, `TEXTLAYOUT_FASTHENRY`, `TEXTLAYOUT_JOSIM`, or
`TEXTLAYOUT_PALACE`. Palace is deliberately not built in this image because its
PETSc/MFEM dependency stack is substantially heavier; see
`scripts/install_palace_wsl.sh` and `simulation/palace_fullchip/README.md`.

No container availability check is physics evidence. A solver must execute,
produce a non-empty owned output, and pass parsing and target comparison.
