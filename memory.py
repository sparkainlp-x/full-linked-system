"""Outer-product holographic memory and the refusing gate.

Memory: W = sum over stored patterns of outer(x, x), diagonal 0.
Recall: y = sign(W @ probe); a 0 dot keeps the probe's own sign
(unknown cells, 0, stay 0 until the sign step maps them: 0 dot with
a 0 probe cell gives 0, reported as 0, not as a guessed +-1).
Overlap and accuracy are always reported overall, never only
among accepted probes — accuracy-among-accepted alone hides
refusal gaming.
"""
import math


def build_W(patterns):
    n = len(patterns[0])
    W = [[0.0] * n for _ in range(n)]
    for x in patterns:
        for i in range(n):
            xi = x[i]
            Wi = W[i]
            for j in range(n):
                Wi[j] += xi * x[j]
    for i in range(n):
        W[i][i] = 0.0
    return W


def matvec(W, v):
    return [sum(W[i][j] * v[j] for j in range(len(v)))
            for i in range(len(W))]


def recall(W, probe):
    out = []
    for dot, p in zip(matvec(W, probe), probe):
        if dot > 0:
            out.append(1)
        elif dot < 0:
            out.append(-1)
        else:
            out.append(p)  # 0 stays 0 (unknown), not a guess
    return out


def overlap(a, b):
    """Mean product over cells where both are non-zero (+-1)."""
    pairs = [(p, q) for p, q in zip(a, b) if p != 0 and q != 0]
    if not pairs:
        return 0.0
    return sum(p * q for p, q in pairs) / len(pairs)


def accuracy(recalled, true):
    pairs = [(p, q) for p, q in zip(recalled, true) if q != 0]
    if not pairs:
        return 0.0
    return sum(1 for p, q in pairs if p == q) / len(pairs)


def score_probe(W, probe, stored):
    """Score = overlap between the probe and its own recall.
    For a single stored pattern this equals |overlap(probe, stored)|
    (the gate sees overlap magnitude only, as in refusing-membrane).
    Scoring recall-vs-stored instead would be +-1 for every probe,
    including random ones, because one-step recall snaps to
    +-stored — that version was tried, gave FPR ~0.5, and was fixed
    here. `stored` is kept in the signature for call compatibility
    and for multi-pattern extensions; the score does not use it
    beyond that, by design for the single-pattern gate."""
    return overlap(probe, recall(W, probe))


def calibrate_gate(true_scores, control_scores):
    """Sweep thresholds at midpoints between sorted unique scores.
    Pick max Youden's J = TPR - FPR. Ties: the smallest threshold
    achieving max J (documented, not tuned afterwards).
    Returns (tau, J, TPR, FPR) on the validation scores given."""
    vals = sorted(set(true_scores) | set(control_scores))
    cands = []
    for a, b in zip(vals, vals[1:]):
        cands.append((a + b) / 2.0)
    cands.extend([vals[0] - 0.01, vals[-1] + 0.01])
    best = None
    for tau in cands:
        tpr = sum(1 for s in true_scores if s >= tau) / len(true_scores)
        fpr = sum(1 for s in control_scores if s >= tau) / len(control_scores)
        j = tpr - fpr
        if best is None or j > best[1] + 1e-12:
            best = (tau, j, tpr, fpr)
    return best


def apply_gate(score, tau):
    return score >= tau


def roc_table(true_scores, control_scores, tau):
    tpr = sum(1 for s in true_scores if s >= tau) / len(true_scores)
    fpr = sum(1 for s in control_scores if s >= tau) / len(control_scores)
    return {"tau": tau, "TPR": tpr, "FPR": fpr, "J": tpr - fpr,
            "n_true": len(true_scores), "n_control": len(control_scores)}
