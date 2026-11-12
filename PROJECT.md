# Project record

Tasks live in Beads. Keep Criteria and Acceptance. Delete any other section this project does not need.

## Objective

Find out which AWS Emulator services behave faithfully enough to learn each service's resource model and API terminology without spending on compute, and record where they fall short.

## Intended use

The owner uses the emulator on a laptop to learn how AWS services, resources and operations fit together, and to build small experiments before touching real AWS. This project produces the evidence for choosing which services to learn on it and which to learn elsewhere. It does not teach the services themselves.

## Requirements

- **R-1.** The emulator build is pinned and rebuildable, with telemetry off and the port bound to `127.0.0.1`.
- **R-2.** Every service that AWS's fidelity suite covers has a recorded per-service score from a run on the pinned build.
- **R-3.** Each service has a count of implemented and unimplemented operations taken from the emulator's source at the pinned commit.
- **R-4.** A core set of about 25 services passes a create, describe, list and delete smoke test, or has its failures recorded.
- **R-5.** The results are reviewed independently of the agent that produced them.

Core set: S3, DynamoDB, SQS, SNS, Lambda, Step Functions, EventBridge, Batch, ECS, ECR, EC2, VPC, IAM, STS, KMS, Secrets Manager, CloudWatch, CloudFormation, RDS, Kinesis, API Gateway, SSM, Glue, Athena, SageMaker.

## Criteria

Status is `open`, `satisfied`, `not satisfied`, `not applicable: <reason>`, or `waived: <reason>`. Use `satisfied` only when the method was carried out. Evidence holds pointers to the current evidence: a path, a commit, or a task ID. Replace it; do not append.

| ID | Type | Traces to | Method | Evidence | Status |
|---|---|---|---|---|---|
| VER-1 | Verification | R-1 | Rebuild the image from the recorded Dockerfile in a clean Docker context. Compare `aws-emulator -v` with the pinned version. Confirm the startup line reports telemetry disabled and that `docker port` shows only `127.0.0.1`. | `Dockerfile`, `bin/`, task aws-emulator-lab-de5 notes | `satisfied` |
| VER-2 | Verification | R-2 | Run AWS's `fidelity-tests-runner` against the pinned build and summarize scores by service. Record the runner version and every service it does not cover. | | `open` |
| VER-3 | Verification | R-3 | For each service crate at the pinned commit, count operations in the Smithy model and those marked `SCAFFOLDED, NOT IMPLEMENTED:` in the source. Record the command and the counts. | `scripts/count_ops.py`, `results/ver3-*`, task aws-emulator-lab-d1w notes | `satisfied` |
| VER-4 | Verification | R-4 | Run the smoke-test harness for each core service on a fresh emulator. Record each operation as works, 501, or error. | | `open` |
| VER-5 | Verification | R-5 | A reviewer that is not Claude Code reads the project record, results and harness read-only and reports findings. Record the findings and what was done about each. | | `open` |
| VAL-1 | Validation | Intended use | The owner reads the results table and ranked list and judges whether they say which services to learn on the emulator. | | `open` |

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
| U-1 | A gap titled "Lambda Invoke refuses every real invocation with NotImplemented" is filed. Current status is unknown. | `open` |
| U-2 | Batch jobs fail with "This emulator does not run containers". Observed 2026-11-12 on v1.0.336, not yet rechecked on the pinned v1.0.338. | `accepted` |
| U-3 | The emulator does not evaluate IAM, bucket or key policies, so results say nothing about authorization. | `accepted` |
| U-4 | It is unknown whether `fidelity-tests-runner` installs and runs on this machine without extra tooling. | `open` |
| U-5 | Outbound network connections made by the emulator were not checked. | `open` |
| U-6 | State clearing on restart was not tested. | `open` |

## Acceptance

Accepted commit: none
