import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

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
        if self.is_enabled():
            ring = self.ring_file.ring
            filename = self.file_name
            partial_path = ring.partial_path(filename)
            dest = ring.copy_source_to_cache(filename, False)
            if (dest is None):
                overwrite_cache = sublime.ok_cancel_dialog(
                    ('%s already exists in the cache.\n'
                     'Would you like to overwrite it?') % partial_path)
                if overwrite_cache:
                    dest = ring.copy_source_to_cache(filename, True)
                else:
                    if partial_path is not None:
                        dest = merge_paths(ring.cache_path,
                                           partial_path)

            if (open_file and (dest is not None) and os.path.isfile(dest)):
                self.view.window().open_file(dest)

    def is_visible(self):
        """Returns True if the Ring is not a local ring."""
        return ((self.ring_file is not None) and
                (self.ring_file.ring is not None) and
                (not is_local_ring(self.ring_file.ring)))

    def is_enabled(self):
        """Returns True if the file is on the server."""
        result = False
        if self.is_visible():
            ring_object = self.ring_file.ring
            result = (ring_object.server_path in self.file_name)
        return result


class DeleteFileFromCacheCommand(RingFileCommand):
    """Command to delete the file from the local cache."""

    def run(self, edit):
        """Deletes the cache copy of the file."""
        if self.is_enabled():
            ring = self.ring_file.ring
            filename = self.file_name
            partial_path = ring.partial_path(filename)
            if (partial_path is not None):
                cache_path = merge_paths(ring.cache_path, partial_path)
                are_you_sure = sublime.ok_cancel_dialog(
                    'Are you sure you want to delete %s from the cache?' %
                    partial_path)
                if are_you_sure:
                    os.remove(cache_path)

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
        if self.is_enabled():
            if (self.ring_file.override_read_only or self.check()):
                self.ring_file.override_read_only = (
                    not self.ring_file.override_read_only)
                logger.debug('Override Read Only: %s',
                             self.ring_file.override_read_only)
                if ((self.ring_file is not None) and
                        self.ring_file.is_read_only()):
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
