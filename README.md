# full-linked-system v0.1.0

**One chain, all the logic: frequency -> nervous decision ->
injection on rejection -> heart clock -> propulsion ->
sensor -> listen -> ledger, with a lattice battery in parallel.**

Stdlib-only Python, seeded, reproducible, AGPL-3.0-only.

## Run

```bash
python demo.py    # full battery, writes results.json
python3 -m unittest tests -v  # 12 tests
```

## The chain, in order

1. **Frequency** — probe scaled by an imposed Gaussian
   sensitivity centred on a chosen 7.0 Hz, width 1.5 Hz,
   without renormalising. s(7.0) = 1.000, s(0.25) = 0.0000,
   s(1.2) = 0.0006, s(10.0) = 0.1353. The curve is imposed,
   not measured in any person.
2. **Nervous decision** — 128 neurons: sensory 40, spinal 32,
   central 24, motor 32; 578 edges, 256 cross-stage, 64
   reflex. Enveloped waves, one-shot projection, frozen
   Youden gate tau 0.243, J 0.990.
3. **Injection on rejection only** — commit p0 0.75, sample
   20 parameter variants (width [8,20], period [30,50]),
   revise by fixed logistic alpha 2.0, decide on best
   variant vs frozen tau. Tau never moves, patterns never
   added, rescued probes never stored.
4. **Heart clock** — movement only on ticks, 1 tick / 10 steps.
   A clock, not a heartbeat.
5. **Propulsion** — withdraw -> drive +1, grasp -> -1,
   balance -> 0, cool-alert -> 0 (fail-safe default).
   Probe moves by local phase gradient, an assumed law.
6. **Sensor** — k_est, omega, coherence from gradients only.
   Sensor confirmation passes by construction in the
   locked-twist ring; it is a consistency check, not an
   independent guard.
7. **Listen** — probe-following sensor sonified, one sample
   per tick, held 40 frames at 8000 Hz, WAV in memory.
   Mapping only, not a recording.
8. **Ledger** — hash-chained record of frequency, decision,
   propulsion, listen. Only actions move/hold/alert exist.
9. **Lattice battery (parallel, not in the live chain)** —
   lateral-score gap for seam shift, row slip, catastrophe
   front vs same-count random flips. A 156-dim lattice
   probe is not a 128-dim nervous probe, so the battery
   is labelled parallel wherever it appears.

## Measured (demo, seed 42)

- Clean pain 7 Hz: accept, withdraw, drive +1,
  displacement **+19.63**, sensor k_est **+1**, action move
- Clean pain 0.25 Hz: **reject**, 20 injection attempts,
  displacement 0, action hold
- Random 7 Hz: **reject**, displacement 0, action hold
- Clean grasp 7 Hz: accept, grasp, drive -1,
  displacement **-19.63**, sensor k_est -1
- Noisy sigma 0.30, 40 probes: stock **19/40** ->
  injected **21/40**, mean net **-0.277** — sampling
  improves acceptance but does NOT pay at c = 0.01.
  Negative kept, not tuned away.
- Routing: reflex median **53.52**, central median **90.65**
  distance units; lesion reflex median **inf**
  (motor unreachable on the reflex route)
- Listen: 200 samples, WAV 16,044 bytes
- Lattice battery: seam gap +0.131, slip +0.043,
  catastrophe +0.420, mean **+0.198**, 2/3 >= 0.10, PASS
- Tau unchanged, patterns still 4, ledger verifies

## Honest limits — read before any use

- **Not a human nervous system, not a brain, not a heart,
  not a propulsion device, not neuroscience, not a medical
  device, not a diagnosis, not a measurement of any real
  person. No human data were used, and no human experiments
  were conducted.**
- The 7 Hz sensitivity is chosen from the bentov-kuramoto
  toy alignment, not fitted to data, not therapeutic.
- Displacement 19.63, not 20, is 2*pi/64 x 200 ticks, by
  construction, as in brain-heart-propulsion.
- Row slip in the lattice battery fails on its own (+0.043).
  The battery passes on mean gap and 2-of-3, with slip's
  failure reported.
- Vendored modules are unchanged from their source
  packages (see DESIGN.md for the map). The new code is
  chain.py, ring.py, ledger.py, experiments.py, and the
  wiring between them.

## Files

- `chain.py` — the linked chain
- `ring.py` — heart clock, ring, sensor
- `ledger.py` — hash-chained ledger
- `nervous.py`, `human.py`, `injection.py` — vendored,
  membrane-nervous-system v0.2.0, unchanged
- `lattice.py`, `memory.py` — vendored,
  microtubule-crystallize v0.1.0, unchanged
- `lat.py` — vendored, microtubule-lattice-memory v0.1.0
- `experiments.py`, `demo.py`, `tests.py` — battery
- `PREREG.md`, `DESIGN.md`, `results.json`
- `LICENSE` — AGPL-3.0-only

## Credits

Project author: **Jean-François Brisson (Spark)**.

Related work: Mun Seok Lee’s *Digital to Wave* paradigm (Zenodo records
21947036 and 21947108) is cited as inspiration for the wave and membrane
work; this source citation does not indicate package coauthorship. Brisson
built the package’s new code with AI assistance. Vendored and adapted
components retain their upstream attributions and license terms, as
documented in `DESIGN.md`.
