"""SQLServerRepository against a fake pyodbc (no real SQL Server available here).

Verifies: parameterized SQL, identifier whitelisting, transaction commit/rollback.
It does NOT prove the live connection works.
"""
import sys
import types

import pytest

from app.config import Settings


class FakeCursor:
    def __init__(self, log):
        self.log, self.description, self._rows = log, [("user_id",), ("is_active",)], [(1, True)]

    def execute(self, sql, params=None):
        self.log.append((sql, list(params or [])))

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return (7,)

    def close(self):
        pass


class FakeConn:
    def __init__(self, log, autocommit):
        self.log, self.autocommit = log, autocommit

    def cursor(self):
        return FakeCursor(self.log)

    def commit(self):
        self.log.append(("COMMIT", []))

    def rollback(self):
        self.log.append(("ROLLBACK", []))

    def close(self):
        pass


@pytest.fixture()
def repo(monkeypatch):
    log = []
    fake = types.SimpleNamespace(pooling=True, connect=lambda cs, autocommit=True, timeout=5: FakeConn(log, autocommit))
    monkeypatch.setitem(sys.modules, "pyodbc", fake)
    from app.repositories import SQLServerRepository
    s = Settings()
    s.sql_host = "h"
    r = SQLServerRepository(s)
    r.log = log
    return r


def test_select_is_parameterized(repo):
    rows = repo.select("users", {"national_id": "x' OR 1=1 --", "role": ["CITIZEN", "LAWYER"]})
    sql, params = repo.log[-1]
    assert "x' OR" not in sql and params == ["x' OR 1=1 --", "CITIZEN", "LAWYER"]
    assert "IN (?,?)" in sql and rows == [{"user_id": 1, "is_active": 1}]


def test_identifiers_whitelisted(repo):
    for bad in (lambda: repo.select("users; DROP TABLE users", None), lambda: repo.select("users", {"x=1;--": 1}),
                lambda: repo.insert("users", {"nope": 1}), lambda: repo.update("users", 1, {"a b": 1})):
        with pytest.raises(ValueError):
            bad()


def test_transaction_commit_and_rollback(repo):
    with repo.transaction():
        repo.insert("audit_logs", {"actor_user_id": 1, "case_id": 1, "action_code": "A", "result": "SUCCESS", "details": "d"})
    assert repo.log[-1][0] == "COMMIT"
    with pytest.raises(RuntimeError):
        with repo.transaction():
            repo.update("users", 1, {"is_active": 0})
            raise RuntimeError("x")
    assert repo.log[-1][0] == "ROLLBACK"


def test_auto_falls_back_to_demo_and_sqlserver_mode_fails_loudly(monkeypatch):
    from app.repositories import DataModeError, DemoRepository, build_repository
    monkeypatch.delitem(sys.modules, "pyodbc", raising=False)
    s = Settings()
    s.sql_host = "somehost"
    s.data_mode = "auto"
    repo, note = build_repository(s)
    assert isinstance(repo, DemoRepository) and "demo" in note
    s.data_mode = "sqlserver"
    with pytest.raises(DataModeError):
        build_repository(s)
