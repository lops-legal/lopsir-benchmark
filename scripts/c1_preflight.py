"""Check C1 study readiness without downloading data or executing a benchmark."""
import argparse
import json
import os
import re
from pathlib import Path


def inspect_study(config, root):
    root = Path(root).resolve()
    methods = config.get("methods", [])
    expected_ids = {f"C1-M{i}" for i in range(1, 6)}
    if len(methods) != 5 or {m.get("id") for m in methods} != expected_ids:
        raise ValueError("C1 requires exactly five uniquely identified methods")
    if config.get("case_type") != "C1":
        raise ValueError("This preflight is exclusively for C1")
    policy = config.get("policy", {})
    if policy.get("allow_synthetic_research_data") is not False or policy.get("allow_external_corpora") is not False:
        raise ValueError("Current research policy requires real project data only")
    issues = []
    data = config.get("data", {})
    for field in ("corpus_path", "queries_path", "qrels_path"):
        value = data.get(field)
        if not value:
            if field == "corpus_path" and data.get("connection_ref"):
                issues.append({"code": "CONNECTION_NOT_VERIFIED", "field": "connection_ref"})
            else:
                issues.append({"code": "REAL_INPUT_NOT_CONFIGURED", "field": field})
            continue
        if value.startswith('env:'):
            env_name=value[4:]
            resolved=os.environ.get(env_name)
            if not resolved:
                issues.append({'code':'INPUT_ENV_NOT_SET','field':field,'environment_variable':env_name})
                continue
            path=Path(resolved)
        else:
            path = Path(value)
        if not path.is_absolute():
            path = root / path
        if not path.exists():
            issues.append({"code": "INPUT_NOT_FOUND", "field": field})
        try:
            relative = path.resolve().relative_to(root)
        except ValueError:
            relative = None
        if relative and relative.parts[0] == "examples":
            issues.append({"code": "HISTORICAL_FIXTURE_FORBIDDEN_FOR_RESEARCH", "field": field})
    for field in ("identity_mapping", "snapshot_sha256", "verified_record_count"):
        if data.get(field) is None:
            issues.append({"code": "DATA_AUDIT_PENDING", "field": field})
    for method in methods:
        if not str(method.get("paper", "")).startswith(("https://doi.org/", "https://arxiv.org/")):
            raise ValueError(f"Missing primary paper for {method['id']}")
        if not str(method.get("code", "")).startswith("https://github.com/"):
            raise ValueError(f"Missing public implementation for {method['id']}")
        if not re.fullmatch(r"[a-f0-9]{40}", method.get("source_inspection_revision", "")):
            raise ValueError(f"Invalid inspected revision for {method['id']}")
        if method.get("implementation_state") != "ready":
            issues.append({"code": "ADAPTER_NOT_READY", "method": method["id"]})
        if not method.get("runtime_lock"):
            issues.append({"code": "RUNTIME_NOT_LOCKED", "method": method["id"]})
    return {
        "kind": "study_readiness_not_a_benchmark",
        "case_type": "C1", "status": "blocked" if issues else "preflight_checks_passed",
        "source_repository": data.get("source_repository"),
        "user_reported_count": data.get("expected_count_reported_by_user"),
        "verified_record_count": data.get("verified_record_count"),
        "methods": [m["id"] for m in methods], "issues": issues,
        "research_metrics": None,
        "notes": ["No corpus download, inference, database provisioning or research run performed.",
                  "Passing config checks does not certify data quality or legal relevance."]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/c1.methods.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/c1/readiness.json"))
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        report = inspect_study(config, Path(__file__).resolve().parents[1])
    except (ValueError, OSError, TypeError, KeyError) as error:
        parser.exit(1, f"Invalid C1 study: {error}\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "issues": len(report["issues"])}))
    if report["issues"]:
        parser.exit(2)


if __name__ == "__main__":
    main()
