import os
from typing import Callable, Optional

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, GLib, Pango

from src.library import database
from src.library.models import Playlist
from src.widgets.context_menu import ContextMenu
from src.widgets.cover import load_cover_pixbuf
from src.widgets.list import SongList

COVER_SIZE = 200


def _format_duration(total_sec: float) -> str:
    total = int(total_sec)
    h, m = divmod(total, 3600)
    m, s = divmod(m, 60)
    if h > 0:
        return f'{h}h {m}m'
    return f'{m}:{s:02d}'


class PlaylistDetail(Gtk.Box):
    def __init__(self, playlist: Playlist):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._playlist = playlist
        self._on_back: Optional[Callable] = None
        self._on_play: Optional[Callable] = None
        self._on_delete: Optional[Callable] = None

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top_bar.set_margin_start(12)
        top_bar.set_margin_end(12)
        top_bar.set_margin_top(8)
        top_bar.set_margin_bottom(8)

        back_btn = Gtk.Button(label='\u2190 Playlists')
        back_btn.add_css_class('flat')
        back_btn.connect('clicked', lambda b: self._on_back() if self._on_back else None)
        top_bar.append(back_btn)

        self._title_label = Gtk.Label(label=playlist.name)
        self._title_label.add_css_class('heading')
        self._title_label.set_halign(Gtk.Align.START)
        self._title_label.set_hexpand(True)
        top_bar.append(self._title_label)

        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name('view-more-symbolic')
        menu_btn.add_css_class('flat')
        menu_btn.add_css_class('menu-btn')
        menu_items = [
            ('Rename Playlist', self._on_rename),
            ('Delete Playlist', self._on_delete_clicked),
        ]
        self._menu_btn = menu_btn
        self._menu_btn.set_popover(ContextMenu(menu_items))
        top_bar.append(self._menu_btn)

        self.append(top_bar)

        songs = database.get_playlist_songs(playlist.id)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        header.set_margin_start(24)
        header.set_margin_end(24)
        header.set_margin_top(8)
        header.set_margin_bottom(8)

        self._cover_box = Gtk.Box()
        self._cover_box.set_size_request(COVER_SIZE, COVER_SIZE)

        cover_path = playlist.cover_path if playlist.cover_path and os.path.exists(playlist.cover_path) else None
        if cover_path:
            pixbuf = load_cover_pixbuf(cover_path, COVER_SIZE)
            if pixbuf is not None:
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                pic = Gtk.Picture.new_for_paintable(texture)
                pic.set_content_fit(Gtk.ContentFit.COVER)
                pic.set_halign(Gtk.Align.FILL)
                pic.set_valign(Gtk.Align.FILL)
                pic.add_css_class('album-cover')
                pic.set_size_request(COVER_SIZE, COVER_SIZE)
                self._cover_box.append(pic)
        else:
            placeholder = Gtk.Box()
            placeholder.set_size_request(COVER_SIZE, COVER_SIZE)
            placeholder.add_css_class('cover-placeholder')
            icon = Gtk.Image.new_from_icon_name('audio-x-generic-symbolic')
            icon.set_pixel_size(64)
            icon.set_opacity(0.4)
            placeholder.append(icon)
            self._cover_box.append(placeholder)

        header.append(self._cover_box)

        info_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_col.set_valign(Gtk.Align.CENTER)

        self._name_label = Gtk.Label(label=playlist.name)
        self._name_label.set_halign(Gtk.Align.START)
        self._name_label.add_css_class('title-2')
        info_col.append(self._name_label)

        total_sec = sum(s.duration for s in songs)
        self._meta_label = Gtk.Label(label=f'{playlist.song_count} songs  \u2022  {_format_duration(total_sec)}')
        self._meta_label.set_halign(Gtk.Align.START)
        self._meta_label.add_css_class('dim-label')
        info_col.append(self._meta_label)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_top(8)

        play_btn = Gtk.Button(label='\u25b6  Play')
        play_btn.add_css_class('suggested-action')
        play_btn.connect('clicked', lambda b: self._on_play(self._playlist) if self._on_play else None)
        btn_row.append(play_btn)

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

    def on_song_activated(self, callback: Callable):
        self._song_list.on_song_activated(callback)

    def on_song_menu(self, callback: Callable):
        self._song_list.on_song_menu(callback)

    def on_delete(self, callback: Callable):
        self._on_delete = callback

    def _on_rename(self):
        GLib.idle_add(self._show_rename_popover)

    def _show_rename_popover(self):
        popover = Gtk.Popover()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)

        entry = Gtk.Entry()
        entry.set_text(self._playlist.name)
        entry.set_activates_default(True)
        box.append(entry)

        rename_btn = Gtk.Button(label='Rename')
        rename_btn.add_css_class('suggested-action')

        def do_rename():
            new_name = entry.get_text().strip()
            if new_name:
                database.rename_playlist(self._playlist.id, new_name)
                self._playlist = Playlist(self._playlist.id, new_name,
                                          self._playlist.song_count, self._playlist.cover_path)
                self._title_label.set_text(new_name)
                self._name_label.set_text(new_name)

            popover.popdown()

        rename_btn.connect('clicked', lambda b: do_rename())
        entry.connect('activate', lambda e: do_rename())
        box.append(rename_btn)

        popover.set_child(box)
        popover.set_parent(self._menu_btn)
        popover.popup()
        return False

    def _on_delete_clicked(self):
        dialog = Gtk.AlertDialog(
            message=f'Delete "{self._playlist.name}"?',
            detail='Songs in the library will not be affected.',
        )
        dialog.set_buttons(['Cancel', 'Delete'])
        dialog.set_cancel_button(0)
        dialog.set_default_button(1)

        def on_response(dlg, result):
            idx = dlg.choose_finish(result)
            if idx == 1:
                database.delete_playlist(self._playlist.id)
                if self._on_delete:
                    self._on_delete()

        dialog.choose(self.get_root(), None, on_response)

    def refresh(self):
        songs = database.get_playlist_songs(self._playlist.id)
        self._song_list.set_songs(songs)
        total_sec = sum(s.duration for s in songs)
        self._meta_label.set_text(f'{len(songs)} songs  \u2022  {_format_duration(total_sec)}')
