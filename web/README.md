# Text-to-Layout public site

Static landing page and explicitly labelled workbench design preview. No server,
telemetry, account system, uploads or solver execution. Only public benchmark
artifacts are deployed. No dependency on the Python core at browser runtime;
all displayed scientific values are retained core output.

Preview: `python3 -m http.server 8765 --bind 127.0.0.1 --directory web`
from the repository root. Open http://127.0.0.1:8765/.

Deploy from `web/`: `vercel link --project text-to-layout --scope jung-lu-chens-projects`,
then `vercel deploy --prod`. Do not deploy the repository root. `.env*` and
`.vercel` are excluded. Authentication belongs in the local Vercel CLI, never Git.

`assets/manifest.json` records the source commit, repository path and SHA-256 for
each copied public artifact. When updating snapshots, copy the complete matching
benchmark revision and regenerate this manifest; never mix showcase execution
evidence into benchmark geometry. Validate every hash before deployment.
