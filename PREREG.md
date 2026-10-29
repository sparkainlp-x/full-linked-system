# PREREG — full-linked-system v0.1.0

Written BEFORE the demo run, after a prototype exploration
that measured the same chain at seed 42 (prototype numbers
are in DESIGN.md). Bars are fixed here and are not moved
after seeing demo results. Where a bar is looser than the
prototype number, that slack is intentional: the bar is the
claim, the prototype number is not.

## The chain, in order

1. FREQUENCY: probe scaled by imposed Gaussian sensitivity
   s(f), centred on chosen 7.0 Hz, width 1.5 Hz, no
   renormalising. Winner unchanged, gate decision moves.
2. NERVOUS DECISION: 128-neuron sensory->spinal->central->
   motor membrane, enveloped waves, frozen Youden gate.
3. INJECTION on rejection only: commit p0 0.75, sample 20
   parameter variants (width [8,20], period [30,50]),
   revise by fixed logistic alpha 2.0, decide on best
   variant vs FROZEN tau. Tau never moves, patterns never
   added, rescued probes never stored. Truth, when supplied
   in experiments, is for scoring only, never for deciding.
4. HEART CLOCK: movement only on ticks, 1 tick / 10 steps.
5. PROPULSION: response -> drive, withdraw +1, grasp -1,
   balance 0, cool-alert 0 (fail-safe default). Probe moves
   by local phase gradient (assumed law, not force).
6. SENSOR: k_est, omega, coherence from gradients only.
   Sensor confirmation (k_est == drive) is a consistency
   check that passes by construction in the locked-twist
   ring; it is reported as such, not as an independent guard.
7. LISTEN: probe-following sensor sonified, one sample per
   tick, held 40 frames at 8000 Hz, WAV in memory. Mapping
   only, not a recording.
8. LEDGER: hash-chained record of frequency, decision,
   propulsion, listen. Only actions move/hold/alert exist.
9. LATTICE BATTERY (parallel, not in the live chain):
   microtubule lattice lateral-score gap, measured in
   experiments, because that logic belongs to the full
   system even though a 156-dim lattice probe is not a
   128-dim nervous probe. The battery is labelled parallel
   wherever it appears; it is never claimed to gate the chain.

## Bars (demo, seed 42 unless stated)

- F1: clean pain at 7.0 Hz -> accept, withdraw, drive +1,
  displacement > 15, sensor k_est +1, action move, ledger ok.
- F2: clean pain at 0.25 Hz -> reject, attempts 20,
  displacement 0, action hold.
- F3: random field at 7.0 Hz -> reject, displacement 0,
  action hold.
- F4: fresh noisy probes, sigma 0.30, 40 probes:
  injected accepts >= stock accepts, and mean net < 0
  (sampling does not pay at c = 0.01 — a negative, kept).
- F5: pain reflex median < central median; lesion
  reflex median = inf.
- F6: lattice battery: mean gap >= 0.15, at least 2 of 3
  corruptions gap >= 0.10 (seam, slip, catastrophe).
- F7: after all runs, tau unchanged, patterns still 4,
  ledger verifies.
- F8: listen samples = heart ticks = 200, WAV bytes > 10000.
