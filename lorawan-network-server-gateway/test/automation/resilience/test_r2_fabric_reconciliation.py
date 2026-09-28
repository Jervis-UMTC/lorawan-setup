#!/usr/bin/env python3
"""Offline R2 status and exact source-set tests. No recorder or Fabric mutation."""
from __future__ import annotations
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TARGET = Path(__file__).with_name("r2_fabric_reconciliation.py")
spec = importlib.util.spec_from_file_location("r2_fabric_reconciliation", TARGET)
assert spec and spec.loader
r2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r2)


def row(key: str, status="pending", digest="a" * 64, tx="", committed=""):
    return {"source_event_key":key, "digest_sha256":digest,"status":status,
            "fabric_tx_id":tx, "committed_at":committed}


class R2OfflineTests(unittest.TestCase):
    def test_source_reconciliation_order_guard(self):
        result = r2.validate_reconciliation_source_contract()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(result["worker_source_sha256"]), 64)

    def test_exact_two_rehearsal_records_are_frozen(self):
        rows=[row("source-1"),row("source-2",status="failed")]
        frozen=r2.freeze_outage_set(rows,2)
        self.assertEqual(set(frozen),{"source-1","source-2"})
        self.assertEqual(frozen["source-2"]["digest"],"a"*64)

    def test_duplicate_keys_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"duplicated"):
            r2.freeze_outage_set([row("same"),row("same")],2)

    def test_missing_record_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"count"):
            r2.freeze_outage_set([row("source-1")],2)

    def test_unrecoverable_statuses_rejected(self):
        for status in ("dead_letter","needs_attention","confirmed","unknown",""):
            with self.subTest(status=status):
                with self.assertRaisesRegex(RuntimeError,"outage boundary invalid"):
                    r2.freeze_outage_set([row("source-1",status=status)],1)

    def test_nonconfirmed_committed_timestamp_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"committed_at"):
            r2.freeze_outage_set([row("source-1",committed="2026-09-21T01:00:00Z")],1)

    def test_missing_and_invalid_digest_rejected(self):
        with self.assertRaisesRegex(RuntimeError,"digest"):
            r2.freeze_outage_set([row("source-1",digest="bad")],1)

    def test_confirmed_requires_tx_and_timestamp(self):
        self.assertEqual(r2.validate_row(row("source-1",status="confirmed",
                 tx="a"*64,committed="2026-09-21T01:00:00Z"),must_confirm=True),[])
        self.assertTrue(r2.validate_row(row("source-1",status="confirmed"),must_confirm=True))

    def test_pending_and_reconciliation_states_are_not_false_verifications(self):
        for status in ("pending","processing","submitted_unknown","reconciling","failed"):
            with self.subTest(status=status):
                self.assertEqual(r2.validate_row(row("source-1",status=status),must_confirm=False),[])

    def test_outage_waits_for_earliest_two_digests_without_cherry_picking(self):
        original=[row("first",digest=""), row("second",digest=""), row("later")]
        sealed=[row("first"),row("second"),row("later")]
        with (patch.object(r2,"outbox_rows",side_effect=[original,sealed]) as exported,
              patch.object(r2,"live_utc",return_value="2026-09-21T08:00:00Z"),
              patch.object(r2.time,"monotonic",side_effect=[0,0.2,0.3]),
              patch.object(r2.time,"sleep")):
            got=r2.wait_outage_rows("ulc01","2026-09-21T07:58:00Z",2,2)
        self.assertEqual([x["source_event_key"] for x in got],["first","second"])
        self.assertEqual(exported.call_count,2)

    def test_outage_confirmed_during_isolation_fails_immediately(self):
        with (patch.object(r2,"outbox_rows",
                           return_value=[row("first",status="confirmed"),row("second")]),
              patch.object(r2,"live_utc",return_value="2026-09-21T08:00:00Z"),
              patch.object(r2.time,"monotonic",side_effect=[0,0.1]),
              patch.object(r2.time,"sleep") as sleeper):
            with self.assertRaisesRegex(RuntimeError,"falsely confirmed"):
                r2.wait_outage_rows("ulc01","2026-09-21T07:58:00Z",2,2)
        sleeper.assert_not_called()


if __name__ == "__main__":
    unittest.main()
