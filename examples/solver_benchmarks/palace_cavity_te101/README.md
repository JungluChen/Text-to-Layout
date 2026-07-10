# Palace TE101 cavity benchmark — a real solver run

A genuine Palace 0.16 execution. Nothing here is synthesised: every frequency and
participation was read out of a CSV that Palace wrote, and every input and output
is recorded by SHA-256 content hash.

**This is not the 6 GHz quarter-wave CPW resonator benchmark.** It is a PEC
rectangular cavity, chosen because its TE101 eigenfrequency has a closed form, so
the solver can be *verified* rather than merely executed. What the CPW benchmark
still needs is listed at the bottom.

## What ran

| | |
|---|---|
| Solver | Palace `0.16.0-34-gea2e7b23` |
| Container | `oras://ghcr.io/volkermuehlhaus/palace_016:latest` |
| Container digest | `sha256:6d59c1aca1425bcdc71e84502f88a9018689c94fa8bb41476617dbe5ed9509ac` |
| Mesher | Gmsh 4.15.2, transfinite structured, nested, refinement ratio 2 |
| Elements | Nédélec order 1 (eigenvalue error ~ h², so the declared formal order is 2) |
| Processes | 1 (serial) |

The container is a Singularity SIF, not a Docker image. It was fetched from the
GHCR blob store and its squashfs extracted; Palace then ran inside an
unprivileged user-namespace chroot, which needs no root:

```bash
# 1. fetch the SIF blob and verify it against the manifest digest
TOKEN=$(curl -s 'https://ghcr.io/token?scope=repository%3Avolkermuehlhaus%2Fpalace_016%3Apull&service=ghcr.io' | jq -r .token)
curl -sL -o palace.sif -H "Authorization: Bearer $TOKEN" \
  https://ghcr.io/v2/volkermuehlhaus/palace_016/blobs/sha256:6d59c1aca1425bcdc71e84502f88a9018689c94fa8bb41476617dbe5ed9509ac
sha256sum palace.sif   # must equal the digest above

# 2. a SIF is a squashfs behind a header; 45056 is where the `hsqs` magic sits
unsquashfs -o 45056 -d rootfs palace.sif

# 3. run, as an unprivileged user
unshare -Ur chroot rootfs /bin/bash -lc 'cd /tmp/work && /opt/palace/bin/palace -serial cavity_N24.json'
```

With Apptainer installed, `apptainer run palace_016.sif` replaces steps 2–3.

## Geometry

A PEC box, vacuum filled, `a = d = 35.330880 mm`, `b = 20 mm`. The side lengths
are *chosen* so the fundamental is exactly 6 GHz:

```
f_TE101 = (c/2) · sqrt((1/a)² + (1/d)²) = 6.000000000 GHz
```

That is why this benchmark has a target rather than a reference run.

## Result: the eigenfrequency is PHYSICS_VERIFIED

Single-domain cavity, nested structured meshes.

| N | h (mm) | tets | ND DOF | TE101 (GHz) | runtime |
|---|---|---|---|---|---|
| 3 | 11.776960 | 162 | 279 | 6.041406133060 | 0.31 s |
| 6 | 5.888480 | 1 296 | 1 854 | 6.021133625145 | 0.80 s |
| 12 | 2.944240 | 10 368 | 13 428 | 6.005732649802 | 3.86 s |
| 24 | 1.472120 | 82 944 | 102 024 | **6.001456051043** | 38.43 s |
| 48 | 0.736060 | 663 552 | 795 024 | **killed** | 508.65 s |

The N=48 level was killed by the OOM killer (exit 137) and left a header-only
`eig.csv`. It is recorded here rather than quietly dropped: `parse_eigenmodes`
rejects that file, which is the behaviour a convergence study needs.

Assessed on the three finest **completed** levels (6, 12, 24):

- observed order **p = 1.848486** against the declared formal order 2
- Richardson extrapolation **5.999811977 GHz** — `−0.003134 %` from the closed form
- **GCI = 0.034243 %** (Roache, Fs = 1.25)
- finest-level frequency change **0.071259 %**
- extracted **6.001456051043 GHz**, error **+0.024268 %** against a 0.5 % tolerance

The coarsest level (N = 3) lies *outside* the asymptotic range: refitting the
order on levels 3/6/12 gives `p = 0.397` against `p = 1.848` on 6/12/24. With all
four levels and no declared formal order, `estimate_order` reports
`in_asymptotic_range = False` and withholds Richardson — correctly. The record
excludes N=3 and says so.

## Result: participation converges, but is *not* verified

Second cavity, split at `x = a/4` into two energy domains so that the
electric-energy vector per mode is non-degenerate and mode tracking has something
to match on. Closed form for the TE101 fraction in `x < a/4`:

```
p_elec[1] = 1/4 − 1/(2π) = 0.090845057
```

| N | h (mm) | tets | ND DOF | p_elec[1] | TE101 (GHz) |
|---|---|---|---|---|---|
| 8 | 4.416360 | 1 920 | 2 693 | 0.094695866 | 5.999744483 |
| 16 | 2.208180 | 13 824 | 17 801 | 0.091880026 | 5.998562623 |
| 32 | 1.104090 | 110 592 | 135 634 | **0.091102528** | 5.999638099 |

- participation observed order **p = 1.858**, **GCI 0.406 %**, Richardson `0.090807`
- finest value is **+0.284 %** from the closed form — inside the 5 % requirement
- `p_elec[1] + p_elec[2] = 1.000000000` at every level
- mode tracking: TE101 matched with **electric_overlap = 1.0000**, score **0.9995**,
  worst margin 0.2520
- modes 2 and 3 (8.604 / 8.609 GHz) are near-degenerate and are **rejected as
  untrackable**, which is the correct outcome

This record is **SIMULATION_EXECUTED, not PHYSICS_VERIFIED**. The eigenfrequency
on *this* mesh sequence is oscillatory (5.99974 → 5.99856 → 5.99964), so the
discretisation is not demonstrably in the asymptotic range. The participation
sequence being monotone does not rescue it: both quantities rest on one
discretisation. Promoting it would be exactly the over-claim the confidence
lattice exists to prevent.

## Acceptance conditions

| Condition | Status |
|---|---|
| a genuine Palace executable or container ran | **met** — Palace 0.16.0-34-gea2e7b23, digest recorded |
| at least three distinct meshes ran | **met** — 4 completed (single-domain), 3 (two-domain) |
| element count and DOF increased under refinement | **met** — recorded as named sanity checks |
| field-overlap mode match exceeds 0.90 | **met** — 0.9995, electric_overlap 1.0000 |
| finest-level frequency change below 0.5 % | **met** — 0.071259 % |
| GCI / extrapolated uncertainty below 1 % | **met** — 0.034243 % |
| domain-size variation below 0.2 % | **not applicable** — a closed PEC cavity has no truncation boundary to vary. Not assessed, not claimed. |
| energy normalization error below 0.1 % | **met** — `E_elec == E_mag` to 1 part in 10¹² |
| participation values converge within 5 % | **met** — +0.284 %, but see the SIMULATION_EXECUTED caveat above |
| all inputs, outputs, solver identity and configuration content-hashed | **met** — meshes, configs, CSVs, container digest |

## Regenerating the evidence

No solver is re-run; the committed outputs are re-parsed with the current parser.

```bash
uv run python scripts/build_palace_benchmark_evidence.py          # write
uv run python scripts/build_palace_benchmark_evidence.py --check  # CI gate
```

Mesh files are not committed (the N=48 mesh alone is ~180 MB). Their SHA-256
hashes, element counts and DOF counts are in `mesh_manifest.json`, and the
generator that produced them is recorded in this README's geometry section.

## What the CPW resonator benchmark still needs

This cavity exercises the whole chain — Gmsh → Palace → mode tracking →
convergence → canonical evidence — but it is not a cQED device. A 6 GHz
quarter-wave CPW resonator additionally requires:

- an `FEMModel` with a substrate volume, a vacuum volume, zero-thickness PEC
  metal surfaces, and a radiation or PML truncation boundary;
- local mesh refinement at conductor edges and in the CPW gaps, where the field
  is singular — a uniform `lc` cannot resolve it at any affordable DOF count;
- domain-size convergence, which only becomes meaningful once a truncation
  boundary exists;
- a target for `f₀` that is itself only known to the accuracy of the
  conformal-mapping `ε_eff` — so the resonator verifies against a *model*, not a
  closed form, and the tolerance must widen accordingly.

None of that is implemented. It is not claimed.
