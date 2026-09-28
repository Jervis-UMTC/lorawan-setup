#!/usr/bin/env python3
"""Rotate the ULC Fabric-adapter OpenBao AppRole SecretID without exposing secrets.

The role intentionally keeps a 24-hour SecretID TTL. This utility discovers the
current OpenBao leader, validates the exact least-privilege role contract, issues
one replacement SecretID on the leader, validates it through the stable HAProxy
endpoint, atomically replaces the host credential file, and then revokes the old
SecretID accessor when it is still valid.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

NODES = ("10.104.0.2", "10.104.0.4", "10.104.0.8")
NODE_PORT = 8200
STABLE_BASE = "https://openbao-kms.internal.lorawan.com:18200"
CA_FILE = Path("/etc/lorawan-pki/openbao/ca.crt")
BOOTSTRAP_FILE = Path("/root/lorawan-openbao-bootstrap/init.json")
CREDENTIAL_DIR = Path("/etc/lorawan-cloud/gateway-evidence/openbao-approle")
ROLE_ID_FILE = CREDENTIAL_DIR / "role_id"
SECRET_ID_FILE = CREDENTIAL_DIR / "secret_id"
LOCK_FILE = Path("/run/lock/lorawan-fabric-approle-rotate.lock")
ROLE_NAME = "fabric-adapter"
EXPECTED_POLICY = "fabric-evidence-signer"
EXPECTED_TOKEN_TTL = 3600
EXPECTED_TOKEN_MAX_TTL = 14400
EXPECTED_SECRET_ID_TTL = 86400
EXPECTED_SECRET_ID_NUM_USES = 0
RUNTIME_GID = 65532


class RotationError(RuntimeError):
    pass


def context() -> ssl.SSLContext:
    if not CA_FILE.is_file():
        raise RotationError(f"OpenBao CA missing: {CA_FILE}")
    return ssl.create_default_context(cafile=str(CA_FILE))


def request_json(
    base: str,
    path: str,
    *,
    method: str = "GET",
    token: str | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["X-Vault-Token"] = token
    req = urllib.request.Request(base + path, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, context=context(), timeout=5) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {}
        return exc.code, parsed
    except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
        raise RotationError(f"OpenBao request failed for {base}: {type(exc).__name__}") from exc


def require_ok(status: int, action: str, allowed: tuple[int, ...] = (200, 204)) -> None:
    if status not in allowed:
        raise RotationError(f"{action} returned HTTP {status}")


def read_secret_text(path: Path, label: str) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RotationError(f"cannot read {label}") from exc
    if not value or "\n" in value or "\r" in value:
        raise RotationError(f"{label} is empty or malformed")
    return value


def load_root_token() -> str:
    try:
        data = json.loads(BOOTSTRAP_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RotationError("cannot read OpenBao bootstrap material") from exc
    token = str(data.get("root_token", "")).strip()
    if not token:
        raise RotationError("OpenBao bootstrap material has no root_token")
    return token


def discover_active() -> str:
    statuses: dict[str, int] = {}
    for node in NODES:
        status, _ = request_json(f"https://{node}:{NODE_PORT}", "/v1/sys/health")
        statuses[node] = status
    active = [node for node, status in statuses.items() if status == 200]
    unexpected = {node: status for node, status in statuses.items() if status not in (200, 429)}
    if unexpected:
        raise RotationError("unexpected OpenBao health state on one or more nodes")
    if len(active) != 1:
        raise RotationError(f"expected exactly one OpenBao active node, found {len(active)}")
    print(f"OPENBAO_ACTIVE_NODE={active[0]}")
    return active[0]


def validate_role(active_base: str, root_token: str, stored_role_id: str) -> None:
    status, response = request_json(
        active_base, f"/v1/auth/approle/role/{ROLE_NAME}", token=root_token
    )
    require_ok(status, "AppRole read")
    data = response.get("data") or {}
    policies = data.get("token_policies") or data.get("policies") or []
    if set(policies) != {EXPECTED_POLICY}:
        raise RotationError("AppRole token policy differs from commissioned signer-only policy")
    expected = {
        "token_ttl": EXPECTED_TOKEN_TTL,
        "token_max_ttl": EXPECTED_TOKEN_MAX_TTL,
        "secret_id_ttl": EXPECTED_SECRET_ID_TTL,
        "secret_id_num_uses": EXPECTED_SECRET_ID_NUM_USES,
    }
    for key, value in expected.items():
        if int(data.get(key, -1)) != value:
            raise RotationError(f"AppRole {key} differs from commissioned value")
    if data.get("bind_secret_id") is not True:
        raise RotationError("AppRole bind_secret_id is not true")

    status, response = request_json(
        active_base, f"/v1/auth/approle/role/{ROLE_NAME}/role-id", token=root_token
    )
    require_ok(status, "AppRole RoleID read")
    live_role_id = str((response.get("data") or {}).get("role_id", "")).strip()
    if not live_role_id or live_role_id != stored_role_id:
        raise RotationError("stored RoleID does not match active OpenBao role")
    print("APPROLE_ROLE_CONTRACT=PASS")


def login_validate(role_id: str, secret_id: str) -> None:
    status, response = request_json(
        STABLE_BASE,
        "/v1/auth/approle/login",
        method="POST",
        payload={"role_id": role_id, "secret_id": secret_id},
    )
    require_ok(status, "stable-endpoint AppRole login", (200,))
    auth = response.get("auth") or {}
    client_token = str(auth.get("client_token", "")).strip()
    policies = auth.get("token_policies") or auth.get("policies") or []
    if not client_token:
        raise RotationError("AppRole login returned no client token")
    effective_policies = set(policies)
    if EXPECTED_POLICY not in effective_policies or not effective_policies.issubset({EXPECTED_POLICY, "default"}):
        raise RotationError("AppRole login returned unexpected token policies")
    revoke_status, _ = request_json(
        STABLE_BASE, "/v1/auth/token/revoke-self", method="POST", token=client_token, payload={}
    )
    if revoke_status not in (200, 204):
        print("APPROLE_VALIDATION_TOKEN_REVOKE=DEFERRED")


def lookup_accessor(active_base: str, root_token: str, secret_id: str) -> str | None:
    status, response = request_json(
        active_base,
        f"/v1/auth/approle/role/{ROLE_NAME}/secret-id/lookup",
        method="POST",
        token=root_token,
        payload={"secret_id": secret_id},
    )
    if status == 400:
        return None
    require_ok(status, "current SecretID lookup", (200,))
    accessor = str((response.get("data") or {}).get("secret_id_accessor", "")).strip()
    return accessor or None


def issue_secret(active_base: str, root_token: str) -> tuple[str, str]:
    status, response = request_json(
        active_base,
        f"/v1/auth/approle/role/{ROLE_NAME}/secret-id",
        method="POST",
        token=root_token,
        payload={},
    )
    require_ok(status, "SecretID issuance", (200,))
    data = response.get("data") or {}
    secret_id = str(data.get("secret_id", "")).strip()
    accessor = str(data.get("secret_id_accessor", "")).strip()
    if not secret_id or not accessor:
        raise RotationError("SecretID issuance returned incomplete credential material")
    return secret_id, accessor


def atomic_install(secret_id: str) -> None:
    st = CREDENTIAL_DIR.stat()
    if st.st_uid != 0 or st.st_gid != RUNTIME_GID or (st.st_mode & 0o777) != 0o750:
        raise RotationError("AppRole credential directory ownership/mode is not root:65532 0750")
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", prefix=".secret_id.", dir=CREDENTIAL_DIR, delete=False
        ) as handle:
            temp_name = handle.name
            handle.write(secret_id + "\n")
            handle.flush()
            os.fchmod(handle.fileno(), 0o440)
            os.fchown(handle.fileno(), 0, RUNTIME_GID)
            os.fsync(handle.fileno())
        os.replace(temp_name, SECRET_ID_FILE)
        dir_fd = os.open(CREDENTIAL_DIR, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def revoke_accessor(active_base: str, root_token: str, accessor: str | None) -> bool:
    if not accessor:
        return True
    status, _ = request_json(
        active_base,
        f"/v1/auth/approle/role/{ROLE_NAME}/secret-id-accessor/destroy",
        method="POST",
        token=root_token,
        payload={"secret_id_accessor": accessor},
    )
    return status in (200, 204)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--min-age-seconds", type=int, default=21600)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise RotationError("must run as root")
    if args.min_age_seconds < 0:
        raise RotationError("min age cannot be negative")

    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        role_id = read_secret_text(ROLE_ID_FILE, "RoleID")
        current_secret = read_secret_text(SECRET_ID_FILE, "SecretID")
        root_token = load_root_token()
        active = discover_active()
        active_base = f"https://{active}:{NODE_PORT}"
        validate_role(active_base, root_token, role_id)
        login_validate(role_id, current_secret)
        print("APPROLE_CURRENT_LOGIN=PASS")

        if args.check_only:
            print("APPROLE_ROTATION_CHECK=PASS")
            return 0

        age = max(0, int(time.time() - SECRET_ID_FILE.stat().st_mtime))
        if not args.force and age < args.min_age_seconds:
            print(f"APPROLE_ROTATION_SKIPPED=credential_age_{age}s_below_threshold")
            return 0

        old_accessor = lookup_accessor(active_base, root_token, current_secret)
        new_secret, _new_accessor = issue_secret(active_base, root_token)
        login_validate(role_id, new_secret)
        print("APPROLE_NEW_LOGIN=PASS")
        atomic_install(new_secret)
        print("APPROLE_SECRET_FILE_REPLACED=PASS")

        installed_secret = read_secret_text(SECRET_ID_FILE, "installed SecretID")
        login_validate(role_id, installed_secret)
        print("APPROLE_INSTALLED_LOGIN=PASS")

        if revoke_accessor(active_base, root_token, old_accessor):
            print("APPROLE_OLD_ACCESSOR_REVOKED=PASS")
        else:
            print("APPROLE_OLD_ACCESSOR_REVOKED=DEFERRED")
        print("APPROLE_ROTATION=PASS")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BlockingIOError:
        print("APPROLE_ROTATION=SKIP_ALREADY_RUNNING", file=sys.stderr)
        raise SystemExit(0)
    except RotationError as exc:
        print(f"APPROLE_ROTATION=FAIL:{exc}", file=sys.stderr)
        raise SystemExit(1)
