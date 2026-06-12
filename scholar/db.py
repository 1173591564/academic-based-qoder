"""
Scholar Studio — Database layer

Wraps psycopg2 for optional PostgreSQL storage.
When DB is unavailable, falls back to file-only mode.
"""
import json
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from . import config


def _try_import_psycopg2():
    try:
        import psycopg2
        import psycopg2.extras
        return psycopg2
    except ImportError:
        return None


class Database:
    """PostgreSQL database interface with file-only fallback."""

    def __init__(self):
        self.psycopg2 = _try_import_psycopg2()
        self._conn = None

    @property
    def available(self) -> bool:
        if self.psycopg2 is None:
            return False
        # Use a fresh throwaway connection so we never cache a dead one
        try:
            conn = self.psycopg2.connect(
                host=config.PG_HOST, port=config.PG_PORT,
                dbname=config.PG_NAME, user=config.PG_USER, password=config.PG_PASS,
            )
            conn.close()
            return True
        except Exception:
            return False

    def _connect(self):
        if self._conn is not None:
            try:
                self._conn.ping()
                return self._conn
            except Exception:
                self._conn = None
        self._conn = self.psycopg2.connect(
            host=config.PG_HOST,
            port=config.PG_PORT,
            dbname=config.PG_NAME,
            user=config.PG_USER,
            password=config.PG_PASS,
        )
        return self._conn

    @contextmanager
    def cursor(self):
        conn = self._connect()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

    # -----------------------------------------------------------
    # Paper operations
    # -----------------------------------------------------------

    def upsert_paper(self, data: dict):
        """Insert or update a paper record."""
        with self.cursor() as cur:
            cur.execute(
                """
                INSERT INTO papers (
                    id, title, authors, year, venue, abstract,
                    arxiv_id, doi,
                    has_tex, parsed_ok, parsed_path,
                    section_count, formula_count, citation_count
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (id) DO UPDATE SET
                    title = EXCLUDED.title,
                    authors = EXCLUDED.authors,
                    year = EXCLUDED.year,
                    venue = EXCLUDED.venue,
                    abstract = EXCLUDED.abstract,
                    arxiv_id = COALESCE(EXCLUDED.arxiv_id, papers.arxiv_id),
                    doi = COALESCE(EXCLUDED.doi, papers.doi),
                    has_tex = EXCLUDED.has_tex,
                    parsed_ok = EXCLUDED.parsed_ok,
                    parsed_path = EXCLUDED.parsed_path,
                    section_count = EXCLUDED.section_count,
                    formula_count = EXCLUDED.formula_count,
                    citation_count = EXCLUDED.citation_count,
                    updated_at = NOW()
                """,
                (
                    data["paper_id"],
                    data.get("title"),
                    data.get("authors", []),
                    data.get("year"),
                    data.get("venue"),
                    data.get("abstract"),
                    data.get("arxiv_id"),
                    data.get("doi"),
                    data.get("has_tex", True),
                    data.get("parsed_ok", True),
                    data.get("parsed_path"),
                    data.get("section_count", 0),
                    data.get("formula_count", 0),
                    data.get("citation_count", 0),
                ),
            )

    def upsert_sections(self, paper_id: str, sections: list[dict]):
        """Replace sections for a paper."""
        with self.cursor() as cur:
            cur.execute("DELETE FROM sections WHERE paper_id = %s", (paper_id,))
            for s in sections:
                cur.execute(
                    """
                    INSERT INTO sections (paper_id, heading, level, content, position)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (paper_id, s.get("heading"), s.get("level", 1),
                     s.get("content", ""), s.get("position", 0)),
                )

    def upsert_formulas(self, paper_id: str, formulas: list[dict]):
        """Replace formulas for a paper."""
        with self.cursor() as cur:
            cur.execute("DELETE FROM formulas WHERE paper_id = %s", (paper_id,))
            for f in formulas:
                cur.execute(
                    """
                    INSERT INTO formulas (paper_id, latex, label, env_type, context)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (paper_id, f.get("latex"), f.get("label"),
                     f.get("env_type"), f.get("context")),
                )

    def upsert_citations(self, paper_id: str, citations: list[str]):
        """Replace citations for a paper."""
        with self.cursor() as cur:
            cur.execute("DELETE FROM citations WHERE from_paper = %s", (paper_id,))
            for ref in citations:
                cur.execute(
                    """
                    INSERT INTO citations (from_paper, to_ref)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (paper_id, ref),
                )

    def ingest_paper(self, data: dict):
        """Full ingest: paper + sections + formulas + citations."""
        self.upsert_paper(data)
        self.upsert_sections(data["paper_id"], data.get("sections", []))
        self.upsert_formulas(data["paper_id"], data.get("formulas", []))
        self.upsert_citations(data["paper_id"], data.get("citations", []))

    # -----------------------------------------------------------
    # Query operations
    # -----------------------------------------------------------

    def get_paper(self, paper_id: str) -> Optional[dict]:
        with self.cursor() as cur:
            cur.execute("SELECT * FROM papers WHERE id = %s", (paper_id,))
            row = cur.fetchone()
            if row:
                cols = [desc[0] for desc in cur.description]
                return dict(zip(cols, row))
        return None

    def list_papers(self, year: Optional[int] = None,
                    read_status: Optional[str] = None) -> list[dict]:
        with self.cursor() as cur:
            query = "SELECT * FROM papers WHERE 1=1"
            params = []
            if year:
                query += " AND year = %s"
                params.append(year)
            if read_status:
                query += " AND read_status = %s"
                params.append(read_status)
            query += " ORDER BY year DESC, title"
            cur.execute(query, params)
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def search_papers(self, keyword: str) -> list[dict]:
        with self.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT p.* FROM papers p
                LEFT JOIN sections s ON s.paper_id = p.id
                WHERE p.title ILIKE %s
                   OR p.abstract ILIKE %s
                   OR s.content ILIKE %s
                ORDER BY p.year DESC
                LIMIT 50
                """,
                (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"),
            )
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def get_stats(self) -> dict:
        with self.cursor() as cur:
            stats = {}
            cur.execute("SELECT COUNT(*) FROM papers")
            stats["total_papers"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM papers WHERE parsed_ok = TRUE")
            stats["parsed_papers"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM sections")
            stats["total_sections"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM formulas")
            stats["total_formulas"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM citations")
            stats["total_citations"] = cur.fetchone()[0]
            cur.execute(
                "SELECT MIN(year), MAX(year) FROM papers WHERE year IS NOT NULL"
            )
            row = cur.fetchone()
            stats["year_range"] = f"{row[0]}-{row[1]}" if row[0] else "N/A"
            return stats


# ---------------------------------------------------------------
# File-only fallback: save/load parsed JSON
# ---------------------------------------------------------------

def save_parsed(data: dict, parsed_dir: Path = None):
    """Save parsed paper data to a JSON file."""
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR
    parsed_dir.mkdir(exist_ok=True)
    out_path = parsed_dir / f"{data['paper_id']}.json"
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def load_parsed(paper_id: str, parsed_dir: Path = None) -> Optional[dict]:
    """Load parsed paper data from JSON."""
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR
    path = parsed_dir / f"{paper_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def list_parsed(parsed_dir: Path = None) -> list[str]:
    """List all parsed paper IDs."""
    if parsed_dir is None:
        parsed_dir = config.PARSED_DIR
    return [p.stem for p in parsed_dir.glob("*.json")]
