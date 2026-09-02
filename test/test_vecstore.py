"""test_vecstore.py — 论文级向量层：内容指纹/增量计划/SQL 组装（FakePG 注入）。"""

import hashlib

import pytest

from scholar import vecstore
from scholar.vecstore import (
    EmbedUnavailable,
    paper_vector_content,
    plan_vector_updates,
)


def _md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


class FakeCursor:
    def __init__(self, parent):
        self.parent = parent
        self.executed: list[tuple[str, object]] = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if "SELECT to_regclass" in sql:
            self._last = [("available",)]
        elif "SELECT EXISTS" in sql:
            self._last = [(True,)]
        elif "SELECT paper_id, content_md5" in sql:
            self._last = [(pid, md5) for pid, md5 in self.parent.existing.items()]
        elif "FROM paper_vectors" in sql and "similarity" in sql:
            self._last = [("01KA", 0.9123), ("01KB", 0.8001)]
        elif "FROM chunks" in sql:
            self._last = [("01KA", "Abstract", "[t] chunk text", 0.7)]
        else:
            self._last = []

    def fetchall(self):
        return getattr(self, "_last", [])

    def fetchone(self):
        rows = getattr(self, "_last", [])
        return rows[0] if rows else None

    def close(self):
        pass


class FakeConn:
    def __init__(self, existing=None):
        self.existing = existing or {}
        self.committed = 0
        self.closed = False
        self.cursor_obj = FakeCursor(self)

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed += 1

    def close(self):
        self.closed = True


@pytest.fixture()
def fake_pg(monkeypatch):
    conn = FakeConn()
    monkeypatch.setattr(vecstore, "_connect", lambda: conn)
    return conn


# ── 纯函数 ──────────────────────────────────────────────────────────────────


def test_paper_vector_content_format():
    c = paper_vector_content({"title": "My Paper", "abstract": "  does things  "})
    assert c == "[My Paper] does things"
    long = paper_vector_content({"title": "T", "abstract": "x" * 5000})
    assert len(long) == 2000


def test_plan_vector_updates():
    items = {"A": "h1", "B": "h2", "C": "h3"}
    existing = {"A": "h1", "B": "old", "D": "gone"}
    to_embed, deleted = plan_vector_updates(items, existing)
    assert to_embed == {"B": "h2", "C": "h3"}
    assert deleted == ["D"]


# ── ensure_paper_vectors（FakePG）────────────────────────────────────────────


def _write_parsed(tmp_path, pid, title, abstract):
    import json

    d = tmp_path / "parsed"
    d.mkdir(exist_ok=True)
    content = paper_vector_content({"title": title, "abstract": abstract})
    (d / f"{pid}.json").write_text(
        json.dumps({"paper_id": pid, "title": title, "abstract": abstract}),
        encoding="utf-8",
    )
    return _md5(content)


def test_ensure_paper_vectors_incremental(tmp_path, fake_pg):
    md5_a = _write_parsed(tmp_path, "01KA", "Paper A", "abstract A")
    md5_b = _write_parsed(tmp_path, "01KB", "Paper B", "abstract B")
    fake_pg.existing = {"01KA": md5_a, "01KZ": _md5("[Gone] old")}

    stats = vecstore.ensure_paper_vectors(
        tmp_path / "parsed", embed_fn=lambda t: [0.1] * 4
    )
    assert stats["total"] == 2
    assert stats["skipped"] == 1  # 01KA 未变
    assert stats["deleted"] == 1  # 01KZ 移除
    assert stats["errors"] == 0
    assert stats["embedded"] == 1  # 01KB 新增
    deletes = [
        p
        for sql, p in fake_pg.cursor_obj.executed
        if sql.startswith("DELETE FROM paper_vectors")
    ]
    assert deletes == [("01KZ",)]
    inserts = [p for sql, p in fake_pg.cursor_obj.executed if "ON CONFLICT" in sql]
    assert len(inserts) == 1 and inserts[0][0] == "01KB"


def test_ensure_paper_vectors_embed_failure_counted(tmp_path, fake_pg):
    _write_parsed(tmp_path, "01KA", "Paper A", "abstract A")
    stats = vecstore.ensure_paper_vectors(tmp_path / "parsed", embed_fn=lambda t: None)
    assert stats["errors"] == 1 and stats["embedded"] == 0


def test_ensure_paper_vectors_force_wipes(tmp_path, fake_pg):
    _write_parsed(tmp_path, "01KA", "Paper A", "abstract A")
    fake_pg.existing = {"01KA": "stale-md5"}
    stats = vecstore.ensure_paper_vectors(
        tmp_path / "parsed", embed_fn=lambda t: [0.2] * 4, force=True
    )
    assert stats["skipped"] == 0 and stats["embedded"] == 1
    wipes = [
        sql
        for sql, _ in fake_pg.cursor_obj.executed
        if sql == "DELETE FROM paper_vectors"
    ]
    assert len(wipes) == 1


# ── 检索路径 ────────────────────────────────────────────────────────────────


def test_search_papers_semantic_rows(fake_pg):
    rows = vecstore.search_papers_semantic(
        "how to balance MoE", k=2, embed_fn=lambda t: [0.3] * 4
    )
    assert rows[0]["paper_id"] == "01KA"
    assert rows[0]["similarity"] == 0.9123
    assert len(rows) == 2


def test_search_papers_semantic_no_embed(fake_pg):
    with pytest.raises(EmbedUnavailable):
        vecstore.search_papers_semantic("q", embed_fn=lambda t: None)


def test_search_papers_semantic_empty_query(fake_pg):
    assert vecstore.search_papers_semantic("  ", embed_fn=lambda t: [0.1]) == []


def test_search_passages_filters(fake_pg):
    rows = vecstore.search_passages(
        "attention", k=5, paper_id="01KA", section="Opt", embed_fn=lambda t: [0.4] * 4
    )
    assert rows and rows[0]["paper_id"] == "01KA"
    sqls = " ".join(sql for sql, _ in fake_pg.cursor_obj.executed)
    assert "paper_id = %s" in sqls and "section ILIKE %s" in sqls
    # 参数顺序：emb, emb, paper_id, section_like, k
    params = [
        p
        for sql, p in fake_pg.cursor_obj.executed
        if "FROM chunks" in sql and "similarity" in sql
    ][0]
    assert params[0].startswith("[") and params[2] == "01KA"
    assert params[3] == "%Opt%" and params[4] == 5


def test_search_passages_no_filters(fake_pg):
    vecstore.search_passages("q", embed_fn=lambda t: [0.5] * 4)
    sqls = [sql for sql, _ in fake_pg.cursor_obj.executed if "FROM chunks" in sql]
    assert "WHERE" not in sqls[0]
