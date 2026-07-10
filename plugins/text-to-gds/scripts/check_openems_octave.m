% Verify that both openEMS and CSXCAD Octave interfaces are on the path.
openems_fn = which('InitFDTD');
csxcad_fn = which('InitCSX');
if isempty(openems_fn)
  error('Octave openEMS path missing: InitFDTD is not defined');
end
if isempty(csxcad_fn)
  error('Octave CSXCAD path missing: InitCSX is not defined');
end
InitFDTD('NrTS', 0, 'EndCriteria', 0);
InitCSX();
fprintf('Octave openEMS path: ok (%s)\n', openems_fn);
fprintf('Octave CSXCAD path: ok (%s)\n', csxcad_fn);
