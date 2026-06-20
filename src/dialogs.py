import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstPbutils', '1.0')
gi.require_version('Gtk', '4.0')
from gi.repository import Gst, GstPbutils, Gtk, GLib, Pango

from .library import database
from .library.models import Song


class ScanProgressDialog(Gtk.Dialog):
    def __init__(self, parent, files, quick):
        super().__init__(title='Scanning\u2026', transient_for=parent, modal=True)
        self.set_default_size(450, 130)

        box = self.get_content_area()
        box.set_margin_start(20)
        box.set_margin_end(20)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_spacing(8)

        self._progress_bar = Gtk.ProgressBar()
        box.append(self._progress_bar)

        self._count_label = Gtk.Label(label='')
        box.append(self._count_label)

        self._file_label = Gtk.Label(label='')
        self._file_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        box.append(self._file_label)

        self._files = files
        self._total = len(files)
        self._index = 0
        self._quick = quick
        self._stats = {'added': 0, 'skipped': 0, 'errors': 0}

        self._update_ui()

    def _update_ui(self):
        if self._total > 0:
            self._progress_bar.set_fraction(self._index / self._total)
        self._count_label.set_label(f'{self._index} / {self._total} files')

    def step(self) -> bool:
        if self._index >= self._total:
            return False

        filepath = self._files[self._index]
        self._index += 1
        self._update_ui()
        self._file_label.set_label(os.path.basename(filepath))

        self._stats[ingest_file(filepath, self._quick)] += 1
        return True

    def get_stats(self):
        return self._stats


class SettingsDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title='Settings', transient_for=parent, modal=True)
        self.set_default_size(500, 400)
        self._scan_was_run = False
        self._usage_cleared = False

        self._build_ui()

    def _build_ui(self):
        box = self.get_content_area()
        box.set_spacing(10)
        box.set_margin_start(20)
        box.set_margin_end(20)
        box.set_margin_top(20)
        box.set_margin_bottom(20)

        # Library Management section
        label = Gtk.Label(label='Library Management')
        label.add_css_class('heading')
        box.append(label)

        # Folder list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_min_content_height(150)
        self._folder_list = Gtk.ListBox()
        self._folder_list.add_css_class('card')
        scrolled.set_child(self._folder_list)
        box.append(scrolled)

        # Folder buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        add_btn = Gtk.Button(label='Add Folder')
        add_btn.connect('clicked', self._on_add_folder)
        remove_btn = Gtk.Button(label='Remove Folder')
        remove_btn.connect('clicked', self._on_remove_folder)
        btn_box.append(add_btn)
        btn_box.append(remove_btn)
        box.append(btn_box)

        # Scan buttons
        scan_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        quick_btn = Gtk.Button(label='Quick Scan')
        quick_btn.connect('clicked', self._on_quick_scan)
        full_btn = Gtk.Button(label='Full Scan')
        full_btn.connect('clicked', self._on_full_scan)
        scan_box.append(quick_btn)
        scan_box.append(full_btn)
        box.append(scan_box)

        # Artist separator
        sep_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sep_box.set_margin_top(8)
        sep_box.set_margin_bottom(8)

        sep_label = Gtk.Label(label='Artist separator:')
        sep_box.append(sep_label)

        self._sep_entry = Gtk.Entry()
        self._sep_entry.set_hexpand(True)
        self._sep_entry.set_max_length(5)
        self._sep_entry.set_width_chars(5)
        self._sep_entry.set_text(database.get_setting('artist_separator', ''))
        self._sep_entry.connect('changed', self._on_sep_changed)
        sep_box.append(self._sep_entry)

        sep_desc = Gtk.Label(label='Separates multiple artists in a single field')
        sep_desc.add_css_class('dim-label')
        sep_desc.set_wrap(True)

        box.append(sep_box)
        box.append(sep_desc)

        # Usage Data
        usage_sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.append(usage_sep)

        usage_label = Gtk.Label(label='Usage Data')
        usage_label.add_css_class('heading')
        box.append(usage_label)

        clear_btn = Gtk.Button(label='Clear Usage Data')
        clear_btn.connect('clicked', self._on_clear_usage)
        box.append(clear_btn)

        # Status label
        self._status_label = Gtk.Label(label='')
        box.append(self._status_label)

        # About section
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        box.append(sep)

        about_label = Gtk.Label(label='Seesow Music v1.0')
        about_label.add_css_class('dim-label')
        box.append(about_label)

        github_btn = Gtk.Button(label='GitHub')
        github_btn.connect('clicked', lambda b: Gtk.show_uri(self, 'https://github.com/banicans/SeesowMusic', 0))
        box.append(github_btn)

        shortcuts_btn = Gtk.Button(label='Keyboard Shortcuts')
        shortcuts_btn.connect('clicked', self._on_shortcuts_clicked)
        box.append(shortcuts_btn)

        close_btn = Gtk.Button(label='Close')
        close_btn.connect('clicked', lambda b: self.close())
        box.append(close_btn)

        self._refresh_folder_list()

    def _on_shortcuts_clicked(self, button):
        dialog = Gtk.Dialog(title='Keyboard Shortcuts', transient_for=self, modal=True)
        dialog.set_default_size(350, 250)

        box = dialog.get_content_area()
        box.set_margin_start(20)
        box.set_margin_end(20)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_spacing(8)

        shortcuts = [
            ('Space', 'Play / Pause'),
            ('\u2190', 'Previous track'),
            ('\u2192', 'Next track'),
            ('Ctrl+F', 'Search'),
            ('Escape', 'Close search'),
            ('Ctrl+Q', 'Quit'),
        ]

        for key, action in shortcuts:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
            key_label = Gtk.Label(label=key)
            key_label.add_css_class('heading')
            key_label.set_xalign(0)
            key_label.set_size_request(80, -1)
            action_label = Gtk.Label(label=action)
            action_label.set_halign(Gtk.Align.START)
            action_label.set_xalign(0)
            row.append(key_label)
            row.append(action_label)
            box.append(row)

        close_btn = Gtk.Button(label='Close')
        close_btn.connect('clicked', lambda b: dialog.close())
        box.append(close_btn)

        dialog.present()

    def _refresh_folder_list(self):
        while child := self._folder_list.get_first_child():
            self._folder_list.remove(child)

        for folder in database.get_folders():
            row = Gtk.ListBoxRow()
            row.set_child(Gtk.Label(label=folder, xalign=0))
            self._folder_list.append(row)

        if not database.get_folders():
            row = Gtk.ListBoxRow()
            row.set_child(Gtk.Label(label='No folders added yet', xalign=0))
            row.set_sensitive(False)
            self._folder_list.append(row)

    def _on_add_folder(self, button):
        dialog = Gtk.FileDialog.new()
        dialog.set_title('Select Music Folder')
        dialog.select_folder(parent=self, cancellable=None, callback=self._on_folder_selected)

    def _on_folder_selected(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                path = folder.get_path()
                database.add_folder(path)
                self._refresh_folder_list()
        except GLib.Error:
            pass

    def _on_remove_folder(self, button):
        selected = self._folder_list.get_selected_row()
        if selected:
            label = selected.get_child()
            database.remove_folder(label.get_text())
            self._refresh_folder_list()

    def _on_quick_scan(self, button):
        self._run_scan(quick=True)

    def _on_full_scan(self, button):
        self._run_scan(quick=False)

    def _on_sep_changed(self, entry):
        database.set_setting('artist_separator', entry.get_text())

    def _on_clear_usage(self, button):
        dialog = Gtk.AlertDialog(
            message='Clear all usage data?',
            detail='This will delete all play history and recently played data. Library, playlists and favourites are not affected.'
        )
        dialog.set_buttons(['Cancel', 'Clear'])
        dialog.set_cancel_button(0)
        dialog.set_default_button(1)

        def on_response(dlg, result):
            idx = dlg.choose_finish(result)
            if idx == 1:
                database.clear_usage_data()
                self._usage_cleared = True
                self._status_label.set_text('Usage data cleared')

        dialog.choose(self, None, on_response)

    def _run_scan(self, quick=False):
        self._scan_was_run = True
        files = collect_audio_files()

        if not quick:
            self._all_scanned_paths = set(files)
        else:
            self._all_scanned_paths = None

        self._scan_dialog = ScanProgressDialog(self, files, quick)
        self._scan_dialog.present()
        GLib.idle_add(self._scan_step)

    def _scan_step(self):
        if self._scan_dialog.step():
            return GLib.SOURCE_CONTINUE

        stats = self._scan_dialog.get_stats()
        self._scan_dialog.close()
        self._scan_dialog = None

        if self._all_scanned_paths is not None:
            database.delete_songs_not_in_paths(self._all_scanned_paths)
            self._all_scanned_paths = None

        self._status_label.set_text(
            f'Scan complete: {stats["added"]} added, '
            f'{stats["skipped"]} skipped, {stats["errors"]} errors'
        )
        return GLib.SOURCE_REMOVE


# ── Scanner functions ──

AUDIO_EXTENSIONS = {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.wma', '.opus'}
COVER_CACHE_DIR = Path(os.getenv('XDG_CACHE_HOME', Path.home() / '.cache')) / 'seesow-music' / 'covers'

_initialized = False
_TAG_MAP = {}

logger = logging.getLogger(__name__)


def _ensure_gst():
    global _initialized
    if not _initialized:
        Gst.init(None)
        _build_tag_map()
        _initialized = True


def _build_tag_map():
    global _TAG_MAP
    _TAG_MAP = {
        Gst.TAG_TITLE: ('string', 'title'),
        Gst.TAG_ARTIST: ('string', 'artist'),
        Gst.TAG_ALBUM: ('string', 'album'),
        Gst.TAG_ALBUM_ARTIST: ('string', 'album_artist'),
        Gst.TAG_TRACK_NUMBER: ('uint', 'track_number'),
        Gst.TAG_DATE: ('date', 'year'),
        Gst.TAG_DATE_TIME: ('date_time', 'year'),
        Gst.TAG_GENRE: ('string', 'genre'),
    }


def is_audio_file(path: str) -> bool:
    return Path(path).suffix.lower() in AUDIO_EXTENSIONS


def _extract_cover(tags, artist: str, album: str) -> Optional[str]:
    COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = f'{artist}|{album}'
    filename = hashlib.sha256(key.encode()).hexdigest()[:16]

    for ext in ('.jpg', '.jpeg', '.png', '.webp'):
        cached = COVER_CACHE_DIR / f'{filename}{ext}'
        if cached.exists():
            return str(cached)

    for tag_name in (Gst.TAG_IMAGE, Gst.TAG_PREVIEW_IMAGE):
        ret, sample = tags.get_sample(tag_name)
        if ret and sample:
            buffer = sample.get_buffer()
            if buffer:
                size = buffer.get_size()
                data = buffer.extract_dup(0, size)
                if data:
                    if data[:4] == b'\x89PNG':
                        ext = '.png'
                    elif data[:2] == b'\xff\xd8':
                        ext = '.jpg'
                    elif data[:4] == b'RIFF':
                        ext = '.webp'
                    else:
                        ext = '.jpg'
                    dest = COVER_CACHE_DIR / f'{filename}{ext}'
                    try:
                        with open(dest, 'wb') as f:
                            f.write(data)
                        return str(dest)
                    except OSError:
                        pass
    return None


def scan_file(path: str) -> Optional[Song]:
    _ensure_gst()
    try:
        uri = Path(path).as_uri()
        discoverer = GstPbutils.Discoverer.new(5 * Gst.SECOND)
        info = discoverer.discover_uri(uri)

        if info.get_result() != GstPbutils.DiscovererResult.OK:
            logger.warning('Discoverer failed for %s: %s', path, info.get_result())
            return None

        tags = info.get_tags()
        if not tags:
            logger.warning('No tags found for %s', path)
            return None

        metadata = {'title': '', 'artist': '', 'album': '', 'album_artist': '',
                    'track_number': 0, 'year': 0, 'genre': ''}

        for tag_name, (tag_type, key) in _TAG_MAP.items():
            if tag_type == 'string':
                _, val = tags.get_string(tag_name)
                if val:
                    metadata[key] = val
            elif tag_type == 'uint':
                _, val = tags.get_uint(tag_name)
                if val:
                    metadata[key] = val
            elif tag_type == 'date':
                _, val = tags.get_date(tag_name)
                if val:
                    metadata['year'] = val.get_year()
            elif tag_type == 'date_time':
                _, val = tags.get_date_time(tag_name)
                if val:
                    metadata['year'] = val.get_year()

        duration_ns = info.get_duration()
        duration = duration_ns / Gst.SECOND if duration_ns != Gst.CLOCK_TIME_NONE else 0.0

        cover_artist = metadata['album_artist'] or metadata['artist'] or 'Unknown Artist'
        cover_path = _extract_cover(tags, cover_artist, metadata['album'] or 'Unknown Album')

        return Song(
            path=path,
            title=metadata['title'] or Path(path).stem,
            artist=metadata['artist'] or 'Unknown Artist',
            album=metadata['album'] or 'Unknown Album',
            track_number=metadata['track_number'],
            duration=duration,
            year=metadata['year'],
            genre=metadata['genre'],
            album_artist=metadata['album_artist'],
            cover_path=cover_path,
        )
    except Exception as e:
        logger.error('Error scanning %s: %s', path, e)
        return None


def collect_audio_files() -> list[str]:
    files = []
    for folder in database.get_folders():
        for root, dirs, fnames in os.walk(folder):
            dirs[:] = [d for d in dirs if '.Trash' not in d]
            for f in fnames:
                if is_audio_file(f):
                    files.append(os.path.join(root, f))
    return files


def ingest_file(filepath: str, quick: bool = False) -> str:
    if quick and database.song_exists(filepath):
        return 'skipped'

    song = scan_file(filepath)
    if song:
        database.add_song(song)
        return 'added'
    return 'errors'
