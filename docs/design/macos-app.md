# macOS workbench — first design increment

Document class: MANUAL_DOCUMENTATION. 2026-09-28. Design preview, not an
installed application or scientific acceptance certificate.

## Technology decision

Use PySide6 for the native implementation. QMainWindow, QMenuBar, QAction and
QFileDialog provide native window/menu/file conventions; QKeySequence standard
keys preserve Command on macOS and Ctrl elsewhere. Use the system palette for
native chrome and the six Design.md content tokens for scientific content.
The browser preview is a separate static reference, not the native runtime.
No legacy server/workbench code is ported. The optional stack preview will
consume existing trimesh geometry; no physics belongs in Qt or JavaScript.

## Implemented design reference

`web/app.html` opens Layout, with Intent and Runs reachable in the sidebar.
It loads a byte-identical snapshot of benchmark `02_cpw_50ohm`, identified by
input SHA, with a source manifest. It intentionally does not use the separate
showcase evidence, whose geometry/input revision and execution history differ.
Ribbon statuses come from the benchmark's actual verification fields (`pass`,
`input_files_prepared`, `pending`), not from invented canonical classifications.
Reference comparison is Unknown because that record is absent.

Editing prompt or positive numeric fields marks original results From an
earlier revision. Restoring originals clears the draft marker. Drafts live only
in tab memory and are discarded on reload. Selection synchronizes polygon and
semantic object table; original vertices remain inspectable. Runs exposes the
single retained preparation record and raw artifacts. No simulated elapsed time,
process exit, reference agreement, retry, resume or execution is fabricated.

## Native handoff

| Area | Native component / boundary | Next acceptance |
| --- | --- | --- |
| Intent | QPlainTextEdit, unit-labelled QDoubleSpinBox, public workflow API | Validate full typed DSL; preserve invalid drafts and undo |
| Layout | QGraphicsView + QAbstractTableModel sharing stable object IDs | Dimensions, ports, scale, fit/reset, keyboard selection |
| Runs | QTableView plus retained artifact reader | Sort revision/solver/stage/time/outcome; missing values explicit |
| Ribbon | Four accessible buttons and detail area | Render EvidenceStatus and acceptance outcomes without promotion |
| Revision | Immutable input digest per run | Editing never mutates old evidence; new runs reference prior IDs |
| Commands | QAction reused by menu and toolbar | Review/generate/prepare/run/export invoke CLI's public services |
| Recovery | Separate retry original and edit-new actions | Offer resume only with actual checkpoint capability |

At >=1200px the browser reference uses three panes. At 800–1199px selection
moves below content into a disclosure; below800 navigation uses a button.
Native implementation should collapse the inspector initially at the middle
breakpoint. Browser baseline uses real HTML controls, system fonts, opaque
surfaces, system light/dark, 4px spacing and no decorative animation.

## Source-informed design choices

Pinned Apple skill da2da6dd03aacf06da3fecf205347601d38bb141 and its accessibility,
layout, typography, color, designing-for-macos, sidebars, windows and entering-data
references were read. Applied principles: accessibility/Vision supports larger
text; layout/Adaptability prioritizes scientific content; windows/Best practices
avoids imitation native chrome; sidebars/Best practices keeps hierarchy shallow;
entering-data/Best practices labels units and validates drafts. The evidence
ribbon and responsive dimensions are project judgments from Design.md.

## Open acceptance items

Actual PySide6 implementation, installed workflow with a real solver, screen-reader
walkthrough, complete accessibility matrix, signing/notarisation, signed update
metadata, update verification/rollback, and installed-app screenshots remain
pending. Windows and Linux desktop are not delivered. PyPI publication remains
blocked on owner configuration, independently of this authorized design work.

Browser increment: Three.js now renders the retained polygons in an orbitable
planar 3D scene. Physical stack dimensions remain absent. The earlier statement
that the optional stack preview is unconnected applies to native Qt only.
