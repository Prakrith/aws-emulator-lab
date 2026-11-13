# Project record

Tasks live in Beads. Keep Criteria and Acceptance. Delete any other section this project does not need.

## Objective

Find out which AWS Emulator services behave faithfully enough to learn each service's resource model and API terminology without spending on compute, and record where they fall short.

## Intended use

The owner uses the emulator on a laptop to learn how AWS services, resources and operations fit together, and to build small experiments before touching real AWS. This project produces the evidence for choosing which services to learn on it and which to learn elsewhere. It does not teach the services themselves.

## Requirements

- **R-1.** The emulator build is pinned and rebuildable, with telemetry off and the port bound to `127.0.0.1`.
- **R-2.** Each core service has a recorded sampled happy-path score from AWS's fidelity suite, run on the pinned build. The score says nothing about error handling or edge cases. VPC is covered by the suite's `ec2` label, so the 25 services map to 24 labels.
- **R-3.** Each service has a count of implemented and unimplemented operations taken from the emulator's source at the pinned commit.
- **R-4.** A core set of about 25 services passes a create, describe, list and delete smoke test, or has its failures recorded.
- **R-5.** The results are reviewed independently of the agent that produced them.

Core set: S3, DynamoDB, SQS, SNS, Lambda, Step Functions, EventBridge, Batch, ECS, ECR, EC2, VPC, IAM, STS, KMS, Secrets Manager, CloudWatch, CloudFormation, RDS, Kinesis, API Gateway, SSM, Glue, Athena, SageMaker.

## Criteria

Status is `open`, `satisfied`, `not satisfied`, `not applicable: <reason>`, or `waived: <reason>`. Use `satisfied` only when the method was carried out. Evidence holds pointers to the current evidence: a path, a commit, or a task ID. Replace it; do not append.

| ID | Type | Traces to | Method | Evidence | Status |
|---|---|---|---|---|---|
| VER-1 | Verification | R-1 | Rebuild the image from the recorded Dockerfile in a clean Docker context. Compare `aws-emulator -v` with the pinned version. Confirm the startup line reports telemetry disabled and that `docker port` shows only `127.0.0.1`. | `Dockerfile`, `bin/`, task aws-emulator-lab-de5 notes | `satisfied` |
| VER-2 | Verification | R-2 | Run AWS's `fidelity-tests-runner` against the pinned build on up to 40 happy-path tests per core label, each on a fresh emulator, and summarize scores by service. Record the runner version, the selection command, the tests excluded for missing tools, and the sample size per service. | `results/ver2-20261113T003946Z/`, `scripts/select_tests.py`, task aws-emulator-lab-jfs notes | `satisfied` |
| VER-3 | Verification | R-3 | For each service crate at the pinned commit, count operations in the Smithy model and those marked `SCAFFOLDED, NOT IMPLEMENTED:` in the source. Record the command and the counts. | `scripts/count_ops.py`, `results/ver3-*`, task aws-emulator-lab-d1w notes | `satisfied` |
| VER-4 | Verification | R-4 | Run the smoke-test harness for each core service on a fresh emulator. Record each operation as works, 501, or error. | `scripts/smoke.py`, `results/ver4-20261113T102029Z/`, task aws-emulator-lab-ffc notes | `satisfied` |
| VER-5 | Verification | R-5 | A reviewer that is not Claude Code reads the project record, results and harness read-only and reports findings. Record the findings and what was done about each. | task aws-emulator-lab-8pj notes | `satisfied` |
| VAL-1 | Validation | Intended use | The owner reads the results table and ranked list and judges whether they say which services to learn on the emulator. | Owner judged 2026-11-13 that the ranking serves as a no-spend first step for learning operations, before choosing whether to deploy low-cost infrastructure on real AWS. Task aws-emulator-lab-73v notes | `satisfied` |

## Reproducible results

For each result that requires reproducibility, state the commit, command, inputs, environment, and limitations.

Not yet produced. VER-1, VER-2, VER-3 and VER-4 each need a recorded commit, command, emulator version and environment, written to a new location on every rerun. A rerun that matches supports reproducibility. It does not show that the emulator matches AWS.

## Decisions

State what holds now. Delete a superseded decision. Record a decision only if it is hard to reverse or would surprise a later reader.

- The emulator runs in Docker through Colima on macOS, because it runs natively only on Linux.
- The pin is v1.0.338 (commit `32b3cf3`), fixed by SHA-256 of the package and the signing key in the Dockerfile. The vendor's `latest` URL serves only the newest build, so a rebuild fails once a newer version is published. v1.0.336, used for the earlier vetting, is not rebuildable.
- Telemetry stays off, and real AWS credentials and `AWS_PROFILE` are cleared before the CLI is pointed at the emulator.
- Results are specific to the pinned version. The emulator releases several times a day.

## Unresolved items

Status is `open`, `closed`, `deferred: <reason>`, or `accepted` as a limitation.

| ID | Item | Status |
|---|---|---|
| U-1 | A gap titled "Lambda Invoke refuses every real invocation with NotImplemented" is filed. On v1.0.338, invoking one python3.12 function returned the expected payload. Other runtimes were not tried. | `closed` |
| U-2 | Batch jobs fail with "This emulator does not run containers". Observed 2026-11-12 on v1.0.336, not yet rechecked on the pinned v1.0.338. | `accepted` |
| U-3 | The emulator does not evaluate IAM, bucket or key policies, so results say nothing about authorization. | `accepted` |
| U-4 | `fidelity-tests-runner` needs `uv`, which was installed with Homebrew. 175 tests need `cdk`, `kubectl` or `ffmpeg`, which are absent. | `closed` |
| U-5 | Sampling the container's sockets every 0.25 s during the smoke run showed no outbound connection with telemetry off. Shorter connections could be missed. | `closed` |
| U-6 | After `docker restart`, the bucket, queue and table created before it were gone. | `closed` |

## Acceptance

Accepted commit: none
