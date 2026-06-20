from typing import Optional, Callable
import hashlib
import cairo
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Pango
from src.library.models import Genre

COVER_SIZE = 180
CARD_PADDING = 8
CARD_WIDTH = COVER_SIZE + CARD_PADDING * 2


def _genre_color(name: str) -> tuple[float, float, float]:
    h = int(hashlib.md5(name.encode()).hexdigest()[:8], 16) / 0xffffffff
    sat = 0.45
    lgt = 0.55
    c = (1 - abs(2 * lgt - 1)) * sat
    x = c * (1 - abs((h * 6) % 2 - 1))
    m = lgt - c / 2
    if h < 1/6:
        return (c + m, x + m, m)
    elif h < 2/6:
        return (x + m, c + m, m)
    elif h < 3/6:
        return (m, c + m, x + m)
    elif h < 4/6:
        return (m, x + m, c + m)
    elif h < 5/6:
        return (x + m, m, c + m)
    else:
        return (c + m, m, x + m)


class GenreCard(Gtk.Box):
    def __init__(self, genre: Genre):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.set_hexpand(False)
        self._genre = genre
        self._data = genre
        self.set_size_request(CARD_WIDTH, -1)
        self.set_halign(Gtk.Align.CENTER)

        self._cover_box = Gtk.Box()
        self._cover_box.set_size_request(COVER_SIZE, COVER_SIZE)
        self._cover_box.set_halign(Gtk.Align.CENTER)
        self._cover_box.set_margin_start(CARD_PADDING)
        self._cover_box.set_margin_end(CARD_PADDING)

        da = Gtk.DrawingArea()
        da.set_size_request(COVER_SIZE, COVER_SIZE)
        da.set_halign(Gtk.Align.CENTER)
        da.set_valign(Gtk.Align.CENTER)

        color = _genre_color(genre.name)
        letter = genre.name[0].upper() if genre.name else '?'

        def _rounded_rect(cr, x, y, w, h, r):
            cr.move_to(x + r, y)
            cr.line_to(x + w - r, y)
            cr.arc(x + w - r, y + r, r, -1.5708, 0)
            cr.line_to(x + w, y + h - r)
            cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
            cr.line_to(x + r, y + h)
            cr.arc(x + r, y + h - r, r, 1.5708, 3.14159)
            cr.line_to(x, y + r)
            cr.arc(x + r, y + r, r, 3.14159, 4.71239)
            cr.close_path()

        def draw(_area, cr, w, h):
            _rounded_rect(cr, 2, 2, w - 4, h - 4, 24)
            cr.set_source_rgb(*color)
            cr.fill()
            cr.set_source_rgb(1, 1, 1)
            cr.select_font_face('Sans', cairo.FontSlant.NORMAL, cairo.FontWeight.BOLD)
            cr.set_font_size(w * 0.42)
            ext = cr.text_extents(letter)
            cr.move_to((w - ext.width) / 2, (h + ext.height) / 2)
            cr.show_text(letter)

        da.set_draw_func(draw)
        self._cover_box.append(da)
        self.append(self._cover_box)

        info_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        info_row.set_margin_start(CARD_PADDING)
        info_row.set_margin_end(CARD_PADDING)

        left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        left_col.set_halign(Gtk.Align.START)
        left_col.set_hexpand(True)

        name_label = Gtk.Label(label=genre.name)
        name_label.set_halign(Gtk.Align.START)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.add_css_class('heading')
        left_col.append(name_label)

        info_label = Gtk.Label(label=f'{genre.song_count} songs')
        info_label.set_halign(Gtk.Align.START)
        info_label.add_css_class('dim-label')
        left_col.append(info_label)

        info_row.append(left_col)
        self.append(info_row)
