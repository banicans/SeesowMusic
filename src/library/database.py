import os
import random
import sqlite3
from pathlib import Path

from .models import Song, Album, Artist, Playlist, Genre


DB_DIR = Path(os.getenv('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'seesow-music'


def get_db_path():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    return str(DB_DIR / 'library.db')


def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_db():
    conn = get_connection()
    conn.execute('PRAGMA journal_mode=WAL')
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS songs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            path        TEXT UNIQUE NOT NULL,
            title       TEXT NOT NULL,
            artist      TEXT NOT NULL DEFAULT '',
            album       TEXT NOT NULL DEFAULT '',
            track_number INTEGER NOT NULL DEFAULT 0,
            duration    REAL NOT NULL DEFAULT 0.0,
            year        INTEGER NOT NULL DEFAULT 0,
            genre       TEXT NOT NULL DEFAULT '',
            cover_path  TEXT,
            album_artist TEXT NOT NULL DEFAULT '',
            date_added  TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS library_folders (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS playlists (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT NOT NULL,
            created TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS playlist_songs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER NOT NULL,
            song_id     INTEGER NOT NULL,
            position    INTEGER NOT NULL,
            FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS recently_played (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id   INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
            played_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS likes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type   TEXT NOT NULL,
            item_id     TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(item_type, item_id)
        );
    ''')
    # Migration: add album_artist if missing (pre-existing databases)
    try:
        conn.execute('ALTER TABLE songs ADD COLUMN album_artist TEXT NOT NULL DEFAULT \'\'')
    except sqlite3.OperationalError:
        pass
    # Migration: add settings table if missing
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def song_exists(path: str) -> bool:
    conn = get_connection()
    row = conn.execute('SELECT 1 FROM songs WHERE path = ?', (path,)).fetchone()
    conn.close()
    return row is not None


def add_song(song: Song) -> int:
    conn = get_connection()
    try:
        cur = conn.execute('''
            INSERT INTO songs (path, title, artist, album, track_number, duration, year, genre, cover_path, album_artist)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                title=excluded.title, artist=excluded.artist, album=excluded.album,
                track_number=excluded.track_number, duration=excluded.duration,
                year=excluded.year, genre=excluded.genre,
                cover_path=COALESCE(excluded.cover_path, cover_path),
                album_artist=excluded.album_artist
        ''', (song.path, song.title, song.artist, song.album, song.track_number,
              song.duration, song.year, song.genre, song.cover_path, song.album_artist))
        conn.commit()
        return cur.lastrowid or 0
    finally:
        conn.close()


def get_setting(key: str, default: str = '') -> str:
    conn = get_connection()
    row = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    conn.close()
    return row[0] if row else default


def set_setting(key: str, value: str):
    conn = get_connection()
    try:
        conn.execute(
            'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
            (key, value)
        )
        conn.commit()
    finally:
        conn.close()


def get_all_songs() -> list[Song]:
    conn = get_connection()
    rows = conn.execute('SELECT * FROM songs ORDER BY album, track_number').fetchall()
    conn.close()
    return [_row_to_song(r) for r in rows]


def get_songs_by_album(album_title: str, album_artist: str) -> list[Song]:
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM songs WHERE album = ? AND (album_artist = ? OR (album_artist = \'\' AND artist = ?)) ORDER BY track_number',
        (album_title, album_artist, album_artist)
    ).fetchall()
    conn.close()
    return [_row_to_song(r) for r in rows]


def get_albums() -> list[Album]:
    conn = get_connection()
    rows = conn.execute('''
        SELECT album,
               MIN(CASE WHEN album_artist = '' THEN artist ELSE album_artist END),
               MIN(year), MIN(cover_path), COUNT(*)
        FROM songs
        GROUP BY album,
                 CASE WHEN album_artist = '' THEN artist ELSE album_artist END
        ORDER BY album
    ''').fetchall()
    conn.close()
    return [
        Album(title=r[0], artist=r[1], year=r[2], cover_path=r[3], song_count=r[4])
        for r in rows
    ]


def get_favourite_albums(limit: int = 5) -> list[Album]:
    conn = get_connection()
    rows = conn.execute('''
        SELECT s.album,
               MIN(CASE WHEN s.album_artist = '' THEN s.artist ELSE s.album_artist END),
               MIN(s.year), MIN(s.cover_path), COUNT(DISTINCT s.id)
        FROM songs s
        LEFT JOIN recently_played rp ON rp.song_id = s.id
        GROUP BY s.album,
                 CASE WHEN s.album_artist = '' THEN s.artist ELSE s.album_artist END
        ORDER BY COUNT(rp.id) DESC
        LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    return [
        Album(title=r[0], artist=r[1], year=r[2], cover_path=r[3], song_count=r[4])
        for r in rows
    ]


def get_artists() -> list[Artist]:
    sep = get_setting('artist_separator', '')
    conn = get_connection()
    rows = conn.execute(
        'SELECT DISTINCT artist FROM songs WHERE artist != \'\''
    ).fetchall()
    conn.close()
    seen: set[str] = set()
    result: list[Artist] = []
    for (r,) in rows:
        parts = [p.strip() for p in r.split(sep)] if sep else [r.strip()]
        for name in parts:
            if name and name not in seen:
                seen.add(name)
                result.append(Artist(name=name))
    result.sort(key=lambda a: a.name.upper())
    return result


def get_songs_by_artist(artist_name: str) -> list[Song]:
    sep = get_setting('artist_separator', '')
    all_songs = get_all_songs()
    if not sep:
        return [s for s in all_songs if s.artist == artist_name]
    return [
        s for s in all_songs
        if artist_name in [p.strip() for p in s.artist.split(sep)]
    ]


def add_folder(path: str):
    conn = get_connection()
    try:
        conn.execute('INSERT OR IGNORE INTO library_folders (path) VALUES (?)', (path,))
        conn.commit()
    finally:
        conn.close()


def remove_folder(path: str):
    conn = get_connection()
    try:
        conn.execute('DELETE FROM library_folders WHERE path = ?', (path,))
        conn.commit()
    finally:
        conn.close()


def get_folders() -> list[str]:
    conn = get_connection()
    rows = conn.execute('SELECT path FROM library_folders').fetchall()
    conn.close()
    return [r[0] for r in rows]


def song_cover_path_is_null(path: str) -> bool:
    conn = get_connection()
    row = conn.execute('SELECT cover_path FROM songs WHERE path = ?', (path,)).fetchone()
    conn.close()
    return row is not None and row[0] is None


def update_cover_path(path: str, cover_path: str):
    conn = get_connection()
    try:
        conn.execute('UPDATE songs SET cover_path = ? WHERE path = ?', (cover_path, path))
        conn.commit()
    finally:
        conn.close()


def clear_library():
    conn = get_connection()
    conn.execute('DELETE FROM songs')
    conn.commit()
    conn.close()


def delete_songs_not_in_paths(paths: set[str]):
    conn = get_connection()
    try:
        conn.execute('CREATE TEMP TABLE IF NOT EXISTS _scan_keep (path TEXT PRIMARY KEY)')
        conn.execute('DELETE FROM _scan_keep')
        conn.executemany('INSERT OR IGNORE INTO _scan_keep (path) VALUES (?)', [(p,) for p in paths])
        conn.execute('DELETE FROM songs WHERE path NOT IN (SELECT path FROM _scan_keep)')
        conn.commit()
    finally:
        conn.execute('DROP TABLE IF EXISTS _scan_keep')
        conn.close()


def record_play(song_id: int):
    conn = get_connection()
    try:
        conn.execute('INSERT INTO recently_played (song_id) VALUES (?)', (song_id,))
        conn.commit()
    finally:
        conn.close()


def get_recently_played(limit: int = 20) -> list[Song]:
    conn = get_connection()
    rows = conn.execute('''
        SELECT s.* FROM songs s
        JOIN (
            SELECT song_id, MAX(played_at) AS last_played
            FROM recently_played
            GROUP BY song_id
        ) rp ON rp.song_id = s.id
        ORDER BY rp.last_played DESC
        LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    return [_row_to_song(r) for r in rows]


def get_library_stats() -> dict:
    conn = get_connection()
    songs = conn.execute('SELECT COUNT(*) FROM songs').fetchone()[0]
    albums = conn.execute('SELECT COUNT(DISTINCT album || album_artist) FROM songs').fetchone()[0]
    artists = conn.execute('SELECT COUNT(DISTINCT artist) FROM songs WHERE artist != \'\'').fetchone()[0]
    playlists = conn.execute('SELECT COUNT(*) FROM playlists').fetchone()[0]
    conn.close()
    return {'songs': songs, 'albums': albums, 'artists': artists, 'playlists': playlists}


def get_song_play_count(song_id: int) -> int:
    conn = get_connection()
    row = conn.execute('SELECT COUNT(*) FROM recently_played WHERE song_id = ?', (song_id,)).fetchone()
    conn.close()
    return row[0] if row else 0


def get_song_last_played(song_id: int) -> str | None:
    conn = get_connection()
    row = conn.execute('SELECT MAX(played_at) FROM recently_played WHERE song_id = ?', (song_id,)).fetchone()
    conn.close()
    return row[0] if row and row[0] else None


def get_album_play_count(album_title: str, album_artist: str) -> int:
    conn = get_connection()
    row = conn.execute('''
        SELECT COUNT(*) FROM recently_played rp
        JOIN songs s ON s.id = rp.song_id
        WHERE s.album = ? AND (s.album_artist = ? OR (s.album_artist = '' AND s.artist = ?))
    ''', (album_title, album_artist, album_artist)).fetchone()
    conn.close()
    return row[0] if row else 0


def get_album_last_played(album_title: str, album_artist: str) -> str | None:
    conn = get_connection()
    row = conn.execute('''
        SELECT MAX(rp.played_at) FROM recently_played rp
        JOIN songs s ON s.id = rp.song_id
        WHERE s.album = ? AND (s.album_artist = ? OR (s.album_artist = '' AND s.artist = ?))
    ''', (album_title, album_artist, album_artist)).fetchone()
    conn.close()
    return row[0] if row and row[0] else None


def clear_usage_data():
    conn = get_connection()
    conn.execute('DELETE FROM recently_played')
    conn.commit()
    conn.close()


def _row_to_song(r) -> Song:
    return Song(
        id=r[0], path=r[1], title=r[2], artist=r[3], album=r[4],
        track_number=r[5], duration=r[6], year=r[7], genre=r[8],
        cover_path=r[9], album_artist=r[10]
    )


def create_playlist(name: str, song_ids: list[int]) -> int:
    conn = get_connection()
    try:
        cur = conn.execute('INSERT INTO playlists (name) VALUES (?)', (name,))
        playlist_id = cur.lastrowid
        for i, sid in enumerate(song_ids):
            conn.execute(
                'INSERT INTO playlist_songs (playlist_id, song_id, position) VALUES (?, ?, ?)',
                (playlist_id, sid, i)
            )
        conn.commit()
        return playlist_id
    finally:
        conn.close()


def get_playlists() -> list[Playlist]:
    conn = get_connection()
    rows = conn.execute('''
        SELECT p.id, p.name, p.created,
               COALESCE(COUNT(ps.id), 0),
               COALESCE(SUM(s.duration), 0),
               (SELECT s2.cover_path FROM playlist_songs ps2
                JOIN songs s2 ON s2.id = ps2.song_id
                WHERE ps2.playlist_id = p.id
                ORDER BY ps2.position LIMIT 1)
        FROM playlists p
        LEFT JOIN playlist_songs ps ON ps.playlist_id = p.id
        LEFT JOIN songs s ON s.id = ps.song_id
        GROUP BY p.id
        ORDER BY p.created DESC
    ''').fetchall()
    conn.close()
    return [
        Playlist(id=r[0], name=r[1], created=r[2], song_count=r[3],
                 duration=r[4], cover_path=r[5])
        for r in rows
    ]


def get_playlist_songs(playlist_id: int) -> list[Song]:
    conn = get_connection()
    rows = conn.execute('''
        SELECT s.* FROM songs s
        JOIN playlist_songs ps ON ps.song_id = s.id
        WHERE ps.playlist_id = ?
        ORDER BY ps.position
    ''', (playlist_id,)).fetchall()
    conn.close()
    return [_row_to_song(r) for r in rows]


def delete_playlist(playlist_id: int):
    conn = get_connection()
    try:
        conn.execute('DELETE FROM playlists WHERE id = ?', (playlist_id,))
        conn.commit()
    finally:
        conn.close()


def add_songs_to_playlist(playlist_id: int, song_ids: list[int]):
    if not song_ids:
        return
    conn = get_connection()
    try:
        existing = set(
            r[0] for r in conn.execute(
                'SELECT song_id FROM playlist_songs WHERE playlist_id = ?',
                (playlist_id,)
            ).fetchall()
        )
        row = conn.execute(
            'SELECT COALESCE(MAX(position), -1) FROM playlist_songs WHERE playlist_id = ?',
            (playlist_id,)
        ).fetchone()
        pos = row[0] + 1
        for sid in song_ids:
            if sid in existing:
                continue
            conn.execute(
                'INSERT INTO playlist_songs (playlist_id, song_id, position) VALUES (?, ?, ?)',
                (playlist_id, sid, pos)
            )
            pos += 1
        conn.commit()
    finally:
        conn.close()


def remove_song_from_playlist(playlist_id: int, song_id: int):
    conn = get_connection()
    try:
        conn.execute(
            'DELETE FROM playlist_songs WHERE playlist_id = ? AND song_id = ?',
            (playlist_id, song_id)
        )
        conn.commit()
    finally:
        conn.close()


def rename_playlist(playlist_id: int, new_name: str):
    conn = get_connection()
    try:
        conn.execute('UPDATE playlists SET name = ? WHERE id = ?', (new_name, playlist_id))
        conn.commit()
    finally:
        conn.close()


def get_genres() -> list[Genre]:
    conn = get_connection()
    rows = conn.execute('''
        SELECT genre, COUNT(*) FROM songs
        WHERE genre != '' AND genre IS NOT NULL
        GROUP BY genre
        ORDER BY genre ASC
    ''').fetchall()
    conn.close()
    return [Genre(name=r[0], song_count=r[1]) for r in rows]


def get_songs_by_genre(genre_name: str) -> list[Song]:
    conn = get_connection()
    rows = conn.execute(
        'SELECT * FROM songs WHERE genre = ? ORDER BY album, track_number',
        (genre_name,)
    ).fetchall()
    conn.close()
    return [_row_to_song(r) for r in rows]


def get_favourite_artists(limit: int = 5) -> list[tuple[str, int]]:
    sep = get_setting('artist_separator', '')
    all_songs = get_all_songs()
    counts: dict[str, int] = {}
    for song in all_songs:
        if not song.artist:
            continue
        parts = [p.strip() for p in song.artist.split(sep)] if sep else [song.artist.strip()]
        for name in parts:
            if name:
                counts[name] = counts.get(name, 0) + 1
    sorted_artists = sorted(counts.items(), key=lambda x: (-x[1], x[0].upper()))
    return sorted_artists[:limit]


def get_most_played_songs(limit: int = 50) -> list[Song]:
    conn = get_connection()
    rows = conn.execute('''
        SELECT s.* FROM songs s
        JOIN recently_played rp ON rp.song_id = s.id
        GROUP BY s.id
        ORDER BY COUNT(rp.id) DESC
        LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    return [_row_to_song(r) for r in rows]


MAX_PER_ARTIST = 10
MAX_PER_ALBUM = 10


def get_smart_playlist(limit: int = 30) -> list[Song]:
    seen: set[int] = set()
    result: list[Song] = []
    artist_counts: dict[str, int] = {}
    album_counts: dict[tuple[str, str], int] = {}
    sep = get_setting('artist_separator', '')

    def add_songs(songs: list[Song]) -> bool:
        for s in songs:
            if s.id is not None and s.id not in seen:
                artists = [p.strip() for p in s.artist.split(sep)] if sep else [s.artist.strip()]
                artists = [a for a in artists if a]
                album_key = (s.album, s.album_artist if s.album_artist else s.artist)
                if any(artist_counts.get(a, 0) >= MAX_PER_ARTIST for a in artists):
                    continue
                if album_counts.get(album_key, 0) >= MAX_PER_ALBUM:
                    continue
                for a in artists:
                    artist_counts[a] = artist_counts.get(a, 0) + 1
                album_counts[album_key] = album_counts.get(album_key, 0) + 1
                seen.add(s.id)
                result.append(s)
                if len(result) >= limit:
                    return True
        return False

    # 1. Liked songs
    liked_song_ids = {int(x) for x in get_liked_ids('song') if x.isdigit()}
    if liked_song_ids:
        conn = get_connection()
        placeholders = ','.join('?' * len(liked_song_ids))
        rows = conn.execute(
            f'SELECT * FROM songs WHERE id IN ({placeholders})',
            list(liked_song_ids)
        ).fetchall()
        conn.close()
        songs = [_row_to_song(r) for r in rows]
        random.shuffle(songs)
        if add_songs(songs):
            return result

    # 2. Liked albums
    for item_id in get_liked_ids('album'):
        if '|||' in item_id:
            title, artist = item_id.split('|||', 1)
            songs = get_songs_by_album(title, artist)
            random.shuffle(songs)
            if add_songs(songs):
                return result

    # 3. Liked artists
    for name in get_liked_ids('artist'):
        songs = get_songs_by_artist(name)
        random.shuffle(songs)
        if add_songs(songs):
            return result

    # 4. Recently played
    songs = get_recently_played(limit * 2)
    random.shuffle(songs)
    if add_songs(songs):
        return result

    # 5. Most played
    songs = get_most_played_songs(limit * 2)
    random.shuffle(songs)
    if add_songs(songs):
        return result

    return result


def toggle_like(item_type: str, item_id: str) -> bool:
    conn = get_connection()
    try:
        existing = conn.execute(
            'SELECT id FROM likes WHERE item_type = ? AND item_id = ?',
            (item_type, item_id)
        ).fetchone()
        if existing:
            conn.execute('DELETE FROM likes WHERE id = ?', (existing[0],))
            conn.commit()
            return False
        else:
            conn.execute(
                'INSERT INTO likes (item_type, item_id) VALUES (?, ?)',
                (item_type, item_id)
            )
            conn.commit()
            return True
    finally:
        conn.close()


def is_liked(item_type: str, item_id: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        'SELECT 1 FROM likes WHERE item_type = ? AND item_id = ?',
        (item_type, item_id)
    ).fetchone()
    conn.close()
    return row is not None


def get_liked_ids(item_type: str) -> set[str]:
    conn = get_connection()
    rows = conn.execute(
        'SELECT item_id FROM likes WHERE item_type = ?', (item_type,)
    ).fetchall()
    conn.close()
    return {r[0] for r in rows}
