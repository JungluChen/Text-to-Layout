# Targeted Palace A/B refinement

Palace 0.17.0 executed with one rank and three retained modes.

The first attempt used `UpdateFraction=0.70`. It expanded 263,313 elements to
861,370 and was terminated at the configured 7 GiB process-group RSS limit.
No owned process remained.

The bounded replacement used `UpdateFraction=0.20`. Palace solved state A at
263,313 elements and 333,954 DOF, then state B at 381,853 elements and 474,616
DOF. Peak process-group RSS was 7,276,322,816 bytes, below the configured
7,516,192,768-byte limit.

State A frequencies were 5.485387034, 5.928063192, and 10.963587122 GHz. State
B frequencies were 5.600931038, 6.063004839, and 11.182125279 GHz.

The physical classifier returned `TARGET_MODE_NOT_FOUND` for state A. Mode 1
had quarter-wave profile correlation 0.989686 but failed all four endpoint
node/antinode gates. Therefore no global target assignment, MAC promotion, or
convergence claim is allowed. The index-wise frequency changes are diagnostic
only.
