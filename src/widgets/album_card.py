import os
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, GdkPixbuf, Gdk, GLib, Pango
from src.library import database
from src.library.models import Album
from src.widgets.cover import load_cover_pixbuf
from src.widgets.context_menu import ContextMenu

COVER_SIZE = 180
CARD_PADDING = 8   # padding on each side of the cover — card is COVER_SIZE + 2*CARD_PADDING wide
CARD_WIDTH = COVER_SIZE + CARD_PADDING * 2


class AlbumCard(Gtk.Box):
    def __init__(self, album: Album):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        # Do NOT set hexpand or a size_request on the card itself — that's
        # what was making the FlowBoxChild wider than the cover.  Instead the
        # card shrink-wraps its children; the AspectFrame below is the single
        # source of truth for the card's width.
        self.set_hexpand(False)
        self.set_halign(Gtk.Align.CENTER)

        self._album = album
        self._data = album
        self._on_play_callback = None
        self._on_add_to_queue_callback = None
        self._on_shuffle_callback = None
        self._on_info_callback = None
        self._on_add_to_playlist_callback = None

        self._cover_path = (
            album.cover_path
            if album.cover_path and os.path.exists(album.cover_path)
            else None
        )

        # ── Cover art ──────────────────────────────────────────────────────
        # The AspectFrame is the width anchor for the whole card. Its
        # allocated width (COVER_SIZE + 2*CARD_PADDING via margins) is what
        # every row below must stay within.
        frame = Gtk.AspectFrame(ratio=1.0, obey_child=False)
        frame.set_size_request(COVER_SIZE, COVER_SIZE)
        frame.set_halign(Gtk.Align.FILL)   # fill the card width so rows below align
        frame.set_margin_start(CARD_PADDING)
        frame.set_margin_end(CARD_PADDING)
        frame.set_overflow(Gtk.Overflow.HIDDEN)
        frame.add_css_class('album-cover-frame')

        self._cover_box = Gtk.Box()
        self._cover_box.set_hexpand(True)
        self._cover_box.set_vexpand(True)
        self._cover_box.add_css_class('album-cover-placeholder')
        frame.set_child(self._cover_box)

        self.append(frame)

        # ── Info row ───────────────────────────────────────────────────────
        # Same left/right margins as the frame so text aligns with cover edges.
        # set_overflow(HIDDEN) on the row prevents any child from widening the
        # card beyond CARD_WIDTH — this is the key fix for the selection-
        # highlight gap and the left-shift on long titles.
        info_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        info_row.set_margin_start(CARD_PADDING)
        info_row.set_margin_end(CARD_PADDING)
        info_row.set_overflow(Gtk.Overflow.HIDDEN)

        # Left column: title / artist / track-count.
        # hexpand=True makes it fill available space and push buttons right,
        # but it will never exceed what the row allows thanks to HIDDEN overflow.
        left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        left_col.set_halign(Gtk.Align.FILL)
        left_col.set_hexpand(True)

        # Estimate how many average-width chars fit under COVER_SIZE minus the
        # ~36 px the two icon buttons occupy.  This gives Pango a wrapping
        # budget so the label doesn't demand more width than is available.
        BUTTON_COL_PX = 24
        TEXT_COL_PX   = COVER_SIZE - BUTTON_COL_PX
        MAX_CHARS      = TEXT_COL_PX // 7   # ~7 px per average character

        title_label = Gtk.Label(label=album.title)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_hexpand(False)
        title_label.set_wrap(True)
        title_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        title_label.set_lines(2)
        title_label.set_ellipsize(Pango.EllipsizeMode.END)
        title_label.set_max_width_chars(MAX_CHARS)
        title_label.add_css_class('heading')
        left_col.append(title_label)

        display_artist = getattr(album, 'album_artist', None) or album.artist or 'Unknown Artist'
        artist_label = Gtk.Label(label=display_artist)
        artist_label.set_halign(Gtk.Align.START)
        artist_label.set_hexpand(False)
        artist_label.set_ellipsize(Pango.EllipsizeMode.END)
        artist_label.set_max_width_chars(MAX_CHARS)
        artist_label.add_css_class('dim-label')
        left_col.append(artist_label)

        info_label = Gtk.Label(label=f'{album.song_count} tracks')
        info_label.set_halign(Gtk.Align.START)
        info_label.set_hexpand(False)
        info_label.add_css_class('dim-label')
        left_col.append(info_label)

        info_row.append(left_col)

        # Right column: play + context-menu buttons — fixed width, never shrinks.
        right_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        right_col.set_halign(Gtk.Align.END)
        right_col.set_valign(Gtk.Align.CENTER)
        right_col.set_hexpand(False)

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

        # Right-click anywhere on the card opens the context menu
        right_click = Gtk.GestureClick()
        right_click.set_button(3)
        right_click.connect('pressed', lambda g, n, x, y: self._on_menu_clicked(self))
        self.add_controller(right_click)

    # ── Callback registration ───────────────────────────────────────────────

    def on_play_album(self, callback):
        self._on_play_callback = callback

    def on_add_to_queue(self, callback):
        self._on_add_to_queue_callback = callback

    def on_shuffle_album(self, callback):
        self._on_shuffle_callback = callback

    def on_info_album(self, callback):
        self._on_info_callback = callback

    def on_add_to_playlist(self, callback):
        self._on_add_to_playlist_callback = callback

    # ── Internal handlers ───────────────────────────────────────────────────

    def _on_play_clicked(self, button):
        if self._on_play_callback:
            self._on_play_callback(self._album)

    def _on_menu_clicked(self, button):
        item_id = f"{self._album.title}|||{self._album.artist}"
        liked = database.is_liked('album', item_id)
        items = [
            ('Play',            lambda: self._on_play_callback(self._album)            if self._on_play_callback            else None),
            ('Add to Queue',    lambda: self._on_add_to_queue_callback(self._album)    if self._on_add_to_queue_callback    else None),
            ('Shuffle',         lambda: self._on_shuffle_callback(self._album)         if self._on_shuffle_callback         else None),
            ('Unlike Album' if liked else 'Like Album',
                                lambda: database.toggle_like('album', item_id)),
            ('Add to Playlist', lambda: self._on_add_to_playlist_callback(self._album) if self._on_add_to_playlist_callback else None),
            ('Info',            lambda: self._on_info_callback(self._album)            if self._on_info_callback            else None),
        ]
        # Filter out entries whose callback is None (i.e. not yet registered)
        menu = ContextMenu([(label, cb) for label, cb in items if cb is not None])
        menu.set_parent(button)
        menu.popup()

    # ── Cover loading ───────────────────────────────────────────────────────

    def load_cover(self):
        """Load and display the cover image. Call after the widget is realised."""
        if not self._cover_path:
            return
        pixbuf = load_cover_pixbuf(self._cover_path, COVER_SIZE)
        if pixbuf is None:
            return

        texture = Gdk.Texture.new_for_pixbuf(pixbuf)
        pic = Gtk.Picture.new_for_paintable(texture)
        # COVER crops the image to fill the square; combined with AspectFrame
        # + overflow=HIDDEN this gives a clean square thumbnail with no
        # letterboxing and no distortion.
        pic.set_content_fit(Gtk.ContentFit.COVER)
        pic.set_hexpand(True)
        pic.set_vexpand(True)
        pic.add_css_class('album-cover')

        # Swap out the placeholder box for the actual picture
        self._cover_box.append(pic)
