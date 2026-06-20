import os
from typing import Callable, Optional

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Pango, Gdk, GLib

from src.library import database
from src.library.models import Song
from src.widgets.cover import load_cover_pixbuf

BATCH_SIZE = 50


COVER_SIZE = 48


class SongList(Gtk.Box):
    def __init__(self, show_album: bool = True, drag_enabled: bool = False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._show_album = show_album
        self._drag_enabled = drag_enabled
        self._on_song_activated: Optional[Callable] = None
        self._on_song_menu: Optional[Callable] = None
        self._on_populated: Optional[Callable] = None
        self._on_reorder: Optional[Callable] = None
        self._drag_source_idx = None
        self._drag_hovered_row = None
        self._liked_song_ids: set[str] = set()
        self._pending_iter = None
        self._idle_source = None

        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.set_vexpand(True)
        self._scrolled.set_hexpand(True)

        self._listbox = Gtk.ListBox()
        self._listbox.add_css_class('song-list')
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._listbox.connect('row-activated', self._on_row_activated)
        self._scrolled.set_child(self._listbox)

        if drag_enabled:
            drop_target = Gtk.DropTarget(
                actions=Gdk.DragAction.MOVE,
                formats=Gdk.ContentFormats.new_for_gtype(GLib.Variant)
            )
            drop_target.connect('accept', self._on_drag_accept)
            drop_target.connect('motion', self._on_drag_motion)
            drop_target.connect('leave', self._on_drag_leave)
            drop_target.connect('drop', self._on_drag_drop)
            self._listbox.add_controller(drop_target)

        self._stack = Gtk.Stack()
        self._stack.set_vexpand(True)
        self._stack.set_hexpand(True)

        self._loading_label = Gtk.Label(label='Loading songs\u2026')
        self._loading_label.set_halign(Gtk.Align.CENTER)
        self._loading_label.set_valign(Gtk.Align.CENTER)
        self._stack.add_named(self._loading_label, 'loading')
        self._stack.add_named(self._scrolled, 'list')
        self._stack.set_visible_child_name('list')

        self.append(self._stack)

    def populate_batched(self, songs: list[Song]):
        self._cancel_batch()
        self._clear()
        self._liked_song_ids = database.get_liked_ids('song')
        self._stack.set_visible_child_name('loading')
        self._pending_iter = iter(songs)
        self._idle_source = GLib.idle_add(self._process_batch)

    def set_songs(self, songs: list[Song]):
        self._cancel_batch()
        self._clear()
        self._liked_song_ids = database.get_liked_ids('song')
        for song in songs:
            self._listbox.append(self._build_row(song))

    def set_grouped(self, grouped: dict[str, list[Song]]):
        self._cancel_batch()
        self._clear()
        self._liked_song_ids = database.get_liked_ids('song')
        for album_key, songs in grouped.items():
            header = Gtk.Label(label=album_key)
            header.add_css_class('album-header-label')
            header.set_halign(Gtk.Align.START)
            header.set_margin_start(12)
            header.set_margin_top(12)
            header.set_margin_bottom(4)
            self._listbox.append(header)
            for song in songs:
                self._listbox.append(self._build_row(song))

    def on_song_activated(self, callback: Callable):
        self._on_song_activated = callback

    def on_song_menu(self, callback: Callable):
        self._on_song_menu = callback

    def on_populated(self, callback: Callable):
        self._on_populated = callback

    def on_reorder(self, callback: Callable):
        self._on_reorder = callback

    def _on_drag_accept(self, drop_target, drop):
        return True

    def _on_drag_motion(self, drop_target, x, y):
        self._clear_drag_hover()
        row = self._listbox.get_row_at_y(int(y))
        if row:
            row.add_css_class('drag-hover')
            self._drag_hovered_row = row
        return Gdk.DragAction.MOVE

    def _on_drag_leave(self, drop_target):
        self._clear_drag_hover()

    def _clear_drag_hover(self):
        if self._drag_hovered_row is not None:
            self._drag_hovered_row.remove_css_class('drag-hover')
            self._drag_hovered_row = None

    def _on_drag_drop(self, drop_target, value, x, y):
        self._clear_drag_hover()
        if self._drag_source_idx is None:
            return False
        source_idx = self._drag_source_idx
        target_row = self._listbox.get_row_at_y(int(y))
        if target_row is None:
            return False
        target_idx = target_row.get_index()
        if source_idx != target_idx and self._on_reorder:
            self._on_reorder(source_idx, target_idx)
        return True

    def _on_drag_begin(self, source, drag):
        row = source.get_widget()
        if hasattr(row, '_drag_opacity'):
            return
        row._drag_opacity = row.get_opacity()
        row.set_opacity(0.4)

    def _on_drag_end(self, source, drag, delete_data):
        self._clear_drag_hover()
        self._drag_source_idx = None
        row = source.get_widget()
        if hasattr(row, '_drag_opacity'):
            row.set_opacity(row._drag_opacity)
            del row._drag_opacity

    def _clear(self):
        self._cancel_batch()
        while child := self._listbox.get_first_child():
            self._listbox.remove(child)

    def _cancel_batch(self):
        self._pending_iter = None
        if self._idle_source is not None:
            GLib.source_remove(self._idle_source)
            self._idle_source = None

    def _process_batch(self) -> bool:
        count = 0
        while self._pending_iter is not None:
            try:
                song = next(self._pending_iter)
            except StopIteration:
                self._pending_iter = None
                self._idle_source = None
                self._stack.set_visible_child_name('list')
                self._notify_populated()
                return GLib.SOURCE_REMOVE
            self._listbox.append(self._build_row(song))
            count += 1
            if count >= BATCH_SIZE:
                return GLib.SOURCE_CONTINUE
        self._idle_source = None
        self._stack.set_visible_child_name('list')
        self._notify_populated()
        return GLib.SOURCE_REMOVE

    def _build_row(self, song: Song) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.add_css_class('song-row')
        row._song = song

        grid = Gtk.Grid()
        grid.set_column_spacing(10)
        grid.set_margin_start(12)
        grid.set_margin_end(12)
        grid.set_margin_top(4)
        grid.set_margin_bottom(4)

        col = 0

        liked = str(song.id) in self._liked_song_ids if song.id is not None else False

        # Column 0: Like star
        star_btn = Gtk.Button(icon_name='starred-symbolic' if liked else 'non-starred-symbolic')
        star_btn.add_css_class('flat')
        star_btn.add_css_class('card-btn')
        star_btn.set_tooltip_text('Unlike' if liked else 'Like')
        star_btn.set_opacity(1.0 if liked else 0.35)
        star_btn.connect('clicked', self._on_heart_clicked, song)
        grid.attach(star_btn, col, 0, 1, 1)
        col += 1

        # Column 1: Album cover
        if song.cover_path and os.path.exists(song.cover_path):
            pixbuf = load_cover_pixbuf(song.cover_path, COVER_SIZE)
            if pixbuf is not None:
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                pic = Gtk.Picture.new_for_paintable(texture)
                pic.set_content_fit(Gtk.ContentFit.COVER)  # preserves aspect ratio
                pic.set_size_request(COVER_SIZE, COVER_SIZE)  # fixed, no expand
                grid.attach(pic, col, 0, 1, 1)
            else:
                grid.attach(_placeholder(COVER_SIZE), col, 0, 1, 1)
        else:
            grid.attach(_placeholder(COVER_SIZE), col, 0, 1, 1)
        col += 1

        # Column 3: Track number
        track_label = Gtk.Label(label=str(song.track_number) if song.track_number else '-')
        track_label.add_css_class('track-number')
        track_label.set_size_request(32, -1)
        track_label.set_halign(Gtk.Align.END)
        grid.attach(track_label, col, 0, 1, 1)
        col += 1

        # Column 4: Song title (expands to fill spare space)
        title_label = Gtk.Label(label=song.title)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_hexpand(True)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.add_css_class('song-title')
        grid.attach(title_label, col, 0, 1, 1)
        col += 1

        # Column 5: Artist
        artist_label = Gtk.Label(label=song.artist or '—')
        artist_label.set_halign(Gtk.Align.START)
        artist_label.set_size_request(160, -1)
        artist_label.set_ellipsize(Pango.EllipsizeMode.END)
        artist_label.add_css_class('song-artist')
        grid.attach(artist_label, col, 0, 1, 1)
        col += 1

        # Column 6: Album (hidden in context where album is already known)
        if self._show_album:
            album_label = Gtk.Label(label=song.album or '—')
            album_label.set_halign(Gtk.Align.START)
            album_label.set_size_request(160, -1)
            album_label.set_ellipsize(Pango.EllipsizeMode.END)
            album_label.add_css_class('song-album')
            grid.attach(album_label, col, 0, 1, 1)
        col += 1

        # Column 7: Genre
        genre_label = Gtk.Label(label=song.genre or '—')
        genre_label.set_halign(Gtk.Align.START)
        genre_label.set_size_request(120, -1)
        genre_label.set_ellipsize(Pango.EllipsizeMode.END)
        genre_label.add_css_class('song-genre')
        grid.attach(genre_label, col, 0, 1, 1)
        col += 1

        # Column 10: Duration
        mins, secs = divmod(int(song.duration), 60)
        dur_label = Gtk.Label(label=f'{mins}:{secs:02d}')
        dur_label.set_halign(Gtk.Align.END)
        dur_label.set_size_request(52, -1)
        dur_label.add_css_class('song-duration')
        grid.attach(dur_label, col, 0, 1, 1)
        col += 1

        # Column 11: 3-dot menu
        menu_btn = Gtk.Button(label='\u22ef')
        menu_btn.add_css_class('flat')
        menu_btn.add_css_class('menu-btn')
        menu_btn.connect('clicked', self._on_menu_clicked, song)
        grid.attach(menu_btn, col, 0, 1, 1)

        row.set_child(grid)

        right_click = Gtk.GestureClick()
        right_click.set_button(3)
        right_click.connect('pressed', lambda g, n, x, y: self._on_row_right_clicked(row))
        row.add_controller(right_click)

        if self._drag_enabled:
            drag_source = Gtk.DragSource()
            drag_source.set_actions(Gdk.DragAction.MOVE)
            drag_source.connect('prepare', self._on_drag_prepare)
            drag_source.connect('drag-begin', self._on_drag_begin)
            drag_source.connect('drag-end', self._on_drag_end)
            row.add_controller(drag_source)

        return row

    def _on_drag_prepare(self, source, x, y):
        row = source.get_widget()
        if not isinstance(row, Gtk.ListBoxRow):
            return None
        self._drag_source_idx = row.get_index()
        return Gdk.ContentProvider.new_for_value(GLib.Variant('i', 0))

    def _on_row_activated(self, listbox, row):
        if self._on_song_activated and hasattr(row, '_song'):
            self._on_song_activated(row._song)

    def _on_menu_clicked(self, button, song):
        if self._on_song_menu:
            self._on_song_menu(button, song)

    def _on_row_right_clicked(self, row):
        if self._on_song_menu and hasattr(row, '_song'):
            self._on_song_menu(row, row._song)

    def _on_heart_clicked(self, button, song):
        if song.id is None:
            return
        liked = database.toggle_like('song', str(song.id))
        button.set_icon_name('starred-symbolic' if liked else 'non-starred-symbolic')
        button.set_tooltip_text('Unlike' if liked else 'Like')
        button.set_opacity(1.0 if liked else 0.35)

    def _notify_populated(self):
        if self._on_populated:
            self._on_populated()


def _placeholder(size: int) -> Gtk.Box:
    """Grey square shown when no cover art is available."""
    box = Gtk.Box()
    box.set_size_request(size, size)
    box.add_css_class('cover-placeholder')
    return box
