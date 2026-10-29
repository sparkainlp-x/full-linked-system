"""Microtubule-like lattice patterns for a classical toy.

Geometry: 13 rows x 12 columns, row-major, N = 156. Row 12 neighbours
row 0 across the seam. Cell state is +-1, labelled "straight /
GTP-like" (+1) vs "curved / GDP-like" (-1) by analogy ONLY. This file
contains no tubulin, no GTP, no hydrolysis, no mechanics, no neuron,
and no quantum state.

Construction: row 0 is random +-1 (seeded). Each following row is
the previous row with ~15% of cells flipped, so lateral neighbours
mostly agree (a B-lattice-like rule). The seam transition (row 12
back to row 0) is inverted, so seam neighbours mostly DISAGREE
(the A-lattice-like mismatch). That contrast is the whole point:
a memory that uses lattice structure should be sensitive to seam
position, and a memory that does not should not be — the package
measures which one it is, it does not assume it.
"""
import random

ROWS = 13
COLS = 12
N = ROWS * COLS


def idx(row, col):
    return row * COLS + col


def build_pattern(seed=42):
    """Deterministic lattice pattern. Returns a list of +-1, len 156."""
    rng = random.Random(seed)
    rows = []
    row = [rng.choice((-1, 1)) for _ in range(COLS)]
    rows.append(row[:])
    for _ in range(ROWS - 1):
        nxt = [(-c if rng.random() < 0.15 else c) for c in row]
        rows.append(nxt)
        row = nxt
    # Seam: row 12 is the inverted image of row 0's neighbourhood in
    # the sense that its agreement with row 0 is forced low. Achieve
    # it by construction: replace row 12 with the inverse of row 0
    # blended with its own chain row (so it is not a trivial copy).
    rows[12] = [(-c if rng.random() < 0.85 else c) for c in rows[0]]
    out = []
    for r in rows:
        out.extend(r)
    return out


def rows_of(x, rows=ROWS):
    return [x[r * COLS:(r + 1) * COLS] for r in range(rows)]


def lateral_agreement(x, r1, r2):
    """Mean agreement (+1 = agree) between two rows, same column."""
    a = rows_of(x)[r1]
    b = rows_of(x)[r2]
    return sum(1 if p == q else -1 for p, q in zip(a, b)) / COLS


def seam_agreement(x):
    return lateral_agreement(x, 12, 0)


def mean_adjacent_agreement(x):
    vals = [lateral_agreement(x, r, r + 1) for r in range(ROWS - 1)]
    return sum(vals) / len(vals)


def flip_bits(x, p, rng):
    return [(-c if rng.random() < p else c) for c in x]


def count_flips(a, b):
    return sum(1 for p, q in zip(a, b) if p != q)


def random_flips(x, k, rng):
    """Flip exactly k distinct cells, chosen at random."""
    out = list(x)
    for i in rng.sample(range(len(x)), k):
        out[i] = -out[i]
    return out


def mask_block(x, r0=4, c0=4, h=3, w=4):
    """Occlusion: masked cells become 0 (unknown), not random."""
    out = list(x)
    for r in range(r0, r0 + h):
        for c in range(c0, c0 + w):
            out[idx(r, c)] = 0
    return out


def mask_row(x, row=6):
    out = list(x)
    for c in range(COLS):
        out[idx(row, c)] = 0
    return out


def mask_seam(x):
    """Mask the seam region: rows 12 and 0, first 4 columns."""
    out = list(x)
    for r in (12, 0):
        for c in range(4):
            out[idx(r, c)] = 0
    return out


def seam_shift(x):
    """Move the seam: un-invert row 12, invert row 5 instead.
    Changes exactly 2 rows (24 cells) if row 12 was ~85% inverted."""
    out = list(x)
    rows = rows_of(out)
    # Restore row 12 to agree with row 0's chain: set it to row 11
    # with 15% flips (the normal chain rule), and invert row 5.
    rows[12] = [(-c if False else c) for c in rows[11]]
    rows[5] = [-c for c in rows[5]]
    flat = []
    for r in rows:
        flat.extend(r)
    return flat


def row_slip(x, row=6, k=3):
    """Cyclically shift one row by k columns."""
    rows = rows_of(x)
    r = rows[row]
    rows[row] = r[-k:] + r[:-k]
    flat = []
    for rr in rows:
        flat.extend(rr)
    return flat


def catastrophe_front(x, rows_to_flip=6, col_from=8):
    """Flip the suffix of the first `rows_to_flip` rows: the toy
    analogue of cap loss. Labelled as such, not a biological event."""
    out = list(x)
    for r in range(rows_to_flip):
        for c in range(col_from, COLS):
            out[idx(r, c)] = -out[idx(r, c)]
    return out


def scrambled(x, rng):
    """Permute rows and columns: bit counts preserved, lattice
    adjacency and seam position destroyed."""
    rows = rows_of(x)
    order_r = list(range(ROWS))
    order_c = list(range(COLS))
    rng.shuffle(order_r)
    rng.shuffle(order_c)
    out = []
    for r in order_r:
        for c in order_c:
            out.append(rows[r][c])
    return out


def shuffled_states(x, rng):
    """Permute all cell values: marginal +-1 fraction preserved,
    all structure destroyed."""
    out = list(x)
    rng.shuffle(out)
    return out


def random_pattern(rng):
    return [rng.choice((-1, 1)) for _ in range(N)]


# --- 12x12 cropped game version -------------------------------------
def build_pattern_12(seed=42):
    """First 12 rows of the 13-row construction, declared cropped.
    12 != 13: this is not a real microtubule."""
    full = build_pattern(seed)
    return full[:12 * COLS]


def fragment_top_rows(x, rows=12, keep=4):
    """Keep only the first `keep` rows, rest 0 (unknown)."""
    out = [0] * len(x)
    for r in range(keep):
        for c in range(COLS):
            out[r * COLS + c] = x[r * COLS + c]
    return out


def fragment_corner(x, rows=12, h=6, w=6):
    out = [0] * len(x)
    for r in range(h):
        for c in range(w):
            out[r * COLS + c] = x[r * COLS + c]
    return out


def sonify_row_overlaps(overlaps):
    """Display only: map per-row overlap [-1, 1] to a pitch in Hz.
    This is never scored, and a 'nice sound' is never a result.
    Base 262 Hz (C4), one octave range."""
    return [262.0 * (2.0 ** ((o + 1.0) / 2.0)) for o in overlaps]
