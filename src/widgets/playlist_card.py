import os
from typing import Optional
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, GdkPixbuf, Gdk, GLib, Pango
from src.library.models import Playlist
from src.widgets.cover import load_cover_pixbuf
from src.widgets.context_menu import ContextMenu

COVER_SIZE = 180
CARD_PADDING = 8
CARD_WIDTH = COVER_SIZE + CARD_PADDING * 2


class PlaylistCard(Gtk.Box):
    def __init__(self, playlist: Playlist):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.set_hexpand(False)
        self._playlist = playlist
        self._data = playlist
        self._on_play_callback = None
        self._on_add_to_queue_callback = None
        self._on_rename_callback = None
        self._on_delete_callback = None
        self.set_size_request(CARD_WIDTH, -1)
        self.set_halign(Gtk.Align.CENTER)

        self._cover_box = Gtk.Box()
        self._cover_box.set_size_request(COVER_SIZE, COVER_SIZE)
        self._cover_box.set_halign(Gtk.Align.CENTER)
        self._cover_box.set_margin_start(CARD_PADDING)
        self._cover_box.set_margin_end(CARD_PADDING)
        self._cover_path = playlist.cover_path if playlist.cover_path and os.path.exists(playlist.cover_path) else None
        self._show_placeholder()
        self.append(self._cover_box)

        info_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        info_row.set_margin_start(CARD_PADDING)
        info_row.set_margin_end(CARD_PADDING)

        left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        left_col.set_halign(Gtk.Align.START)
        left_col.set_hexpand(True)

        title_label = Gtk.Label(label=playlist.name)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_wrap(True)
        title_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        title_label.set_lines(2)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.add_css_class('heading')
        left_col.append(title_label)

        info_label = Gtk.Label(label=f'{playlist.song_count} tracks')
        info_label.set_halign(Gtk.Align.START)
        info_label.add_css_class('dim-label')
        left_col.append(info_label)

        info_row.append(left_col)

        right_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        right_col.set_halign(Gtk.Align.END)
        right_col.set_valign(Gtk.Align.CENTER)

        play_btn = Gtk.Button(label='\u25b6')
        play_btn.add_css_class('flat')
        play_btn.add_css_class('album-action-btn')
        play_btn.connect('clicked', self._on_play_clicked)
        right_col.append(play_btn)

        menu_btn = Gtk.Button(label='\u22ef')
        menu_btn.add_css_class('flat')
        menu_btn.add_css_class('album-action-btn')
        menu_btn.connect('clicked', self._on_menu_clicked)
        right_col.append(menu_btn)

        info_row.append(right_col)
        self.append(info_row)

        right_click = Gtk.GestureClick()
        right_click.set_button(3)
        right_click.connect('pressed', lambda g, n, x, y: self._on_menu_clicked(self))
        self.add_controller(right_click)

    def _show_placeholder(self):
        box = Gtk.Box()
        box.set_size_request(COVER_SIZE, COVER_SIZE)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)
        box.add_css_class('cover-placeholder')
        icon = Gtk.Image.new_from_icon_name('audio-x-generic-symbolic')
        icon.set_pixel_size(48)
        icon.set_opacity(0.4)
        icon.set_halign(Gtk.Align.CENTER)
        icon.set_valign(Gtk.Align.CENTER)
        icon.set_hexpand(True)
        icon.set_vexpand(True)
        box.append(icon)
        self._cover_box.append(box)

    def on_play_playlist(self, callback):
        self._on_play_callback = callback

    def on_add_to_queue(self, callback):
        self._on_add_to_queue_callback = callback

    def on_delete_playlist(self, callback):
        self._on_delete_callback = callback

    def on_rename_playlist(self, callback):
        self._on_rename_callback = callback

    def _on_play_clicked(self, button):
        if self._on_play_callback:
            self._on_play_callback(self._playlist)

    def _on_menu_clicked(self, button):
        items = [
            ('Play', lambda: self._on_play_callback(self._playlist) if self._on_play_callback else None),
            ('Add to Queue', lambda: self._on_add_to_queue_callback(self._playlist) if self._on_add_to_queue_callback else None),
            ('Rename', lambda: self._on_rename_callback(self._playlist) if self._on_rename_callback else None),
            ('Delete', lambda: self._on_delete_callback(self._playlist) if self._on_delete_callback else None),
        ]
        menu = ContextMenu([(l, cb) for l, cb in items if cb is not None])
        menu.set_parent(button)
        menu.popup()

    def load_cover(self):
        if not self._cover_path:
            return
        pixbuf = load_cover_pixbuf(self._cover_path, COVER_SIZE)
        if pixbuf is not None:
            while child := self._cover_box.get_first_child():
                self._cover_box.remove(child)
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            pic = Gtk.Picture.new_for_paintable(texture)
            pic.set_content_fit(Gtk.ContentFit.COVER)
            pic.set_halign(Gtk.Align.FILL)
            pic.set_valign(Gtk.Align.FILL)
            pic.add_css_class('album-cover')
            self._cover_box.append(pic)
