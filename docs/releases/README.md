# Distribution and release status

**Document class: MANUAL_DOCUMENTATION.** This page distinguishes the existing
Python package from requested desktop and npm products. Publishing a package
does not certify an external solver or a graphical application.

| Delivery | Current state | Release acceptance |
| --- | --- | --- |
| Python `text-to-gds` / `textlayout` CLI | Buildable wheel and source archive; tag workflow exists | Exact version tag on `main`, Windows/macOS/Linux Python 3.12 suite, build and CLI checks, evidence gates, configured PyPI trusted publisher, install test from the published index |
| macOS desktop app | No installable desktop bundle | Signed/notarized build, actual installed workflow and solver recovery test, update-channel test, versioned screenshots |
| Windows desktop app | No installable desktop bundle | Signed installer, actual installed workflow and solver recovery test, update-channel test, versioned screenshots |
| Linux desktop app | No installable desktop bundle | Documented package format, actual installed workflow and solver recovery test, update-channel test, versioned screenshots |
| npm package | No JavaScript package or supported npm API | Specify an actual JS/browser or CLI client using the shared service, package name/ownership, API compatibility, tests, provenance and trusted-publisher configuration |

The tag workflow in `.github/workflows/release.yml` builds and verifies the
Python package on all three OS runners before uploading distributions. It
checks that a `vMAJOR.MINOR.PATCH` tag matches `pyproject.toml` and points to
a commit contained in `main`. The publish job uses the existing official PyPA
trusted-publishing action with GitHub OIDC; it does not need a stored PyPI
token. A PyPI project/trusted-publisher binding for this repository and
`release.yml` must exist before the first tag can publish. The workflow
creates a GitHub release only after PyPI succeeds. Do not create a release tag
until the intended version, public claims and installation checks are ready.

The current full suite and platform matrix cover source operation, not a
native desktop installer. `check_palace_amr_benchmark.py` may return zero while
reporting scientific blockers; those blockers remain visible and prohibit a
claim of Palace accuracy. Desktop auto-update must be implemented per platform
with signed release metadata, update verification, rollback and actual
installed-app testing. An npm publish workflow will follow a real package;
publishing an empty wrapper would misrepresent the product.

For the 100 candidate integrations, use the generated
[completion checklist](../integrations/checklist.md). An unchecked entry may
already have exploratory code; it is not accepted until the listed provenance,
execution, numerical and platform evidence is retained. The guidebook
tracks real UI captures and paper-backed result walkthroughs separately.
