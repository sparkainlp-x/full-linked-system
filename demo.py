"""Demo for full-linked-system v0.1.0. Run: python demo.py
Writes results.json in this directory.
"""
import json

from experiments import run_all


def main():
    res = run_all()
    c = res["exp_chain"]
    print("full-linked-system v0.1.0")
    print(f"gate: tau {c['tau']:.3f}, Youden J {c['youden_j']:.3f} (frozen)")
    print(f"clean pain 7 Hz: {c['clean_pain_7hz']}")
    print(f"clean pain 0.25 Hz: {c['clean_pain_0_25hz']}")
    print(f"random 7 Hz: {c['random_7hz']}")
    print(f"clean grasp 7 Hz: {c['clean_grasp_7hz']}")
    print(f"noisy sigma 0.30: {c['noisy_sigma_0_30']}")
    print(f"routing: {c['routing']}")
    print(f"listen: {c['listen']}")
    print(f"tau unchanged: {c['tau_unchanged']}, "
          f"patterns still 4: {c['patterns_still_4']}")
    print(f"lattice battery (parallel): {res['exp_lattice_battery']}")
    with open("results.json", "w") as f:
        json.dump(res, f, indent=2)
    print("wrote results.json")


if __name__ == "__main__":
    main()
