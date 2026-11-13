#!/usr/bin/env python3
"""Smoke-test the core services on a fresh pinned emulator.

usage: python3 -I scripts/smoke.py <new-output-dir> [--only svc1,svc2] [--port 9500]

Starts a fresh container (telemetry off, 127.0.0.1 only, 2 GB), then for each core service runs
a create, describe, list and delete sequence with the AWS CLI. Each call is recorded as
  works    exit code 0 (Lambda Invoke also needs the expected payload)
  501      the emulator answered NotImplemented
  error    any other failure, with the message
  skipped  a value an earlier step should have produced is missing
While it runs, the container's TCP and UDP sockets are sampled for outbound connections (U-5).
After the sequences it creates marker resources, restarts the container, and lists them (U-6).
Writes results.csv, calls.jsonl, outbound.txt, restart.txt and meta.txt to the output directory.
"""
import csv, json, os, re, subprocess, sys, tempfile, threading, time, zipfile
import ssl, urllib.request

IMAGE = "aws-emulator:pinned"
ROLE = "arn:aws:iam::000000000000:role/smoke"
LAMBDA_SRC = "def handler(event, context):\n    return {'echo': event.get('x'), 'ok': True}\n"
SFN_DEF = json.dumps({"StartAt": "P", "States": {"P": {"Type": "Pass", "Result": "hi", "End": True}}})
CFN_TEMPLATE = json.dumps({"Resources": {"Q": {"Type": "AWS::SQS::Queue"}}})


PLACEHOLDERS = ("bodyfile outfile zipfile item lpayload qurl topic sm exec jd job inst vpc subnet sg "
                "key ctfile api qid").split()
PH_RE = re.compile(r"\{(" + "|".join(PLACEHOLDERS) + r")\}")


def fill(arg, ctx):
    """Substitute {name} placeholders only; JSON braces in arguments stay as they are."""
    return PH_RE.sub(lambda m: ctx[m.group(1)], arg)


def save_ciphertext(out, ctx):
    import base64
    path = os.path.join(os.path.dirname(ctx["outfile"]), "ct.bin")
    open(path, "wb").write(base64.b64decode(out["CiphertextBlob"]))
    return {"ctfile": f"fileb://{path}"}


# (service, step, aws args with {ctx} placeholders, extractor -> ctx key, seconds to wait after)
def S(svc, step, args, ext=None, wait=0):
    return {"svc": svc, "step": step, "args": args.split() if isinstance(args, str) else args,
            "ext": ext, "wait": wait}


def steps():
    n = "smoke"
    return [
        S("s3", "create-bucket", f"s3api create-bucket --bucket {n}-bkt"),
        S("s3", "head-bucket", f"s3api head-bucket --bucket {n}-bkt"),
        S("s3", "list-buckets", "s3api list-buckets"),
        S("s3", "put-object", f"s3api put-object --bucket {n}-bkt --key k --body {{bodyfile}}"),
        S("s3", "list-objects-v2", f"s3api list-objects-v2 --bucket {n}-bkt"),
        S("s3", "get-object", f"s3api get-object --bucket {n}-bkt --key k {{outfile}}"),
        S("s3", "delete-object", f"s3api delete-object --bucket {n}-bkt --key k"),
        S("s3", "delete-bucket", f"s3api delete-bucket --bucket {n}-bkt"),

        S("dynamodb", "create-table", f"dynamodb create-table --table-name {n}-t --attribute-definitions AttributeName=id,AttributeType=S --key-schema AttributeName=id,KeyType=HASH --billing-mode PAY_PER_REQUEST"),
        S("dynamodb", "describe-table", f"dynamodb describe-table --table-name {n}-t"),
        S("dynamodb", "list-tables", "dynamodb list-tables"),
        S("dynamodb", "put-item", f"dynamodb put-item --table-name {n}-t --item {{item}}"),
        S("dynamodb", "get-item", f"dynamodb get-item --table-name {n}-t --key {{item}}"),
        S("dynamodb", "delete-table", f"dynamodb delete-table --table-name {n}-t"),

        S("sqs", "create-queue", f"sqs create-queue --queue-name {n}-q", lambda o, c: {"qurl": o["QueueUrl"]}),
        S("sqs", "get-queue-attributes", "sqs get-queue-attributes --queue-url {qurl} --attribute-names All"),
        S("sqs", "list-queues", "sqs list-queues"),
        S("sqs", "send-message", "sqs send-message --queue-url {qurl} --message-body hello"),
        S("sqs", "receive-message", "sqs receive-message --queue-url {qurl}"),
        S("sqs", "delete-queue", "sqs delete-queue --queue-url {qurl}"),

        S("sns", "create-topic", f"sns create-topic --name {n}-topic", lambda o, c: {"topic": o["TopicArn"]}),
        S("sns", "get-topic-attributes", "sns get-topic-attributes --topic-arn {topic}"),
        S("sns", "list-topics", "sns list-topics"),
        S("sns", "publish", "sns publish --topic-arn {topic} --message hello"),
        S("sns", "delete-topic", "sns delete-topic --topic-arn {topic}"),

        S("lambda", "create-function", f"lambda create-function --function-name {n}-fn --runtime python3.12 --handler h.handler --role {ROLE} --zip-file fileb://{{zipfile}}"),
        S("lambda", "get-function", f"lambda get-function --function-name {n}-fn"),
        S("lambda", "list-functions", "lambda list-functions"),
        S("lambda", "invoke", f"lambda invoke --function-name {n}-fn --cli-binary-format raw-in-base64-out --payload {{lpayload}} {{outfile}}"),
        S("lambda", "delete-function", f"lambda delete-function --function-name {n}-fn"),

        S("stepfunctions", "create-state-machine", ["stepfunctions", "create-state-machine", "--name", f"{n}-sm", "--definition", SFN_DEF, "--role-arn", ROLE], lambda o, c: {"sm": o["stateMachineArn"]}),
        S("stepfunctions", "describe-state-machine", "stepfunctions describe-state-machine --state-machine-arn {sm}"),
        S("stepfunctions", "list-state-machines", "stepfunctions list-state-machines"),
        S("stepfunctions", "start-execution", "stepfunctions start-execution --state-machine-arn {sm}", lambda o, c: {"exec": o["executionArn"]}, wait=1),
        S("stepfunctions", "describe-execution", "stepfunctions describe-execution --execution-arn {exec}"),
        S("stepfunctions", "delete-state-machine", "stepfunctions delete-state-machine --state-machine-arn {sm}"),

        S("events", "create-event-bus", f"events create-event-bus --name {n}-bus"),
        S("events", "describe-event-bus", f"events describe-event-bus --name {n}-bus"),
        S("events", "list-event-buses", "events list-event-buses"),
        S("events", "put-rule", ["events", "put-rule", "--name", f"{n}-rule", "--event-bus-name", f"{n}-bus", "--event-pattern", '{"source":["smoke"]}']),
        S("events", "list-rules", f"events list-rules --event-bus-name {n}-bus"),
        S("events", "put-events", ["events", "put-events", "--entries", f'[{{"Source":"smoke","DetailType":"t","Detail":"{{}}","EventBusName":"{n}-bus"}}]']),
        S("events", "delete-rule", f"events delete-rule --name {n}-rule --event-bus-name {n}-bus"),
        S("events", "delete-event-bus", f"events delete-event-bus --name {n}-bus"),

        S("batch", "create-compute-environment", f"batch create-compute-environment --compute-environment-name {n}-ce --type UNMANAGED"),
        S("batch", "describe-compute-environments", f"batch describe-compute-environments --compute-environments {n}-ce"),
        S("batch", "create-job-queue", f"batch create-job-queue --job-queue-name {n}-jq --priority 1 --compute-environment-order order=1,computeEnvironment={n}-ce"),
        S("batch", "describe-job-queues", f"batch describe-job-queues --job-queues {n}-jq"),
        S("batch", "register-job-definition", ["batch", "register-job-definition", "--job-definition-name", f"{n}-jd", "--type", "container", "--container-properties", '{"image":"busybox","vcpus":1,"memory":128,"command":["true"]}'], lambda o, c: {"jd": o["jobDefinitionArn"]}),
        S("batch", "submit-job", f"batch submit-job --job-name {n}-job --job-queue {n}-jq --job-definition {{jd}}", lambda o, c: {"job": o["jobId"]}, wait=1),
        S("batch", "describe-jobs", "batch describe-jobs --jobs {job}"),
        S("batch", "list-jobs", f"batch list-jobs --job-queue {n}-jq"),
        S("batch", "terminate-job", "batch terminate-job --job-id {job} --reason smoke"),
        S("batch", "deregister-job-definition", "batch deregister-job-definition --job-definition {jd}"),
        S("batch", "update-job-queue-disable", f"batch update-job-queue --job-queue {n}-jq --state DISABLED"),
        S("batch", "delete-job-queue", f"batch delete-job-queue --job-queue {n}-jq", wait=1),
        S("batch", "update-compute-environment-disable", f"batch update-compute-environment --compute-environment {n}-ce --state DISABLED"),
        S("batch", "delete-compute-environment", f"batch delete-compute-environment --compute-environment {n}-ce"),

        S("ecs", "create-cluster", f"ecs create-cluster --cluster-name {n}-cl"),
        S("ecs", "describe-clusters", f"ecs describe-clusters --clusters {n}-cl"),
        S("ecs", "list-clusters", "ecs list-clusters"),
        S("ecs", "register-task-definition", ["ecs", "register-task-definition", "--family", f"{n}-td", "--container-definitions", '[{"name":"c","image":"busybox","memory":64}]']),
        S("ecs", "list-task-definitions", "ecs list-task-definitions"),
        S("ecs", "deregister-task-definition", f"ecs deregister-task-definition --task-definition {n}-td:1"),
        S("ecs", "delete-cluster", f"ecs delete-cluster --cluster {n}-cl"),

        S("ecr", "create-repository", f"ecr create-repository --repository-name {n}-repo"),
        S("ecr", "describe-repositories", f"ecr describe-repositories --repository-names {n}-repo"),
        S("ecr", "list-images", f"ecr list-images --repository-name {n}-repo"),
        S("ecr", "get-authorization-token", "ecr get-authorization-token"),
        S("ecr", "delete-repository", f"ecr delete-repository --repository-name {n}-repo --force"),

        S("ec2", "describe-instances", "ec2 describe-instances"),
        S("ec2", "run-instances", "ec2 run-instances --image-id ami-0123456789abcdef0 --instance-type t2.micro --count 1", lambda o, c: {"inst": o["Instances"][0]["InstanceId"]}),
        S("ec2", "describe-instances-by-id", "ec2 describe-instances --instance-ids {inst}"),
        S("ec2", "terminate-instances", "ec2 terminate-instances --instance-ids {inst}"),
        S("vpc", "create-vpc", "ec2 create-vpc --cidr-block 10.0.0.0/16", lambda o, c: {"vpc": o["Vpc"]["VpcId"]}),
        S("vpc", "describe-vpcs", "ec2 describe-vpcs --vpc-ids {vpc}"),
        S("vpc", "create-subnet", "ec2 create-subnet --vpc-id {vpc} --cidr-block 10.0.1.0/24", lambda o, c: {"subnet": o["Subnet"]["SubnetId"]}),
        S("vpc", "describe-subnets", "ec2 describe-subnets --subnet-ids {subnet}"),
        S("vpc", "create-security-group", f"ec2 create-security-group --group-name {n}-sg --description smoke --vpc-id {{vpc}}", lambda o, c: {"sg": o["GroupId"]}),
        S("vpc", "describe-security-groups", "ec2 describe-security-groups --group-ids {sg}"),
        S("vpc", "delete-security-group", "ec2 delete-security-group --group-id {sg}"),
        S("vpc", "delete-subnet", "ec2 delete-subnet --subnet-id {subnet}"),
        S("vpc", "delete-vpc", "ec2 delete-vpc --vpc-id {vpc}"),

        S("iam", "create-user", f"iam create-user --user-name {n}-user"),
        S("iam", "get-user", f"iam get-user --user-name {n}-user"),
        S("iam", "list-users", "iam list-users"),
        S("iam", "create-role", ["iam", "create-role", "--role-name", f"{n}-role", "--assume-role-policy-document", '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}']),
        S("iam", "get-role", f"iam get-role --role-name {n}-role"),
        S("iam", "list-roles", "iam list-roles"),
        S("iam", "delete-role", f"iam delete-role --role-name {n}-role"),
        S("iam", "delete-user", f"iam delete-user --user-name {n}-user"),

        S("sts", "get-caller-identity", "sts get-caller-identity"),
        S("sts", "create-role-to-assume", ["iam", "create-role", "--role-name", f"{n}-sts-role", "--assume-role-policy-document", '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"AWS":"arn:aws:iam::000000000000:root"},"Action":"sts:AssumeRole"}]}']),
        S("sts", "assume-role", f"sts assume-role --role-arn arn:aws:iam::000000000000:role/{n}-sts-role --role-session-name smoke"),
        S("sts", "get-session-token", "sts get-session-token"),
        S("sts", "delete-role-assumed", f"iam delete-role --role-name {n}-sts-role"),

        S("kms", "create-key", "kms create-key", lambda o, c: {"key": o["KeyMetadata"]["KeyId"]}),
        S("kms", "describe-key", "kms describe-key --key-id {key}"),
        S("kms", "list-keys", "kms list-keys"),
        S("kms", "encrypt", "kms encrypt --key-id {key} --plaintext aGVsbG8=", save_ciphertext),
        S("kms", "decrypt", "kms decrypt --ciphertext-blob {ctfile}"),
        S("kms", "schedule-key-deletion", "kms schedule-key-deletion --key-id {key} --pending-window-in-days 7"),

        S("secretsmanager", "create-secret", f"secretsmanager create-secret --name {n}-secret --secret-string s3cret"),
        S("secretsmanager", "describe-secret", f"secretsmanager describe-secret --secret-id {n}-secret"),
        S("secretsmanager", "list-secrets", "secretsmanager list-secrets"),
        S("secretsmanager", "get-secret-value", f"secretsmanager get-secret-value --secret-id {n}-secret"),
        S("secretsmanager", "delete-secret", f"secretsmanager delete-secret --secret-id {n}-secret --force-delete-without-recovery"),

        S("cloudwatch", "put-metric-data", "cloudwatch put-metric-data --namespace Smoke --metric-name M --value 1"),
        S("cloudwatch", "list-metrics", "cloudwatch list-metrics --namespace Smoke"),
        S("cloudwatch", "put-metric-alarm", f"cloudwatch put-metric-alarm --alarm-name {n}-alarm --namespace Smoke --metric-name M --statistic Sum --period 60 --evaluation-periods 1 --threshold 1 --comparison-operator GreaterThanThreshold"),
        S("cloudwatch", "describe-alarms", f"cloudwatch describe-alarms --alarm-names {n}-alarm"),
        S("cloudwatch", "delete-alarms", f"cloudwatch delete-alarms --alarm-names {n}-alarm"),

        S("cloudformation", "create-stack", ["cloudformation", "create-stack", "--stack-name", f"{n}-stack", "--template-body", CFN_TEMPLATE], wait=2),
        S("cloudformation", "describe-stacks", f"cloudformation describe-stacks --stack-name {n}-stack"),
        S("cloudformation", "list-stacks", "cloudformation list-stacks"),
        S("cloudformation", "list-stack-resources", f"cloudformation list-stack-resources --stack-name {n}-stack"),
        S("cloudformation", "delete-stack", f"cloudformation delete-stack --stack-name {n}-stack"),

        S("rds", "create-db-instance", f"rds create-db-instance --db-instance-identifier {n}-db --db-instance-class db.t3.micro --engine mysql --master-username admin --master-user-password password123 --allocated-storage 20"),
        S("rds", "describe-db-instances", f"rds describe-db-instances --db-instance-identifier {n}-db"),
        S("rds", "describe-db-engine-versions", "rds describe-db-engine-versions --engine mysql --max-items 1"),
        S("rds", "delete-db-instance", f"rds delete-db-instance --db-instance-identifier {n}-db --skip-final-snapshot"),

        S("kinesis", "create-stream", f"kinesis create-stream --stream-name {n}-stream --shard-count 1", wait=1),
        S("kinesis", "describe-stream", f"kinesis describe-stream --stream-name {n}-stream"),
        S("kinesis", "list-streams", "kinesis list-streams"),
        S("kinesis", "put-record", f"kinesis put-record --stream-name {n}-stream --partition-key p --data aGVsbG8="),
        S("kinesis", "delete-stream", f"kinesis delete-stream --stream-name {n}-stream"),

        S("apigateway", "create-rest-api", f"apigateway create-rest-api --name {n}-api", lambda o, c: {"api": o["id"]}),
        S("apigateway", "get-rest-api", "apigateway get-rest-api --rest-api-id {api}"),
        S("apigateway", "get-rest-apis", "apigateway get-rest-apis"),
        S("apigateway", "get-resources", "apigateway get-resources --rest-api-id {api}"),
        S("apigateway", "delete-rest-api", "apigateway delete-rest-api --rest-api-id {api}"),

        S("ssm", "put-parameter", f"ssm put-parameter --name /{n}/p --value v --type String"),
        S("ssm", "get-parameter", f"ssm get-parameter --name /{n}/p"),
        S("ssm", "describe-parameters", "ssm describe-parameters"),
        S("ssm", "delete-parameter", f"ssm delete-parameter --name /{n}/p"),

        S("glue", "create-database", ["glue", "create-database", "--database-input", f'{{"Name":"{n}_db"}}']),
        S("glue", "get-database", f"glue get-database --name {n}_db"),
        S("glue", "get-databases", "glue get-databases"),
        S("glue", "create-table", ["glue", "create-table", "--database-name", f"{n}_db", "--table-input", f'{{"Name":"{n}_tbl"}}']),
        S("glue", "get-tables", f"glue get-tables --database-name {n}_db"),
        S("glue", "delete-table", f"glue delete-table --database-name {n}_db --name {n}_tbl"),
        S("glue", "delete-database", f"glue delete-database --name {n}_db"),

        S("athena", "create-work-group", f"athena create-work-group --name {n}-wg"),
        S("athena", "get-work-group", f"athena get-work-group --work-group {n}-wg"),
        S("athena", "list-work-groups", "athena list-work-groups"),
        S("athena", "start-query-execution", ["athena", "start-query-execution", "--query-string", "SELECT 1", "--work-group", f"{n}-wg", "--result-configuration", f"OutputLocation=s3://{n}-out/"], lambda o, c: {"qid": o["QueryExecutionId"]}, wait=1),
        S("athena", "get-query-execution", "athena get-query-execution --query-execution-id {qid}"),
        S("athena", "delete-work-group", f"athena delete-work-group --work-group {n}-wg --recursive-delete-option"),

        S("sagemaker", "create-model", ["sagemaker", "create-model", "--model-name", f"{n}-model", "--execution-role-arn", ROLE, "--primary-container", '{"Image":"123456789012.dkr.ecr.us-east-1.amazonaws.com/x:latest"}']),
        S("sagemaker", "describe-model", f"sagemaker describe-model --model-name {n}-model"),
        S("sagemaker", "list-models", "sagemaker list-models"),
        S("sagemaker", "delete-model", f"sagemaker delete-model --model-name {n}-model"),
    ]


class Emulator:
    def __init__(self, name, port, work):
        self.name, self.port, self.work = name, port, work

    def sh(self, *a, **k):
        return subprocess.run(a, capture_output=True, text=True, **k)

    def start(self):
        self.sh("docker", "rm", "-f", self.name)
        r = self.sh("docker", "run", "-d", "--name", self.name, "-e", "EMULATOR_TELEMETRY=off",
                    "-p", f"127.0.0.1:{self.port}:9297", "--memory", "2g", IMAGE)
        if r.returncode:
            sys.exit(r.stderr)
        self.wait()

    def wait(self):
        ctx = ssl._create_unverified_context()
        for _ in range(300):
            try:
                urllib.request.urlopen(f"https://127.0.0.1:{self.port}/__admin/health", context=ctx, timeout=1)
                break
            except Exception:
                time.sleep(0.1)
        else:
            sys.exit("emulator never became healthy")
        for f in ("ca.pem", "emulator_credentials"):
            r = self.sh("docker", "cp", f"{self.name}:/home/emulator/.aws/emulator/9297/{f}", self.work)
            if r.returncode:
                sys.exit(r.stderr)

    def env(self):
        e = {k: v for k, v in os.environ.items() if not k.startswith("AWS_")}
        e.update(AWS_ENDPOINT_URL=f"https://127.0.0.1:{self.port}", AWS_CA_BUNDLE=f"{self.work}/ca.pem",
                 AWS_SHARED_CREDENTIALS_FILE=f"{self.work}/emulator_credentials",
                 AWS_CONFIG_FILE="/dev/null", AWS_DEFAULT_REGION="us-east-1", AWS_PAGER="")
        return e

    def aws(self, args):
        t = time.time()
        p = subprocess.run(["aws", *args, "--output", "json"] if "--output" not in args else ["aws", *args],
                           capture_output=True, text=True, env=self.env(), timeout=90)
        return p, time.time() - t


def classify(p):
    if p.returncode == 0:
        return "works", ""
    err = " ".join(p.stderr.split())
    if "(NotImplemented)" in err or re.search(r"\b501\b", err):
        return "501", err[:300]
    return "error", err[:300]


def sample_outbound(name, stop, found):
    def parse_tcp(text, v6):
        for line in text.splitlines()[1:]:
            f = line.split()
            if len(f) < 4:
                continue
            lport = int(f[1].split(":")[1], 16)
            rem, rport = f[2].split(":")
            st = f[3]
            yield lport, rem, int(rport, 16), st
    def loop(r):
        return r.startswith("0100007F") or r == "00000000000000000000000001000000" or set(r) == {"0"}
    while not stop.is_set():
        for proto in ("tcp", "tcp6", "udp", "udp6"):
            p = subprocess.run(["docker", "exec", name, "cat", f"/proc/net/{proto}"], capture_output=True, text=True)
            for lport, rem, rport, st in parse_tcp(p.stdout, proto.endswith("6")):
                if lport == 9297 or loop(rem):
                    continue
                if proto.startswith("tcp") and st not in ("01", "02"):  # ESTABLISHED, SYN_SENT
                    continue
                found.add((proto, lport, rem, rport, st))
        stop.wait(0.25)


def main(out, only=None, port=9500):
    os.makedirs(out)
    work = tempfile.mkdtemp(prefix="smoke-")
    open(f"{work}/body.txt", "w").write("hello")
    with zipfile.ZipFile(f"{work}/fn.zip", "w") as z:
        z.writestr("h.py", LAMBDA_SRC)
    em = Emulator("aws-emulator-smoke", port, work)
    em.start()
    want = set(only.split(",")) if only else None
    ctx = {"bodyfile": f"{work}/body.txt", "outfile": f"{work}/out.bin", "zipfile": f"{work}/fn.zip",
           "item": '{"id":{"S":"1"}}', "lpayload": '{"x":42}'}
    stop, found = threading.Event(), set()
    th = threading.Thread(target=sample_outbound, args=(em.name, stop, found), daemon=True)
    th.start()
    rows = []
    with open(f"{out}/calls.jsonl", "w") as calls:
        for s in steps():
            if want and s["svc"] not in want:
                continue
            try:
                args = [fill(a, ctx) for a in s["args"]]
            except KeyError as e:
                rows.append((s["svc"], s["step"], "skipped", f"needs {e} from an earlier step", 0)); continue
            try:
                p, secs = em.aws(args)
            except subprocess.TimeoutExpired:
                rows.append((s["svc"], s["step"], "error", "timed out after 90 s", 90)); continue
            status, msg = classify(p)
            out_json = None
            if p.returncode == 0:
                try:
                    out_json = json.loads(p.stdout) if p.stdout.strip() else None
                except ValueError:
                    pass
                if s["ext"] and out_json is not None:
                    try:
                        ctx.update(s["ext"](out_json, ctx))
                    except (KeyError, IndexError, TypeError) as e:
                        status, msg = "error", f"response lacked {e}"
                if s["svc"] == "lambda" and s["step"] == "invoke":
                    body = open(ctx["outfile"]).read()
                    if out_json and out_json.get("FunctionError"):
                        status, msg = "error", f"FunctionError {out_json['FunctionError']}: {body[:200]}"
                    elif json.loads(body) != {"echo": 42, "ok": True}:
                        status, msg = "error", f"unexpected payload: {body[:200]}"
            calls.write(json.dumps({"svc": s["svc"], "step": s["step"], "args": args, "rc": p.returncode,
                                    "stdout": p.stdout[:1500], "stderr": p.stderr[:600]}) + "\n")
            rows.append((s["svc"], s["step"], status, msg, round(secs, 2)))
            if s["wait"]:
                time.sleep(s["wait"])
    stop.set(); th.join()
    with open(f"{out}/results.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["service", "step", "status", "message", "seconds"]); w.writerows(rows)
    with open(f"{out}/outbound.txt", "w") as f:
        f.write("sampled /proc/net/{tcp,tcp6,udp,udp6} in the container every 0.25 s during the run\n"
                "non-loopback, non-listener ESTABLISHED/SYN_SENT TCP and any UDP peer seen:\n")
        f.write("\n".join(map(str, sorted(found))) if found else "none observed\n")
    restart_test(em, out, work)
    open(f"{out}/meta.txt", "w").write(
        f"emulator: {em.sh('docker', 'run', '--rm', '--entrypoint', 'aws-emulator', IMAGE, '-v').stdout.strip()}\n"
        f"aws cli: {subprocess.run(['aws', '--version'], capture_output=True, text=True).stdout.strip()}\n"
        f"command: python3 -I scripts/smoke.py {out}" + (f" --only {only}" if only else "") + f" --port {port}\n"
        f"finished: {time.strftime('%FT%TZ', time.gmtime())}\n")
    em.sh("docker", "rm", "-f", em.name)
    print(f"{len(rows)} calls:", {k: sum(1 for r in rows if r[2] == k) for k in ("works", "501", "error", "skipped")})


def restart_test(em, out, work):
    """U-6: create markers, restart the container, see what survives."""
    marks = [("s3api", "create-bucket", ["--bucket", "marker-bkt"], "s3api", "list-buckets", "Buckets"),
             ("sqs", "create-queue", ["--queue-name", "marker-q"], "sqs", "list-queues", "QueueUrls"),
             ("dynamodb", "create-table", ["--table-name", "marker-t", "--attribute-definitions", "AttributeName=id,AttributeType=S",
                                           "--key-schema", "AttributeName=id,KeyType=HASH", "--billing-mode", "PAY_PER_REQUEST"],
              "dynamodb", "list-tables", "TableNames")]
    lines = []
    for svc, op, a, lsvc, lop, key in marks:
        p, _ = em.aws([svc, op, *a]); lines.append(f"before restart: {svc} {op} -> rc {p.returncode}")
    def listing():
        res = {}
        for svc, op, a, lsvc, lop, key in marks:
            p, _ = em.aws([lsvc, lop])
            try:
                res[lsvc] = (len(json.loads(p.stdout).get(key) or []) if p.stdout.strip() else 0) if p.returncode == 0 else f"rc {p.returncode}: {p.stderr[:120]}"
            except ValueError:
                res[lsvc] = "unparseable"
        return res
    lines.append(f"before restart, listed counts: {listing()}")
    em.sh("docker", "restart", em.name)
    em.wait()
    lines.append(f"after docker restart, listed counts: {listing()}")
    open(f"{out}/restart.txt", "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    opts = {"only": None, "port": 9500}
    out, i = a[0], 1
    while i < len(a):
        opts[a[i].lstrip("-")] = a[i + 1]; i += 2
    main(out, opts["only"], int(opts["port"]))
