"""
AkyelIA - Couche d'abstraction Base de Données
Support SQLite (local) + PostgreSQL (Render.com)
"""
import os
import re
from pathlib import Path
from typing import Optional

# Détection du mode PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "")
IS_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith("postgres"))

# Pool PostgreSQL global (lazy init)
_pg_pool = None


def _convert_sql(sql: str) -> str:
    """Convert SQLite ? placeholders to PostgreSQL $N style."""
    if not IS_POSTGRES:
        return sql
    count = 0
    def _replacer(m):
        nonlocal count
        count += 1
        return f"${count}"
    return re.sub(r"\?", _replacer, sql)


def _adapt_schema(sql_script: str) -> list[str]:
    """
    Adapt SQL schema from SQLite dialect to PostgreSQL.
    Returns a list of individual SQL statements.
    """
    if not IS_POSTGRES:
        # SQLite: execute as-is with executescript
        return [sql_script]

    statements = []
    for stmt in sql_script.split(";"):
        stmt = stmt.strip()
        if not stmt:
            continue
        
        # INTEGER PRIMARY KEY AUTOINCREMENT → SERIAL PRIMARY KEY
        stmt = re.sub(
            r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
            "SERIAL PRIMARY KEY",
            stmt,
            flags=re.IGNORECASE,
        )
        
        statements.append(stmt + ";")
    
    return statements


class RowProxy:
    """Dict-like wrapper for asyncpg Row objects, compatible with aiosqlite.Row."""
    def __init__(self, row):
        self._row = row
    
    def __getitem__(self, key):
        return self._row[key]
    
    def __getattr__(self, key):
        try:
            return self._row[key]
        except (KeyError, IndexError):
            raise AttributeError(key)
    
    def __setitem__(self, key, value):
        pass

    def items(self):
        return {k: self._row[k] for k in dict(self._row).keys()}.items()
    
    def keys(self):
        return list(dict(self._row).keys())
    
    def values(self):
        return list(dict(self._row).values())

    def __iter__(self):
        return iter(dict(self._row).keys())

    def __contains__(self, key):
        return key in dict(self._row)


class Cursor:
    """Compatible cursor wrapper for asyncpg results.
    Matches aiosqlite.Cursor API so app.py doesn't need changes."""
    def __init__(self, rows=None, lastrowid=None):
        self._rows = rows or []
        self._index = 0
        self.lastrowid = lastrowid
    
    async def fetchone(self):
        if self._index < len(self._rows):
            row = self._rows[self._index]
            self._index += 1
            return RowProxy(row) if not isinstance(row, RowProxy) else row
        return None
    
    async def fetchall(self):
        result = []
        for row in self._rows:
            result.append(RowProxy(row) if not isinstance(row, RowProxy) else row)
        self._index = len(self._rows)
        return result
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        row = await self.fetchone()
        if row is None:
            raise StopAsyncIteration
        return row


class Database:
    """
    Database handle wrapping aiosqlite (SQLite) or asyncpg (PostgreSQL).
    
    Usage:
        db = await Database.open()
        try:
            row = await db.fetchone("SELECT * FROM ... WHERE id = ?", (id,))
            rows = await db.fetchall("SELECT * FROM ...")
            await db.execute("INSERT INTO ...", (val,))
            await db.commit()
        finally:
            await db.close()
    """

    def __init__(self):
        self._conn = None
        self._is_pg = IS_POSTGRES
        self._lastrowid = None

    @classmethod
    async def open(cls):
        """Create and open a new database connection."""
        db = cls()
        if db._is_pg:
            await db._open_pg()
        else:
            await db._open_sqlite()
        return db

    async def _open_pg(self):
        global _pg_pool
        import asyncpg

        if _pg_pool is None:
            _pg_pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=1,
                max_size=10,
                command_timeout=60,
            )
        self._conn = await _pg_pool.acquire()

    async def _open_sqlite(self):
        import aiosqlite

        db_path = os.getenv("DB_PATH", "akyelia.db")
        # If relative, resolve relative to project root
        if not os.path.isabs(db_path):
            db_path = str(Path(__file__).parent / db_path)
        
        self._conn = await aiosqlite.connect(db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

    async def close(self):
        """Close the database connection."""
        if self._conn is None:
            return
        if self._is_pg:
            if _pg_pool is not None:
                await _pg_pool.release(self._conn)
        else:
            await self._conn.close()
        self._conn = None

    async def execute(self, sql: str, params: tuple = ()):
        """Execute a SQL statement. Returns a Cursor for SELECT, else None."""
        self._lastrowid = None
        if self._is_pg:
            sql = _convert_sql(sql)
            upper = sql.strip().upper()
            # SELECT / WITH queries → return a Cursor with results
            if upper.startswith("SELECT") or upper.startswith("WITH"):
                if params:
                    rows = await self._conn.fetch(sql, *params)
                else:
                    rows = await self._conn.fetch(sql)
                return Cursor(rows=rows)
            # INSERT → use RETURNING id to get the row ID
            if upper.startswith("INSERT"):
                insert_sql = sql.rstrip().rstrip(";") + " RETURNING id"
                if params:
                    row = await self._conn.fetchrow(insert_sql, *params)
                else:
                    row = await self._conn.fetchrow(insert_sql)
                if row:
                    self._lastrowid = row["id"]
                return Cursor(lastrowid=self._lastrowid)
            # UPDATE/DELETE
            if params:
                await self._conn.execute(sql, *params)
            else:
                await self._conn.execute(sql)
            return Cursor()
        else:
            # SQLite: capture lastrowid from the cursor
            cursor = await self._conn.execute(sql, params)
            if cursor.lastrowid:
                self._lastrowid = cursor.lastrowid
            return cursor

    async def executescript(self, sql_script: str):
        """Execute multiple SQL statements (CREATE TABLE, etc.)."""
        if self._is_pg:
            statements = _adapt_schema(sql_script)
            for stmt in statements:
                if stmt.strip().rstrip(";"):
                    stmt_converted = _convert_sql(stmt)
                    await self._conn.execute(stmt_converted)
        else:
            await self._conn.executescript(sql_script)

    async def fetchone(self, sql: str, params: tuple = ()):
        """Fetch a single row."""
        if self._is_pg:
            sql = _convert_sql(sql)
            row = await (self._conn.fetchrow(sql, *params) if params else self._conn.fetchrow(sql))
            if row is None:
                return None
            # Wrap in RowProxy for dict-like access (compatible with aiosqlite.Row)
            return RowProxy(row)
        else:
            cursor = await self._conn.execute(sql, params)
            return await cursor.fetchone()

    async def fetchall(self, sql: str, params: tuple = ()):
        """Fetch all rows."""
        if self._is_pg:
            sql = _convert_sql(sql)
            rows = await (self._conn.fetch(sql, *params) if params else self._conn.fetch(sql))
            return [RowProxy(r) for r in rows]
        else:
            cursor = await self._conn.execute(sql, params)
            return await cursor.fetchall()

    async def commit(self):
        """Commit transaction (no-op for PostgreSQL - auto-commit)."""
        if not self._is_pg:
            await self._conn.commit()

    @property
    def lastrowid(self):
        """Get last inserted row ID."""
        return self._lastrowid

    async def execute_insert_returning(self, sql: str, params: tuple = ()):
        """
        Execute INSERT with RETURNING * support.
        For PostgreSQL: uses RETURNING clause.
        For SQLite: executes and returns lastrowid.
        """
        if self._is_pg:
            sql = _convert_sql(sql)
            row = await (self._conn.fetchrow(sql, *params) if params else self._conn.fetchrow(sql))
            if row is None:
                return None
            return RowProxy(row)
        else:
            cursor = await self._conn.execute(sql, params)
            return cursor.lastrowid


# ============================================
# Global DB helper for initialization
# ============================================
async def init_database():
    """Initialize database schema."""
    db = await Database.open()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'Nouvelle conversation',
                provider TEXT NOT NULL DEFAULT 'deepseek',
                model TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                provider TEXT,
                model TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at DESC);

            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                repo_url TEXT NOT NULL,
                description TEXT DEFAULT '',
                author TEXT DEFAULT '',
                installed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                enabled INTEGER DEFAULT 1,
                skill_path TEXT NOT NULL,
                repo_full_name TEXT DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name);

            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                system_prompt TEXT DEFAULT '',
                provider TEXT DEFAULT 'omniroute',
                model TEXT DEFAULT '',
                temperature REAL DEFAULT 0.7,
                max_tokens INTEGER DEFAULT 4096,
                icon TEXT DEFAULT '🤖',
                color TEXT DEFAULT '#7c3aed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_agents_updated ON agents(updated_at DESC);

            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                language TEXT DEFAULT '',
                icon TEXT DEFAULT '📁',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at DESC);

            CREATE TABLE IF NOT EXISTS project_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                path TEXT NOT NULL,
                content TEXT DEFAULT '',
                language TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                UNIQUE(project_id, path)
            );
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                context TEXT DEFAULT '',
                source_conv_id TEXT DEFAULT '',
                importance INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_recalled_at TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
            CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC);
            CREATE INDEX IF NOT EXISTS idx_project_files_path ON project_files(project_id, path);
        """)
        await db.commit()
        print(f"[DB] Base de données initialisée ({'IS_POSTGRES' if IS_POSTGRES else 'SQLite'})")
    finally:
        await db.close()
