"""Unified Repository layer: DemoRepository (in-memory seed) and SQLServerRepository (pyodbc).

Both implement the same generic operations so every service/authorization rule runs
unchanged in either mode. No DDL is ever executed.
"""
import copy
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager

from . import schema
from .fixtures import load_seed


def _check_table(table, cols=()):
    meta = schema.TABLES.get(table)
    if meta is None:
        raise ValueError("unknown table")
    allowed = set(meta["cols"]) | {meta["pk"]}
    for c in cols:
        if c not in allowed:
            raise ValueError("unknown column")
    return meta


class Repository(ABC):
    mode = "unknown"

    @abstractmethod
    def select(self, table, where=None, order_by=None): ...
    @abstractmethod
    def get(self, table, pk): ...
    @abstractmethod
    def insert(self, table, row): ...
    @abstractmethod
    def update(self, table, pk, fields): ...
    @abstractmethod
    def transaction(self): ...
    @abstractmethod
    def health(self): ...

    def reset(self):
        raise NotImplementedError("reset is only available in demo mode")

    def one(self, table, where):
        rows = self.select(table, where)
        return rows[0] if rows else None


def _match(row, where):
    for col, val in (where or {}).items():
        if isinstance(val, (list, tuple, set)):
            if row.get(col) not in val:
                return False
        elif row.get(col) != val:
            return False
    return True


class DemoRepository(Repository):
    mode = "demo"

    def __init__(self):
        self._lock = threading.RLock()
        self.reset()

    def reset(self):
        with self._lock:
            self._data = {t: {r[schema.TABLES[t]["pk"]]: self._full(t, r) for r in rows}
                          for t, rows in load_seed().items()}
            self._seq = {t: max(rows.keys(), default=0) for t, rows in self._data.items()}
            for t in schema.TABLES:
                self._data.setdefault(t, {})
                self._seq.setdefault(t, 0)

    @staticmethod
    def _full(table, row):
        meta = schema.TABLES[table]
        out = {c: None for c in meta["cols"]}
        for c, d in meta["defaults"].items():
            out[c] = d() if callable(d) else d
        out.update(row)
        out[meta["pk"]] = row[meta["pk"]]
        return out

    def select(self, table, where=None, order_by=None):
        meta = _check_table(table, (where or {}).keys())
        rows = [copy.deepcopy(r) for r in self._data[table].values() if _match(r, where)]
        key = order_by or meta["pk"]
        desc = key.startswith("-")
        key = key.lstrip("-")
        rows.sort(key=lambda r: (r.get(key) is None, r.get(key)), reverse=desc)
        return rows

    def get(self, table, pk):
        _check_table(table)
        r = self._data[table].get(pk)
        return copy.deepcopy(r) if r else None

    def insert(self, table, row):
        meta = _check_table(table, row.keys())
        with self._lock:
            new = self._full(table, {meta["pk"]: None, **row})
            schema.validate_row(table, {k: v for k, v in new.items() if k != meta["pk"]})
            self._enforce_unique(table, new)
            self._seq[table] += 1
            new[meta["pk"]] = self._seq[table]
            self._data[table][new[meta["pk"]]] = new
            return new[meta["pk"]]

    def update(self, table, pk, fields):
        _check_table(table, fields.keys())
        with self._lock:
            cur = self._data[table].get(pk)
            if cur is None:
                raise ValueError("row not found")
            merged = {**cur, **fields}
            schema.validate_row(table, {k: v for k, v in merged.items() if k != schema.TABLES[table]["pk"]})
            self._data[table][pk] = merged

    def _enforce_unique(self, table, new):
        uniq = {"users": ["national_id", "username"], "cases": ["case_number"],
                "government_entities": ["entity_code"]}.get(table, [])
        for c in uniq:
            if any(r[c] == new[c] for r in self._data[table].values()):
                raise ValueError(f"UNIQUE violated {table}.{c}")

    @contextmanager
    def transaction(self):
        with self._lock:
            snap = (copy.deepcopy(self._data), dict(self._seq))
            try:
                yield self
            except BaseException:
                self._data, self._seq = snap
                raise

    def health(self):
        return True, "demo"


class SQLServerRepository(Repository):
    """pyodbc implementation. Parameterized SQL only; table/column names are whitelisted."""
    mode = "sqlserver"

    def __init__(self, settings):
        import pyodbc  # imported lazily: absent in some environments -> demo fallback
        self._pyodbc = pyodbc
        self._s = settings
        self._local = threading.local()
        parts = [f"DRIVER={{{settings.sql_driver}}}",
                 f"SERVER={settings.sql_host},{settings.sql_port}",
                 f"DATABASE={settings.sql_database}",
                 f"UID={settings.sql_username}", f"PWD={settings.sql_password}",
                 "Encrypt=yes", f"TrustServerCertificate={'yes' if settings.sql_trust_cert else 'no'}",
                 f"Connection Timeout={settings.sql_timeout}"]
        self._cs = ";".join(parts)
        pyodbc.pooling = True
        c = self._connect()  # fail fast
        c.close()

    def _connect(self):
        return self._pyodbc.connect(self._cs, autocommit=True, timeout=self._s.sql_timeout)

    @contextmanager
    def _cursor(self):
        conn = getattr(self._local, "tx_conn", None)
        if conn is not None:
            cur = conn.cursor()
            try:
                yield cur
            finally:
                cur.close()
            return
        conn = self._connect()
        try:
            cur = conn.cursor()
            yield cur
        finally:
            conn.close()

    @staticmethod
    def _rows(cur):
        cols = [d[0] for d in cur.description]
        out = []
        for r in cur.fetchall():
            d = dict(zip(cols, r))
            for k, v in d.items():
                if isinstance(v, bool):
                    d[k] = int(v)
            out.append(d)
        return out

    def select(self, table, where=None, order_by=None):
        meta = _check_table(table, (where or {}).keys())
        sql, params, clauses = f"SELECT * FROM {table}", [], []
        for col, val in (where or {}).items():
            if isinstance(val, (list, tuple, set)):
                vals = list(val)
                if not vals:
                    return []
                clauses.append(f"{col} IN ({','.join('?' * len(vals))})")
                params += vals
            elif val is None:
                clauses.append(f"{col} IS NULL")
            else:
                clauses.append(f"{col} = ?")
                params.append(val)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        key = order_by or meta["pk"]
        direction = "DESC" if key.startswith("-") else "ASC"
        _check_table(table, [key.lstrip("-")])
        sql += f" ORDER BY {key.lstrip('-')} {direction}"
        with self._cursor() as cur:
            cur.execute(sql, params)
            return self._rows(cur)

    def get(self, table, pk):
        meta = _check_table(table)
        with self._cursor() as cur:
            cur.execute(f"SELECT * FROM {table} WHERE {meta['pk']} = ?", [pk])
            rows = self._rows(cur)
            return rows[0] if rows else None

    def insert(self, table, row):
        meta = _check_table(table, row.keys())
        cols = list(row.keys())
        sql = (f"INSERT INTO {table} ({','.join(cols)}) OUTPUT INSERTED.{meta['pk']} "
               f"VALUES ({','.join('?' * len(cols))})")
        with self._cursor() as cur:
            cur.execute(sql, [row[c] for c in cols])
            return int(cur.fetchone()[0])

    def update(self, table, pk, fields):
        meta = _check_table(table, fields.keys())
        cols = list(fields.keys())
        sql = f"UPDATE {table} SET {','.join(c + ' = ?' for c in cols)} WHERE {meta['pk']} = ?"
        with self._cursor() as cur:
            cur.execute(sql, [fields[c] for c in cols] + [pk])

    @contextmanager
    def transaction(self):
        conn = self._pyodbc.connect(self._cs, autocommit=False, timeout=self._s.sql_timeout)
        self._local.tx_conn = conn
        try:
            yield self
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            self._local.tx_conn = None
            conn.close()

    def health(self):
        try:
            with self._cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            return True, "sqlserver"
        except Exception:
            return False, "تعذّر الاتصال بقاعدة البيانات"


class DataModeError(RuntimeError):
    pass


def build_repository(settings):
    """Resolve DATA_MODE=auto|sqlserver|demo. Returns (repo, note)."""
    mode = settings.data_mode
    if mode not in ("auto", "sqlserver", "demo"):
        raise DataModeError("قيمة DATA_MODE غير صالحة (auto | sqlserver | demo)")
    if mode == "demo":
        return DemoRepository(), "DATA_MODE=demo"
    try:
        if not settings.sql_host:
            raise DataModeError("SQL_SERVER_HOST غير مضبوط")
        return SQLServerRepository(settings), "connected"
    except Exception as exc:  # driver missing, network, auth...
        if mode == "sqlserver":
            raise DataModeError(
                "DATA_MODE=sqlserver لكن الاتصال فشل. تحقق من SQL_SERVER_* ومن توفر ODBC Driver 18 "
                "ومن إتاحة الشبكة بشكل آمن.") from exc
        return DemoRepository(), "auto: SQL Server unavailable -> demo"
