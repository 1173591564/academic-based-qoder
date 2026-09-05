"""PostgreSQL execution coverage for scoped passage retrieval."""

import os

import psycopg2
import pytest

from scholar import vecstore


@pytest.fixture
def passage_postgres(monkeypatch):
    dsn = os.getenv("SCHOLAR_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("SCHOLAR_TEST_POSTGRES_DSN is not configured")
    connection = psycopg2.connect(dsn)
    cursor = connection.cursor()
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cursor.execute(
        """
        CREATE TEMP TABLE chunks (
            paper_id TEXT NOT NULL,
            section TEXT,
            content TEXT NOT NULL,
            embedding vector(4) NOT NULL
        )
        """
    )
    cursor.executemany(
        """
        INSERT INTO chunks (paper_id, section, content, embedding)
        VALUES (%s, %s, %s, %s::vector)
        """,
        [
            ("paper-a", "Introduction", "intro evidence", "[1,0,0,0]"),
            ("paper-a", "Optimization", "scoped evidence", "[0,1,0,0]"),
            ("paper-b", "Optimization", "other paper", "[0,1,0,0]"),
        ],
    )
    connection.commit()
    monkeypatch.setattr(vecstore, "_connect", lambda: connection)
    yield connection
    if not connection.closed:
        connection.close()


def test_scoped_passage_query_executes_against_postgres(passage_postgres):
    rows = vecstore.search_passages(
        "scoped",
        paper_id="paper-a",
        section="Opt",
        embed_fn=lambda _text: [0, 1, 0, 0],
    )

    assert rows == [{
        "paper_id": "paper-a",
        "section": "Optimization",
        "content": "scoped evidence",
        "similarity": 1.0,
    }]
