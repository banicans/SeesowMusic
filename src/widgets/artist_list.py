from typing import Callable, Optional
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
from src.library.models import Artist


class ArtistList(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._on_artist_activated: Optional[Callable] = None

        self._scrolled = Gtk.ScrolledWindow()
        self._scrolled.set_vexpand(True)
        self._scrolled.set_hexpand(True)

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._listbox.connect('row-activated', self._on_row_activated)
        self._listbox.set_header_func(self._header_func)

        self._scrolled.set_child(self._listbox)
        self.append(self._scrolled)

    def set_artists(self, artists: list[Artist]):
        self._clear()

        # Sort artists alphabetically by name
        sorted_artists = sorted(
            (a for a in artists if a.name.strip()),
            key=lambda a: (
                '0' + a.name.strip().upper()  # '#' group sorts last
                if not a.name.strip()[0].isalpha()
                else a.name.strip().upper()
            )
        )

        for artist in sorted_artists:
            row = Gtk.ListBoxRow()
            row._artist = artist
            row._letter = self._get_letter(artist.name)

            label = Gtk.Label(label=artist.name, xalign=0)
            label.set_margin_start(24)
            label.set_margin_end(12)
            label.set_margin_top(6)
            label.set_margin_bottom(6)
            label.set_hexpand(True)

            row.set_child(label)
            self._listbox.append(row)

    def on_artist_activated(self, callback: Callable):
        self._on_artist_activated = callback

    def _get_letter(self, name: str) -> str:
        name = name.strip()
        if not name:
            return '#'
        first = name[0].upper()
        return first if first.isalpha() else '#'

    def _header_func(self, row: Gtk.ListBoxRow, before: Optional[Gtk.ListBoxRow]):
        """Attach a letter heading to the first row in each alphabetical group."""
        current_letter = getattr(row, '_letter', None)
        before_letter = getattr(before, '_letter', None) if before else None

        if current_letter != before_letter:
            header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

            # Divider between sections (skip for the very first header)
            if before is not None:
                separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
                separator.set_margin_top(4)
                separator.set_margin_bottom(4)
                header_box.append(separator)

            label = Gtk.Label(label=current_letter)
            label.add_css_class('heading')
            label.set_halign(Gtk.Align.START)
            label.set_margin_start(12)
            label.set_margin_top(12)
            label.set_margin_bottom(4)
            header_box.append(label)

            row.set_header(header_box)
        else:
            row.set_header(None)

    def _clear(self):
        while child := self._listbox.get_first_child():
            self._listbox.remove(child)

    def _on_row_activated(self, listbox: Gtk.ListBox, row: Gtk.ListBoxRow):
        if self._on_artist_activated and hasattr(row, '_artist'):
            self._on_artist_activated(row._artist)
