#!/usr/bin/env python3
"""Count implemented, scaffolded and unwired operations per service crate.

usage: python3 -I scripts/count_ops.py <emulator-source-dir> <new-output-dir>

For each crate under services/ (except common):
  total       operation shapes in the crate's Smithy model
  wired       operations with a `//! @op <Name>` header in src/ops/*.rs
  scaffolded  wired operations whose header says `SCAFFOLDED, NOT IMPLEMENTED:`
  implemented wired minus scaffolded
  unwired     modeled operations with no `@op` header (answered 501 by the framework)
Scaffolded and unwired operations both answer HTTP 501.
"""
import csv, hashlib, json, os, platform, re, subprocess, sys

MARK = "SCAFFOLDED, NOT IMPLEMENTED:"
OP_RE = re.compile(r"^//! @op (\w+)\s*$", re.M)
OPS_MD_RE = re.compile(r"^(\d+) operations? from ", re.M)


def smithy_ops(crate):
    d = os.path.join(crate, "smithy-model")
    names = set()
    for f in sorted(os.listdir(d)):
        if f.endswith(".json"):
            shapes = json.load(open(os.path.join(d, f)))["shapes"]
            names |= {k.split("#", 1)[1] for k, v in shapes.items() if v["type"] == "operation"}
    return names


def ops_files(crate):
    d = os.path.join(crate, "src", "ops")
    wired, scaffolded = set(), set()
    for f in sorted(os.listdir(d)):
        p = os.path.join(d, f)
        if not (f.endswith(".rs") and os.path.isfile(p)):
            continue
        text = open(p, encoding="utf-8").read()
        m = OP_RE.search(text)
        if not m:
            continue
        wired.add(m.group(1))
        head = "\n".join(l for l in text.splitlines() if l.startswith("//!"))
        if MARK in head:
            scaffolded.add(m.group(1))
    return wired, scaffolded


def main(src, out):
    commit = subprocess.check_output(["git", "-C", src, "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", src, "status", "--porcelain"], text=True).strip()
    pinned = open(os.path.join(os.path.dirname(__file__), "..", "pinned-commit")).read().strip()
    if commit != pinned or dirty:
        sys.exit(f"source is at {commit} (dirty={bool(dirty)}), pinned is {pinned}")
    os.makedirs(out)
    rows, problems = [], []
    sdir = os.path.join(src, "services")
    for name in sorted(os.listdir(sdir)):
        crate = os.path.join(sdir, name)
        if name == "common" or not os.path.isdir(crate):
            continue
        model = smithy_ops(crate)
        wired, scaf = ops_files(crate)
        m = OPS_MD_RE.search(open(os.path.join(crate, "OPERATIONS.md"), encoding="utf-8").read())
        if m and int(m.group(1)) != len(model):
            problems.append(f"{name}: OPERATIONS.md says {m.group(1)}, model has {len(model)}")
        if wired - model:
            problems.append(f"{name}: @op not in model: {sorted(wired - model)}")
        rows.append({
            "service": name.removeprefix("service-"),
            "total": len(model),
            "implemented": len(wired & model) - len(scaf & model),
            "scaffolded": len(scaf & model),
            "unwired": len(model - wired),
        })
    cols = ["service", "total", "implemented", "scaffolded", "unwired"]
    with open(os.path.join(out, "counts.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(rows)
    tot = {c: sum(r[c] for r in rows) for c in cols[1:]}
    with open(os.path.join(out, "meta.txt"), "w") as f:
        f.write(f"source commit: {commit}\ncommand: python3 -I scripts/count_ops.py {src} {out}\n")
        f.write(f"script sha256: {hashlib.sha256(open(__file__, 'rb').read()).hexdigest()}\n")
        f.write(f"python: {platform.python_version()} on {platform.platform()}\n")
        f.write(f"services: {len(rows)}\ntotals: {tot}\n")
        f.write(f"consistency problems: {len(problems)}\n" + "".join(f"  {p}\n" for p in problems))
    print(f"{len(rows)} services, totals {tot}, {len(problems)} consistency problems")
    for p in problems[:10]:
        print(" ", p)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
