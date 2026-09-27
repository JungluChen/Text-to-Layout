# v0.3.1 — release candidate, not published

Local-first CLI MVP: design prompt to inspectable geometry and an honest
evidence report. Promoted examples are 01–04 only. Archived examples 05
(invalid resonator output) and 06 (analytical full tile) remain retained and
audited; neither is a promoted success.

No foundry-qualified PDK is included. All committed measurement calibration
data is synthetic. Nothing is fabrication ready. CPW estimates remain
analytical at confidence 0.65, including scikit-rf; a fallback is labelled.
Optional scqubits execution generates model spectra, not independently
validated hardware predictions. The pinned public WM1 check preserves mask
geometry; its third-party measured electrical values are not reproduced.

Windows and Linux desktop applications are not delivered. No macOS desktop
application, updater, npm package or hosted service is delivered by this
Python MVP. The planned next milestone is a PySide6 macOS shell, only after
this release, with installed-app, signing/notarisation and signed update/
rollback evidence. Existing Python platform tests do not certify a desktop app.

Publication is blocked: the owner confirmed PyPI Trusted Publishing is not
configured. Do not tag v0.3.1 until configuration and all exact-SHA release
gates are verified. See the dated progress report for installed-wheel evidence
and unresolved items.
