import os
from typing import Callable, Optional
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib
from src.library import database
from src.library.models import Song
from src.widgets.cover import load_cover_pixbuf


def _format_time(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f'{m}:{s:02d}'


class PlayingFooter(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class('playing-footer')
        self._on_play_cb: Optional[Callable] = None
        self._on_next_cb: Optional[Callable] = None
        self._on_prev_cb: Optional[Callable] = None
        self._on_seek_cb: Optional[Callable] = None
        self._on_volume_cb: Optional[Callable] = None
        self._current_song: Optional[Song] = None

        # --- Top row: info / controls / volume ---
        top_row = Gtk.CenterBox()
        top_row.set_margin_start(12)
        top_row.set_margin_end(12)
        top_row.set_margin_top(8)
        top_row.set_margin_bottom(4)

        # Left: cover + song info
        left = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        left.set_size_request(300, -1)

        self._cover_box = Gtk.Box()
        self._cover_box.set_size_request(96, 96)
        self._cover_box.add_css_class('footer-cover')
        self._cover_pic = None
        left.append(self._cover_box)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._title_label = Gtk.Label(label='No song playing')
        self._title_label.set_halign(Gtk.Align.START)
        self._title_label.add_css_class('footer-title')
        self._artist_album_label = Gtk.Label(label='')
        self._artist_album_label.set_halign(Gtk.Align.START)
        self._artist_album_label.add_css_class('footer-artist')
        info_box.append(self._title_label)
        info_box.append(self._artist_album_label)
        left.append(info_box)

        # Center: control buttons
        center = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        self._prev_btn = Gtk.Button(label='\u23ee')
        self._prev_btn.add_css_class('flat')
        self._prev_btn.add_css_class('footer-btn')
        self._prev_btn.connect('clicked', lambda b: self._on_prev_cb() if self._on_prev_cb else None)

        self._play_btn = Gtk.Button(label='\u23ef')
        self._play_btn.add_css_class('flat')
        self._play_btn.add_css_class('footer-btn')
        self._play_btn.add_css_class('play-btn')
        self._play_btn.connect('clicked', lambda b: self._on_play_cb() if self._on_play_cb else None)

        self._next_btn = Gtk.Button(label='\u23ed')
        self._next_btn.add_css_class('flat')
        self._next_btn.add_css_class('footer-btn')
        self._next_btn.connect('clicked', lambda b: self._on_next_cb() if self._on_next_cb else None)

        center.append(self._prev_btn)
        center.append(self._play_btn)
        center.append(self._next_btn)

        # Right: star + volume
        right = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        right.set_size_request(200, -1)
        right.set_halign(Gtk.Align.END)

        self._footer_star_btn = Gtk.Button(icon_name='non-starred-symbolic')
        self._footer_star_btn.add_css_class('flat')
        self._footer_star_btn.add_css_class('footer-btn')
        self._footer_star_btn.set_tooltip_text('Like')
        self._footer_star_btn.set_opacity(0.35)
        self._footer_star_btn.set_sensitive(False)
        self._footer_star_btn.connect('clicked', self._on_footer_star_clicked)
        right.append(self._footer_star_btn)

        self._volume_btn = Gtk.MenuButton()
        self._volume_btn.set_icon_name('audio-volume-high-symbolic')
        self._volume_btn.add_css_class('flat')
        self._volume_btn.add_css_class('footer-btn')
        self._volume_popover = Gtk.Popover()
        self._volume_popover.set_position(Gtk.PositionType.TOP)
        self._volume_popup, self._volume_scale = self._build_volume_popup()
        self._volume_popover.set_child(self._volume_popup)
        self._volume_btn.set_popover(self._volume_popover)
        right.append(self._volume_btn)

        top_row.set_start_widget(left)
        top_row.set_center_widget(center)
        top_row.set_end_widget(right)

        # --- Bottom row: progress ---
        bottom_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bottom_row.set_margin_start(12)
        bottom_row.set_margin_end(12)
        bottom_row.set_margin_bottom(8)

        self._current_time = Gtk.Label(label='0:00')
        self._current_time.add_css_class('time-label')

        self._progress = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 0, 100, 1
        )
        self._progress.set_hexpand(True)
        self._progress.set_draw_value(False)
        self._progress.set_sensitive(False)
        self._progress.add_css_class('progress-slider')
        self._progress.connect('change-value', self._on_seek)

        self._total_time = Gtk.Label(label='0:00')
        self._total_time.add_css_class('time-label')

        bottom_row.append(self._current_time)
        bottom_row.append(self._progress)
        bottom_row.append(self._total_time)

        self.append(top_row)
        self.append(bottom_row)

    def _build_volume_popup(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.VERTICAL, 0, 100, 1
        )
        scale.set_value(70)
        scale.set_size_request(30, 120)
        scale.set_draw_value(False)
        scale.set_inverted(True)
        scale.connect('value-changed', self._on_volume_changed)
        box.append(scale)
        return box, scale

    # --- Public API for MainWindow ---

    def on_play(self, callback: Callable):
        self._on_play_cb = callback

    def on_next(self, callback: Callable):
        self._on_next_cb = callback

    def on_prev(self, callback: Callable):
        self._on_prev_cb = callback

    def on_seek(self, callback: Callable):
        self._on_seek_cb = callback

    def on_volume_changed(self, callback: Callable):
        self._on_volume_cb = callback

    def set_song(self, song: Optional[Song]):
        if self._cover_pic is not None:
            self._cover_box.remove(self._cover_pic)
            self._cover_pic = None

        self._current_song = song

        if song:
            self._title_label.set_label(song.title)
            self._artist_album_label.set_label(f'{song.artist} — {song.album}')
            if song.cover_path and os.path.exists(song.cover_path):
                pixbuf = load_cover_pixbuf(song.cover_path, 96)
                if pixbuf is not None:
                    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                    self._cover_pic = Gtk.Picture.new_for_paintable(texture)
                    self._cover_pic.set_content_fit(Gtk.ContentFit.COVER)  # preserves aspect ratio
                    self._cover_pic.set_size_request(96, 96)
                    self._cover_pic.add_css_class('album-cover')
                    self._cover_box.append(self._cover_pic)
            if song.id is not None:
                liked = database.is_liked('song', str(song.id))
                self._footer_star_btn.set_icon_name('starred-symbolic' if liked else 'non-starred-symbolic')
                self._footer_star_btn.set_opacity(1.0 if liked else 0.35)
                self._footer_star_btn.set_tooltip_text('Unlike' if liked else 'Like')
                self._footer_star_btn.set_sensitive(True)
        else:
            self._title_label.set_label('No song playing')
            self._artist_album_label.set_label('')
            self._footer_star_btn.set_icon_name('non-starred-symbolic')
            self._footer_star_btn.set_opacity(0.35)
            self._footer_star_btn.set_tooltip_text('Like')
            self._footer_star_btn.set_sensitive(False)

    def set_playing(self, playing: bool):
        self._play_btn.set_label('\u23f8' if playing else '\u23ef')

    def update_position(self, current: float, duration: float):
        self._current_time.set_label(_format_time(current))
        self._total_time.set_label(_format_time(duration))
        if duration > 0:
            self._progress.set_sensitive(True)
            self._progress.set_value((current / duration) * 100)
        else:
            self._progress.set_sensitive(False)
            self._progress.set_value(0)

    def _on_seek(self, scale, scroll, value):
        if self._on_seek_cb:
            self._on_seek_cb(value / 100.0)

    def _on_footer_star_clicked(self, button):
        if self._current_song and self._current_song.id is not None:
            liked = database.toggle_like('song', str(self._current_song.id))
            button.set_icon_name('starred-symbolic' if liked else 'non-starred-symbolic')
            button.set_opacity(1.0 if liked else 0.35)
            button.set_tooltip_text('Unlike' if liked else 'Like')

    def _on_volume_changed(self, scale):
        if self._on_volume_cb:
            self._on_volume_cb(scale.get_value() / 100.0)
