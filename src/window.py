import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GLib, Pango

import os
import random

from src.dialogs import SettingsDialog
from src.widgets.cover import load_cover_pixbuf
from src.widgets.info_dialog import InfoDialog
from src.library import database
from src.widgets.list import SongList
from src.widgets.artist_list import ArtistList
from src.widgets.card_grid import CardGrid
from src.widgets.album_card import AlbumCard
from src.widgets.album_detail import AlbumDetail
from src.widgets.playlist_card import PlaylistCard
from src.widgets.playlist_detail import PlaylistDetail
from src.widgets.artist_detail import ArtistDetail
from src.widgets.genre_card import GenreCard
from src.widgets.genre_detail import GenreDetail
from src.widgets.playlist_picker import PlaylistPicker
from src.widgets.context_menu import ContextMenu
from src.widgets.playing_footer import PlayingFooter
from src.queue_manager import QueueManager
from src.audio.player import AudioPlayer
from src.splash import LoadingOverlay


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title('Seesow Music')
        self.set_default_size(1200, 800)

        database.init_db()
        self._apply_styles()

        self._queue_manager = QueueManager()
        self._audio_player = AudioPlayer()

        self._covers_ready = False
        self._current_playlist_id = None
        self._album_sort_by = 'title'
        self._album_sort_order_asc = True
        self._build_stack()
        self._all_songs = database.get_all_songs()
        self._refresh_queue()
        self._start_cover_loading()

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(self._build_header())
        toolbar_view.set_content(self._build_content())

        self._wire_footer()

        overlay = Gtk.Overlay()
        overlay.set_child(toolbar_view)
        self._loading_overlay = LoadingOverlay()
        overlay.add_overlay(self._loading_overlay)
        self._loading_overlay.set_visible(True)
        self.set_content(overlay)
        self._setup_shortcuts()

    def _build_header(self):
        header = Adw.HeaderBar()

        view_switcher = Adw.ViewSwitcher()
        view_switcher.set_stack(self._stack)
        header.set_title_widget(view_switcher)

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text('Search...')
        self._search_entry.set_size_request(300, -1)
        self._search_entry.connect('search-changed', self._on_search_changed)
        self._search_entry.connect('stop-search', lambda e: self._hide_search_results())

        settings_btn = Gtk.Button(icon_name='emblem-system-symbolic')
        settings_btn.add_css_class('flat')
        settings_btn.connect('clicked', lambda b: self._open_settings())

        header.pack_end(settings_btn)
        header.pack_end(self._search_entry)

        return header

    def _build_content(self):
        self._search_results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._search_results_box.add_css_class('search-results-panel')

        self._search_revealer = Gtk.Revealer()
        self._search_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self._search_revealer.set_child(self._search_results_box)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(self._search_revealer)
        box.append(self._stack)
        self._footer = PlayingFooter()
        box.append(self._footer)
        return box

    _TAB_ICONS = {
        'Home': 'go-home-symbolic',
        'Albums': 'media-optical-cd-audio-symbolic',
        'Artists': 'avatar-default-symbolic',
        'Genres': 'audio-x-generic-symbolic',
        'Playlists': 'xapp-user-favorites-symbolic',
        'Queue': 'xsi-media-playlist-consecutive-symbolic',
    }

    def _build_stack(self):
        self._stack = Adw.ViewStack()
        self._stack.set_transition_duration(200)

        for name in self._TAB_ICONS:
            if name == 'Queue':
                page = self._build_queue_tab()
            elif name == 'Albums':
                page = self._build_albums_tab()
            elif name == 'Artists':
                page = self._build_artists_tab()
            elif name == 'Playlists':
                page = self._build_playlists_tab()
            elif name == 'Genres':
                page = self._build_genres_tab()
            elif name == 'Home':
                page = self._build_home_tab()
            else:
                label = Gtk.Label(label=f'{name} Tab')
                label.set_vexpand(True)
                page = self._stack.add_titled(label, name, name)
            page.set_icon_name(self._TAB_ICONS[name])

    def _build_queue_tab(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top_bar.set_margin_start(12)
        top_bar.set_margin_end(12)
        top_bar.set_margin_top(8)
        top_bar.set_margin_bottom(8)

        save_btn = Gtk.Button(label='Save as Playlist')
        save_btn.add_css_class('flat')
        save_btn.connect('clicked', lambda b: self._on_save_queue())

        clear_btn = Gtk.Button(label='Clear')
        clear_btn.add_css_class('flat')
        clear_btn.connect('clicked', lambda b: self._on_clear_queue())

        add_to_pl_btn = Gtk.Button(label='Add to Playlist')
        add_to_pl_btn.add_css_class('flat')
        add_to_pl_btn.connect('clicked', lambda b: self._on_add_queue_to_playlist())

        left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        left_box.append(save_btn)
        left_box.append(add_to_pl_btn)
        left_box.append(clear_btn)

        self._queue_info_label = Gtk.Label(label='')
        self._queue_info_label.add_css_class('dim-label')

        menu_btn = Gtk.Button(label='\u22ef')
        menu_btn.add_css_class('flat')
        menu_btn.add_css_class('menu-btn')
        menu_btn.connect('clicked', self._on_queue_menu)

        right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        right_box.set_hexpand(True)
        right_box.set_halign(Gtk.Align.END)
        right_box.append(self._queue_info_label)
        right_box.append(menu_btn)

        top_bar.append(left_box)
        top_bar.append(right_box)

        self._queue_list = SongList(drag_enabled=True)
        self._queue_list.on_song_activated(self._on_queue_song_clicked)
        self._queue_list.on_song_menu(self._on_queue_song_menu)
        self._queue_list.on_reorder(self._on_queue_reorder)
        self._queue_manager.on_change(self._refresh_queue)

        box.append(top_bar)
        box.append(self._queue_list)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        top_bar.append(separator)

        return self._stack.add_titled(box, 'Queue', 'Queue')

    def _build_albums_tab(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top_bar.set_margin_start(12)
        top_bar.set_margin_end(12)
        top_bar.set_margin_top(8)
        top_bar.set_margin_bottom(8)

        sort_label = Gtk.Label(label='Sort:')
        sort_label.add_css_class('dim-label')
        top_bar.append(sort_label)

        self._album_sort_dropdown = Gtk.DropDown(
            model=Gtk.StringList.new(['Title', 'Artist', 'Year'])
        )
        self._album_sort_dropdown.connect('notify::selected', self._on_album_sort_changed)
        top_bar.append(self._album_sort_dropdown)

        self._album_sort_dir_btn = Gtk.Button(label='\u2191')
        self._album_sort_dir_btn.add_css_class('flat')
        self._album_sort_dir_btn.connect('clicked', self._on_album_sort_dir_changed)
        top_bar.append(self._album_sort_dir_btn)

        self._album_grid = CardGrid()
        self._album_grid.on_card_activated(self._on_album_activated)

        grid_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        grid_box.append(top_bar)
        grid_box.append(self._album_grid)

        self._album_stack = Gtk.Stack()
        self._album_stack.set_transition_duration(200)
        self._album_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self._album_stack.add_named(grid_box, 'grid')
        outer.append(self._album_stack)

        self._refresh_albums()
        return self._stack.add_titled(outer, 'Albums', 'Albums')

    def _build_playlists_tab(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top_bar.set_margin_start(12)
        top_bar.set_margin_end(12)
        top_bar.set_margin_top(8)
        top_bar.set_margin_bottom(8)

        new_btn = Gtk.Button(label='New Playlist')
        new_btn.add_css_class('flat')
        new_btn.connect('clicked', lambda b: self._on_new_playlist())
        top_bar.append(new_btn)

        self._playlist_grid = CardGrid()
        self._playlist_grid.on_card_activated(self._on_playlist_activated)

        grid_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        grid_box.append(top_bar)
        grid_box.append(self._playlist_grid)

        self._playlist_stack = Gtk.Stack()
        self._playlist_stack.set_transition_duration(200)
        self._playlist_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self._playlist_stack.add_named(grid_box, 'grid')
        outer.append(self._playlist_stack)

        self._refresh_playlists()
        return self._stack.add_titled(outer, 'Playlists', 'Playlists')

    def _build_genres_tab(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top_bar.set_margin_start(12)
        top_bar.set_margin_end(12)
        top_bar.set_margin_top(8)
        top_bar.set_margin_bottom(8)

        label = Gtk.Label(label='Genres')
        label.add_css_class('heading')
        top_bar.append(label)

        self._genre_grid = CardGrid()
        self._genre_grid.on_card_activated(self._on_genre_activated)

        grid_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        grid_box.append(top_bar)
        grid_box.append(self._genre_grid)

        self._genre_stack = Gtk.Stack()
        self._genre_stack.set_transition_duration(200)
        self._genre_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self._genre_stack.add_named(grid_box, 'grid')
        outer.append(self._genre_stack)

        self._refresh_genres()
        return self._stack.add_titled(outer, 'Genres', 'Genres')

    def _refresh_genres(self):
        genres = database.get_genres()
        cards = []
        for genre in genres:
            card = GenreCard(genre)
            cards.append(card)
        self._genre_grid.set_cards(cards)

    def _build_home_tab(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # ── Your Mix ──
        self._mix_songs = []
        self._mix_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._mix_box.set_margin_start(16)
        self._mix_box.set_margin_end(16)
        self._mix_box.set_margin_top(20)

        mix_center = Gtk.CenterBox()

        # Left: cascading covers
        cover_base = Gtk.Box()
        cover_base.set_size_request(140, 140)
        self._mix_cover_overlay = Gtk.Overlay()
        self._mix_cover_overlay.set_child(cover_base)

        self._mix_cover_pics = []
        for _ in range(3):
            pic = Gtk.Picture()
            pic.set_size_request(84, 84)
            pic.set_content_fit(Gtk.ContentFit.COVER)
            pic.add_css_class('album-cover')
            pic.set_halign(Gtk.Align.START)
            pic.set_valign(Gtk.Align.END)
            pic.set_visible(False)
            self._mix_cover_pics.append(pic)

        # Back (dimmsest, furthest up-right)
        self._mix_cover_pics[2].set_margin_start(48)
        self._mix_cover_pics[2].set_margin_bottom(48)
        self._mix_cover_pics[2].set_opacity(0.25)
        self._mix_cover_overlay.add_overlay(self._mix_cover_pics[2])

        # Middle
        self._mix_cover_pics[1].set_margin_start(24)
        self._mix_cover_pics[1].set_margin_bottom(24)
        self._mix_cover_pics[1].set_opacity(0.55)
        self._mix_cover_overlay.add_overlay(self._mix_cover_pics[1])

        # Front (full opacity, bottom-left)
        self._mix_cover_pics[0].set_margin_start(0)
        self._mix_cover_pics[0].set_margin_bottom(0)
        self._mix_cover_pics[0].set_opacity(1.0)
        self._mix_cover_overlay.add_overlay(self._mix_cover_pics[0])

        mix_center.set_start_widget(self._mix_cover_overlay)

        # Right: text + buttons
        right_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right_col.set_hexpand(True)
        right_col.set_valign(Gtk.Align.START)
        right_col.set_halign(Gtk.Align.END)

        mix_heading = Gtk.Label(label='Your Mix')
        mix_heading.add_css_class('title-1')
        mix_heading.set_halign(Gtk.Align.END)
        mix_heading.set_xalign(1.0)
        right_col.append(mix_heading)

        self._mix_featuring = Gtk.Label(label='')
        self._mix_featuring.set_halign(Gtk.Align.END)
        self._mix_featuring.set_xalign(1.0)
        self._mix_featuring.set_ellipsize(Pango.EllipsizeMode.END)
        self._mix_featuring.add_css_class('dim-label')
        right_col.append(self._mix_featuring)

        self._mix_count = Gtk.Label(label='')
        self._mix_count.set_halign(Gtk.Align.END)
        self._mix_count.set_xalign(1.0)
        self._mix_count.add_css_class('dim-label')
        right_col.append(self._mix_count)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_margin_top(6)
        btn_row.set_halign(Gtk.Align.END)
        play_btn = Gtk.Button(label='\u25b6 Play All')
        play_btn.add_css_class('suggested-action')
        play_btn.connect('clicked', self._on_mix_play_all)
        self._mix_refresh_btn = Gtk.Button(label='\u21bb Refresh')
        self._mix_refresh_btn.add_css_class('flat')
        self._mix_refresh_btn.connect('clicked', self._on_mix_refresh)
        btn_row.append(play_btn)
        btn_row.append(self._mix_refresh_btn)
        right_col.append(btn_row)

        mix_center.set_end_widget(right_col)
        self._mix_box.append(mix_center)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(8)
        sep.set_margin_bottom(4)
        self._mix_box.append(sep)

        outer.append(self._mix_box)

        self._home_stats_label = Gtk.Label(label='')
        self._home_stats_label.set_margin_start(16)
        self._home_stats_label.set_margin_end(16)
        self._home_stats_label.set_margin_top(8)
        self._home_stats_label.set_halign(Gtk.Align.START)
        self._home_stats_label.add_css_class('dim-label')
        outer.append(self._home_stats_label)

        heading = Gtk.Label(label='Recently Played')
        heading.add_css_class('heading')
        heading.set_margin_start(16)
        heading.set_margin_end(16)
        heading.set_margin_top(16)
        heading.set_margin_bottom(4)
        heading.set_halign(Gtk.Align.START)

        self._home_list = SongList(show_album=True)
        self._home_list.on_song_activated(self._on_song_clicked)
        self._home_list.on_song_menu(self._on_song_context_menu)

        recent_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        recent_box.append(heading)
        recent_box.append(self._home_list)

        fav_heading = Gtk.Label(label='Favourite Albums')
        fav_heading.add_css_class('heading')
        fav_heading.set_margin_start(16)
        fav_heading.set_margin_end(16)
        fav_heading.set_margin_top(16)
        fav_heading.set_margin_bottom(4)
        fav_heading.set_halign(Gtk.Align.START)

        self._home_fav_grid = CardGrid()
        self._home_fav_grid.on_card_activated(self._on_home_album_activated)
        self._home_fav_grid.set_vexpand(False)
        self._home_fav_grid.set_propagate_natural_height(True)

        fav_artists_heading = Gtk.Label(label='Favourite Artists')
        fav_artists_heading.add_css_class('heading')
        fav_artists_heading.set_margin_start(16)
        fav_artists_heading.set_margin_end(16)
        fav_artists_heading.set_margin_top(12)
        fav_artists_heading.set_margin_bottom(4)
        fav_artists_heading.set_halign(Gtk.Align.START)

        self._home_artist_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._home_artist_box.set_margin_start(16)
        self._home_artist_box.set_margin_end(16)

        fav_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        fav_box.append(fav_heading)
        fav_box.append(self._home_fav_grid)
        fav_box.append(fav_artists_heading)
        fav_box.append(self._home_artist_box)

        middle = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        middle.set_vexpand(True)
        middle.append(recent_box)
        middle.append(fav_box)
        outer.append(middle)

        self._refresh_home()
        return self._stack.add_titled(outer, 'Home', 'Home')

    def _refresh_home(self):
        # ── Your Mix ──
        self._mix_songs = database.get_smart_playlist(30)
        if self._mix_songs:
            sep = database.get_setting('artist_separator', '')
            artists = []
            for s in self._mix_songs:
                parts = [p.strip() for p in s.artist.split(sep)] if sep else [s.artist.strip()]
                for name in parts:
                    if name and name not in artists:
                        artists.append(name)
                        if len(artists) >= 5:
                            break
                if len(artists) >= 5:
                    break
            self._mix_featuring.set_text(f'Featuring: {", ".join(artists)}')
            self._mix_featuring.set_visible(True)
            count = len(self._mix_songs)
            self._mix_count.set_label(f'{count} song{"s" if count != 1 else ""}')
            self._mix_box.set_visible(True)
            GLib.idle_add(self._load_mix_covers)
        else:
            self._mix_box.set_visible(False)

        stats = database.get_library_stats()
        self._home_stats_label.set_text(
            f'{stats["songs"]} songs  \u2022  {stats["albums"]} albums  \u2022  {stats["artists"]} artists  \u2022  {stats["playlists"]} playlists'
        )
        songs = database.get_recently_played(7)
        self._home_list.set_songs(songs)

        while child := self._home_artist_box.get_first_child():
            self._home_artist_box.remove(child)
        for artist_name, count in database.get_favourite_artists(5):
            inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            name_lbl = Gtk.Label(label=artist_name)
            name_lbl.set_halign(Gtk.Align.START)
            name_lbl.set_hexpand(True)
            name_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            count_lbl = Gtk.Label(label=f'{count}')
            count_lbl.add_css_class('dim-label')
            count_lbl.set_halign(Gtk.Align.END)
            inner.append(name_lbl)
            inner.append(count_lbl)
            btn = Gtk.Button()
            btn.add_css_class('flat')
            btn.add_css_class('home-artist-row')
            btn.set_child(inner)
            btn.connect('clicked', lambda _b, name=artist_name: self._on_fav_artist_clicked(name))
            self._home_artist_box.append(btn)

        fav_albums = database.get_favourite_albums(5)
        cards = []
        for album in fav_albums:
            card = AlbumCard(album)
            card.on_play_album(self._on_play_album)
            card.on_add_to_queue(self._on_add_to_queue_album)
            card.on_shuffle_album(self._on_shuffle_album)
            card.on_add_to_playlist(self._on_add_album_to_playlist)
            card.on_info_album(self._show_album_info)
            cards.append(card)
        self._home_fav_grid.set_cards(cards)

        if cards:
            GLib.idle_add(self._load_home_fav_covers, cards)

    def _on_mix_play_all(self, button):
        if not self._mix_songs:
            return
        songs = list(self._mix_songs)
        random.shuffle(songs)
        self._queue_manager.clear()
        for song in songs:
            self._queue_manager.add(song)
        self._play_song(songs[0])

    def _fade_pic(self, pic: Gtk.Picture, target: float, duration_ms: int = 200):
        steps = max(4, duration_ms // 30)
        start = pic.get_opacity()
        step = (target - start) / steps
        remaining = steps

        def tick():
            nonlocal remaining
            remaining -= 1
            pic.set_opacity(target - remaining * step)
            return remaining > 0

        GLib.timeout_add(duration_ms // steps, tick)

    def _on_mix_refresh(self, button):
        button.set_sensitive(False)
        button.set_label('\u21bb Refreshing\u2026')
        for pic in self._mix_cover_pics:
            self._fade_pic(pic, 0.0, 200)
        GLib.timeout_add(400, self._delayed_mix_refresh)

    def _delayed_mix_refresh(self):
        self._refresh_home()
        return False

    def _load_mix_covers(self):
        for pic in self._mix_cover_pics:
            pic.set_paintable(None)
            pic.set_visible(False)

        added = 0
        seen_covers: set[str] = set()
        for song in self._mix_songs:
            if added >= 3:
                break
            if song.cover_path and song.cover_path not in seen_covers and os.path.exists(song.cover_path):
                seen_covers.add(song.cover_path)
                pixbuf = load_cover_pixbuf(song.cover_path, 84)
                if pixbuf:
                    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                    self._mix_cover_pics[added].set_paintable(texture)
                    self._mix_cover_pics[added].set_visible(True)
                    added += 1

        self._mix_cover_pics[2].set_opacity(0.0)
        self._mix_cover_pics[1].set_opacity(0.0)
        self._mix_cover_pics[0].set_opacity(0.0)
        GLib.idle_add(lambda: self._fade_pic(self._mix_cover_pics[2], 0.25, 200))
        GLib.idle_add(lambda: self._fade_pic(self._mix_cover_pics[1], 0.55, 200))
        GLib.idle_add(lambda: self._fade_pic(self._mix_cover_pics[0], 1.0, 200))
        self._mix_refresh_btn.set_sensitive(True)
        self._mix_refresh_btn.set_label('\u21bb Refresh')
        return GLib.SOURCE_REMOVE

    def _load_home_fav_covers(self, cards):
        for card in cards:
            if card._cover_path:
                card.load_cover()
        return GLib.SOURCE_REMOVE

    def _refresh_albums(self):
        self._all_albums = database.get_albums()
        rev = not self._album_sort_order_asc
        if self._album_sort_by == 'title':
            self._all_albums.sort(key=lambda a: a.title.lower(), reverse=rev)
        elif self._album_sort_by == 'artist':
            self._all_albums.sort(key=lambda a: a.artist.lower(), reverse=rev)
        elif self._album_sort_by == 'year':
            self._all_albums.sort(key=lambda a: a.year if a.year else 9999, reverse=rev)

        cards = []
        for album in self._all_albums:
            card = AlbumCard(album)
            card.on_play_album(self._on_play_album)
            card.on_add_to_queue(self._on_add_to_queue_album)
            card.on_shuffle_album(self._on_shuffle_album)
            card.on_info_album(self._show_album_info)
            card.on_add_to_playlist(self._on_add_album_to_playlist)
            cards.append(card)
        self._album_cards = cards
        self._album_grid.set_cards(cards)

    def _on_album_sort_changed(self, *args):
        idx = self._album_sort_dropdown.get_selected()
        fields = ['title', 'artist', 'year']
        self._album_sort_by = fields[idx] if 0 <= idx < len(fields) else 'title'
        self._refresh_albums()
        self._start_cover_loading()

    def _on_album_sort_dir_changed(self, button):
        self._album_sort_order_asc = not self._album_sort_order_asc
        button.set_label('\u2191' if self._album_sort_order_asc else '\u2193')
        self._refresh_albums()
        self._start_cover_loading()

    def _refresh_playlists(self):
        playlists = database.get_playlists()
        cards = []
        for pl in playlists:
            card = PlaylistCard(pl)
            card.on_play_playlist(self._on_play_playlist)
            card.on_add_to_queue(self._on_add_to_queue_playlist)
            card.on_rename_playlist(self._on_rename_playlist)
            card.on_delete_playlist(self._on_delete_playlist)
            cards.append(card)
        self._playlist_grid.set_cards(cards)

        if playlists:
            GLib.idle_add(self._load_playlist_covers, cards)

    def _load_playlist_covers(self, cards):
        for card in cards:
            if card._cover_path:
                card.load_cover()
        return GLib.SOURCE_REMOVE

    def _build_artists_tab(self):
        self._artist_list = ArtistList()
        self._artist_list.on_artist_activated(self._on_artist_activated)
        self._all_artists = database.get_artists()
        self._artist_list.set_artists(self._all_artists)

        self._artist_stack = Gtk.Stack()
        self._artist_stack.set_transition_duration(200)
        self._artist_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self._artist_stack.add_named(self._artist_list, 'list')
        return self._stack.add_titled(self._artist_stack, 'Artists', 'Artists')

    def _hide_search_results(self):
        self._search_revealer.set_reveal_child(False)

    def _on_search_changed(self, entry):
        query = entry.get_text().strip().lower()
        if not query:
            self._hide_search_results()
            return

        song_matches = []
        album_matches = []
        artist_matches = []

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_margin_top(12)
        content.set_margin_bottom(12)

        any_results = False

        # --- Songs ---
        song_matches = [
            s for s in self._all_songs
            if query in s.title.lower()
        ][:10]
        if song_matches:
            any_results = True
            header = Gtk.Label(label=f'Songs ({len(song_matches)})')
            header.add_css_class('heading')
            header.set_halign(Gtk.Align.START)
            header.set_margin_bottom(2)
            content.append(header)
            for song in song_matches:
                row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                title_lbl = Gtk.Label(label=song.title)
                title_lbl.set_halign(Gtk.Align.START)
                title_lbl.set_hexpand(False)
                title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
                artist_lbl = Gtk.Label(label=song.artist)
                artist_lbl.add_css_class('dim-label')
                artist_lbl.set_halign(Gtk.Align.START)
                artist_lbl.set_ellipsize(Pango.EllipsizeMode.END)
                album_lbl = Gtk.Label(label=song.album)
                album_lbl.add_css_class('dim-label')
                album_lbl.set_halign(Gtk.Align.START)
                album_lbl.set_ellipsize(Pango.EllipsizeMode.END)
                row_box.append(title_lbl)
                row_box.append(artist_lbl)
                row_box.append(album_lbl)
                row_box.add_css_class('search-result-row')
                gesture = Gtk.GestureClick()
                gesture.connect('pressed', lambda g, n, x, y, s=song: self._on_search_song(s))
                row_box.add_controller(gesture)
                content.append(row_box)

        if song_matches and (album_matches or artist_matches):
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            sep.set_margin_top(4)
            sep.set_margin_bottom(4)
            content.append(sep)

        # --- Albums ---
        album_matches = [
            a for a in self._all_albums
            if query in a.title.lower()
        ][:5]
        if album_matches:
            any_results = True
            header = Gtk.Label(label=f'Albums ({len(album_matches)})')
            header.add_css_class('heading')
            header.set_halign(Gtk.Align.START)
            header.set_margin_bottom(2)
            content.append(header)
            for album in album_matches:
                row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                title_lbl = Gtk.Label(label=album.title)
                title_lbl.set_halign(Gtk.Align.START)
                title_lbl.set_ellipsize(Pango.EllipsizeMode.END)
                artist_lbl = Gtk.Label(label=album.artist)
                artist_lbl.add_css_class('dim-label')
                artist_lbl.set_halign(Gtk.Align.START)
                artist_lbl.set_ellipsize(Pango.EllipsizeMode.END)
                row_box.append(title_lbl)
                row_box.append(artist_lbl)
                row_box.add_css_class('search-result-row')
                gesture = Gtk.GestureClick()
                gesture.connect('pressed', lambda g, n, x, y, a=album: self._on_search_album(a))
                row_box.add_controller(gesture)
                content.append(row_box)

        if album_matches and artist_matches:
            sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            sep.set_margin_top(4)
            sep.set_margin_bottom(4)
            content.append(sep)

        # --- Artists ---
        artist_matches = [
            a for a in self._all_artists
            if query in a.name.lower()
        ][:10]
        if artist_matches:
            any_results = True
            header = Gtk.Label(label=f'Artists ({len(artist_matches)})')
            header.add_css_class('heading')
            header.set_halign(Gtk.Align.START)
            header.set_margin_bottom(2)
            content.append(header)
            for artist in artist_matches:
                row = Gtk.Label(label=artist.name)
                row.set_halign(Gtk.Align.START)
                row.add_css_class('search-result-row')
                gesture = Gtk.GestureClick()
                gesture.connect('pressed', lambda g, n, x, y, a=artist: self._on_search_artist(a))
                row.add_controller(gesture)
                content.append(row)

        # Replace content
        while child := self._search_results_box.get_first_child():
            self._search_results_box.remove(child)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_min_content_height(300)
        scrolled.set_max_content_height(400)
        scrolled.set_can_focus(False)
        scrolled.set_child(content)
        self._search_results_box.append(scrolled)

        if any_results:
            self._search_revealer.set_reveal_child(True)
        else:
            self._hide_search_results()

    def _on_search_song(self, song):
        self._hide_search_results()
        self._search_entry.set_text('')
        self._queue_manager.clear()
        self._queue_manager.add(song)
        self._play_song(song)

    def _on_search_album(self, album):
        self._hide_search_results()
        self._search_entry.set_text('')
        self._stack.set_visible_child_name('Albums')
        self._on_album_activated(album)

    def _on_search_artist(self, artist):
        self._hide_search_results()
        self._search_entry.set_text('')
        songs = database.get_songs_by_artist(artist.name)
        if not songs:
            return
        self._stack.set_visible_child_name('Artists')
        self._on_artist_activated(artist)

    def _refresh_queue(self):
        songs = self._queue_manager.get_all()
        self._queue_list.set_songs(songs)
        dur = self._queue_manager.total_duration()
        minutes = int(dur // 60)
        seconds = int(dur % 60)
        self._queue_info_label.set_label(
            f'{len(songs)} Tracks \u2014 {minutes}:{seconds:02d}'
        )

    def _start_cover_loading(self):
        cards = [c for c in self._album_cards if c._cover_path]
        self._pending_covers = cards
        self._covers_total = len(cards)
        self._covers_loaded = 0
        if not cards:
            self._covers_ready = True
            self._loading_overlay.set_visible(False)
            return
        GLib.idle_add(self._process_cover_batch)

    def _process_cover_batch(self) -> bool:
        batch_size = 10
        count = 0
        while self._pending_covers and count < batch_size:
            card = self._pending_covers.pop(0)
            card.load_cover()
            self._covers_loaded += 1
            count += 1

        if self._covers_loaded < self._covers_total:
            self._loading_overlay.set_progress(self._covers_loaded, self._covers_total)
        else:
            self._loading_overlay.set_complete_text()

        if not self._pending_covers:
            self._covers_ready = True
            self._loading_overlay.set_visible(False)
            return GLib.SOURCE_REMOVE

        return GLib.SOURCE_CONTINUE

    def _wire_footer(self):
        player = self._audio_player
        footer = self._footer

        footer.on_play(lambda: self._on_play_pause())
        footer.on_next(self._on_next)
        footer.on_prev(self._on_prev)
        footer.on_seek(lambda frac: self._on_seek(frac))
        footer.on_volume_changed(lambda v: player.set_volume(v))

        player.on_position_updated(footer.update_position)
        player.on_song_finished(self._on_song_finished)

    def _setup_shortcuts(self):
        ctrl = Gtk.EventControllerKey()
        ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        ctrl.connect('key-pressed', self._on_key_pressed)
        self.add_controller(ctrl)

    def _on_key_pressed(self, controller, keyval, keycode, state):
        focused = self.get_focus()
        editing = isinstance(focused, Gtk.Editable) if focused else False
        mod = state & Gdk.ModifierType.CONTROL_MASK

        if keyval == Gdk.KEY_q and mod:
            self.get_application().quit()
            return True

        if keyval == Gdk.KEY_f and mod:
            self._search_entry.grab_focus()
            return True

        if keyval == Gdk.KEY_Escape:
            self._hide_search_results()
            self._search_entry.set_text('')
            self.set_focus(None)
            return True

        if editing:
            return False

        if keyval == Gdk.KEY_space:
            self._on_play_pause()
            return True
        if keyval == Gdk.KEY_Left:
            self._on_prev()
            return True
        if keyval == Gdk.KEY_Right:
            self._on_next()
            return True

        return False

    def _on_play_pause(self):
        player = self._audio_player
        if not player.current_song():
            songs = self._queue_manager.get_all()
            if not songs:
                return
            player.load(songs[0])
        player.toggle()
        self._footer.set_playing(player.is_playing())

    def _on_next(self):
        songs = self._queue_manager.get_all()
        if not songs:
            return
        cur = self._audio_player.current_song()
        if cur and cur in songs:
            idx = songs.index(cur) + 1
            if idx < len(songs):
                self._play_song(songs[idx])

    def _on_prev(self):
        songs = self._queue_manager.get_all()
        if not songs:
            return
        cur = self._audio_player.current_song()
        if cur and cur in songs:
            idx = songs.index(cur) - 1
            if idx >= 0:
                self._play_song(songs[idx])

    def _on_seek(self, fraction: float):
        dur = self._audio_player.get_duration()
        self._audio_player.seek(fraction * dur)

    def _on_song_finished(self):
        self._footer.set_playing(False)
        self._on_next()

    def _play_song(self, song):
        self._audio_player.load(song)
        self._audio_player.play()
        self._footer.set_song(song)
        self._footer.set_playing(True)
        if song.id is not None:
            database.record_play(song.id)

    def _on_song_clicked(self, song):
        self._queue_manager.clear()
        self._queue_manager.add(song)
        self._play_song(song)

    def _on_song_context_menu(self, button, song):
        liked = database.is_liked('song', str(song.id)) if song.id is not None else False
        items = [
            ('Play', lambda: self._on_song_clicked(song)),
            ('Add to Queue', lambda: self._queue_manager.add(song)),
            ('Add to Playlist', lambda: self._on_add_song_to_playlist(song)),
            ('Unlike' if liked else 'Like', lambda: database.toggle_like('song', str(song.id))),
            ('Info', lambda: self._show_song_info(song)),
        ]
        if self._current_playlist_id is not None and song.id is not None:
            def do_remove():
                database.remove_song_from_playlist(self._current_playlist_id, song.id)
                if hasattr(self, '_playlist_detail') and self._playlist_detail:
                    self._playlist_detail.refresh()
            items.insert(0, ('Remove from Playlist', do_remove))
        menu = ContextMenu(items)
        menu.set_parent(button)
        menu.popup()

    def _on_play_album(self, album):
        songs = database.get_songs_by_album(album.title, album.artist)
        if not songs:
            return
        self._queue_manager.clear()
        self._queue_manager.add_multiple(songs)
        self._play_song(songs[0])

    def _on_add_to_queue_album(self, album):
        songs = database.get_songs_by_album(album.title, album.artist)
        if songs:
            self._queue_manager.add_multiple(songs)

    def _on_shuffle_album(self, album):
        songs = database.get_songs_by_album(album.title, album.artist)
        if not songs:
            return
        random.shuffle(songs)
        self._queue_manager.clear()
        self._queue_manager.add_multiple(songs)
        self._play_song(songs[0])

    def _on_home_album_activated(self, album):
        self._stack.set_visible_child_name('Albums')
        self._on_album_activated(album)

    def _on_album_activated(self, album):
        if hasattr(self, '_album_detail') and self._album_detail.get_parent() == self._album_stack:
            self._album_stack.remove(self._album_detail)
        self._album_detail = AlbumDetail(album)
        self._album_detail.on_back(self._on_back_to_grid)
        self._album_detail.on_play(self._on_play_album)
        self._album_detail.on_shuffle(self._on_shuffle_album)
        self._album_detail.on_song_activated(self._on_song_clicked)
        self._album_detail.on_song_menu(self._on_song_context_menu)
        self._album_detail.on_add_to_queue(self._on_add_to_queue_album)
        self._album_detail.on_add_to_playlist(self._on_add_album_to_playlist)
        self._album_detail.on_info(self._show_album_info)
        self._album_stack.add_named(self._album_detail, 'detail')
        self._album_stack.set_visible_child_name('detail')

    def _show_song_info(self, song):
        dialog = InfoDialog(self)
        dialog.show_song(song)
        dialog.present()

    def _show_album_info(self, album):
        dialog = InfoDialog(self)
        dialog.show_album(album)
        dialog.present()

    def _on_add_song_to_playlist(self, song):
        song_ids = [s.id for s in [song] if s.id is not None]
        if song_ids:
            picker = PlaylistPicker(self, song_ids)
            picker.connect('response', lambda d, r: self._refresh_playlists())
            picker.present()

    def _on_add_album_to_playlist(self, album):
        songs = database.get_songs_by_album(album.title, album.artist)
        song_ids = [s.id for s in songs if s.id is not None]
        if song_ids:
            picker = PlaylistPicker(self, song_ids)
            picker.connect('response', lambda d, r: self._refresh_playlists())
            picker.present()

    def _on_back_to_grid(self):
        if hasattr(self, '_album_detail') and self._album_detail.get_parent() == self._album_stack:
            self._album_stack.remove(self._album_detail)
        self._album_stack.set_visible_child_name('grid')

    def _on_clear_queue(self):
        self._queue_manager.clear()

    def _on_queue_reorder(self, from_idx, to_idx):
        self._queue_manager.move(from_idx, to_idx)

    def _on_queue_song_clicked(self, song):
        self._play_song(song)

    def _on_queue_song_menu(self, button, song):
        items = [('Remove from Queue', lambda: self._on_remove_from_queue(song))]
        menu = ContextMenu(items)
        menu.set_parent(button)
        menu.popup()

    def _on_remove_from_queue(self, song):
        songs = self._queue_manager.get_all()
        idx = next((i for i, s in enumerate(songs) if s.path == song.path), None)
        if idx is not None:
            self._queue_manager.remove(idx)

    def _on_add_queue_to_playlist(self):
        songs = self._queue_manager.get_all()
        if not songs:
            dialog = Gtk.AlertDialog(
                message='Queue is empty',
                detail='Add some songs to the queue first.'
            )
            dialog.show(self)
            return
        song_ids = [s.id for s in songs if s.id is not None]
        if song_ids:
            picker = PlaylistPicker(self, song_ids)
            picker.connect('response', lambda d, r: self._refresh_playlists())
            picker.present()

    def _on_queue_menu(self, button):
        items = [
            ('Save as Playlist', lambda: self._on_save_queue()),
            ('Clear Queue', lambda: self._on_clear_queue()),
        ]
        menu = ContextMenu(items)
        menu.set_parent(button)
        menu.popup()

    def _on_save_queue(self):
        songs = self._queue_manager.get_all()
        if not songs:
            dialog = Gtk.AlertDialog(
                message='Queue is empty',
                detail='Add some songs to the queue first.'
            )
            dialog.show(self)
            return

        dialog = Gtk.Dialog(title='Save Playlist', transient_for=self, modal=True)
        dialog.add_button('Cancel', Gtk.ResponseType.CANCEL)
        dialog.add_button('Save', Gtk.ResponseType.OK)
        dialog.set_default_size(350, -1)

        content = dialog.get_content_area()
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_spacing(8)

        label = Gtk.Label(label='Playlist name:')
        label.set_xalign(0)
        content.append(label)

        entry = Gtk.Entry()
        entry.set_placeholder_text('My Playlist')
        entry.set_max_length(20)
        content.append(entry)

        dialog.connect('response', lambda d, r: self._on_save_queue_response(d, r, entry))
        dialog.present()

    def _on_save_queue_response(self, dialog, response, entry):
        if response == Gtk.ResponseType.OK:
            name = entry.get_text().strip()
            if name:
                songs = self._queue_manager.get_all()
                song_ids = [s.id for s in songs if s.id is not None]
                if song_ids:
                    database.create_playlist(name, song_ids)
                    self._refresh_playlists()
        dialog.close()

    def _on_new_playlist(self):
        dialog = Gtk.Dialog(title='New Playlist', transient_for=self, modal=True)
        dialog.add_button('Cancel', Gtk.ResponseType.CANCEL)
        dialog.add_button('Create', Gtk.ResponseType.OK)
        dialog.set_default_size(350, -1)

        content = dialog.get_content_area()
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_spacing(8)

        label = Gtk.Label(label='Playlist name:')
        label.set_xalign(0)
        content.append(label)

        entry = Gtk.Entry()
        entry.set_placeholder_text('My Playlist')
        entry.set_max_length(20)
        content.append(entry)

        def on_response(d, r):
            if r == Gtk.ResponseType.OK:
                name = entry.get_text().strip()
                if name:
                    database.create_playlist(name, [])
                    self._refresh_playlists()
            d.close()

        dialog.connect('response', on_response)
        dialog.present()

    def _on_play_playlist(self, playlist):
        songs = database.get_playlist_songs(playlist.id)
        if not songs:
            return
        self._queue_manager.clear()
        self._queue_manager.add_multiple(songs)
        self._play_song(songs[0])

    def _on_add_to_queue_playlist(self, playlist):
        songs = database.get_playlist_songs(playlist.id)
        if songs:
            self._queue_manager.add_multiple(songs)

    def _on_rename_playlist(self, playlist):
        dialog = Gtk.Dialog(title='Rename Playlist', transient_for=self, modal=True)
        dialog.add_button('Cancel', Gtk.ResponseType.CANCEL)
        dialog.add_button('Rename', Gtk.ResponseType.OK)
        dialog.set_default_size(350, -1)

        content = dialog.get_content_area()
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_spacing(8)

        label = Gtk.Label(label='New name:')
        label.set_xalign(0)
        content.append(label)

        entry = Gtk.Entry()
        entry.set_text(playlist.name)
        entry.set_placeholder_text('My Playlist')
        entry.set_max_length(20)
        content.append(entry)

        def on_response(d, r):
            if r == Gtk.ResponseType.OK:
                name = entry.get_text().strip()
                if name:
                    database.rename_playlist(playlist.id, name)
                    self._refresh_playlists()
            d.close()

        dialog.connect('response', on_response)
        dialog.present()

    def _on_delete_playlist(self, playlist):
        confirm = Gtk.AlertDialog(
            message=f'Delete "{playlist.name}"?',
            detail='This cannot be undone.'
        )
        confirm.set_buttons(['Cancel', 'Delete'])
        confirm.set_cancel_button(0)
        confirm.set_default_button(1)

        def on_confirm(dialog, result):
            btn = dialog.choose_finish(result)
            if btn == 1:
                database.delete_playlist(playlist.id)
                self._refresh_playlists()

        confirm.choose(self, None, on_confirm)

    def _on_playlist_activated(self, playlist):
        self._current_playlist_id = playlist.id
        if hasattr(self, '_playlist_detail') and self._playlist_detail.get_parent() == self._playlist_stack:
            self._playlist_stack.remove(self._playlist_detail)
        self._playlist_detail = PlaylistDetail(playlist)
        self._playlist_detail.on_back(self._on_back_to_playlist_grid)
        self._playlist_detail.on_play(self._on_play_playlist)
        self._playlist_detail.on_song_activated(self._on_song_clicked)
        self._playlist_detail.on_song_menu(self._on_song_context_menu)
        self._playlist_detail.on_delete(self._on_delete_playlist_and_back)
        self._playlist_stack.add_named(self._playlist_detail, 'detail')
        self._playlist_stack.set_visible_child_name('detail')

    def _on_delete_playlist_and_back(self):
        self._on_back_to_playlist_grid()
        self._refresh_playlists()

    def _on_back_to_playlist_grid(self):
        self._current_playlist_id = None
        if hasattr(self, '_playlist_detail') and self._playlist_detail.get_parent() == self._playlist_stack:
            self._playlist_stack.remove(self._playlist_detail)
        self._playlist_stack.set_visible_child_name('grid')

    def _on_fav_artist_clicked(self, name):
        from src.library.models import Artist
        artist = Artist(name=name)
        self._stack.set_visible_child_name('Artists')
        self._on_artist_activated(artist)

    def _on_artist_activated(self, artist):
        songs = database.get_songs_by_artist(artist.name)
        if not songs:
            return
        if hasattr(self, '_artist_detail') and self._artist_detail.get_parent() == self._artist_stack:
            self._artist_stack.remove(self._artist_detail)
        self._artist_detail = ArtistDetail(artist)
        self._artist_detail.on_back(self._on_back_to_artist_grid)
        self._artist_detail.on_play(self._on_play_artist)
        self._artist_detail.on_shuffle(self._on_shuffle_artist)
        self._artist_detail.on_song_activated(self._on_song_clicked)
        self._artist_detail.on_song_menu(self._on_song_context_menu)
        self._artist_stack.add_named(self._artist_detail, 'detail')
        self._artist_stack.set_visible_child_name('detail')

    def _on_back_to_artist_grid(self):
        if hasattr(self, '_artist_detail') and self._artist_detail.get_parent() == self._artist_stack:
            self._artist_stack.remove(self._artist_detail)
        self._artist_stack.set_visible_child_name('list')

    def _on_play_artist(self, artist):
        songs = database.get_songs_by_artist(artist.name)
        if not songs:
            return
        self._queue_manager.clear()
        self._queue_manager.add_multiple(songs)
        self._play_song(songs[0])

    def _on_shuffle_artist(self, artist):
        songs = database.get_songs_by_artist(artist.name)
        if not songs:
            return
        random.shuffle(songs)
        self._queue_manager.clear()
        self._queue_manager.add_multiple(songs)
        self._play_song(songs[0])

    def _on_genre_activated(self, genre):
        if hasattr(self, '_genre_detail') and self._genre_detail.get_parent() == self._genre_stack:
            self._genre_stack.remove(self._genre_detail)
        self._genre_detail = GenreDetail(genre)
        self._genre_detail.on_back(self._on_back_to_genre_grid)
        self._genre_detail.on_play(self._on_play_genre)
        self._genre_detail.on_shuffle(self._on_shuffle_genre)
        self._genre_detail.on_song_activated(self._on_song_clicked)
        self._genre_detail.on_song_menu(self._on_song_context_menu)
        self._genre_stack.add_named(self._genre_detail, 'detail')
        self._genre_stack.set_visible_child_name('detail')

    def _on_back_to_genre_grid(self):
        if hasattr(self, '_genre_detail') and self._genre_detail.get_parent() == self._genre_stack:
            self._genre_stack.remove(self._genre_detail)
        self._genre_stack.set_visible_child_name('grid')

    def _on_play_genre(self, genre):
        songs = database.get_songs_by_genre(genre.name)
        if not songs:
            return
        self._queue_manager.clear()
        self._queue_manager.add_multiple(songs)
        self._play_song(songs[0])

    def _on_shuffle_genre(self, genre):
        songs = database.get_songs_by_genre(genre.name)
        if not songs:
            return
        random.shuffle(songs)
        self._queue_manager.clear()
        self._queue_manager.add_multiple(songs)
        self._play_song(songs[0])

    def _refresh_artists(self):
        self._all_artists = database.get_artists()
        self._artist_list.set_artists(self._all_artists)

    def _open_settings(self):
        dialog = SettingsDialog(self)

        def on_response(d, r):
            self._refresh_artists()
            if d._scan_was_run:
                self._all_songs = database.get_all_songs()
                self._refresh_albums()
                self._refresh_genres()
                self._start_cover_loading()
                self._refresh_playlists()
                self._refresh_queue()
                self._refresh_home()
            elif d._usage_cleared:
                self._refresh_home()

        dialog.connect('response', on_response)
        dialog.present()

    def _apply_styles(self):
        provider = Gtk.CssProvider()
        provider.load_from_string(
            '.track-number {\n'
            '  min-width: 36px;\n'
            '}\n'
        '.cover-placeholder {\n'
        '  min-width: 128px;\n'
        '  min-height: 128px;\n'
        '}\n'
            '.menu-btn {\n'
            '  min-width: 28px;\n'
            '  min-height: 28px;\n'
            '}\n'
            '.footer-btn {\n'
            '  min-width: 36px;\n'
            '  min-height: 36px;\n'
            '  font-size: 1.7em;\n'
            '}\n'
            '.play-btn {\n'
            '  min-width: 44px;\n'
            '  min-height: 44px;\n'
            '  font-size: 2.0em;\n'
            '}\n'
            '.time-label {\n'
            '  min-width: 36px;\n'
            '}\n'
            '.progress-slider {\n'
            '  min-height: 6px;\n'
            '}\n'
            '.card-btn {\n'
            '  min-width: 32px;\n'
            '  min-height: 32px;\n'
            '}\n'
            '.album-action-btn {\n'
            '  min-width: 20px;\n'
            '  min-height: 20px;\n'
            '  padding: 2px 4px;\n'
            '}\n'
            '.album-cover {\n'
            '  border-radius: 6px;\n'
            '}\n'
            '.context-menu-item {\n'
            '  min-width: 180px;\n'
            '  padding: 6px 16px;\n'
            '}\n'
            '.context-menu-item:hover {\n'
            '  background-color: @accent_bg_color;\n'
            '  color: @accent_fg_color;\n'
            '}\n'
            '.search-result-row {\n'
            '  padding: 4px 8px;\n'
            '  border-radius: 4px;\n'
            '}\n'
            '.search-result-row:hover {\n'
            '  background-color: @accent_bg_color;\n'
            '  color: @accent_fg_color;\n'
            '}\n'
            '.search-results-panel {\n'
            '  background-color: @view_bg_color;\n'
            '  border-bottom: 1px solid @borders;\n'
            '}\n'
            '.song-row.drag-hover {\n'
            '  background-color: alpha(@accent_bg_color, 0.2);\n'
            '}\n'
            '.loading-overlay {\n'
            '  background-color: @window_bg_color;\n'
            '}\n'
            '.loading-box {\n'
            '  min-width: 400px;\n'
            '  padding: 40px;\n'
            '}\n'
            '.home-artist-row {\n'
            '  background: none;\n'
            '  border: none;\n'
            '  box-shadow: none;\n'
            '  padding: 4px 8px;\n'
            '  border-radius: 6px;\n'
            '}\n'
            '.home-artist-row:hover {\n'
            '  background-color: alpha(@accent_bg_color, 0.12);\n'
            '}\n'
        )
        Gtk.StyleContext.add_provider_for_display(
            Gtk.Widget.get_display(self),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
