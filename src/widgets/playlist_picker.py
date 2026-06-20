from typing import Callable, Optional

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Pango

from src.library import database


class PlaylistPicker(Gtk.Dialog):
    def __init__(self, parent, song_ids: list[int]):
        super().__init__(
            title='Add to Playlist',
            transient_for=parent,
            modal=True
        )
        self.set_default_size(380, 350)
        self._song_ids = song_ids
        self._checkbuttons: list[tuple[int, Gtk.CheckButton]] = []

        self.add_button('Cancel', Gtk.ResponseType.CANCEL)
        self.add_button('Add', Gtk.ResponseType.OK)

        content = self.get_content_area()
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_spacing(8)

        label = Gtk.Label(label=f'Add {len(song_ids)} song(s) to:')
        label.set_xalign(0)
        content.append(label)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_min_content_height(200)

        listbox = Gtk.ListBox()
        listbox.add_css_class('card')

        playlists = database.get_playlists()
        for pl in playlists:
            row = Gtk.ListBoxRow()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.set_margin_start(4)
            box.set_margin_end(4)
            box.set_margin_top(4)
            box.set_margin_bottom(4)

            cb = Gtk.CheckButton()
            box.append(cb)

            name_label = Gtk.Label(label=pl.name)
            name_label.set_xalign(0)
            name_label.set_hexpand(True)
            name_label.set_ellipsize(Pango.EllipsizeMode.END)
            box.append(name_label)

            count_label = Gtk.Label(label=f'{pl.song_count} songs')
            count_label.add_css_class('dim-label')
            box.append(count_label)

            row.set_child(box)
            listbox.append(row)
            self._checkbuttons.append((pl.id, cb))

        scrolled.set_child(listbox)
        content.append(scrolled)

        self.connect('response', self._on_response)

    def _on_response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            for pl_id, cb in self._checkbuttons:
                if cb.get_active():
                    database.add_songs_to_playlist(pl_id, self._song_ids)
        self.close()
