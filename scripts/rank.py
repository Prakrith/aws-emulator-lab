"""Combine fidelity, operation-count and smoke results into one table and a ranked list.

Usage: rank.py <fidelity-by-service.csv> <ver3-counts.csv> <ver4-results.csv> <new-out-dir>
"""
import csv, sys, os, collections

fid_csv, ops_csv, smoke_csv, out = sys.argv[1:5]
os.makedirs(out)

# Core service -> (fidelity label, ops crate, smoke groups). VPC shares the ec2 label and crate.
CORE = [
    ("s3", "s3", "com-amazonaws-s3-amazons3", ["s3"]),
    ("dynamodb", "dynamodb", "com-amazonaws-dynamodb-dynamodb-20120810", ["dynamodb"]),
    ("sqs", "sqs", "com-amazonaws-sqs-amazonsqs", ["sqs"]),
    ("sns", "sns", "com-amazonaws-sns-amazonsimplenotificationservice", ["sns"]),
    ("lambda", "lambda", "com-amazonaws-lambda-awsgirapiservice", ["lambda"]),
    ("stepfunctions", "stepfunctions", "com-amazonaws-sfn-awsstepfunctions", ["stepfunctions"]),
    ("eventbridge", "events", "com-amazonaws-eventbridge-awsevents", ["events"]),
    ("batch", "batch", "com-amazonaws-batch-awsbatchv20160810", ["batch"]),
    ("ecs", "ecs", "com-amazonaws-ecs-amazonec2containerservicev20141113", ["ecs"]),
    ("ecr", "ecr", "com-amazonaws-ecr-amazonec2containerregistry-v20150921", ["ecr"]),
    ("ec2", "ec2", "com-amazonaws-ec2-amazonec2", ["ec2"]),
    ("vpc", "ec2", "com-amazonaws-ec2-amazonec2", ["vpc"]),
    ("iam", "iam", "com-amazonaws-iam-awsidentitymanagementv20100508", ["iam"]),
    ("sts", "sts", "com-amazonaws-sts-awssecuritytokenservicev20110615", ["sts"]),
    ("kms", "kms", "com-amazonaws-kms-trentservice", ["kms"]),
    ("secretsmanager", "secretsmanager", "com-amazonaws-secretsmanager-secretsmanager", ["secretsmanager"]),
    ("cloudwatch", "cloudwatch", "com-amazonaws-cloudwatch-graniteserviceversion20100801", ["cloudwatch"]),
    ("cloudformation", "cloudformation", "com-amazonaws-cloudformation-cloudformation", ["cloudformation"]),
    ("rds", "rds", "com-amazonaws-rds-amazonrdsv19", ["rds"]),
    ("kinesis", "kinesis", "com-amazonaws-kinesis-kinesis-20131202", ["kinesis"]),
    ("apigateway", "apigateway", "com-amazonaws-apigateway-backplanecontrolservice", ["apigateway"]),
    ("ssm", "ssm", "com-amazonaws-ssm-amazonssm", ["ssm"]),
    ("glue", "glue", "com-amazonaws-glue-awsglue", ["glue"]),
    ("athena", "athena", "com-amazonaws-athena-amazonathena", ["athena"]),
    ("sagemaker", "sagemaker", "com-amazonaws-sagemaker-sagemaker", ["sagemaker"]),
]

fid = {r["service"]: r for r in csv.DictReader(open(fid_csv))}
ops = {r["service"]: r for r in csv.DictReader(open(ops_csv))}
smoke = collections.defaultdict(lambda: collections.Counter())
for r in csv.DictReader(open(smoke_csv)):
    smoke[r["service"]][r["status"]] += 1

rows = []
for name, label, crate, groups in CORE:
    f, o = fid[label], ops[crate]
    total, impl = int(o["total"]), int(o["implemented"])
    s = sum((smoke[g] for g in groups), collections.Counter())
    calls = sum(s.values())
    rate, share = float(f["pass_rate"]), impl / total
    if rate >= 0.85 and share >= 0.85:
        tier = "A"
    elif rate < 0.5 or share < 0.6:
        tier = "C"
    else:
        tier = "B"
    why = []
    if int(f["not_implemented"]):
        why.append(f"{f['not_implemented']} of {f['scored']} sampled tests hit 501")
    if int(f["timeout"]):
        why.append(f"{f['timeout']} timed out")
    if int(f["target_error"]):
        why.append(f"{f['target_error']} target errors")
    rows.append(dict(
        service=name, tier=tier, sampled=f["scored"], passed=f["passed"], pass_rate=f["pass_rate"],
        ops_total=total, ops_implemented=impl, ops_share=f"{share:.2f}",
        smoke_works=s["works"], smoke_501=s["501"], smoke_error=s["error"], smoke_calls=calls,
        notes="; ".join(why)))

rows.sort(key=lambda r: (r["tier"], -float(r["pass_rate"]), -float(r["ops_share"])))
with open(os.path.join(out, "table.csv"), "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)

with open(os.path.join(out, "ranking.md"), "w") as fh:
    fh.write("| # | Tier | Service | Sampled pass | Ops implemented | Smoke | Notes |\n|---|---|---|---|---|---|---|\n")
    for i, r in enumerate(rows, 1):
        fh.write(f"| {i} | {r['tier']} | {r['service']} | {r['passed']}/{r['sampled']} ({float(r['pass_rate']):.0%}) | "
                 f"{r['ops_implemented']}/{r['ops_total']} ({float(r['ops_share']):.0%}) | "
                 f"{r['smoke_works']}/{r['smoke_calls']} | {r['notes']} |\n")
print(open(os.path.join(out, "ranking.md")).read())
