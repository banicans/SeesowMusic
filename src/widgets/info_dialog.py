import os
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Pango, Gdk
from src.library.models import Song, Album
from src.library import database
from src.widgets.cover import load_cover_pixbuf


COVER_SIZE = 150


def _format_played_at(dt_str: str | None) -> str:
    if not dt_str:
        return '\u2014'
    date_part = dt_str[:10]
    return date_part


class InfoDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(transient_for=parent, modal=True)
        self.set_default_size(450, -1)
        self.set_title('Info')
        self.add_button('Close', Gtk.ResponseType.CLOSE)
        self.connect('response', lambda d, r: d.close())

        self._content = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=12
        )
        self._content.set_margin_start(16)
        self._content.set_margin_end(16)
        self._content.set_margin_top(16)
        self._content.set_margin_bottom(16)

        self._cover_box = Gtk.Box()
        self._cover_box.set_valign(Gtk.Align.CENTER)

        self._info_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=0
        )
        self._info_box.set_hexpand(True)
        self._info_box.set_valign(Gtk.Align.START)

        self._content.append(self._cover_box)
        self._content.append(self._info_box)

        content_area = self.get_content_area()
        content_area.append(self._content)

    def _clear_info_box(self):
        while child := self._info_box.get_first_child():
            self._info_box.remove(child)
        while child := self._cover_box.get_first_child():
            self._cover_box.remove(child)

    def _add_cover(self, cover_path: str | None, size: int):
        if cover_path and os.path.exists(cover_path):
            pixbuf = load_cover_pixbuf(cover_path, size)
            if pixbuf:
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                pic = Gtk.Picture.new_for_paintable(texture)
                pic.set_content_fit(Gtk.ContentFit.COVER)
                pic.set_size_request(size, size)
                pic.add_css_class('album-cover')
                self._cover_box.append(pic)
                return
        placeholder = Gtk.Box()
        placeholder.set_size_request(size, size)
        placeholder.add_css_class('cover-placeholder')
        self._cover_box.append(placeholder)

    def _add_info_row(self, label: str, value: str, selectable: bool = False):
        if value:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            lbl = Gtk.Label(label=label)
            lbl.set_xalign(0)
            lbl.add_css_class('dim-label')
            row.append(lbl)

            val = Gtk.Label(label=value)
            val.set_xalign(0)
            val.set_hexpand(True)
            val.set_ellipsize(Pango.EllipsizeMode.END)
            if selectable:
                val.set_selectable(True)
            row.append(val)
            self._info_box.append(row)

    def _add_spacer(self, height: int = 6):
        spacer = Gtk.Box()
        spacer.set_size_request(-1, height)
        self._info_box.append(spacer)

    def show_song(self, song: Song):
        self._clear_info_box()
        self.set_title(f'{song.title} \u2014 Info')

        self._add_cover(song.cover_path, COVER_SIZE)

        title = Gtk.Label(label=song.title)
        title.set_xalign(0)
        title.add_css_class('title-1')
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.set_wrap(True)
        self._info_box.append(title)

        artist = Gtk.Label(label=song.artist or 'Unknown Artist')
        artist.set_xalign(0)
        artist.add_css_class('title-4')
        self._info_box.append(artist)

        self._add_spacer(10)
        self._add_info_row('Album:', song.album)
        self._add_info_row('Album Artist:', song.album_artist)
        self._add_info_row('Track:', str(song.track_number) if song.track_number else '—')
        self._add_info_row('Year:', str(song.year) if song.year else '—')
        self._add_info_row('Genre:', song.genre or '—')

        mins, secs = divmod(int(song.duration), 60)
        hrs = mins // 60
        if hrs:
            self._add_info_row('Duration:', f'{hrs}:{mins % 60:02d}:{secs:02d}')
        else:
            self._add_info_row('Duration:', f'{mins}:{secs:02d}')

        self._add_spacer(10)
        self._add_info_row('File:', song.path, selectable=True)

        if song.id is not None:
            play_count = database.get_song_play_count(song.id)
            last_played = database.get_song_last_played(song.id)
            self._add_spacer(6)
            self._add_info_row('Played:', f'{play_count} times')
            self._add_info_row('Last Played:', _format_played_at(last_played))

    def show_album(self, album: Album):
        self._clear_info_box()
        self.set_title(f'{album.title} \u2014 Info')

        self._add_cover(album.cover_path, COVER_SIZE)

        title = Gtk.Label(label=album.title)
        title.set_xalign(0)
        title.add_css_class('title-1')
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.set_wrap(True)
        self._info_box.append(title)

        artist = Gtk.Label(label=album.artist or 'Unknown Artist')
        artist.set_xalign(0)
        artist.add_css_class('title-4')
        self._info_box.append(artist)

        self._add_spacer(10)
        self._add_info_row('Year:', str(album.year) if album.year else '—')
        self._add_info_row('Tracks:', str(album.song_count))

        if album.songs:
            total = sum(s.duration for s in album.songs)
            mins, secs = divmod(int(total), 60)
            hrs = mins // 60
            if hrs:
                self._add_info_row('Total Duration:', f'{hrs}:{mins % 60:02d}:{secs:02d}')
            else:
                self._add_info_row('Total Duration:', f'{mins}:{secs:02d}')

        play_count = database.get_album_play_count(album.title, album.artist)
        last_played = database.get_album_last_played(album.title, album.artist)
        self._add_spacer(6)
        self._add_info_row('Played:', f'{play_count} times')
        self._add_info_row('Last Played:', _format_played_at(last_played))
