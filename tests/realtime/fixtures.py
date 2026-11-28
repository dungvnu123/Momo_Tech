import json
import unittest
import test_backend_integration as fixtures
from app.ai.service import AIService
from app.ai.realtime.service import RealtimeService
from app.backend.events import ensure_schema, publish
from app.backend.store import Tools
from app.security import hash_pin
from .clients import RealtimeClient


class RealtimeFixture(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.BackendIntegrationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.store = Tools(self.fixture.database)
        self.addCleanup(self.store.db.close)
        for name, kind in {
            "day": "TEXT",
            "kind": "TEXT",
            "transfer_id": "TEXT",
            "title": "TEXT",
            "reason": "TEXT",
            "severity": "TEXT",
            "priority": "REAL",
            "confidence": "REAL",
            "size": "INT",
            "n_reports": "INT",
            "suspected_type": "TEXT",
            "latest": "BOOLEAN DEFAULT TRUE",
        }.items():
            self.store.run(f"ALTER TABLE alerts ADD COLUMN {name} {kind}")
        self.store.db.executescript(
            "\n            CREATE TABLE khach_accounts(phone TEXT PRIMARY KEY,app_id TEXT,display_name TEXT,pin_salt BYTEA,pin_hash BYTEA,balance BIGINT);\n            CREATE TABLE khach_loans(loan_id SERIAL PRIMARY KEY,phone TEXT,amount BIGINT,disbursed_at TEXT);\n            CREATE TABLE khach_transfers(tx_id SERIAL PRIMARY KEY,phone TEXT,ts TEXT,to_type TEXT,to_id TEXT,to_bank TEXT,to_name TEXT,\n                amount BIGINT,note TEXT,decision TEXT,reasons TEXT,status TEXT);\n            CREATE TABLE khach_contacts(phone TEXT,contact_phone TEXT,name TEXT,saved_at TEXT,PRIMARY KEY(phone,contact_phone));\n            CREATE TABLE khach_inbox(msg_id SERIAL PRIMARY KEY,phone TEXT,ts TEXT,sender TEXT,body TEXT,kind TEXT,is_read BOOLEAN,reported_verdict TEXT);\n            CREATE TABLE simo_list(to_id TEXT PRIMARY KEY);\n            CREATE TABLE ring_accounts(to_id TEXT,cid TEXT,verdict TEXT,n_senders INT);\n        "
        )
        ensure_schema(self.store)
        salt = b"fixed-test-salt!"
        self.store.run(
            "INSERT INTO khach_accounts VALUES (?,?,?,?,?,?)",
            "0900000001",
            "A",
            "PRIVATE NAME",
            salt,
            hash_pin("123456", salt),
            10000000,
        )
        self.graph = self.fixture.database.parent / "live-graph.db"
        self.client = RealtimeClient()
        self.service = RealtimeService(
            self.fixture.database,
            self.graph,
            AIService(self.client),
            self.client,
            max_per_minute=100,
        )

    def loan(self, amount=2000000, at="2026-11-01T09:01:00"):
        return self.store.q(
            "INSERT INTO khach_loans(phone,app_id,amount,disbursed_at) VALUES ('0900000001','A',?,?) RETURNING loan_id",
            amount,
            at,
        )[0]["loan_id"]

    def transfer(self, loan_id, *, status="held", at="2026-11-01T09:02:00", amount=500000):
        context = json.dumps(
            {
                "loan_id": loan_id,
                "loan_amount": 2000000,
                "minutes_after_disbursal": 1,
                "simo_flag": False,
                "recipient_in_contacts": False,
                "prior_transfers_to_recipient": 0,
            }
        )
        tx = self.store.q(
            "INSERT INTO khach_transfers(phone,ts,to_type,to_id,to_bank,to_name,amount,note,decision,reasons,status,app_id,loan_id,context) VALUES ('0900000001',?,'bank','001234567890','ACB','PRIVATE RECIPIENT',?,'',?,'[]',?,'A',?,?) RETURNING tx_id",
            at,
            amount,
            "hold" if status == "held" else "allow",
            status,
            loan_id,
            context,
        )[0]["tx_id"]
        return "KT" + str(tx)

    def event(self, transfer_id, *, simulated=False):
        publish(
            self.store, "transfer", transfer_id, "A", "2026-11-01T09:02:00", simulated=simulated
        )
