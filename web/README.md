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

## Three.js build

From web/: `npm ci`, `npm test`, `npm run build`. Preview `web/dist/`, not the
source directory, with the HTTP server. Vercel builds and serves dist/ using
vercel.json. Three.js0.186.1 and esbuild0.28.2 are pinned with npm integrity locks;
the bundle is same-origin and its MIT license is served as THREE-LICENSE.txt.
No CDN or CSP exception is needed. The lazy renderer makes no physical stack
inference. The old dependency-free statement describes the initial increment.
