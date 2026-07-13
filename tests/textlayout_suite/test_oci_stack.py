from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILES = [
    REPO_ROOT / "docker" / name
    for name in (
        "core.Dockerfile",
        "palace.Dockerfile",
        "openems.Dockerfile",
        "klayout.Dockerfile",
        "josephson.Dockerfile",
        "josim.Dockerfile",
        "paraview.Dockerfile",
    )
]


def test_requested_oci_files_exist() -> None:
    for path in [
        REPO_ROOT / "compose.yaml",
        REPO_ROOT / "docker-bake.hcl",
        REPO_ROOT / ".dockerignore",
        *DOCKERFILES,
    ]:
        assert path.is_file(), path


def test_dockerfiles_pin_base_digest_and_run_non_root() -> None:
    for path in DOCKERFILES:
        text = path.read_text(encoding="utf-8")
        from_lines = [line for line in text.splitlines() if line.startswith("FROM ")]
        assert from_lines, path
        assert all("@sha256:" in line for line in from_lines), path
        assert "USER appuser" in text, path
        assert "org.opencontainers.image.source" in text, path
        assert "org.opencontainers.image.revision" in text, path
        assert "org.opencontainers.image.licenses" in text, path
        assert "sbom.spdx.json" in text, path
        assert "tool-identity.json" in text or "package-identity.json" in text, path
        assert "TODO" not in text, path
        assert "HFSS" not in text and "Sonnet" not in text and "COMSOL" not in text, path


def test_compose_profiles_cover_solver_stack() -> None:
    compose = yaml.safe_load((REPO_ROOT / "compose.yaml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert set(services) == {
        "core",
        "palace",
        "openems",
        "klayout",
        "josephson",
        "josim",
        "paraview",
    }
    profiles = {profile for service in services.values() for profile in service["profiles"]}
    assert {
        "core",
        "palace",
        "fdtd",
        "signoff",
        "jpa",
        "transient",
        "visualization",
    } <= profiles
    assert set(compose["volumes"]) >= {
        "textlayout-artifacts",
        "palace-output",
        "openems-output",
        "klayout-output",
        "josephson-output",
        "josim-output",
        "paraview-output",
    }
