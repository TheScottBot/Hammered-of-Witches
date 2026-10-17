"""The SQLite database: each server's filter levels and hidden passages.

Call init() once at startup (the tests call it with ":memory:"). A server with no rows has the default preset.
"""

import sqlite3

from hammered import content

conn: sqlite3.Connection = None  # type: ignore[assignment]  # Set by init().

SCHEMA = [
    # A server's level for one category, as chosen with /setup. Categories it hasn't set have the default's level.
    """
    CREATE TABLE IF NOT EXISTS filter_levels (
        guild_id INTEGER NOT NULL,
        category TEXT NOT NULL,     -- content.CATEGORIES key, e.g. "lgbt"
        level    INTEGER NOT NULL,  -- 0 off, 1 mild, 2 full
        PRIMARY KEY (guild_id, category)
    )
    """,
    # Passages a server has hidden by hand (/setup hide), whatever its levels.
    """
    CREATE TABLE IF NOT EXISTS hidden_passages (
        guild_id   INTEGER NOT NULL,
        passage_id TEXT NOT NULL,
        PRIMARY KEY (guild_id, passage_id)
    )
    """,
]


def init(path: str) -> None:
    global conn
    conn = sqlite3.connect(path)
    for statement in SCHEMA:
        conn.execute(statement)
    conn.commit()


def limits(guild_id: int | None) -> dict[str, int]:
    """The highest level of each category this server allows. DMs get the default."""
    out = dict(content.DEFAULT.limits)
    if guild_id is not None:
        rows = conn.execute("SELECT category, level FROM filter_levels WHERE guild_id = ?", (guild_id,))
        out.update({category: level for category, level in rows if category in content.BY_KEY})
    return out


def set_level(guild_id: int, category: str, level: int) -> None:
    conn.execute("INSERT INTO filter_levels (guild_id, category, level) VALUES (?, ?, ?) "
                 "ON CONFLICT (guild_id, category) DO UPDATE SET level = excluded.level", (guild_id, category, level))
    conn.commit()


def set_limits(guild_id: int, levels: dict[str, int]) -> None:
    with conn:
        for category, level in levels.items():
            conn.execute("INSERT INTO filter_levels (guild_id, category, level) VALUES (?, ?, ?) "
                         "ON CONFLICT (guild_id, category) DO UPDATE SET level = excluded.level",
                         (guild_id, category, level))


def hidden(guild_id: int | None) -> set[str]:
    if guild_id is None:
        return set()
    return {row[0] for row in conn.execute("SELECT passage_id FROM hidden_passages WHERE guild_id = ?", (guild_id,))}


def hide(guild_id: int, passage_id: str) -> bool:
    """Hide a passage in a server. False if it was already hidden."""
    cursor = conn.execute("INSERT OR IGNORE INTO hidden_passages (guild_id, passage_id) VALUES (?, ?)",
                          (guild_id, passage_id))
    conn.commit()
    return cursor.rowcount > 0


def unhide(guild_id: int, passage_id: str) -> bool:
    """Show a hidden passage again. False if it wasn't hidden."""
    cursor = conn.execute("DELETE FROM hidden_passages WHERE guild_id = ? AND passage_id = ?", (guild_id, passage_id))
    conn.commit()
    return cursor.rowcount > 0


def forget(guild_id: int) -> None:
    """Back to the default preset, with nothing hidden (/setup reset)."""
    with conn:
        conn.execute("DELETE FROM filter_levels WHERE guild_id = ?", (guild_id,))
        conn.execute("DELETE FROM hidden_passages WHERE guild_id = ?", (guild_id,))
