"""membrane-nervous-system v0.1.0 — a sparkainlp-x membrane in a
nervous-system-shaped toy.

Stdlib-only Python, seeded, reproducible, AGPL-3.0-only.

Lineage, reused exactly
-----------------------
1. membrane-capacity: complex oscillators; patterns stored as an
   outer-product holographic memory; recognition is one-shot
   projection — winner = argmax |overlap|, probs = |m|^2 / sum |m|^2.
2. refusing-membrane / membrane-vs-hopfield: REJECT iff max
   |overlap| < tau, tau calibrated once via Youden's J and frozen,
   with the midpoint-of-max-J improvement (first-best tau sits on
   the edge of the gap).
3. membrane-heart / membrane-brain: a wave is stored as an
   ENVELOPED phasor field, not a pure phase wave. Pure phase
   snapshots differ only by a global phase, which |overlap|
   cannot see (that bug was caught in membrane-heart: recognition
   0.325 before the envelope, 39/40 after). The envelope is kept
   from the start.
4. holo-heart-neurons / membrane-brain: seeded neurons,
   k-nearest-neighbour edges, Dijkstra propagation delays.

The toy nervous system
----------------------
128 neurons in four stages, by id:
  sensory  40: touch 12 (0-11), temperature 8 (12-19),
               pain 8 (20-27), proprioception 12 (28-39)
  spinal   32: ids 40-71
  central  24: ids 72-95
  motor    32: flexor 16 (96-111), extensor 16 (112-127)
Stages are position zones, not anatomy: sensory west, spinal
centre, motor east, central as a cap on top. Edges are 4-NN plus
explicit nearest cross-stage edges: sensory->spinal, spinal->
motor (the reflex arc), spinal->central, central->motor.
Four stored "responses" are enveloped waves seeded at one
sensory modality each: pain -> withdraw, touch -> grasp,
proprioception -> balance, temperature -> cool-alert.

Two routes are measured, in distance units, never milliseconds:
  reflex route: sensory -> spinal -> motor, central nodes excluded
  central route: sensory -> spinal -> central -> motor
A toy lesion (removing the spinal->motor reflex edges) makes the
reflex route unreachable while the central route remains — a
graph property of this toy, not a claim about real lesions.

What this is NOT — read before any use
---------------------------------------
Not a human nervous system. Not neuroscience, not a neural model
of sensation or movement, not a medical device, not a diagnosis,
not a measurement of any real person. No receptors, ion channels,
synapses with plasticity, spinal tracts, or cortex. The "stages"
are four position zones; the "responses" are four wave snapshots;
the "reflex" is a shorter graph path, not a measured reflex.
Synthetic, toy, educational.
"""

import heapq
import math
import random

__version__ = "0.2.0"


# ---------------------------------------------------------------- helpers
def normalize(v):
    n = math.sqrt(sum(abs(c) ** 2 for c in v))
    if n == 0:
        raise ValueError("cannot normalize a zero vector")
    return [c / n for c in v]


def overlap(field, pattern):
    return sum(p.conjugate() * f for p, f in zip(pattern, field))


def noisy(field, sigma, rng):
    return normalize(
        [c + complex(rng.gauss(0, sigma), rng.gauss(0, sigma))
         for c in field]
    )


def rand_field(n, rng):
    return normalize(
        [complex(rng.gauss(0, 1), rng.gauss(0, 1)) for _ in range(n)]
    )


def median(vals):
    vals = sorted(vals)
    if not vals:
        return math.inf
    return vals[len(vals) // 2]


# ---------------------------------------------------------------- geometry
class Neuron:
    def __init__(self, nid, x, y, stage, modality=None):
        self.id = nid
        self.x = float(x)
        self.y = float(y)
        self.stage = stage
        self.modality = modality

    def __repr__(self):
        return (f"Neuron({self.id}, {self.x:.2f}, {self.y:.2f}, "
                f"{self.stage!r}, {self.modality!r})")


# (stage, count, centre_x, centre_y, rx, ry, modalities in order)
STAGES = (
    ("sensory", 40, -24.0, 0.0, 7.0, 28.0,
     ["touch"] * 12 + ["temperature"] * 8 + ["pain"] * 8
     + ["proprioception"] * 12),
    ("spinal", 32, 0.0, 0.0, 7.0, 28.0, [None] * 32),
    ("central", 24, 0.0, 38.0, 18.0, 8.0, [None] * 24),
    ("motor", 32, 24.0, 0.0, 7.0, 28.0,
     ["flexor"] * 16 + ["extensor"] * 16),
)


class NervousGeometry:
    """Four-zone neuron layout + k-NN + cross-stage edges."""

    def __init__(self, seed=42, k=4):
        self.seed = seed
        self.k = k
        rng = random.Random(seed)
        neurons = []
        for stage, count, cx, cy, rx, ry, mods in STAGES:
            made = 0
            attempts = 0
            while made < count and attempts < 20000:
                attempts += 1
                x = rng.uniform(cx - rx, cx + rx)
                y = rng.uniform(cy - ry, cy + ry)
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                    neurons.append(Neuron(len(neurons), x, y,
                                          stage, mods[made]))
                    made += 1
            while made < count:  # fallback: centre jitter
                neurons.append(Neuron(len(neurons), cx, cy,
                                      stage, mods[made]))
                made += 1
        self.neurons = neurons
        self.n = len(neurons)
        self.edges, self.reflex_edges, self.cross_stage_edges = \
            self._connect(k)

    def _connect(self, k):
        edges = set()
        for a in self.neurons:
            dists = sorted(
                ((a.x - b.x) ** 2 + (a.y - b.y) ** 2, b.id)
                for b in self.neurons if b.id != a.id
            )
            for _, bid in dists[:k]:
                edges.add((min(a.id, bid), max(a.id, bid)))
        # Explicit cross-stage edges: 2 nearest of the target stage.
        reflex = set()
        cross = set()

        def link(src_stage, dst_stage, per, tag):
            for a in [n for n in self.neurons if n.stage == src_stage]:
                near = sorted(
                    ((a.x - b.x) ** 2 + (a.y - b.y) ** 2, b.id)
                    for b in self.neurons if b.stage == dst_stage
                )[:per]
                for _, bid in near:
                    e = (min(a.id, bid), max(a.id, bid))
                    edges.add(e)
                    cross.add(e)
                    if tag == "reflex":
                        reflex.add(e)

        link("sensory", "spinal", 2, "sense")
        link("spinal", "motor", 2, "reflex")
        link("spinal", "central", 2, "central")
        link("central", "motor", 2, "central")
        return sorted(edges), sorted(reflex), sorted(cross)

    def neighbours(self, nid, edges=None):
        out = []
        for a, b in (edges if edges is not None else self.edges):
            if a == nid:
                out.append(b)
            elif b == nid:
                out.append(a)
        return sorted(out)

    def delays_from(self, source, exclude_stages=(), forbidden_edges=()):
        """Dijkstra delays; inf if unreachable. Forbidden edges are
        excluded as undirected pairs; excluded stages are skipped
        as intermediate and target nodes (except the source)."""
        by_id = {neu.id: neu for neu in self.neurons}
        forbidden = set((min(a, b), max(a, b)) for a, b in forbidden_edges)
        times = {neu.id: math.inf for neu in self.neurons}
        times[source] = 0.0
        heap = [(0.0, source)]
        while heap:
            t, nid = heapq.heappop(heap)
            if t > times[nid]:
                continue
            a = by_id[nid]
            for mid in self.neighbours(nid):
                if mid != source and by_id[mid].stage in exclude_stages:
                    continue
                e = (min(nid, mid), max(nid, mid))
                if e in forbidden:
                    continue
                b = by_id[mid]
                w = math.hypot(a.x - b.x, a.y - b.y)
                if t + w < times[mid]:
                    times[mid] = t + w
                    heapq.heappush(heap, (times[mid], mid))
        return [times[neu.id] for neu in self.neurons]

    def stage_ids(self, stage):
        return [n.id for n in self.neurons if n.stage == stage]

    def first_id(self, stage, modality):
        for n in self.neurons:
            if n.stage == stage and n.modality == modality:
                return n.id
        raise ValueError(f"no {modality} in {stage}")


# ---------------------------------------------------------------- membrane
class MembraneNervous:
    """Nervous-system-shaped membrane: store, project, refuse."""

    RESPONSE_NAMES = ("withdraw", "grasp", "balance", "cool-alert")
    # Seeds, one sensory modality each, in RESPONSE_NAMES order.
    SEED_MODALITIES = ("pain", "touch", "proprioception", "temperature")

    def __init__(self, seed=42, width=12.0, period=40.0):
        if width <= 0 or period <= 0:
            raise ValueError("width and period must be positive")
        self.geometry = NervousGeometry(seed=seed)
        self.n = self.geometry.n
        self.width = width
        self.period = period
        self.seed_ids = [
            self.geometry.first_id("sensory", m)
            for m in self.SEED_MODALITIES
        ]
        self.patterns = [self.wave(sid) for sid in self.seed_ids]
        self.tau = None

    def wave(self, source):
        """Enveloped wave field started from neuron `source`."""
        delays = self.geometry.delays_from(source)
        out = []
        for d in delays:
            if math.isinf(d):
                out.append(0j)
                continue
            amp = math.exp(-(d * d) / (2.0 * self.width * self.width))
            phase = 2.0 * math.pi * d / self.period
            out.append(amp * complex(math.cos(phase),
                                     math.sin(phase)))
        return normalize(out)

    def overlaps(self, field):
        return [overlap(field, p) for p in self.patterns]

    def project(self, field):
        ms = self.overlaps(field)
        tot = sum(abs(m) ** 2 for m in ms)
        if tot == 0:
            return None, [0.0] * len(ms)
        probs = [abs(m) ** 2 / tot for m in ms]
        return max(range(len(ms)), key=lambda i: abs(ms[i])), probs

    def max_overlap(self, field):
        return max(abs(m) for m in self.overlaps(field))

    def calibrate(self, in_probes, ood_probes, grid=101):
        """Freeze tau: midpoint of the taus maximising Youden's J."""
        in_max = [self.max_overlap(f) for f in in_probes]
        ood_max = [self.max_overlap(f) for f in ood_probes]
        best_j, best_taus = -2.0, []
        for step in range(grid + 1):
            tau = step / grid
            tpr = sum(1 for v in in_max if v >= tau) / len(in_max)
            fpr = sum(1 for v in ood_max if v >= tau) / len(ood_max)
            j = tpr - fpr
            if j > best_j + 1e-12:
                best_j, best_taus = j, [tau]
            elif abs(j - best_j) <= 1e-12:
                best_taus.append(tau)
        self.tau = (best_taus[0] + best_taus[-1]) / 2.0
        return self.tau, best_j

    def decide(self, field):
        """('accept', response_name, probs) or ('reject', None, probs)."""
        winner, probs = self.project(field)
        if winner is None:
            return "reject", None, probs
        if self.tau is not None and self.max_overlap(field) < self.tau:
            return "reject", None, probs
        return "accept", self.RESPONSE_NAMES[winner], probs

    def reflex_time(self, source):
        """Median delay source -> motor, central nodes excluded."""
        delays = self.geometry.delays_from(
            source, exclude_stages=("central",))
        motor = self.geometry.stage_ids("motor")
        vals = [delays[i] for i in motor if math.isfinite(delays[i])]
        return median(vals)

    def central_time(self, source):
        """Median over motor nodes of min_c delay(source->c)
        + delay(c->motor), c in central. Route must pass central."""
        full = self.geometry.delays_from(source)
        central = self.geometry.stage_ids("central")
        motor = self.geometry.stage_ids("motor")
        vals = []
        for m in motor:
            # Delay from each central node to m, via full graph.
            best = math.inf
            for c in central:
                d_cm = self.geometry.delays_from(c)[m]
                if math.isfinite(full[c]) and math.isfinite(d_cm):
                    best = min(best, full[c] + d_cm)
            if math.isfinite(best):
                vals.append(best)
        return median(vals)

    def lesion_reflex_time(self, source):
        """Reflex route with spinal->motor reflex edges removed
        and central excluded: motor should become unreachable."""
        delays = self.geometry.delays_from(
            source, exclude_stages=("central",),
            forbidden_edges=self.geometry.reflex_edges)
        motor = self.geometry.stage_ids("motor")
        vals = [delays[i] for i in motor if math.isfinite(delays[i])]
        return median(vals)
