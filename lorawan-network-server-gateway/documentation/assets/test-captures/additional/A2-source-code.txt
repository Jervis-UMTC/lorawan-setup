#!/usr/bin/env python3
"""A2 Fabric endorsement-policy evidence scorer (offline, read-only).

Scores evidence supplied by the Fabric team; does not invoke Fabric, create
identities, change policies, submit transactions or assert external authenticity.
PASS here means the *supplied* trial evidence is internally complete and meets
the frozen A2 rules, NOT that a live Fabric run has been commissioned.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from pathlib import Path
from typing import Any

HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
CONDITIONS = ("NORMAL", "ENDORSEMENT_VIOLATION", "RESTORED")
REQUIRED_FIELDS = ("run_id", "policy_ref", "policy_sha256", "approved_fixture_ref",
                   "fixture_namespace", "required_endorser", "violation_injection_ref",
                   "restoration_proof_ref", "run_manifest_sha256", "record_manifest_sha256")
AUTH_SOURCE = "lorawan-gateway-evidence"


def is_hash(value: Any) -> bool:
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


def state_errors(state: Any, key: str, prefix: str) -> list[str]:
    if not isinstance(state, dict):
        return [f"{prefix}: missing pre/post Fabric query object"]
    errors = []
    if state.get("key") != key:
        errors.append(f"{prefix}: world-state key mismatch")
    if type(state.get("exists")) is not bool:
        errors.append(f"{prefix}: world-state existence not proven")
    if not str(state.get("query_ref") or "").strip():
        errors.append(f"{prefix}: independent world-state query reference missing")
    digest = state.get("state_sha256")
    if state.get("exists") is True and not is_hash(digest):
        errors.append(f"{prefix}: existing world-state SHA-256 missing/invalid")
    if state.get("exists") is False and digest is not None:
        errors.append(f"{prefix}: absent world-state must have null SHA-256")
    return errors


def score_trial(trial: Any, *, condition: str, attempt: int, namespace: str,
                policy_sha: str) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(trial, dict):
        return {"condition": condition, "attempt": attempt, "status": "INVALID",
                "errors": ["trial evidence is not an object"]}
    prefix = f"{condition}/{attempt}"
    if trial.get("condition") != condition or trial.get("attempt") != attempt:
        errors.append("trial condition/attempt mismatch")
    key = str(trial.get("world_state_key") or "")
    if not key.startswith(namespace + ":") or len(key) <= len(namespace) + 1:
        errors.append("world-state key outside dedicated fixture namespace")
    if not str(trial.get("trial_id") or "").strip() or not str(trial.get("source_record_id") or "").strip():
        errors.append("trial/source identity missing")
    if trial.get("policy_sha256") != policy_sha:
        errors.append("approved endorsement policy digest mismatch")
    if trial.get("authenticated_source_system_id") != AUTH_SOURCE:
        errors.append("authenticated source-system ID mismatch")
    if not is_hash(trial.get("payload_sha256")):
        errors.append("exact-payload SHA-256 missing/invalid")
    for field in ("pre", "post"):
        errors.extend(state_errors(trial.get(field), key, field))
    for field in ("attempt_ref", "response_ref", "endorsement_probe_ref"):
        if not str(trial.get(field) or "").strip():
            errors.append(f"{field} missing")
    if trial.get("identity_authorized") is not True or trial.get("record_schema_valid") is not True:
        errors.append("authorized/schema-valid fixture not proven")
    if trial.get("unrelated_fabric_outage") is not False:
        errors.append("unrelated Fabric outage not excluded")
    try:
        latency = float(trial.get("response_time_ms"))
        if not math.isfinite(latency) or latency < 0:
            raise ValueError()
    except (TypeError, ValueError, OverflowError):
        errors.append("finite nonnegative response_time_ms missing")
        latency = None
    endorsements = trial.get("required_endorsements_satisfied")
    if type(endorsements) is not bool:
        errors.append("required-endorsement observation missing")
    if condition == "ENDORSEMENT_VIOLATION":
        if endorsements is not False:
            errors.append("missing required endorsement not proven")
    elif endorsements is not True:
        errors.append("required endorsement path not proven healthy")

    # INVALID = no reliable decision denominator. Once the attempt is valid,
    # unexpected acceptance/rejection remains FAIL evidence and is never hidden.
    if condition != "ENDORSEMENT_VIOLATION" and not is_hash(trial.get("expected_world_state_sha256")):
        errors.append("expected committed world-state digest missing")
    if errors:
        return {"condition": condition, "attempt": attempt, "status": "INVALID",
                "errors": errors, "trial_id": trial.get("trial_id"),
                "world_state_key": key}

    pre, post = trial["pre"], trial["post"]
    outcome = trial.get("normalized_status")
    state_unchanged = (pre["exists"] == post["exists"] and
                       pre["state_sha256"] == post["state_sha256"])
    if outcome not in ("COMMITTED", "REJECTED"):
        return {"condition": condition, "attempt": attempt, "status": "INVALID",
                "errors": [f"terminal Fabric outcome unavailable: {outcome!r}"],
                "trial_id": trial["trial_id"], "world_state_key": key}

    if (condition == "ENDORSEMENT_VIOLATION" and outcome == "REJECTED"
            and trial.get("failure_category") != "MISSING_REQUIRED_ENDORSEMENT"):
        return {"condition": condition, "attempt": attempt, "status": "INVALID",
                "errors": ["missing endorsement was not proven as rejection cause"],
                "trial_id": trial["trial_id"], "world_state_key": key}
    problems: list[str] = []
    if condition == "ENDORSEMENT_VIOLATION":
        if outcome != "REJECTED":
            problems.append("policy-violating attempt was not rejected")
        if trial.get("failure_category") != "MISSING_REQUIRED_ENDORSEMENT":
            problems.append("rejection was not attributed to required endorsement")
        if not state_unchanged:
            problems.append("unauthorized world-state change")
    else:
        if outcome != "COMMITTED":
            problems.append("valid transaction rejected")
        if not is_hash(trial.get("fabric_tx_id")):
            problems.append("committed transaction ID missing/invalid")
        if pre["exists"] is not False:
            problems.append("fresh unique key was not absent before valid commit")
        if post["exists"] is not True or post["state_sha256"] != trial.get("expected_world_state_sha256"):
            problems.append("expected committed world state not independently read back")
    return {"condition": condition, "attempt": attempt, "status": "FAIL" if problems else "PASS",
            "errors": problems, "trial_id": trial["trial_id"], "world_state_key": key,
            "response_time_ms": latency,
            "unauthorized_state_change": condition == "ENDORSEMENT_VIOLATION" and not state_unchanged}


def validate(evidence: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(evidence, dict):
        return {"test_id": "A2", "status": "INVALID", "errors": ["evidence must be an object"],
                "trials": [], "counted_research": False}
    if evidence.get("test_id") != "A2":
        errors.append("not an A2 evidence export")
    if type(evidence.get("formal")) is not bool:
        errors.append("formal must be boolean")
    formal = evidence.get("formal") is True
    if formal and evidence.get("evidence_origin") != "FABRIC_SIDE":
        errors.append("formal scoring requires real Fabric-side evidence_origin")
    count = evidence.get("attempts_per_condition")
    if type(count) is not int or not 1 <= count <= 10 or (formal and count != 10):
        errors.append("invalid attempt count; formal A2 requires 10 per condition")
    for field in REQUIRED_FIELDS:
        if not str(evidence.get(field) or "").strip():
            errors.append(f"{field} missing")
    for field in ("policy_sha256", "run_manifest_sha256", "record_manifest_sha256"):
        if not is_hash(evidence.get(field)):
            errors.append(f"{field} missing/invalid")
    if evidence.get("authenticated_source_system_id") != AUTH_SOURCE:
        errors.append("authenticated source-system ID mismatch")
    groups = evidence.get("conditions")
    if not isinstance(groups, dict) or set(groups) != set(CONDITIONS):
        errors.append("exactly NORMAL, ENDORSEMENT_VIOLATION, RESTORED required")
    if errors:
        return {"test_id": "A2", "status": "INVALID", "errors": errors,
                "trials": [], "counted_research": False}

    results: list[dict[str, Any]] = []
    seen_trials: set[str] = set()
    seen_source: set[str] = set()
    seen_keys: set[str] = set()
    for condition in CONDITIONS:
        trials = groups[condition]
        if not isinstance(trials, list) or len(trials) != count:
            errors.append(f"{condition}: expected exactly {count} trials")
            continue
        for attempt, trial in enumerate(trials, 1):
            result = score_trial(trial, condition=condition, attempt=attempt,
                                 namespace=evidence["fixture_namespace"],
                                 policy_sha=evidence["policy_sha256"])
            results.append(result)
            if not isinstance(trial, dict):
                continue
            for field, seen in (("trial_id", seen_trials),
                                ("source_record_id", seen_source),
                                ("world_state_key", seen_keys)):
                value = trial.get(field)
                if not isinstance(value, str) or not value or value in seen:
                    errors.append(f"{condition}/{attempt}: repeated/missing {field}")
                else:
                    seen.add(value)
    invalid = bool(errors) or any(row["status"] == "INVALID" for row in results)
    failed = any(row["status"] == "FAIL" for row in results)
    status = "INVALID" if invalid else ("FAIL" if failed else "PASS")
    count_by_condition = {}
    for condition in CONDITIONS:
        condition_rows = [row for row in results if row["condition"] == condition]
        times = [row["response_time_ms"] for row in condition_rows
                 if row["status"] != "INVALID" and "response_time_ms" in row]
        count_by_condition[condition] = {
            "passed": sum(row["status"] == "PASS" for row in condition_rows),
            "failed": sum(row["status"] == "FAIL" for row in condition_rows),
            "invalid": sum(row["status"] == "INVALID" for row in condition_rows),
            "mean_response_time_ms": statistics.mean(times) if times else None,
            "sample_sd_response_time_ms": statistics.stdev(times) if len(times) > 1 else None,
        }
    return {"test_id": "A2", "run_id": evidence.get("run_id"),
            "status": status, "errors": errors, "trials": results,
            "attempts_per_condition": count, "conditions": count_by_condition,
            "unauthorized_state_change_count": sum(
                bool(row.get("unauthorized_state_change")) for row in results),
            "counted_research": False,
            "source_declared_formal": formal,
            "requires_fabric_provenance_review": True,
            "qualification": "SUPPLIED_EVIDENCE_VALIDATION_ONLY"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--evidence", required=True, type=Path,
                    help="Fabric-side JSON export; no live connection is made")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.evidence.resolve() == args.output.resolve():
        raise ValueError("refusing to overwrite source evidence")
    result = validate(json.loads(args.evidence.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"A2_EVIDENCE_CHECK={result['status']} CODE_ONLY_SCORER=1")
    print(f"A2_RESULT={args.output}")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        raise SystemExit(1)
