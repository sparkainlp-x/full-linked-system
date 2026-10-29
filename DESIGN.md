# DESIGN.md — full-linked-system v0.1.0

## Vendoring map

- nervous.py, human.py, injection.py: copied unchanged
  from membrane-nervous-system v0.2.0 (the public repo at
  commit 4f2b357, folder synthetic-parameter-injection).
- lattice.py, memory.py: copied unchanged from
  microtubule-crystallize v0.1.0.
- lat.py: copied unchanged from microtubule-lattice-memory
  v0.1.0.
- ring.py: adapted from brain-heart-propulsion v0.1.0
  (HeartClock, PropulsionRing, sensor from gradients).
- ledger.py: new, hash-chained, only move/hold/alert.
- chain.py, experiments.py: new wiring.

## Prototype numbers

A prototype of this exact chain at seed 42, before PREREG,
measured: tau 0.243, clean pain 7 Hz +19.63, off-frequency
reject, random reject, grasp -19.63, reflex 53.52, central
90.65, lesion inf, noisy stock 19 / injected 21. The demo
reproduced every one of those numbers, and added net mean
-0.277 once truth scoring was passed through (prototype
had no truth, so no net). The 0.001 difference from the
nervous-system demo's -0.276 is a scoring-scope difference
(all 40 probes scored here, including stock accepts at
p0), not a code change to the decision path.

## What is NOT in the live chain, and why

- Verification-suite logic: the suite re-runs other
  packages; it is a tool about the system, not a stage
  inside it. It is not wired in, and is not claimed to be.
- Waveholo real-data validation: needs numpy and real
  holograms; out of scope for a stdlib toy chain.
- Membrane-arena 3x3: needs numpy; its injection rule is
  already the rule used here (commit-sample-revise).
- Browser games: JavaScript artifacts, not Python stages.
- Private work: excluded entirely, never imported.

## Falsifiers

- If clean pain at 7 Hz fails to move, or off-frequency
  pain moves, F1/F2 fail and the frequency gate claim fails.
- If injected accepts fall below stock accepts, F4 fails.
- If the lattice battery mean gap falls below 0.15, F6
  fails, and the lattice component of the system fails
  even if the chain passes.
