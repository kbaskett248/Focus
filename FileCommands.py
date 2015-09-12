import functools
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel('INFO')

import sublime
import sublime_plugin

from .classes.command_templates import RingFileCommand
from .tools.classes import get_ring_file, is_local_ring
from .tools.general import merge_paths
from .tools.settings import get_translate_on_save


class MTRingFileEventListener(sublime_plugin.EventListener):

    def get_file_for_view(self, view):
        return get_ring_file(view.file_name())

    def on_activated(self, view):
        logger.debug("Checking for read only", )
        ring_file = get_ring_file(view.file_name())
        logger.debug("ring_file=%s", ring_file)
        if ((ring_file is not None) and ring_file.is_read_only()):
            view.set_read_only(True)
            view.set_status('focus_read_only', 'Read-only')
            logger.info('Setting view for %s to read only',
                        ring_file.file_name)
            logger.debug('Read Only: %s' % view.is_read_only())
        else:
            view.set_read_only(False)
            view.erase_status('focus_read_only')

    def on_post_save_async(self, view):
        s = get_translate_on_save()

        if isinstance(s, dict):
            ext = os.path.splitext(view.file_name())[1][1:]
            try:
                s = s[ext]
            except KeyError:
                s = False

        if s:
            ring_file = self.get_file_for_view(view)
            if ((ring_file is not None) and
                    ring_file.is_translatable()):
                view.run_command('translate_ring_file',
                                 {"encoding": "ascii",
                                  "exec_cmd": "enhanced_exec",
                                  "startup_info": False})


class CopyFileToCacheCommand(RingFileCommand):
    """Command to copy a file from the ring server path to the local cache."""

    def run(self, edit, open_file=True):
        """Copies the RingFile to the local cache."""
        if not self.is_enabled():
            return

        dest = None
        ring = self.ring_file.ring
        partial_path = ring.partial_path(self.file_name)

        if (ring.pgm_cache_path in self.file_name):
            # "Replace Cached File"
            if self.check_overwrite():
                dest = ring.copy_source_to_cache(self.file_name, True)

        elif open_file and ring.file_exists_in_cache(self.file_name):
            # "Open Cached File"
            dest = merge_paths(ring.pgm_cache_path, partial_path)

        else:
            # "Copy File to Cache and Open"
            dest = ring.copy_source_to_cache(self.file_name, False)
            if (dest is None):
                if self.check_overwrite():
                    dest = ring.copy_source_to_cache(self.file_name, True)

        if (open_file and (dest is not None) and os.path.isfile(dest)):
            self.view.window().open_file(dest)

    def check_overwrite(self):
        return sublime.ok_cancel_dialog(
            ('%s already exists in the cache for %s. '
             'Would you like to overwrite it?') %
            (os.path.basename(self.file_name), self.ring_file.ring))

    def is_visible(self, open_file=True):
        """Returns True if the Ring is not a local ring."""
        return ((self.ring_file is not None) and
                (self.ring_file.ring is not None) and
                (not is_local_ring(self.ring_file.ring)))

    def is_enabled(self, open_file=True):
        """Returns True if the file is on the server."""
        if self.is_visible():
            ring_object = self.ring_file.ring
            return ((ring_object.server_path in self.file_name) or
                    (ring_object.pgm_cache_path in self.file_name))
        return False

    def description(self, open_file=True):
        """Returns the description for the DocFinder assigned to the view."""
        if open_file:
            ring = self.ring_file.ring
            if (ring.pgm_cache_path in self.file_name):
                return "Replace Cached File"
            elif ring.file_exists_in_cache(self.file_name):
                return "Open Cached File"
            else:
                return "Copy File to Cache and Open"
        else:
            return "Copy File to Cache"


class DeleteFileFromCacheCommand(RingFileCommand):
    """Command to delete the file from the local cache."""

    def run(self, edit):
        """Deletes the cache copy of the file."""
        if self.is_enabled():
            ring = self.ring_file.ring
            filename = self.file_name
            partial_path = ring.partial_path(filename)
            if (partial_path is not None):
                self.cache_path = merge_paths(
                    ring.pgm_cache_path, partial_path)
                logger.debug('cache_path = %s', self.cache_path)
                if self.check_delete():
                    self.close_file_instances(self.cache_path)
                    os.remove(self.cache_path)

    def check_delete(self):
        return sublime.ok_cancel_dialog(
            ('Are you sure you want to close all instances of %s\\\n%s and '
             'delete it from the cache?') %
            os.path.split(self.cache_path))

    def close_file_instances(self, file_path):
        """Closes all instances of the given file."""
        file_path = file_path.lower()
        for win in sublime.windows():
            for v in win.views():
                if (v.file_name() and
                        (v.file_name().lower() == file_path)):
                    active_view = win.active_view()
                    reset_view = active_view.id() != v.id()
                    win.focus_view(v)
                    win.run_command('close')
                    if reset_view:
                        win.focus_view(active_view)

    def is_visible(self):
        """Returns True if the Ring is not a local ring."""
        return ((self.ring_file is not None) and
                (self.ring_file.ring is not None) and
                (not is_local_ring(self.ring_file.ring)))

    def is_enabled(self):
        """Returns True if the file is in the cache."""
        result = False
        if self.is_visible():
            ring = self.ring_file.ring
            result = ring.file_exists_in_cache(self.file_name)
        return result


class OverrideReadOnlyCommand(RingFileCommand):
    """Command to override the read only attribute of a RingFile."""

    def run(self, edit):
        """Toggles the read only attribute of a RingFile."""
        if not self.is_enabled():
            return

        if (self.ring_file.override_read_only or self.check()):
            self.ring_file.override_read_only = (
                not self.ring_file.override_read_only)

            logger.debug('Override Read Only: %s',
                         self.ring_file.override_read_only)

            if ((self.ring_file is not None) and
                    self.ring_file.is_read_only()):
                if self.view.is_dirty():
                    logger.info("Reverting changes to file")
                    sublime.set_timeout(
                        functools.partial(self.view.run_command, 'revert'), 0)

                self.view.set_read_only(True)
                self.view.set_status('focus_read_only', 'Read-only')
                logger.info('Setting view for %s to read only',
                            self.file_name)
                logger.debug('Read Only: %s' % self.view.is_read_only())

            else:
                self.view.set_read_only(False)
                self.view.erase_status('focus_read_only')

    def check(self):
        return sublime.ok_cancel_dialog(
            'Are you sure you want to allow this server file to be edited?\n' +
            'In general, files on the server should not be edited.')

    def description(self):
        desc = "Enable editing for this file"
        if ((self.ring_file is not None) and
                self.ring_file.override_read_only):
            desc = "Set file as read-only"
        return desc

    def is_visible(self):
        """Returns True if the file is on the server."""
        return ((self.ring_file is not None) and
                (self.ring_file.ring is not None) and
                (not is_local_ring(self.ring_file.ring)) and
                (self.ring_file.ring.server_path in self.file_name))

    def is_enabled(self):
        return self.is_visible()
