"""Experiments for full-linked-system v0.1.0. Bars in PREREG.md."""
import random

from chain import FullLinkedSystem
from human import modulate
from lat import lateral_score
from lattice import (build_pattern, catastrophe_front, count_flips,
                     random_flips, row_slip, seam_shift)
from nervous import noisy, rand_field


def exp_chain():
    s = FullLinkedSystem(seed=42)
    tau, j = s.calibrate()
    tau_before = tau
    f1 = s.run(s.system.patterns[0], f_hz=7.0)
    f2 = s.run(s.system.patterns[0], f_hz=0.25)
    f3 = s.run(rand_field(128, random.Random(7)), f_hz=7.0)
    grasp = s.run(s.system.patterns[1], f_hz=7.0)
    # Noisy batch: stock decision on modulated probe, vs chain.
    rng = random.Random(99)
    stock = injected = 0
    nets = []
    for k in range(40):
        probe = noisy(s.system.patterns[k % 4], 0.30, rng)
        if s.system.decide(modulate(probe, 7.0))[0] == "accept":
            stock += 1
        r = s.run(probe, f_hz=7.0, truth=1)
        if r.decision == "accept":
            injected += 1
        if r.net is not None:
            nets.append(r.net)
    net_mean = sum(nets) / len(nets) if nets else None
    pain = s.system.seed_ids[0]
    reflex = s.system.reflex_time(pain)
    central = s.system.central_time(pain)
    lesion = s.system.lesion_reflex_time(pain)
    return {
        "tau": round(tau, 3), "youden_j": round(j, 3),
        "clean_pain_7hz": {"decision": f1.decision,
                           "response": f1.response, "drive": f1.drive,
                           "displacement": round(f1.displacement, 2),
                           "sensor_k_est": f1.sensor["k_est"],
                           "action": f1.action,
                           "ledger_ok": f1.ledger_ok},
        "clean_pain_0_25hz": {"decision": f2.decision,
                             "attempts": f2.attempts,
                             "displacement": f2.displacement,
                             "action": f2.action},
        "random_7hz": {"decision": f3.decision,
                       "displacement": f3.displacement,
                       "action": f3.action},
        "clean_grasp_7hz": {"decision": grasp.decision,
                            "response": grasp.response,
                            "drive": grasp.drive,
                            "displacement": round(grasp.displacement, 2),
                            "sensor_k_est": grasp.sensor["k_est"]},
        "noisy_sigma_0_30": {"stock": stock, "injected": injected,
                             "net_mean": round(net_mean, 3)
                             if net_mean is not None else None},
        "routing": {"reflex_median": round(reflex, 2),
                    "central_median": round(central, 2),
                    "lesion_reflex_median": lesion},
        "listen": {"samples": f1.heart_ticks,
                   "wav_bytes": f1.wav_bytes},
        "tau_unchanged": s.system.tau == tau_before,
        "patterns_still_4": len(s.system.patterns) == 4,
    }


def exp_lattice_battery(reps=20):
    """Parallel battery, NOT in the live chain (see PREREG)."""
    out = {}
    for name, fn in [("seam_shift", seam_shift),
                     ("row_slip", row_slip),
                     ("catastrophe_front", catastrophe_front)]:
        gaps = []
        for seed in (42, 43, 44):
            pat = build_pattern(seed)
            corr = fn(pat)
            k = count_flips(pat, corr)
            rvals = [lateral_score(pat, random_flips(pat, k,
                                                     random.Random(100 + r)))
                     for r in range(reps)]
            gaps.append(lateral_score(pat, corr)
                        - sum(rvals) / len(rvals))
        out[name] = round(sum(gaps) / len(gaps), 3)
    mean_gap = sum(out.values()) / len(out)
    out["bar_F6"] = {"mean_gap": round(mean_gap, 3),
                     "n_ge_0.10": sum(1 for v in out.values()
                                      if v >= 0.10),
                     "pass": mean_gap >= 0.15
                     and sum(1 for v in out.values()
                             if v >= 0.10) >= 2}
    return out


def run_all():
    return {"exp_chain": exp_chain(),
            "exp_lattice_battery": exp_lattice_battery()}
