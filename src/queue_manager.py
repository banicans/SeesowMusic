from typing import Callable, Optional

from src.library.models import Song


class QueueManager:
    def __init__(self):
        self._songs: list[Song] = []
        self._listeners: list[Callable] = []

    def add(self, song: Song):
        self._songs.append(song)
        self._notify()

    def add_multiple(self, songs: list[Song]):
        self._songs.extend(songs)
        self._notify()

    def clear(self):
        self._songs.clear()
        self._notify()

    def remove(self, index: int):
        if 0 <= index < len(self._songs):
            del self._songs[index]
            self._notify()

    def move(self, from_idx: int, to_idx: int):
        if from_idx < 0 or from_idx >= len(self._songs):
            return
        if to_idx < 0 or to_idx >= len(self._songs):
            return
        song = self._songs.pop(from_idx)
        self._songs.insert(to_idx, song)
        self._notify()

    def get_all(self) -> list[Song]:
        return list(self._songs)

    def total_duration(self) -> float:
        return sum(s.duration for s in self._songs)

    def on_change(self, callback: Callable):
        self._listeners.append(callback)

    def _notify(self):
        for cb in self._listeners:
            cb()
