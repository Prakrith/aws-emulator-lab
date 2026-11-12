# AWS Emulator lab

Runs AWS Emulator in Docker on an ARM64 Mac (Colima) to check which services behave faithfully. See `PROJECT.md` for the objective and criteria.

## Prerequisites

Docker with a running daemon (for example `colima start`) and the AWS CLI v2. The emulator runs natively only on Linux, so macOS needs the container.

## Build

```sh
bin/build --no-cache
```

This builds `aws-emulator:pinned` from `Dockerfile` and prints `aws-emulator -v`. The build fails unless the RPM and the signing key match the SHA-256 values in the Dockerfile. The package URL is the vendor's `LTS/latest` path, so once the vendor publishes a newer version the build fails by design; the pinned RPM can then only be recovered from an existing image.

## Run

```sh
bin/start
. bin/env.sh
aws sts get-caller-identity
```

`bin/start` runs the container with telemetry off (`EMULATOR_TELEMETRY=off`), the port published on `127.0.0.1` only, and a 2 GB memory limit. The emulator serves HTTPS with its own CA and per-run credentials. `bin/env.sh` clears every `AWS_*` variable, copies the CA and credentials into `run/` (not committed), and points the CLI at the emulator. Source it from the repository root.

Stop with `docker rm -f aws-emulator`. Set `EMULATOR_CONTAINER` or `EMULATOR_PORT` to run a second instance.

## Checks

```sh
docker port aws-emulator          # only 127.0.0.1
docker logs aws-emulator | head   # startup line reports telemetry disabled
curl -sk https://127.0.0.1:9297/__admin/health   # ok
```

The emulator does not evaluate IAM, bucket or key policies. Results say nothing about authorization.
