"""Crystallize injection inside membrane-nervous-system v0.2.0.

Stdlib-only, AGPL-3.0-only.

Lineage, reused exactly
-----------------------
- membrane-arena-3x3 crystallize injection: on a rejection,
  do not stop — commit, sample fresh variants, revise, score.
  The stock path is untouched when injection is not used.
- microtubule-crystallize calibration.py: the revise rule and
  the scoring. Copied formulas, same constants where stated:
  revise by a fixed logistic update, Brier = (p - y) ** 2,
  net = -Brier - c * n, points = 100 * (1 - 4 * Brier).

What a variant is — and is not
-------------------------------
A variant is a fresh MEMBRANE PARAMETER set, exactly as in the
arena injection (dt shrunk, mirror softened there). Here:
wave width uniform [8, 20] (stock 12), wave period uniform
[30, 50] (stock 40), geometry, seed and probe unchanged,
patterns recomputed from the cached Dijkstra delays.

A variant is NOT a re-noised copy of the probe. That first
draft was tried and abandoned: re-noising an already noisy
probe only degrades it, and it failed the pre-registered
rescue bar (19/40 stock, 19/40 injected). See PREREG.md.

What happens on a rejection
----------------------------
1. COMMIT p0 = 0.75 that a fresh variant will pass the frozen
   gate. p0 is the membrane-arena default, fixed in PREREG.md.
2. SAMPLE n = 20 parameter variants (dedicated RNG stream).
3. REVISE p1 = sigmoid(logit(p0) + alpha * (mean_overlap - tau)),
   alpha = 2.0, mean_overlap over the variants' best overlaps.
4. DECIDE on the best variant only: accept iff its overlap
   >= the FROZEN tau.
5. SCORE (demo only): if truth is supplied (1 = probe came
   from a stored pattern, 0 = random field), Brier, points and
   net are computed. Truth is NEVER used for the decision.

Fail-closed, preserved
----------------------
- tau is never moved, patterns are never added, rescued probes
  are never stored. A rescued accept is for that probe only.
- A variant that fails the gate changes nothing.
- If the stock gate already accepts, injection runs 0 attempts
  and costs nothing.
- If the frequency is far from 7.0 Hz, sensitivity is near
  zero, every variant stays below tau, and injection correctly
  cannot rescue an off-frequency probe.

This is a calibration ledger about toy probes, not a claim
about learning, healing, or a real nervous system.
"""

import math
import random

from human import modulate
from nervous import normalize, overlap

__version__ = "0.2.0"

P0 = 0.75
N_SAMPLES = 20
COST_PER_SAMPLE = 0.01
ALPHA = 2.0
WIDTH_RANGE = (8.0, 20.0)
PERIOD_RANGE = (30.0, 50.0)


def _logit(p):
    p = min(max(p, 1e-6), 1.0 - 1e-6)
    return math.log(p / (1.0 - p))


def _sigmoid(z):
    return 1.0 / (1.0 + math.exp(-z))


def revise(p0, mean_overlap, tau, alpha=ALPHA):
    """Fixed logistic update — same rule as microtubule-crystallize."""
    return _sigmoid(_logit(p0) + alpha * (mean_overlap - tau))


def brier(p, y):
    return (p - y) ** 2


def points(p, y):
    """Crystallize points: 100 * (1 - 4 * Brier)."""
    return 100.0 * (1.0 - 4.0 * brier(p, y))


def net_score(p1, y, n, c=COST_PER_SAMPLE):
    return -brier(p1, y) - c * n


def _wave_from_delays(delays, width, period):
    out = []
    for d in delays:
        if math.isinf(d):
            out.append(0j)
            continue
        amp = math.exp(-(d * d) / (2.0 * width * width))
        phase = 2.0 * math.pi * d / period
        out.append(amp * complex(math.cos(phase), math.sin(phase)))
    return normalize(out)


class InjectionResult:
    """One injected decision. Fields are plain attributes."""

    def __init__(self, decision, response, probs, attempts, p0, p1,
                 mean_overlap, best_overlap, brier_score=None,
                 points_score=None, net=None):
        self.decision = decision
        self.response = response
        self.probs = probs
        self.attempts = attempts
        self.p0 = p0
        self.p1 = p1
        self.mean_overlap = mean_overlap
        self.best_overlap = best_overlap
        self.brier = brier_score
        self.points = points_score
        self.net = net

    def __repr__(self):
        return (f"InjectionResult({self.decision!r}, {self.response!r}, "
                f"attempts={self.attempts}, p1={self.p1}, "
                f"best={self.best_overlap:.3f})")


class CrystallizeInjection:
    """Wraps a calibrated MembraneNervous with injection on reject."""

    def __init__(self, system, p0=P0, n_samples=N_SAMPLES,
                 cost=COST_PER_SAMPLE, alpha=ALPHA):
        if system.tau is None:
            raise ValueError("calibrate the system gate first")
        self.system = system
        self.p0 = p0
        self.n_samples = n_samples
        self.cost = cost
        self.alpha = alpha
        # Cached Dijkstra delays per stored-pattern seed; geometry
        # is fixed, only width/period vary across variants.
        self.seed_delays = [
            system.geometry.delays_from(sid) for sid in system.seed_ids
        ]

    def _variant_overlaps(self, modulated_field, width, period):
        patterns = [
            _wave_from_delays(d, width, period) for d in self.seed_delays
        ]
        overlaps = [overlap(modulated_field, p) for p in patterns]
        best = max(range(len(overlaps)), key=lambda i: abs(overlaps[i]))
        return abs(overlaps[best]), best, patterns[best]

    def attempt(self, field, f_hz, rng=None, truth=None):
        """Decide on a probe, injecting only if stock rejects.

        field: the original (unmodulated) probe.
        f_hz: its frequency, for human.modulate.
        truth: optional 1/0 for scoring only, never for deciding.
        """
        system = self.system
        modulated = modulate(field, f_hz)
        decision, response, probs = system.decide(modulated)
        if decision == "accept":
            return InjectionResult("accept", response, probs, 0,
                                   self.p0, self.p0, None, None)
        rng = rng if rng is not None else random.Random(0)
        overlaps = []
        best_overlap, best_winner = -1.0, None
        for _ in range(self.n_samples):
            width = rng.uniform(*WIDTH_RANGE)
            period = rng.uniform(*PERIOD_RANGE)
            ov, winner, _ = self._variant_overlaps(
                modulated, width, period)
            overlaps.append(ov)
            if ov > best_overlap:
                best_overlap, best_winner = ov, winner
        mean_overlap = sum(overlaps) / len(overlaps)
        p1 = revise(self.p0, mean_overlap, system.tau, self.alpha)
        if best_overlap >= system.tau:
            decision = "accept"
            response = system.RESPONSE_NAMES[best_winner]
            probs = None
        else:
            decision, response, probs = "reject", None, None
        result = InjectionResult(decision, response, probs,
                                 self.n_samples, self.p0, p1,
                                 mean_overlap, best_overlap)
        if truth is not None:
            result.brier = brier(p1, truth)
            result.points = points(p1, truth)
            result.net = net_score(p1, truth, self.n_samples, self.cost)
        return result
