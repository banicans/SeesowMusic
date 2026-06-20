from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Song:
    path: str
    title: str
    artist: str
    album: str
    track_number: int
    duration: float
    year: int
    genre: str
    album_artist: str = ''
    cover_path: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Album:
    title: str
    artist: str
    year: int
    cover_path: Optional[str] = None
    song_count: int = 0
    id: Optional[int] = None
    songs: list[Song] = field(default_factory=list)


@dataclass
class Artist:
    name: str
    id: Optional[int] = None


@dataclass
class Genre:
    name: str
    song_count: int = 0
    id: Optional[int] = None


@dataclass
class Playlist:
    name: str
    song_count: int = 0
    duration: float = 0.0
    cover_path: Optional[str] = None
    created: str = ''
    id: Optional[int] = None
