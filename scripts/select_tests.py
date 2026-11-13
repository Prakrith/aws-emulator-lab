#!/usr/bin/env python3
"""Select the sampled happy-path tests for the core service labels.

usage: python3 -I scripts/select_tests.py <suite-dir> <per-label> <tests-out> <excluded-out>

Takes `axis:happy-path` tests of each core label whose required tools are present, drops those
that need docker, git, npm or ssh-keygen on the host, and picks <per-label> of them at even
spacing in sorted path order. <excluded-out> lists happy-path core tests dropped, with the reason.
"""
import json, subprocess, sys

CORE = ("s3 dynamodb sqs sns lambda stepfunctions events batch ecs ecr ec2 iam sts kms "
        "secretsmanager cloudwatch cloudformation rds kinesis apigateway ssm glue athena "
        "sagemaker").split()
HOST_SIDE = {"docker", "git", "npm", "ssh-keygen"}


def requirements(suite, paths):
    out = {}
    for i in range(0, len(paths), 500):
        p = subprocess.run(["uv", "run", "--no-sync", "fidelity-tests-runner", "requirements",
                            "--json", *paths[i:i + 500]], cwd=suite, capture_output=True, text=True)
        for r in json.loads(p.stdout):
            out[r["file"]] = r
    return out


def main(suite, per_label, tests_out, excluded_out):
    n = int(per_label)
    rows = [json.loads(l) for l in open(f"{suite}/manifest.jsonl")]
    rows = [r for r in rows if r["service"] in CORE and "axis:happy-path" in r["labels"]]
    req = requirements(suite, sorted(r["path"] for r in rows))
    picked, excluded = [], []
    for label in CORE:
        ok = []
        for path in sorted(r["path"] for r in rows if r["service"] == label):
            q = req[path]
            why = ([f"missing {t}" for t in q["missing_tools"]]
                   + [f"missing python package {t}" for t in q["missing_python_packages"]]
                   + [f"host-side {t}" for t in q["tools"] if t in HOST_SIDE])
            if why:
                excluded.append(f"{path}\t{'; '.join(why)}")
            else:
                ok.append(path)
        k = min(n, len(ok))
        picked += [ok[(len(ok) * j) // k + len(ok) // (2 * k)] for j in range(k)]
    open(tests_out, "w").write("\n".join(picked) + "\n")
    open(excluded_out, "w").write("\n".join(excluded) + ("\n" if excluded else ""))
    print(f"{len(picked)} selected, {len(excluded)} excluded")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])
