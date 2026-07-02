# Upgrade Progress Log

Living log for the trust-hardening sprint (branch `mvp2-trust-hardening`).
Each phase lists: what changed, why, what was verified, what's still open.

## Checklist

- [x] Phase 0 — Baseline & setup (ruff PASS, pytest 726 passed / 8 skipped, uv build PASS; see docs/AUDIT_REPORT.md)
- [x] Phase 1 — Whole-project audit (docs/AUDIT_REPORT.md)
- [ ] Phase 2 — Trustworthy evidence model (`textlayout/evidence.py`)
- [ ] Phase 3 — Text entry point (`textlayout prompt`, `POST /layout/from-text`)
- [ ] Phase 4 — Closed-loop IDC optimization
- [ ] Phase 5 — Correct simulation flow (FasterCap evidence mapping)
- [ ] Phase 6 — Geometry & verification regression coverage
- [ ] Phase 7 — Generator consistency matrix
- [ ] Phase 8 — Claim-validation CI (`scripts/validate_readme_claims.py`)
- [ ] Phase 9 — Testing requirements (8 categories)
- [ ] Phase 10 — README improvement (30-second demo + support matrix)
- [ ] Phase 11 — Final acceptance

## Log

### 2026-07-02 — Phase 0 + 1 complete

- Measured baseline (see AUDIT_REPORT.md §Phase 0): ruff clean, 726 passed /
  8 skipped, build OK. Suite is GREEN at baseline.
- Branch review: `review-fixes` and `codex/evidence-first-layout-plugin` are
  fully merged into `main` (ahead 0); deleted locally and on origin. Current
  branch `mvp2-trust-hardening` is identical to `main`; sprint work lands here
  and merges to `main` at the end.
- Removed stale `__pycache__` bytecode for never-committed modules
  (`prompt`, `evidence_contract`, `acceptance`, `optimization.idc`,
  `workflows.from_text`, `simulation.runners`, `ports.validator`).
