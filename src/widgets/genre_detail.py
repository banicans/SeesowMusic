from typing import Callable, Optional

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, GLib, Pango

from src.library import database
from src.library.models import Genre
from src.widgets.list import SongList


class GenreDetail(Gtk.Box):
    def __init__(self, genre: Genre):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._genre = genre
        self._on_back: Optional[Callable] = None
        self._on_play: Optional[Callable] = None
        self._on_shuffle: Optional[Callable] = None

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top_bar.set_margin_start(12)
        top_bar.set_margin_end(12)
        top_bar.set_margin_top(8)
        top_bar.set_margin_bottom(8)

        back_btn = Gtk.Button(label='\u2190 Genres')
        back_btn.add_css_class('flat')
        back_btn.connect('clicked', lambda b: self._on_back() if self._on_back else None)
        top_bar.append(back_btn)

        title_label = Gtk.Label(label=genre.name)
        title_label.add_css_class('heading')
        title_label.set_halign(Gtk.Align.START)
        title_label.set_hexpand(True)
        top_bar.append(title_label)

        self.append(top_bar)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        header.set_margin_start(24)
        header.set_margin_end(24)
        header.set_margin_top(8)
        header.set_margin_bottom(8)

        info_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_col.set_valign(Gtk.Align.CENTER)

        name_label = Gtk.Label(label=genre.name)
        name_label.set_halign(Gtk.Align.START)
        name_label.add_css_class('title-2')
        info_col.append(name_label)

        songs = database.get_songs_by_genre(genre.name)
        meta_label = Gtk.Label(label=f'{len(songs)} songs')
        meta_label.set_halign(Gtk.Align.START)
        meta_label.add_css_class('dim-label')
        info_col.append(meta_label)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_top(8)

        play_btn = Gtk.Button(label='\u25b6  Play All')
        play_btn.add_css_class('suggested-action')
        play_btn.connect('clicked', lambda b: self._on_play(self._genre) if self._on_play else None)
        btn_row.append(play_btn)

        shuffle_btn = Gtk.Button()
        shuffle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        shuffle_icon = Gtk.Image(icon_name='media-playlist-shuffle-symbolic')
        shuffle_box.append(shuffle_icon)
        shuffle_box.append(Gtk.Label(label='Shuffle'))
        shuffle_btn.set_child(shuffle_box)
        shuffle_btn.connect('clicked', lambda b: self._on_shuffle(self._genre) if self._on_shuffle else None)
        btn_row.append(shuffle_btn)

        info_col.append(btn_row)
        header.append(info_col)
        self.append(header)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(4)
        sep.set_margin_bottom(4)
        self.append(sep)

        self._song_list = SongList(show_album=True)
        self._song_list.set_songs(songs)
        self._song_list.set_vexpand(True)
        self.append(self._song_list)

    def on_back(self, callback: Callable):
        self._on_back = callback

    def on_play(self, callback: Callable):
        self._on_play = callback

    def on_shuffle(self, callback: Callable):
        self._on_shuffle = callback

    def on_song_activated(self, callback: Callable):
        self._song_list.on_song_activated(callback)

    def on_song_menu(self, callback: Callable):
        self._song_list.on_song_menu(callback)
