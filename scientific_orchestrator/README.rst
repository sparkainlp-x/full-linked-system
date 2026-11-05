Bounded exploratory orchestration (stdlib only)
================================================

Commands::

    python -m scientific_orchestrator plan scientific_orchestrator/smoke.json
    python -m scientific_orchestrator run scientific_orchestrator/smoke.json --output scientific_orchestrator/smoke-output
    python -m scientific_orchestrator verify scientific_orchestrator/smoke-output
    python -m unittest discover -s scientific_orchestrator -p 'test_*.py'
    python -m scientific_orchestrator run scientific_orchestrator/baseline.json --output scientific_orchestrator/baseline-output
    python -m scientific_orchestrator run scientific_orchestrator/legacy.json --output scientific_orchestrator/legacy-output

Public Python API: ``load_config(path) -> dict``, ``validate_config(dict) -> plan``,
``execute(dict, output, extended=False) -> manifest``, ``verify(output) -> verification``,
and ``Contract.from_dict(dict)``. Validation errors raise ``ValueError``; I/O errors
remain ``OSError``. A complete manifest may include non-success terminal statuses.
CLI run/replay exits 2 for such results, 1 for invalid input and 0 for success.
``plan`` validates the schema and DAG; execution additionally enforces smoke caps
and dev-only use. No dependencies, network operations or shell-command config.
Its ``cost_estimate`` reports planned/max attempted node-seed runs and declared
wall, CPU, per-run and per-process memory ceilings, explicitly not measured or
predicted costs. It does not fabricate an aggregate RSS bound.

Version 1 schema
----------------

``smoke.json`` is the full schema example. Unknown fields, duplicate JSON keys,
nonfinite numbers and booleans where numbers are required are rejected.
All three seed lists must be nonempty, disjoint, unique unsigned 32-bit integers.
Protocol locks ``primary_metric=paired_error_difference`` (maxabs error minus RMS
error), ``baseline=rms``, practical threshold in [0,1], ``stopping=fixed_budget``,
``interpretation=exploratory``, and selected ``run_split``.
No automatic calibration, adaptive thresholds, early scientific stopping,
independent preregistration claims or heldout leakage are implemented.
Calibration execution requires explicit ``--extended``; it remains exploratory.
Heldout execution is universally rejected, including extended plans and
verification, until locked selection and heldout-use accounting exist.
Known local historic results cannot be made independent by changing this label.

All six budgets are required. ``max_runs`` counts **node-seed attempts**, including
generators. Smoke caps: runs 12, workers 1, wall 30s, CPU 20s, address-space memory
256 MiB, per-run wall 10s. Extended hard caps: 128, 1, 300s, 240s, 1024 MiB, 60s.
Planned node-seed records are also capped at 12/128, even if most would be skipped.
Workers other than 1 are explicitly rejected. CPU budgets require integer
seconds >=1. CPU is cumulative worker usage,
rounded up to whole seconds for Linux RLIMIT_CPU; wall includes orchestration.
Each child gets RLIMIT_AS, RLIMIT_CPU and disabled core dumps. Parent stays
bounded by schema/run limits but is not itself memory-limited. Memory is virtual
address space, not RSS; peak RSS is recorded separately. Small CPU limits can
overshoot by the kernel's one-second granularity. A timeout consumes conservative
CPU accounting if the child cannot report usage.
Worker accounting includes waited subprocess children via RUSAGE_CHILDREN;
self/child CPU and child peak RSS are recorded separately. Reported peak memory
is maximum per-process RSS, not simultaneous aggregate RSS. Nested public
execution inherits limits and further caps its process at 128 MiB/2 CPU seconds.
Worker sessions allow timeout cleanup to signal the specific worker process
group, including nested adapter subprocesses.

Nodes have ``id``, adapter name, parent ID list, ``params``, output ``contract``, and
``input_contract`` when a parent exists. At most one parent per adapter; arbitrary
domain tracks are uncoupled by default (conceptually parallel, executed serially).
DAG ordering is per seed. Edges require **exact** matching contracts, including
data type, shape, units, coordinates, sample rate, normalization, time origin,
noise description and evidence origin. No padding/truncation/unit conversion.
``adapters.TRANSFORMS`` is empty. ``dimension_transform`` and ``public_adapter`` registry
entries are ``NOT_IMPLEMENTED``, produce BLOCKED capsules, and never synthetic mocks.
This registry is not a plugin security sandbox.

Adapters
~~~~~~~~

* ``signal_generator``: samples 8..4096, rate .001..1e6 Hz, amplitude/noise sigma
  0..100, stress in clean/null/shuffle/noise/drift/missing/local/shared, missing
  probability [0,1]. A known pulse occupies ``[n//3, n//3+max(1,n//8))``; null has
  no event. Seeded Gaussian noise, amplified noise stress, shuffled samples,
  linear drift, explicit nullable missing samples, one local impulse, or common
  shared offset are local synthetic perturbations. Local/shared are explicitly
  time-local/time-shared single-channel stresses, not multichannel validation.
  Shared means within one signal, not cross-seed independence. Contract matches the example,
  with shape/rate/noise reflecting params.
* ``signal_baseline``: one generator parent; locked nonnegative ``rms_threshold``
  and ``maxabs_threshold`` <=1000. Computes RMS/maxabs over observed samples only,
  no imputation. All-missing fails. Output contract is the example's telemetry
  contract. TP/TN/FP/FN/errors are event-presence counts (one trial per node-seed),
  **not** localization or application accuracy. Shuffle therefore is not expected
  to change these order-insensitive baselines. Latency is explicitly
  NOT_IMPLEMENTED, not a successful null latency; event states distinguish
  DETECTED, MISSED, FALSE_ALARM and TRUE_NULL and missed events remain FN errors.
  Run SUCCESS denotes completed computation, never successful detection.
  Direct independent APIs ``adapters.rms_baseline(values, threshold, event_reference)``
  and ``adapters.maxabs_baseline(...)`` work with the other component removed.
  No coupling benefit is claimed. ``baseline.json`` executes this track alone.
* ``legacy_chain``: no parents. Params ``probe`` pulse/null, noise_sigma 0..10,
  frequency .001..1000 Hz, steps 1..2000. Imports unchanged ``FullLinkedSystem``;
  outer seed controls system/probe, but internal calibration 11 and injection
  1234 stay fixed: **exploratory regression, not independent sampling**.
  Its contract is ``data_type=record``, ``shape=[1]``, ``units=dimensionless``,
  ``coordinates=["run"]``, ``sample_rate=null``, ``normalization=legacy``,
  ``time=ticks``, ``noise=legacy``, ``evidence_origin=synthetic``.
  Legacy identifies source lineage, never real-world evidence origin. The adapter
  records calibrated tau and pattern counts before/after and fails if tau or any
  stored pattern changed. It explicitly reports NOT_MEASURED toy synthetic probes
  and simulated propulsion, not measured signals. ``legacy.json`` is offline-only.
  Reports every injection attempt and
  cost ``0.01*attempts``, not a rescued-acceptance claim. Legacy metrics are never
  included in the synthetic paired interval.

* ``oes32_residual``: independent no-parent numerical track, not a dimension
  transform or coupling claim. Params: explicit absolute ``source_directory``,
  exactly 32 finite reference/observed components, nonnegative tolerance.
  Output contract: float64[32], dimensionless, coordinates ["component index"],
  no sample rate, normalization none, static time, deterministic noise, synthetic
  evidence. Version pins revision fc0059bea09048baee0fc9c70d8de4d5da0d9493.
  Offline execution calls the local hash-checking subprocess adapter and never
  prepares/downloads code. Missing prepared files are BLOCKED, subprocess
  timeouts TIMEOUT, mismatching pins/output FAILED. A successfully computed
  failed residual criterion is valid SUCCESS computation with
  ``criterion_passed=false``, never a scientific success or stabilizer-QEC claim.
  Payloads record the pinned repository, revision, license and three file hashes;
  identity/verification lock these pins and recheck prepared sources.
  ``public.json`` names the caller's prepared external directory; edit that
  explicit path for another preparation location. Preparation remains separate::

      python public_residual_adapter.py prepare --directory scientific_orchestrator/prepared-public --allow-network
      OES32_PREPARED="$PWD/scientific_orchestrator/prepared-public" python -m unittest discover -s scientific_orchestrator -p 'test_*.py'

  Without explicitly prepared test sources, genuine upstream integration is
  visibly SKIPPED, not mocked or silently passed. Generic ``public_adapter``
  remains NOT_IMPLEMENTED.

Seed-level paired differences average all telemetry nodes/stresses within each
seed before constructing a bounded, distribution-free 95% Hoeffding interval
(range [-1,1]), assuming independent seed clusters. This is intentionally wide
in smoke runs. Missing/failed seeds make the comparison incomplete and disable
the practical-threshold support flag. Trial counts do not imply independent
replicates. No scientific aggregate score, zero-error certainty, or externally
validated application evidence is exported.

``signal_comparison.conditions`` separately reports every configured telemetry
condition, including null and failed/missing conditions, its generator and
locked baseline params, split, status counts and all planned seed outcomes.
Complete conditions get per-method Wilson 95% failure intervals and a one-sided
zero-error upper bound via local ``benchmark_analysis.failure_interval``, with one
Bernoulli event-presence trial per independent seed. Incomplete conditions get
no inferential intervals; pooled cross-condition counts remain descriptive.
Root Python source locking includes ``benchmark_analysis.py``. The available exact
sign-flip helper is deliberately not invoked: this protocol does not establish
exchangeability/symmetric differences under the null. No unregistered p-values,
Holm claims or independent-trial assumptions about correlated frames are made.

Artifacts, resume and replay
---------------------------

Canonical ASCII JSON objects are SHA256 content addressed in ``objects/``.
Original protocol seeds remain independent paired-unit IDs in ``seed``.
``execution_seed`` is a deterministic 64-bit SHA256 derivation from config hash,
node ID, partition name and original seed, with a versioned derivation domain.
It seeds adapter execution independently for each configured node/experiment.
Records, payloads, failure capsules and runtime metadata retain both seeds;
verification recomputes the derivation and summaries pair only original seeds.
Identity locks config, generated-dataset specification, adapter versions,
stdlib/runtime identity, and all root/package Python source hashes, including
new nested package Python modules. Dataset
hash identifies the generation specification, not a real-world data corpus;
generated samples are additionally covered by artifact hashes. Parent artifact
IDs are recorded. Runtime timestamp, measured wall/CPU and peak RSS metadata
are separate from deterministic objects.
Budget accounting is a separate nondeterministic content-addressed checkpoint
linked by ``manifest.accounting_id``. It covers runtime rows, cumulative CPU,
attempt counts and cumulative invocation wall (including orchestration through
each checkpoint). Resume debits the prior invocation-wall total, not only
worker durations. Verification checks the digest/runtime mirror, finite
nonnegative numeric values and exact attempted-run/seed correspondence.
Clearing or editing mutable manifest runtime rows cannot reset budgets while
passing verification. Hashes detect ordinary tampering, not authenticity:
coordinated replacement of every accounting object and reference cannot be
authenticated without an external trusted anchor. A hard interruption may lose
time after its last persisted checkpoint; no unmeasured time is claimed.

Writes use flush/fsync and same-directory atomic rename. A per-output exclusive
lock prevents concurrent runners. An interrupted writer can leave a lock: inspect
that process before removing it. Checkpoints permit verified resume; saved
failures/skips are not silently retried, and budget accounting is retained.
An interruption between export and manifest replacement can invalidate the
checkpoint; this implementation detects it, but does not repair it automatically.

``manifest.json`` lists SUCCESS/FAILED/TIMEOUT/BUDGET_EXCEEDED/BLOCKED/SKIPPED;
non-successes link replayable capsules containing config, node, seed, sources,
parents and error. Replay command::

    python -m scientific_orchestrator replay OUTPUT CAPSULE_ID --output FRESH_OUTPUT

This verifies the originating evidence and reruns its entire
locked DAG, preserving dependencies. It does not bypass limits or alter the
seed protocol. This is a replay request, not a promise to reproduce timing faults.

Exports are ``results.json``, ``results.csv``, and escaped static ``results.html``.
Verification detects object/export corruption, source/runtime/config/dataset
mismatches, inconsistent status/provenance and missing planned runs. Hashes
are **not signatures**: coordinated replacement of the entire local manifest
and artifacts cannot be authenticated. Runtime metadata is informational.
Adapter records and metadata are schema/type validated, including probability
bounds [0,1], integer counts, boolean fields, calibration invariants and explicit
unimplemented latency. Brier can be null only because legacy stock accepts do
not compute that metric; it is not a successful error-free score.
No upstream repository compatibility claim follows from this local manifest.
