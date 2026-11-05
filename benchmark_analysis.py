"""Small, bounded seed-level analyses; no cross-domain success score."""
import math
from itertools import product
from statistics import mean


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("expected a finite numeric observation")
    return value


def failure_interval(errors, trials):
    """Wilson 95% interval for independent Bernoulli trials, not frames."""
    if (type(errors) is not int or type(trials) is not int
            or trials <= 0 or not 0 <= errors <= trials):
        raise ValueError("require integer 0 <= errors <= trials and trials > 0")
    z = 1.959963984540054
    p = errors / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    half = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return {
        "errors": errors, "trials": trials, "estimate": p,
        "wilson_95": [max(0.0, center - half), min(1.0, center + half)],
        "zero_error_upper_95_one_sided": -math.expm1(math.log(0.05) / trials) if errors == 0 else None,
        "independent_unit": "trial",
    }


def paired_comparison(baseline, treatment, practical_threshold, independent_unit="seed"):
    """Exact two-sided sign-flip test of paired differences (at most 16 units).

    Exchangeability/symmetric differences under the null must be justified by
    the protocol. A descriptive range is not a confidence interval.
    """
    if independent_unit not in ("seed", "session", "specimen"):
        raise ValueError("correlated frames are not independent units")
    if not isinstance(baseline, dict) or not isinstance(treatment, dict):
        raise ValueError("observations must be mappings keyed by independent unit")
    if not baseline or set(baseline) != set(treatment) or len(baseline) > 16:
        raise ValueError("require 1..16 matching paired units")
    threshold = _finite(practical_threshold)
    if threshold < 0:
        raise ValueError("practical threshold must be nonnegative")
    differences = [_finite(treatment[k]) - _finite(baseline[k]) for k in sorted(baseline)]
    for difference in differences:
        _finite(difference)
    observed = abs(mean(differences))
    extreme = sum(
        abs(mean(s * d for s, d in zip(signs, differences))) >= observed - 1e-12
        for signs in product((-1, 1), repeat=len(differences))
    )
    effect = mean(differences)
    return {
        "n_pairs": len(differences), "independent_unit": independent_unit,
        "treatment_minus_baseline": effect,
        "paired_difference_range": [min(differences), max(differences)],
        "two_sided_sign_flip_p": extreme / (2 ** len(differences)),
        "practical_threshold": threshold,
        "exceeds_absolute_practical_threshold": abs(effect) > threshold,
        "interpretation": "exploratory; metric direction must be stated separately",
    }


def holm_adjust(p_values):
    """Holm family-wise correction; include every registered family member."""
    if not isinstance(p_values, dict) or not p_values:
        raise ValueError("require the complete named confirmatory family")
    if any(not isinstance(k, str) for k in p_values):
        raise ValueError("family identifiers must be strings")
    for p in p_values.values():
        if not 0 <= _finite(p) <= 1:
            raise ValueError("invalid probability")
    ordered = sorted(p_values, key=lambda k: (p_values[k], k))
    adjusted, previous = {}, 0.0
    for rank, key in enumerate(ordered):
        previous = max(previous, min(1.0, (len(ordered) - rank) * p_values[key]))
        adjusted[key] = previous
    return adjusted
