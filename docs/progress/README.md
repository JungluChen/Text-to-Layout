# Daily improvement reports

**Document class: MANUAL_DOCUMENTATION.** Reports describe executed work and
continuation instructions; they do not replace generated scientific evidence.

Save each scheduled run as `YYYY-MM-DD-HHMMSS.md` using Asia/Taipei time. Use
explicit statuses: pending, passed, failed, skipped, blocked, or untested.
Retain a report even when no code can be completed. Return its substantive
results in the Codex conversation after every run.

Each report must contain:

1. **Run identity:** start/end timestamps and timezone, selected backlog item,
   starting Git SHA/branch, host/platform and relevant tool/solver versions.
2. **Work and scientific findings:** reviewed/changed behavior, rationale,
   references, assumptions, tolerance definitions, measured errors, convergence,
   evidence paths and limitations. Distinguish execution from validation.
3. **Verification:** exact commands, exit codes, repeated-run outcomes,
   passed/failed/skipped counts and untested checks with reasons. Include the
   full publication gates for code changes and relevant regression evidence.
4. **Git and CI:** implementation/documentation commit hashes, push outcome,
   inspected remote SHA, exact-SHA workflow links/IDs and current results.
   Keep pending CI pending. Record known hashes in subsequent documentation
   commits; never amend merely to insert a commit's own hash.
5. **Continuation:** unfinished files/work, blockers, next command/working
   directory, active local process ownership or CI job IDs, and conditions for
   safely resuming. Explain any skipped blocked backlog item.

On the first scheduled run, also verify report creation, top-to-bottom backlog
selection, commit/push behavior, continuation handling and the next daily
01:00 Taipei schedule. Do not claim this execution validation during setup.

Keep compact evidence in Git according to repository artifact policy; do not
commit binaries, virtual environments, credentials or large solver fields.
