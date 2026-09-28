#!/usr/bin/env python3
"""I3 HRC source-bound anchor scorer, supplied-evidence validation only.

No network, SQL, Fabric, OpenBao or sensor access. Synthetic fixtures exercise
10 baseline CREATEs, 10 same-exact-payload duplicates and 10 conflicting
exact-payload attempts in one dedicated namespace. References to independently
queried ledger state require external provenance review before counted work.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path
from typing import Any

SOURCE_SYSTEM = "lorawan-gateway-evidence"
NAMESPACE = "i3-synthetic:"
HEX64 = re.compile(r"^[a-f0-9]{64}$")
ANCHOR_FIELDS = frozenset({
    "record_id", "authenticated_source_system_id", "source_record_id",
    "digest_algorithm", "digest", "payload_length", "source_type",
    "producer", "produced_at", "schema_version",
})
PHASES = ("BASELINE", "DUPLICATE_SAME_HASH", "CONFLICTING_OVERWRITE")
ERROR_CATEGORY = "CONFLICTING_ANCHOR"


def hex64(value: Any) -> bool:
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


def exact_payload(value: Any) -> bytes | None:
    if not isinstance(value, str):
        return None
    try:
        payload = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        return None
    if not payload or base64.b64encode(payload).decode("ascii") != value:
        return None
    return payload


def anchor_errors(anchor: Any, source_record_id: str, digest: str,
                  length: int, *, allow_missing: bool = False) -> list[str]:
    if anchor is None and allow_missing:
        return []
    if not isinstance(anchor, dict):
        return ["queried anchor missing"]
    errors = []
    if set(anchor) != ANCHOR_FIELDS:
        errors.append("queried anchor field set differs from HRC contract")
    for name in ("record_id", "source_type", "producer", "produced_at", "schema_version"):
        if not isinstance(anchor.get(name), str) or not anchor[name].strip():
            errors.append(f"anchor {name} missing")
    if anchor.get("authenticated_source_system_id") != SOURCE_SYSTEM:
        errors.append("anchor source-system namespace mismatch")
    if anchor.get("source_record_id") != source_record_id:
        errors.append("anchor source-record identity mismatch")
    if anchor.get("digest_algorithm") != "sha256" or anchor.get("digest") != digest:
        errors.append("anchor original exact-payload digest mismatch")
    if type(anchor.get("payload_length")) is not int or anchor["payload_length"] != length:
        errors.append("anchor exact-payload length mismatch")
    return errors


def query_errors(query: Any, source_record_id: str, expected: Any,
                 *, expect_absent: bool = False, post_attempt: bool = False) -> list[str]:
    if not isinstance(query, dict):
        return ["independent Fabric query result missing"]
    errors = []
    if not str(query.get("query_ref") or "").strip():
        errors.append("independent Fabric query reference missing")
    if query.get("authenticated_source_system_id") != SOURCE_SYSTEM:
        errors.append("query source-system ID mismatch")
    if query.get("source_record_id") != source_record_id:
        errors.append("query source-record ID mismatch")
    count = query.get("record_count")
    if type(count) is not int or count < 0:
        errors.append("independent record count missing")
    if type(query.get("found")) is not bool:
        errors.append("query found flag missing")
    if expect_absent:
        if query.get("found") is not False or count != 0 or query.get("anchor") is not None:
            errors.append("baseline fixture not independently proven absent")
    elif post_attempt and query.get("found") is False and count == 0 and query.get("anchor") is None:
        # A positively observed disappearance is a security FAIL, not missing evidence.
        pass
    elif query.get("found") is not True or count is None or count < 1:
        errors.append("existing anchor not independently proven")
    elif not isinstance(query.get("anchor"), dict):
        errors.append("queried anchor object missing")
    elif set(query["anchor"]) != ANCHOR_FIELDS:
        errors.append("queried anchor field set incomplete/unknown")
    elif isinstance(expected, dict) and (
        query["anchor"].get("record_id") != expected.get("record_id")
    ):
        errors.append("query anchor record ID differs from frozen baseline")
    return errors


def response_errors(response: Any, key: str, payload_digest: str,
                    payload_length: int) -> list[str]:
    if not isinstance(response, dict):
        return ["Fabric submission response missing"]
    errors = []
    if not str(response.get("request_ref") or "").strip() or not str(response.get("response_ref") or "").strip():
        errors.append("request/response evidence references missing")
    if response.get("source_record_id") != key or response.get("authenticated_source_system_id") != SOURCE_SYSTEM:
        errors.append("submitted source identity mismatch")
    if response.get("payload_sha256") != payload_digest or response.get("payload_length") != payload_length:
        errors.append("submitted exact payload/digest mismatch")
    if response.get("status") not in ("COMMITTED", "REJECTED"):
        errors.append("terminal transaction status unavailable")
    try:
        ms = float(response.get("response_time_ms"))
        if not math.isfinite(ms) or ms < 0:
            errors.append("nonfinite or negative response time")
    except (ValueError, TypeError, OverflowError):
        errors.append("response time missing")
    return errors


def score(trial: Any, phase: str, attempt: int, baseline: dict[str, Any],
          frozen: Any) -> dict[str, Any]:
    result = {"phase": phase, "attempt": attempt}
    if not isinstance(trial, dict):
        return {**result, "status": "INVALID", "errors": ["trial not an object"]}
    problems: list[str] = []
    errors: list[str] = []
    key = baseline.get("source_record_id")
    if trial.get("phase") != phase or trial.get("attempt") != attempt:
        errors.append("phase/attempt mismatch")
    if trial.get("source_record_id") != key:
        errors.append("attempt not bound to its frozen baseline source ID")
    if not str(trial.get("trial_id") or "").strip():
        errors.append("trial ID missing")
    payload = exact_payload(trial.get("exact_payload_base64"))
    if payload is None:
        errors.append("exact payload is missing/noncanonical Base64")
        payload = b""
    submitted_digest = hashlib.sha256(payload).hexdigest()
    if not hex64(trial.get("payload_sha256")) or trial["payload_sha256"] != submitted_digest:
        errors.append("submitted SHA-256 differs from exact payload bytes")
    if phase == "DUPLICATE_SAME_HASH":
        if submitted_digest != baseline["payload_sha256"] or payload != frozen:
            errors.append("duplicate was not byte-for-byte the baseline payload")
    elif phase == "CONFLICTING_OVERWRITE":
        if submitted_digest == baseline["payload_sha256"] or payload == frozen:
            errors.append("conflicting overwrite did not use a different exact payload")
    else:
        errors.append("unsupported attack phase")
    errors += response_errors(trial.get("response"), key, submitted_digest, len(payload))
    for name in ("pre_query", "post_query"):
        errors += [name + ": " + e for e in query_errors(
            trial.get(name), key,
            baseline.get("anchor") if name == "pre_query" else None,
            post_attempt=name == "post_query")]
    if trial.get("unrelated_fabric_outage") is not False:
        errors.append("unrelated Fabric outage has not been excluded")
    # Do not throw out independently proven security failures to improve scores.
    if not errors:
        for name in ("pre_query", "post_query"):
            state = trial[name]
            if state["anchor"] != baseline["anchor"]:
                if name == "pre_query":
                    errors.append("pre-attempt ledger already differs from frozen baseline")
                else:
                    problems.append("post-attempt original anchor was changed")
            if state["record_count"] != 1:
                if name == "pre_query":
                    errors.append("pre-attempt ledger multiplicity is invalid")
                else:
                    problems.append("post-attempt anchor multiplicity changed")
        response = trial["response"]
        status = response["status"]
        outcome = response.get("outcome")
        if phase == "DUPLICATE_SAME_HASH":
            # HRC CreateSourceBoundAnchor returns IDEMPOTENT_RETRY for a
            # same-exact-payload retry. An explicitly rejected duplicate is
            # also safe if the original anchor remains intact.
            if (status == "REJECTED" and outcome == "REJECTED_DUPLICATE"
                    and (response.get("failure_category") != "DUPLICATE_ANCHOR"
                         or response.get("decision_source") != "CHAINCODE")):
                errors.append("duplicate rejection not proven to originate from HRC chaincode")
            if not ((status == "COMMITTED" and outcome == "IDEMPOTENT_RETRY")
                    or (status == "REJECTED" and outcome == "REJECTED_DUPLICATE")):
                problems.append("duplicate outcome did not preserve idempotent semantics")
            if status == "COMMITTED" and not hex64(response.get("fabric_tx_id")):
                errors.append("committed idempotent retry lacks transaction ID")
        else:
            if status == "COMMITTED":
                problems.append("conflicting overwrite was accepted")
            elif (outcome != "REJECTED_CONFLICT"
                  or response.get("failure_category") != ERROR_CATEGORY
                  or response.get("decision_source") != "CHAINCODE"):
                errors.append("rejection was not proven to be an HRC anchor conflict")
    if errors:
        return {**result, "status": "INVALID", "errors": errors,
                "source_record_id": key}
    changed = any("anchor was changed" in p or "multiplicity changed" in p for p in problems)
    return {**result, "status": "FAIL" if problems else "PASS", "errors": problems,
            "source_record_id": key, "response_time_ms": float(trial["response"]["response_time_ms"]),
            "state_changed": changed,
            "unauthorized_state_change": changed and phase == "CONFLICTING_OVERWRITE",
            "duplicate_effectively_prevented": phase == "DUPLICATE_SAME_HASH" and not changed and not problems,
            "duplicate_explicitly_rejected": phase == "DUPLICATE_SAME_HASH" and trial["response"]["status"] == "REJECTED" and not changed and not problems,
            "conflict_rejected": phase == "CONFLICTING_OVERWRITE" and trial["response"]["status"] == "REJECTED"
                                 and not changed and not problems,
            "original_hash_preserved": isinstance(trial["post_query"]["anchor"], dict) and trial["post_query"]["anchor"].get("digest") == baseline["payload_sha256"]}


def score_baseline(entry: Any, attempt: int) -> tuple[dict[str, Any], bytes | None]:
    result = {"phase": "BASELINE", "attempt": attempt}
    if not isinstance(entry, dict):
        return {**result, "status": "INVALID", "errors": ["baseline not an object"]}, None
    errors = []
    if entry.get("attempt") != attempt or not str(entry.get("trial_id") or "").strip():
        errors.append("baseline attempt/trial ID invalid")
    key = entry.get("source_record_id")
    if not isinstance(key, str) or not key.startswith(NAMESPACE) or len(key) <= len(NAMESPACE):
        errors.append("dedicated I3 source record namespace missing")
        key = str(key or "")
    payload = exact_payload(entry.get("exact_payload_base64"))
    if payload is None:
        errors.append("baseline exact payload missing/noncanonical")
        payload = b""
    expected = hashlib.sha256(payload).hexdigest()
    if entry.get("payload_sha256") != expected or not hex64(entry.get("payload_sha256")):
        errors.append("baseline digest does not match exact bytes")
    errors += query_errors(entry.get("pre_query"), key, None, expect_absent=True)
    errors += query_errors(entry.get("post_query"), key, None, post_attempt=True)
    errors += response_errors(entry.get("response"), key, expected, len(payload))
    errors += anchor_errors(entry.get("anchor"), key, expected, len(payload))
    if entry.get("unrelated_fabric_outage") is not False:
        errors.append("baseline unrelated Fabric outage not excluded")
    if errors:
        return {**result, "status": "INVALID", "errors": errors,
                "source_record_id": key}, None
    problems = []
    if entry["post_query"]["record_count"] != 1 or entry["post_query"]["anchor"] != entry["anchor"]:
        problems.append("baseline not independently read back as one identical anchor")
    if (entry["response"]["status"] != "COMMITTED"
            or entry["response"].get("outcome") != "CREATE"
            or not hex64(entry["response"].get("fabric_tx_id"))):
        problems.append("baseline valid anchor creation not committed")
    return {**result, "status": "FAIL" if problems else "PASS", "errors": problems,
            "source_record_id": key, "response_time_ms": float(entry["response"]["response_time_ms"]),
            "original_hash_preserved": not problems}, payload


def validate(evidence: Any) -> dict[str, Any]:
    errors = []
    if not isinstance(evidence, dict):
        return {"test_id": "I3", "status": "INVALID",
                "errors": ["evidence must be object"], "counted_research": False}
    if evidence.get("test_id") != "I3" or evidence.get("authenticated_source_system_id") != SOURCE_SYSTEM:
        errors.append("I3 identity/source-system mismatch")
    if type(evidence.get("formal")) is not bool:
        errors.append("formal must be boolean")
    n = evidence.get("attempts_per_phase")
    if type(n) is not int or n not in range(1, 11) or (evidence.get("formal") is True and n != 10):
        errors.append("formal I3 requires ten baseline, ten duplicate and ten conflict")
    for field in ("run_id", "run_manifest_sha256", "record_manifest_sha256",
                  "fabric_export_ref", "fixture_namespace"):
        if not str(evidence.get(field) or "").strip():
            errors.append(f"{field} missing")
    for field in ("run_manifest_sha256", "record_manifest_sha256"):
        if not hex64(evidence.get(field)):
            errors.append(f"{field} invalid SHA-256")
    if evidence.get("fixture_namespace") != NAMESPACE[:-1]:
        errors.append("wrong dedicated fixture namespace")
    phases = evidence.get("phases")
    if not isinstance(phases, dict) or set(phases) != set(PHASES):
        errors.append("exactly BASELINE, DUPLICATE_SAME_HASH, CONFLICTING_OVERWRITE required")
    if errors:
        return {"test_id": "I3", "status": "INVALID",
                "errors": errors, "counted_research": False}
    rows: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    seen_trials: set[str] = set()
    baseline: list[dict[str, Any]] = phases["BASELINE"]
    if not isinstance(baseline, list) or len(baseline) != n:
        errors.append(f"BASELINE expected {n} entries")
        baseline = []
    originals: list[bytes | None] = []
    for i, entry in enumerate(baseline, 1):
        result, raw = score_baseline(entry, i)
        rows.append(result)
        originals.append(raw)
        if isinstance(entry, dict):
            key, tid = entry.get("source_record_id"), entry.get("trial_id")
            if not isinstance(key, str) or not key or key in seen_keys:
                errors.append(f"BASELINE/{i}: duplicate/missing source key")
            else: seen_keys.add(key)
            if not isinstance(tid, str) or not tid or tid in seen_trials:
                errors.append(f"BASELINE/{i}: duplicate/missing trial ID")
            else: seen_trials.add(tid)
    for phase in PHASES[1:]:
        group = phases[phase]
        if not isinstance(group, list) or len(group) != n:
            errors.append(f"{phase}: expected {n} entries")
            continue
        for i, trial in enumerate(group, 1):
            if (i <= len(baseline) and isinstance(baseline[i-1], dict)
                    and originals[i-1] is not None and rows[i-1]["status"] == "PASS"):
                result = score(trial, phase, i, baseline[i-1], originals[i-1])
            else:
                result = {"phase": phase, "attempt": i, "status": "INVALID",
                          "errors": ["baseline not independently proven PASS"]}
            rows.append(result)
            if isinstance(trial, dict):
                tid = trial.get("trial_id")
                if not isinstance(tid, str) or not tid or tid in seen_trials:
                    errors.append(f"{phase}/{i}: duplicate/missing trial ID")
                else: seen_trials.add(tid)
    overall = ("INVALID" if errors or any(x["status"] == "INVALID" for x in rows)
               else "FAIL" if any(x["status"] == "FAIL" for x in rows) else "PASS")
    phase_stats = {}
    for phase in PHASES:
        group = [r for r in rows if r["phase"] == phase]
        times = [r["response_time_ms"] for r in group if "response_time_ms" in r]
        phase_stats[phase] = {
            "passed": sum(r["status"] == "PASS" for r in group),
            "failed": sum(r["status"] == "FAIL" for r in group),
            "invalid": sum(r["status"] == "INVALID" for r in group),
            "mean_response_time_ms": statistics.mean(times) if times else None,
            "sample_sd_response_time_ms": statistics.stdev(times) if len(times) > 1 else None,
        }
    return {"test_id": "I3", "status": overall, "errors": errors,
            "baseline_fixtures": n, "mutation_attempts": 2 * n,
            "trials": rows, "phases": phase_stats,
            "duplicate_effective_prevention_count": sum(r.get("duplicate_effectively_prevented", False) for r in rows),
            "duplicate_explicit_rejection_count": sum(r.get("duplicate_explicitly_rejected", False) for r in rows),
            "conflict_rejection_count": sum(r.get("conflict_rejected", False) for r in rows),
            "original_hash_preservation_count": sum(r.get("original_hash_preserved", False) for r in rows if r["phase"] != "BASELINE"),
            "unauthorized_state_change_count": sum(r.get("unauthorized_state_change", False) for r in rows),
            "counted_research": False, "requires_fabric_provenance_review": True,
            "qualification": "SUPPLIED_EVIDENCE_VALIDATION_ONLY"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.evidence.resolve() == args.output.resolve():
        raise ValueError("source evidence may not be overwritten")
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    result = validate(evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"I3_EVIDENCE_CHECK={result['status']} CODE_ONLY_SCORER=1")
    print(f"I3_RESULT={args.output}")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    try: raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR={exc}", file=sys.stderr)
        raise SystemExit(1)
