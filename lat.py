"""Pattern-specific lateral score for the microtubule lattice.

Geometry, reused from lattice.py: 13 rows x 12 columns,
row-major, N = 156. Neighbour pairs are the lattice edges:
vertical pairs row r -> r+1 for r = 0..11, the seam pair
row 12 -> row 0, and horizontal pairs col c -> c+1 for
c = 0..10. Total 156 + 143 = 299 pairs.

For a stored pattern `pat` (±1) and a probe `x` (±1, or 0
for unknown cells, which are skipped), the lateral score is:

  lat(x) = mean over pairs (i, j) of (pat_i * pat_j)
                                            * (x_i * x_j)

For x = pat, lat = 1.0 by construction. For a random
pattern, lat ~ 0. For a probe whose flips are scattered,
most neighbour products change, so lat falls fast. For a
probe whose flips are structured (a whole row inverted,
a seam moved, a front flipped), many neighbour products
are preserved — a whole inverted row keeps its horizontal
products, a flipped front keeps its internal vertical
products — so lat falls slower than for scattered flips
at the same flip count. That difference is the
lattice-specific signal, and it is measured, not assumed.

This score does NOT use any biology. It is a graph score
on a 13x12 grid with a seam edge. "Straight / GTP-like"
and "curved / GDP-like" are labels from lattice.py, analogy
only.
"""
from lattice import COLS, ROWS, idx


def neighbour_pairs():
    pairs = []
    for r in range(ROWS):
        for c in range(COLS):
            i = idx(r, c)
            if r < ROWS - 1:
                pairs.append((i, idx(r + 1, c)))
            else:
                pairs.append((i, idx(0, c)))  # seam edge
            if c < COLS - 1:
                pairs.append((i, idx(r, c + 1)))
    return pairs


PAIRS = neighbour_pairs()


def lateral_score(pat, x):
    vals = []
    for i, j in PAIRS:
        if x[i] == 0 or x[j] == 0:
            continue
        vals.append((pat[i] * pat[j]) * (x[i] * x[j]))
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def combined_score(pat, x, overlap_fn):
    """S = 0.5 * overlap + 0.5 * lateral_score, weights fixed
    in PREREG.md. overlap_fn is memory.overlap."""
    return 0.5 * overlap_fn(x, pat) + 0.5 * lateral_score(pat, x)
