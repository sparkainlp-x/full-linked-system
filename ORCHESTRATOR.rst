Bounded scientific orchestration, first reviewable slice
======================================================

This is a software benchmark orchestrator, not a unified physical theory,
discovery guarantee, quantum device, clinical intervention, or hardware
controller. No release or merge is part of this change. Historical files
DESIGN.md, PREREG.md and results.json remain authoritative records of the
legacy toy and are not rewritten by this pipeline.

Architecture
------------

::

  versioned config + local source locks + public inventory (inspection record)
             |
      schema / protocol / DAG / resource preflight
             |
        explicit offline plan
             |
      bounded isolated worker processes
             |
       +-----+-------------------+---------------------+
       |                         |                     |
  legacy-chain              telemetry baseline   pinned public adapter
  (128 complex slots)       (synthetic samples)    (only when prepared)
       |                         |                     |
       +----- independent domain artifacts -----------+
             |
  canonical payload hashes + parent IDs + failure capsules
             |
  local provenance + runtime/memory metadata + JSON / CSV / static HTML

Tracks remain independent. A DAG edge is not evidence of a physical
relationship. Contracts must match data type, exact shape, units,
coordinates, sampling rate, normalization, time semantics, noise assumptions,
and evidence origin. There is no implicit padding, truncation or
normalization. No dimension-changing transform is currently registered.
The 156-dimensional lattice cannot be passed to the 128-dimensional membrane.

Scientific scope and limitations
-------------------------------

* Legacy calibration and rescue behavior are reproduced without moving
  thresholds. The legacy implementation has fixed internal RNG streams:
  calibration 11 and injection 1234. New experiment seeds do not magically
  make these internal replicates independent. This is exploratory regression
  evidence, not a new confirmatory sample.
* The imposed 7 Hz Gaussian sensitivity is a modeling choice. The ring sensor
  is derived from the same imposed twist state: a consistency check, not
  independent measurement. Audio is sonification, not recorded evidence.
* Archived upstream/legacy numbers are not newly executed pipeline results.
  Keep stock 19/40, injected 21/40 and net -0.277 together: acceptance
  alone does not demonstrate accuracy, calibrated probability, or payoff.
  Row-slip +0.043 remains an individual negative result.
* A telemetry event test with imposed pulses validates the implementation
  under stated synthetic conditions, not a physical sensor or a deployed
  anomaly detector. RMS and maximum-absolute baselines must be reported
  separately. Missing channels must be explicit, not silently imputed.
* Waveholo's pupil phase_variance negative finding must be preserved in
  any later optics integration. Its real-data slope check is not
  absolute-focus validation. No implemented optics result is claimed here.
* Coherent transport and density-matrix experiments stay separate from
  memory, residual monitoring and optics. OES residual gates are not
  stabilizer QEC. Simulated-code memory, if later implemented, must report
  logical failure counts and uncertainty without hardware or advantage
  claims. A hydrogen-orbital educational module is a future independently
  validated track; no image establishes an implemented capability.
* Evidence origin (synthetic or measured dataset), execution status
  (not run / passed / failed / blocked / skipped), and interpretation
  (exploratory / baseline stronger / reproduced within conditions) are
  separate dimensions. Local manifests do not assert compatibility with
  evidence-passport or claims-layer. SHA256 shows consistency, not truth,
  authenticated provenance, or independent preregistration.

Protocol review
---------------

``protocols/scientific-template.json`` is explicitly a NON-EXECUTABLE review
template. ``scientific_orchestrator/smoke.json`` is the executable versioned
smoke configuration. Inspecting a development result makes it exploratory.
Development, calibration, and held-out seed groups must be disjoint; smoke
must not execute held-out data. Confirmatory unlocking, winner selection and
held-out reuse are not implemented. No protocol hash is presented as an
independently timestamped registration.

The first-slice telemetry endpoint tests pulse presence, not event onset.
Detection latency and multichannel missing-channel/local-versus-shared
validation are explicitly NOT_IMPLEMENTED. Local/shared toy perturbations
refer only to time-local impulses and a time-shared offset in one stream.
They are not evidence of coupling benefit or independent sensor validation.

Before any new family of experiments, lock a single domain-appropriate
primary metric, its direction, a practical effect threshold, the baseline,
the independent sampling unit, sample/CPU/time/memory/run budgets, all
configurations and a fixed stopping rule. Failed and timed-out configurations
must remain visible. Do not treat repeated frames from a seed/session/specimen
as independent observations. Paired comparisons require matching independent
units and justified exchangeability. ``benchmark_analysis.py`` supplies a
bounded exact sign-flip test (at most 16 pairs), Wilson binomial intervals,
a one-sided zero-error upper bound, and Holm family-wise correction.
The paired range is descriptive, not a confidence interval.

Exploratory sweeps must state multiplicity; confirmatory Holm families must
include registered failed/blocked members conservatively (for example p=1),
not remove them after inspection. The smoke tier does not claim confirmatory
power or practical significance. No cross-domain aggregate success score
exists.

Public inventory and local preparation
-------------------------------------

``public_sources.json`` records only explicitly verified public observations.
Null SHAs, shapes or APIs mean not inspected, never guessed. Discovery scope,
pagination and completion are recorded inside the file. Missing or unclear
licenses block code copying and dependency redistribution pending review.
The legacy vendoring map remains unchanged and does not substitute for a new
upstream license audit.

Public-only search pagination returned 126 names on 13 pages; 21 sources were
inspected in more detail, with 20 full SHAs resolved. The other 105 names use
explicit discovery-only defaults (candidate requiring inspection,
NOT_IMPLEMENTED, unknown license/API/revision). ``complete:false`` refers to
source inspection, not failure of the later name-discovery pagination.
``python3 public_registry.py public_sources.json --export`` expands the
compact registry into one full record and URL per discovered public project.

Offline validation: ``python3 public_registry.py public_sources.json``.
This checks the registry schema, not authenticity or current visibility.
To extend the inventory, explicitly request online preparation, inspect an
unauthenticated PUBLIC GitHub repository response, then its full commit SHA,
license and actual API at that revision. Record shapes, units, assumptions,
dependencies and limitations. Do not use authenticated all-repository listing
or disclose nonpublic metadata. When public access fails, retain the verified
subset, mark discovery incomplete and record the failure; do not infer absence.
Experiments never fetch, install, scan networks, control devices or launch jobs.
Optional sources belong in isolated prepared checkouts/environments, not one
combined dependency environment. A missing adapter is NOT_IMPLEMENTED/blocked,
never a successful mock.

Integration coverage and ranked follow-ups
-----------------------------------------

=============================== ==========================================
Track / check                   First-slice coverage
=============================== ==========================================
Legacy chain                    Runnable; frozen regression, costs recorded
Simple telemetry baseline       Runnable offline synthetic reference
Cross-public adapter            See registry; only inspected pinned APIs
OES-32 residual reference       Runnable pinned optional numerical gate
Optics                          NOT_IMPLEMENTED; no focus validation claim
Density matrices                NOT_IMPLEMENTED; trace/Hermiticity/PSD next
Coherent transport              NOT_IMPLEMENTED; accounting/convergence next
Memory capacity/refusal          Legacy four-pattern toy only, no capacity sweep
OES monitoring                  NOT_IMPLEMENTED unless registry states otherwise
Telemetry detection latency     NOT_IMPLEMENTED; event presence only
Multichannel stress validation  NOT_IMPLEMENTED; local/shared toy time offsets
Stabilizer simulated QEC         NOT_IMPLEMENTED; isolated future track
Claims/evidence upstream schemas NOT_IMPLEMENTED; local manifest only
Dimension-changing transforms   NOT_IMPLEMENTED; incompatible edges rejected
Cross-domain coupling benefit   NOT_IMPLEMENTED; no matched-budget claim
Held-out confirmatory execution NOT_IMPLEMENTED; held-out use rejected
Hardware / educational orbitals NOT_IMPLEMENTED and outside smoke scope
=============================== ==========================================

1. Extend the independently executable telemetry experiment with preregistered
   seed-level paired max-absolute/RMS versus inspected upstream monitors;
   include baseline-only, component-removal, shuffled/null, drift, missing
   channels and local/shared disturbances at matched full cost.
2. Evaluate memory rescue with correct-label recall, refusal risk/coverage and
   null/OOD false acceptance at matched full retry cost, not just acceptance.
   Capacity and corruption sweeps need a separate bounded protocol.
3. Prepare an isolated optics adapter and verify analytic reconstruction and
   focus failures, preserving phase_variance and slope-check limitations.
4. Validate separate small density matrices (trace, Hermiticity, positivity)
   against analytic cases; then transport probability accounting and
   time-step/truncation convergence.
5. Only after those independent references, propose explicit tested couplings
   and compare with independent modules at matched budgets. Any synthetic
   coupling remains an assumption.
6. Inspect simulated QEC and evidence schemas/licenses separately before
   adding either. No hardware or physical-advantage extrapolation.

These follow-ups are proposed scientific work, not implemented commands.

Exact clean-checkout commands
----------------------------

Python 3.10+ and Linux are required for enforced process resource limits.
There are no pip packages for the offline core. Adapt the checkout path only
if your checkout is elsewhere. Run these from the repository root::

  cd /home/runner/work/full-linked-system/full-linked-system
  python3 -m unittest tests test_legacy_regression test_benchmark_analysis test_public_registry test_public_residual_adapter -v
  python3 -m unittest discover -s scientific_orchestrator -p 'test_*.py' -v
  python3 public_registry.py /home/runner/work/full-linked-system/full-linked-system/public_sources.json
  python3 -m scientific_orchestrator plan /home/runner/work/full-linked-system/full-linked-system/scientific_orchestrator/smoke.json
  python3 -m scientific_orchestrator run /home/runner/work/full-linked-system/full-linked-system/scientific_orchestrator/smoke.json --output /tmp/full-linked-smoke
  python3 -m scientific_orchestrator verify /tmp/full-linked-smoke
  python3 -m scientific_orchestrator run /home/runner/work/full-linked-system/full-linked-system/scientific_orchestrator/baseline.json --output /tmp/full-linked-baseline
  python3 -m scientific_orchestrator run /home/runner/work/full-linked-system/full-linked-system/scientific_orchestrator/legacy.json --output /tmp/full-linked-legacy

Reusing the same unmodified configuration and output directory resumes
verified results. Use a fresh directory for a changed configuration, source,
runtime or failed-run replay. ``demo.py`` is still the historical executable,
but it writes results.json; do not use it to overwrite the committed archive
when testing this orchestrator. The regression calls its experiment functions
without writing the archive.

The optional OES-32 source is not included or installed by default.
The following preparation command is explicitly ONLINE, downloads only the
inspected revision's source and license files, verifies fixed SHA256 hashes,
and requires a fresh isolated directory. It installs no packages::

  python3 /home/runner/work/full-linked-system/full-linked-system/public_residual_adapter.py prepare --directory /tmp/oes32-prepared --allow-network
  python3 /home/runner/work/full-linked-system/full-linked-system/public_residual_adapter.py run --request /home/runner/work/full-linked-system/full-linked-system/protocols/residual-request.json --source-dir /tmp/oes32-prepared
  OES32_PREPARED=/tmp/oes32-prepared python3 -m unittest discover -s scientific_orchestrator -p 'test_*.py' -v
  python3 -m scientific_orchestrator run /home/runner/work/full-linked-system/full-linked-system/scientific_orchestrator/public.json --output /tmp/full-linked-public
  python3 -m scientific_orchestrator verify /tmp/full-linked-public

After preparation the adapter is offline. Its version is pinned to
``fc0059bea09048baee0fc9c70d8de4d5da0d9493``. Absence is blocked, altered
source/license is failed, timeout is not a numerical pass. A successful
execution can return a scientifically failed residual criterion; those are
different statuses. Subprocesses use a trusted Python interpreter, fixed
wrapper, argument lists, timeout, memory/CPU limits and validated output;
they are not a hostile-code security sandbox. AGPL obligations still apply.

The library's default budget enforcement applies Linux CPU/address-space
limits to execution workers, with bounded serial orchestration; controller
memory is bounded by schema/run limits, not a controller RLIMIT. Whole-second
kernel CPU-limit granularity is documented. Peak RSS is a separate measurement,
not the virtual-address-space cap. No hardware/cloud execution is supported.

The schema in ``schemas/experiment-v1.schema.json`` is descriptive;
the functional CLI performs additional strict adapter, DAG, numerical and
budget validation without fetching remote JSON schemas. The review template
is intentionally not accepted as an executable configuration.

Observed verification for this change
------------------------------------

Commands actually executed, distinct from proposed future experiments:

* ``python -m unittest tests test_legacy_regression test_benchmark_analysis
  test_public_registry test_public_residual_adapter -v``:
  31 tests passed, latest wall time 5.375 seconds.
* ``OES32_PREPARED="$PWD/scientific_orchestrator/.final-public-source" python -m unittest
  discover -s scientific_orchestrator -p 'test_*.py' -q``:
  33 tests passed in 3.695 seconds in the implementation process, including
  genuine pinned public execution. Without that explicit environment variable
  the genuine integration test is skipped with a reason; missing-source
  blocking is still tested. A final pass including the HTML wording regression
  also passed all 33 tests in 3.705 seconds. Temporary prepared sources were removed.
* ``python -m scientific_orchestrator plan/run/verify`` and resumed execution
  were exercised for smoke, baseline, legacy and public examples.
  Smoke produced six completed node-seed computations, with no practical
  improvement conclusion. Last instrumented smoke checkpoint: six attempts,
  CPU 0.011356 seconds, cumulative active wall 0.052403 seconds,
  peak worker RSS 17,084 KiB.
* Pinned public numerical cases at tolerance 0.25, deltas 0, 0.25 and 0.5:
  numerical criteria true, true, false; all three computations completed.
  Last single-case public pipeline measurement: accounted wall 0.056715
  seconds, CPU 0.043757 seconds including child CPU 0.040126 seconds,
  peak worker/child RSS 17,708 KiB.
* ``python public_residual_adapter.py prepare --directory /tmp/oes32-prepared
  --allow-network`` and its offline ``run --request protocols/residual-request.json
  --source-dir /tmp/oes32-prepared`` were executed successfully. Root standalone
  adapter tests also cover malformed input, source tampering, missing files,
  timeout and exact-byte execution.
* ``python public_registry.py public_sources.json`` validated 126 expanded
  records; ``--export`` emitted one record/URL per public source. No private
  repository discovery or metadata was used.

The public REST owner listing failed with 403; targeted MCP file reads also
timed out. Public search pagination and pinned raw-source inspection provided
the explicitly qualified fallback. The review found held-out unlocking and
unverified resume accounting; both were fixed and regression-tested.
Expected timeout, budget, malformed-input and tampering failures are tested
negative paths, not silently successful runs. Historic rescue payoff and
row-slip negatives remain preserved.

These are recorded verification observations, not the sum of all development
compute, lookup time or iterative tests. End-to-end CLI startup and the total
development cost were not instrumented. No exhaustive sweep, measured-data
benchmark, coupling-benefit study, hardware/cloud experiment, release or merge
was performed. Only telemetry has an implemented primary-metric comparison;
legacy/public examples are exploratory adapter conformance checks, not
confirmatory domain benchmark protocols.
