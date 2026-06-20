import os
from typing import Callable, Optional

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, GLib, Pango

from src.library import database
from src.library.models import Album
from src.widgets.cover import load_cover_pixbuf
from src.widgets.context_menu import ContextMenu
from src.widgets.list import SongList

COVER_SIZE = 200


def _format_duration(total_sec: float) -> str:
    total = int(total_sec)
    h, m = divmod(total, 3600)
    m, s = divmod(m, 60)
    if h > 0:
        return f'{h}h {m}m'
    return f'{m}:{s:02d}'


class AlbumDetail(Gtk.Box):
    def __init__(self, album: Album):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._album = album
        self._on_back: Optional[Callable] = None
        self._on_play: Optional[Callable] = None
        self._on_shuffle: Optional[Callable] = None
        self._on_add_to_queue: Optional[Callable] = None
        self._on_add_to_playlist: Optional[Callable] = None
        self._on_info: Optional[Callable] = None

        # Top bar with back button
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top_bar.set_margin_start(12)
        top_bar.set_margin_end(12)
        top_bar.set_margin_top(8)
        top_bar.set_margin_bottom(8)

        back_btn = Gtk.Button(label='\u2190 Albums')
        back_btn.add_css_class('flat')
        back_btn.connect('clicked', lambda b: self._on_back() if self._on_back else None)
        top_bar.append(back_btn)

        title_label = Gtk.Label(label=album.title)
        title_label.add_css_class('heading')
        title_label.set_halign(Gtk.Align.START)
        title_label.set_hexpand(True)
        top_bar.append(title_label)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name('view-more-symbolic')
        menu_btn.add_css_class('flat')
        menu_btn.add_css_class('menu-btn')
        menu_items = [
            ('Play', lambda: self._on_play(self._album) if self._on_play else None),
            ('Add to Queue', lambda: self._on_add_to_queue(self._album) if self._on_add_to_queue else None),
            ('Shuffle', lambda: self._on_shuffle(self._album) if self._on_shuffle else None),
            ('Add to Playlist', lambda: self._on_add_to_playlist(self._album) if self._on_add_to_playlist else None),
            ('Info', lambda: self._on_info(self._album) if self._on_info else None),
        ]
        menu_btn.set_popover(ContextMenu(menu_items))
        top_bar.append(menu_btn)

        self.append(top_bar)

        # Fetch songs early so we can compute total duration for the header
        songs = database.get_songs_by_album(album.title, album.artist)

        # Album info header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        header.set_margin_start(24)
        header.set_margin_end(24)
        header.set_margin_top(8)
        header.set_margin_bottom(8)

        self._cover_box = Gtk.Box()
        self._cover_box.set_size_request(COVER_SIZE, COVER_SIZE)

        if album.cover_path and os.path.exists(album.cover_path):
            pixbuf = load_cover_pixbuf(album.cover_path, COVER_SIZE)
            if pixbuf is not None:
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                pic = Gtk.Picture.new_for_paintable(texture)
                pic.set_content_fit(Gtk.ContentFit.COVER)
                pic.set_halign(Gtk.Align.FILL)
                pic.set_valign(Gtk.Align.FILL)
                pic.add_css_class('album-cover')
                pic.set_size_request(COVER_SIZE, COVER_SIZE)
                self._cover_box.append(pic)

        header.append(self._cover_box)

        # Info column
        info_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_col.set_valign(Gtk.Align.CENTER)

        artist_label = Gtk.Label(label=album.artist or 'Unknown Artist')
        artist_label.set_halign(Gtk.Align.START)
        artist_label.add_css_class('title-2')
        info_col.append(artist_label)

        total_sec = sum(s.duration for s in songs)
        meta_label = Gtk.Label(label=f'{album.year}  \u2022  {album.song_count} songs  \u2022  {_format_duration(total_sec)}')
        meta_label.set_halign(Gtk.Align.START)
        meta_label.add_css_class('dim-label')
        info_col.append(meta_label)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_top(8)

        play_btn = Gtk.Button(label='\u25b6  Play')
        play_btn.add_css_class('suggested-action')
        play_btn.connect('clicked', lambda b: self._on_play(self._album) if self._on_play else None)
        btn_row.append(play_btn)

        shuffle_btn = Gtk.Button()
        shuffle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        shuffle_icon = Gtk.Image(icon_name='media-playlist-shuffle-symbolic')
        shuffle_box.append(shuffle_icon)
        shuffle_box.append(Gtk.Label(label='Shuffle'))
        shuffle_btn.set_child(shuffle_box)
        shuffle_btn.add_css_class('flat')
        shuffle_btn.connect('clicked', lambda b: self._on_shuffle(self._album) if self._on_shuffle else None)
        btn_row.append(shuffle_btn)

        liked = database.is_liked('album', f"{album.title}|||{album.artist}")
        star_btn = Gtk.Button(icon_name='starred-symbolic' if liked else 'non-starred-symbolic')
        star_btn.add_css_class('flat')
        star_btn.set_tooltip_text('Unlike' if liked else 'Like')
        star_btn.set_opacity(1.0 if liked else 0.35)
        star_btn.connect('clicked', self._on_album_star_clicked)
        btn_row.append(star_btn)

        info_col.append(btn_row)

        header.append(info_col)
        self.append(header)

        # Divider
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(4)
        sep.set_margin_bottom(4)
        self.append(sep)

        # Song list
        self._song_list = SongList(show_album=False)
        self._song_list.set_songs(songs)
        self._song_list.set_vexpand(True)
        self.append(self._song_list)

    def on_back(self, callback: Callable):
        self._on_back = callback

    def on_play(self, callback: Callable):
        self._on_play = callback

    def on_shuffle(self, callback: Callable):
        self._on_shuffle = callback

    def on_add_to_queue(self, callback: Callable):
        self._on_add_to_queue = callback

    def on_add_to_playlist(self, callback: Callable):
        self._on_add_to_playlist = callback

    def on_info(self, callback: Callable):
        self._on_info = callback

    def _on_album_star_clicked(self, button):
        item_id = f"{self._album.title}|||{self._album.artist}"
        liked = database.toggle_like('album', item_id)
        button.set_icon_name('starred-symbolic' if liked else 'non-starred-symbolic')
        button.set_tooltip_text('Unlike' if liked else 'Like')
        button.set_opacity(1.0 if liked else 0.35)

    def on_song_activated(self, callback: Callable):
        self._song_list.on_song_activated(callback)

    def on_song_menu(self, callback: Callable):
        self._song_list.on_song_menu(callback)
