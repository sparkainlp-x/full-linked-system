"""Human-frequency layer for membrane-nervous-system v0.2.0.

Stdlib-only, AGPL-3.0-only.

What this is
------------
A frequency gate on top of the v0.1.0 membrane. The v0.1.0 gate
decides on overlap magnitude alone: accept iff max |overlap|
>= tau. This layer scales a probe field by a frequency
sensitivity s(f) BEFORE that decision, without renormalising.
Scaling a field by s scales every overlap by s, so the winner
(response name) is unchanged, but the accept/reject decision
now depends on frequency: a probe far from the sensitive
frequency loses overlap and falls below the frozen tau.

That is the whole mechanism, stated plainly. The sensitivity
curve is IMPOSED by the parameters below, not discovered from
a person or a recording.

Frequencies reused
------------------
Bands copied exactly from bentov-kuramoto/chain.py NATURAL_HZ,
which labels them illustrative, not measurements:

    breath 0.25 Hz, heart 1.2 Hz, aorta 7.0 Hz, brain 10.0 Hz

Sensitive frequency
-------------------
SENSITIVE_HZ = 7.0 Hz. This is Bentov's alignment frequency:
in bentov-kuramoto, meditation ON forces heart, aorta, breath
and brain toward ~7 Hz and the heart-brain phase-difference
spread falls to 0.000 (circular by design — the forcing is the
point). Reusing 7.0 Hz here reuses that toy alignment. It is
NOT a measurement of any human, NOT a therapeutic frequency,
NOT evidence that 7 Hz resonates in a real body, and NOT a
validation of Bentov.

Sensitivity curve (chosen parameters, see PREREG.md):

    s(f) = exp(-0.5 * ((f - 7.0) / 1.5) ** 2)

s(7.0) = 1.0, s(0.25) ~ 0.00004, s(1.2) ~ 0.0006,
s(10.0) ~ 0.135. Width 1.5 Hz is chosen, not fitted to data:
there is no human data in this package to fit to.
"""

import math

__version__ = "0.2.0"

# Hz, illustrative only — see module docstring.
BANDS = {
    "breath": 0.25,
    "heart": 1.2,
    "aorta": 7.0,
    "brain": 10.0,  # alpha mid-band
}

SENSITIVE_HZ = 7.0
SENSITIVITY_WIDTH_HZ = 1.5


def sensitivity(f_hz):
    """Imposed sensitivity at frequency f_hz, in [0, 1].

    1.0 exactly at SENSITIVE_HZ, falling as a Gaussian away
    from it. This is a design choice, not a measured curve.
    """
    if f_hz < 0:
        raise ValueError("frequency must be >= 0")
    z = (f_hz - SENSITIVE_HZ) / SENSITIVITY_WIDTH_HZ
    return math.exp(-0.5 * z * z)


def modulate(field, f_hz):
    """Scale a probe field by s(f_hz), WITHOUT renormalising.

    Deliberately not renormalised: renormalising would erase
    the frequency effect entirely, since overlaps would scale
    back up. The caller passes the modulated field to
    MembraneNervous.decide / project exactly as before.
    """
    s = sensitivity(f_hz)
    return [s * c for c in field]


def frequency_response(frequencies):
    """Table of (f_hz, sensitivity) for a sweep. No membrane run."""
    return [(f, sensitivity(f)) for f in frequencies]
