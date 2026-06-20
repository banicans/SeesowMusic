from pathlib import Path
from typing import Callable, Optional

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

from src.library.models import Song


class AudioPlayer:
    def __init__(self):
        self._playbin = None
        self._bus = None
        self._current_song: Optional[Song] = None
        self._position_timer: Optional[int] = None
        self._on_position: Optional[Callable] = None
        self._on_finished: Optional[Callable] = None
        self._is_playing = False

    def _ensure_init(self):
        if self._playbin is not None:
            return
        Gst.init(None)
        self._playbin = Gst.ElementFactory.make('playbin', 'player')
        self._bus = self._playbin.get_bus()
        self._bus.add_signal_watch()
        self._bus.connect('message', self._on_message)

    def load(self, song: Song):
        self._ensure_init()
        self._current_song = song
        uri = Path(song.path).as_uri()
        self._playbin.set_state(Gst.State.NULL)
        self._playbin.set_property('uri', uri)
        self._is_playing = False
        self._start_position_timer()

    def play(self):
        self._ensure_init()
        self._playbin.set_state(Gst.State.PLAYING)
        self._is_playing = True
        self._start_position_timer()

    def pause(self):
        self._ensure_init()
        self._playbin.set_state(Gst.State.PAUSED)
        self._is_playing = False
        self._stop_position_timer()

    def toggle(self):
        if self._is_playing:
            self.pause()
        else:
            self.play()

    def stop(self):
        if self._playbin is None:
            return
        self._playbin.set_state(Gst.State.NULL)
        self._is_playing = False
        self._stop_position_timer()

    def seek(self, position_seconds: float):
        self._ensure_init()
        ns = int(position_seconds * Gst.SECOND)
        self._playbin.seek_simple(
            Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT, ns
        )

    def set_volume(self, volume: float):
        self._ensure_init()
        self._playbin.set_property('volume', max(0.0, min(1.0, volume)))

    def get_volume(self) -> float:
        self._ensure_init()
        return self._playbin.get_property('volume')

    def get_position(self) -> float:
        if self._playbin is None:
            return 0.0
        ok, pos = self._playbin.query_position(Gst.Format.TIME)
        return pos / Gst.SECOND if ok else 0.0

    def get_duration(self) -> float:
        if self._playbin is None:
            return 0.0
        ok, dur = self._playbin.query_duration(Gst.Format.TIME)
        return dur / Gst.SECOND if ok else 0.0

    def is_playing(self) -> bool:
        return self._is_playing

    def current_song(self) -> Optional[Song]:
        return self._current_song

    def on_position_updated(self, callback: Callable):
        self._on_position = callback

    def on_song_finished(self, callback: Callable):
        self._on_finished = callback

    def _on_message(self, bus, msg):
        if msg.type == Gst.MessageType.EOS:
            self._is_playing = False
            self._stop_position_timer()
            if self._on_finished:
                self._on_finished()
        elif msg.type == Gst.MessageType.ERROR:
            err, debug = msg.parse_error()
            self._is_playing = False
            self._stop_position_timer()

    def _start_position_timer(self):
        self._stop_position_timer()
        self._position_timer = GLib.timeout_add(250, self._emit_position)

    def _stop_position_timer(self):
        if self._position_timer:
            GLib.source_remove(self._position_timer)
            self._position_timer = None

    def _emit_position(self):
        if not self._is_playing:
            self._position_timer = None
            return GLib.SOURCE_REMOVE
        pos = self.get_position()
        dur = self.get_duration()
        if self._on_position:
            self._on_position(pos, dur)
        return GLib.SOURCE_CONTINUE
