"""Solver backends built on validated contracts.

* :mod:`textlayout.simulation.backends.palace` -- headless Gmsh -> Palace
  eigenmode driver with AMR convergence validation.

Existing Palace, openEMS, FasterCap, FastHenry and circuit adapters retain
their current execution paths; importing this namespace registers nothing and
imports no solver binding.
"""
