'use strict';
const $ = (id) => document.getElementById(id);
const sourceFiles = ['layout.json', 'output.json', 'verification.json', 'manifest.json'];
Promise.all(sourceFiles.map(async (name) => {
  const response = await fetch(`assets/${name}`);
  if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`);
  return response.json();
})).then(async ([layout, geometry, verification, manifest]) => {
  const promptResponse = await fetch('assets/prompt.md');
  if (!promptResponse.ok) throw new Error('Prompt artifact unavailable');
  const originalPrompt = await promptResponse.text();
  const revision = manifest.files['layout.json'].sha256;
  $('revision').textContent = `Original input SHA-256: ${revision.slice(0, 12)} · retained artifact`;
  $('run-revision').textContent = revision.slice(0, 12);
  $('run-stage').textContent = verification.simulation_evidence.status;
  $('prompt').value = originalPrompt;
  $('load-status').textContent = 'Retained artifacts loaded. No simulation was started.';
  const fields = [['center_width_um', 'Center width (µm)'], ['gap_um', 'Gap (µm)'], ['length_um', 'Length (µm)'], ['ground_width_um', 'Ground width (µm)']];
  fields.forEach(([key, label]) => {
    const container = document.createElement('div');
    const text = document.createElement('label'); text.htmlFor = key; text.textContent = label;
    const input = document.createElement('input'); input.id = key; input.type = 'number'; input.step = 'any'; input.required = true; input.value = layout.parameters[key]; input.setAttribute('aria-describedby', 'validation');
    container.append(text, input); $('parameters').append(container);
    input.addEventListener('input', updateDraft);
  });
  function updateDraft() {
    const invalid = fields.some(([key]) => !$(key).value || !Number.isFinite(Number($(key).value)) || Number($(key).value) <= 0);
    fields.forEach(([key]) => $(key).setAttribute('aria-invalid', String(!$(key).value || Number($(key).value) <= 0)));
    $('validation').textContent = invalid ? 'Enter positive finite values in µm. Invalid draft values are retained for correction.' : '';
    $('stale').hidden = $('prompt').value === originalPrompt && fields.every(([key]) => Number($(key).value) === layout.parameters[key] && $(key).value !== '');
  }
  $('prompt').addEventListener('input', updateDraft);
  $('reset').addEventListener('click', () => { $('prompt').value = originalPrompt; fields.forEach(([key]) => { $(key).value = layout.parameters[key]; }); updateDraft(); });
  const stages = [
    ['Inputs', 'Original retained inputs', `Original layout SHA-256: ${revision}. Technology ${layout.technology}. No new input validation is performed by this preview.`],
    ['Geometry checks', verification.geometry_verification.status, 'Retained geometry verification: ' + verification.geometry_verification.checks.map(x => `${x.name}: ${x.status}`).join('; ') + '. A geometry pass is not physics validation.'],
    ['Solver output', verification.simulation_evidence.status, `${verification.simulation_evidence.note} solver_executed: ${verification.simulation_evidence.solver_executed}. Solver output files: ${verification.simulation_evidence.solver_output_files.length}. Process exit status: Unknown; no solver executed.`],
    ['Reference comparison', 'Unknown', 'Missing reference-comparison evidence for this benchmark revision. Physics verification status: ' + verification.physics_verification.status + '. Analytical estimates must not be promoted to independent solver validation.']
  ];
  stages.forEach(([name, status, detail], index) => {
    const button = document.createElement('button'); button.type = 'button'; button.textContent = name;
    const statusLabel = document.createElement('strong'); statusLabel.textContent = status; button.append(statusLabel); button.setAttribute('aria-pressed', 'false');
    button.addEventListener('click', () => {
      [...$('ribbon').children].forEach(x => x.setAttribute('aria-pressed', String(x === button)));
      const heading = document.createElement('p'); heading.className = 'stage-title'; heading.textContent = name;
      const content = document.createElement('p'); content.textContent = detail; $('stage-detail').replaceChildren(heading, content);
    });
    $('ribbon').append(button); if (index === 2) button.click();
  });
  const svg = $('geometry'); const ns = 'http://www.w3.org/2000/svg'; const box = geometry.bbox_um;
  const view = `${box.ymin - 50} ${box.xmin - 30} ${box.height + 100} ${box.width + 60}`;
  svg.setAttribute('viewBox', view);
  let stack = null;
  let selectedIndex = 0;
  function select(index) {
    selectedIndex = index;
    stack?.select(index);
    [...svg.querySelectorAll('polygon')].forEach((p, i) => p.classList.toggle('selected', i === index));
    document.querySelectorAll('[data-object]').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.object) === index)));
    const p = geometry.polygons[index];
    const title = document.createElement('h3'); title.textContent = `Polygon ${index + 1}`;
    const details = document.createElement('p'); details.textContent = `Layer: ${p.layer}. Original vertices (x, y), µm: ${p.points.map(v => `(${v.join(', ')})`).join('; ')}.`;
    $('selection').replaceChildren(title, details);
  }
  geometry.polygons.forEach((polygon, index) => {
    const shape = document.createElementNS(ns, 'polygon'); shape.setAttribute('points', polygon.points.map(([x, y]) => `${y},${x}`).join(' ')); shape.addEventListener('click', () => select(index)); svg.append(shape);
    const row = document.createElement('tr'); [`Polygon ${index + 1}`, polygon.layer, polygon.points.length].forEach(value => {const td = document.createElement('td');td.textContent = value;row.append(td);});
    const td = document.createElement('td'); const button = document.createElement('button'); button.textContent = `Select polygon ${index + 1}`; button.dataset.object = index; button.setAttribute('aria-pressed','false');button.addEventListener('click', () => select(index));td.append(button);row.append(td);$('objects').append(row);
  });
  $('fit').addEventListener('click', () => svg.setAttribute('viewBox', view));
  $('zoom').addEventListener('click', () => svg.setAttribute('viewBox', `${box.ymin + box.height / 4} ${box.xmin - 10} ${box.height / 2} ${box.width + 20}`));
  const portsText = document.createElement('pre'); portsText.textContent = JSON.stringify({bbox_um: geometry.bbox_um, ports: geometry.ports}, null, 2); $('ports').append(portsText);
  let loadingStack = false;
  const loadStack = async () => {
    if (!$('stack-panel').open || stack || loadingStack) return;
    loadingStack = true;
    $('stack-status').textContent = 'Loading Three.js…';
    try {
      const {createStack} = await import('./stack.bundle.js');
      stack = createStack($('stack-canvas'), geometry, select);
      stack.select(selectedIndex);
      $('stack-status').textContent = '3D renderer ready · retained planar M1 geometry · physical stack data missing.';
    } catch (error) {
      $('stack-status').textContent = `3D unavailable: ${error.message}. The 2D view and object table remain usable. Close and reopen this section to retry.`;
    } finally { loadingStack = false; }
  };
  $('stack-panel').addEventListener('toggle', loadStack);
  if ($('stack-panel').open) loadStack();
  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => stack?.command(button.dataset.view)));
  window.addEventListener('pagehide', event => { if (!event.persisted) stack?.dispose(); });
  select(0);
}).catch(error => { $('load-status').textContent = `Artifacts could not be loaded: ${error.message}. Reload the page or inspect the repository. No evidence status is available.`; });
function navigate() {
  const screen = ['intent','layout','runs'].includes(location.hash.slice(1)) ? location.hash.slice(1) : 'layout';
  ['intent','layout','runs'].forEach(id => { $(id).hidden = id !== screen; });
  document.querySelectorAll('.sidebar a[href^="#"]').forEach(link => { if (link.hash === `#${screen}`) link.setAttribute('aria-current','page'); else link.removeAttribute('aria-current'); });
}
window.addEventListener('hashchange', navigate); navigate();
$('menu').addEventListener('click', () => { const open = $('navigation').classList.toggle('open'); $('menu').setAttribute('aria-expanded', String(open)); });
