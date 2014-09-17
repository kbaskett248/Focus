import os

import sublime
import sublime_plugin

from .src.Managers.RingFileManager import RingFileManager
from .src.FocusFile import FocusFile
from .src.XMLRingFile import XMLRingFile
from .src.tools import merge_paths


FILE_MANAGER = RingFileManager.getInstance()

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class RingFileCommand(sublime_plugin.TextCommand):
    """
    Parent class for TextCommands that rely on the file being a Ring File.

    """

    def __init__(self, view):
        super(RingFileCommand, self).__init__(view)
        self._ring_file = None
        self._initialized = False

    @property
    def ring_file(self):
        """Returns a reference to the command's ring file."""
        if (not self._initialized):
            self._ring_file = FILE_MANAGER.get_ring_file(self.view)
            self._initialized = True
        return self._ring_file

    @property
    def filename(self):
        """Returns the filename of the file associated with the command."""
        return self.ring_file.filename

    @property
    def ring_object(self):
        """Returns a reference to the ring file's ring object."""
        return self.ring_file.ring_object

    def run_ring_method(self, command):
        """Runs a method of the ring file's ring."""
        if ((self.ring_file is not None) and (self.ring_object is not None)):
            command(self.ring_object)

    def is_visible(self):
        return (self.ring_file is not None)

    def is_enabled(self):
        return self.is_visible()


class TranslateCommand(RingFileCommand):
    """Translate command for RingFiles.

    If the file can be translated, this will run the translate routine defined
    for that type of file.

    """
        
    def run(self, edit):
        """Calls the translate command for the selected file.

        Special handling is done for Focus include files. All open files are
        checked to see if they include the file. Any that do are also 
        translated.

        """
        if self.ring_file.is_translatable():
            if (isinstance(self.ring_file, FocusFile) and self.ring_file.is_includable()):
                logger.info('Instead of translating %s, translating all open files that include it', self.filename)
                for f in self.get_including_files(self.ring_file):
                    logger.debug('Translating %s', f.filename)
                    f.translate()
            else:
                if self.ring_file.translate():
                    sublime.status_message('Translating %s' % self.filename)

    def get_including_files(self, include_file):
        """Returns a list of all open files that include the given file."""
        files_to_translate = set()
        files_to_translate.add(include_file)
        logger.debug('Getting including files for %s', include_file.filename)
        if (include_file.ring_object is not None):
            for w in sublime.windows():
                for v in w.views():
                    f = FILE_MANAGER.get_ring_file(v)
                    if (f is not None) and isinstance(f, FocusFile):
                        if (f in files_to_translate):
                            continue
                        elif (f.ring_object is include_file.ring_object):
                            logger.debug('Current File: %s', f.filename)
                            for a in f.get_include_files(v):
                                if (include_file.filename.lower() == a.lower()):
                                    logger.debug('%s is included in %s', include_file.filename, f.filename)
                                    if f.is_includable():
                                        files_to_translate = files_to_translate.union(self.get_including_files(f))
                                    else:
                                        files_to_translate.add(f)
                                    break
        else:
            logger.debug('%s has no ring', include_file.filename)
        return files_to_translate

    def is_visible(self):
        return (super(TranslateCommand, self).is_visible() and 
                self.ring_file.is_translatable())

class BuildTranslateCommand(sublime_plugin.WindowCommand):
    """Build command to translate a RingFile."""

    def __init__(self, window):
        super(BuildTranslateCommand, self).__init__(window)
        self.view = self.window.active_view()
        self._ring_file = None
        self._initialized = False

    @property
    def ring_file(self):
        """Returns a reference to the command's ring file."""
        if (not self._initialized):
            self._ring_file = FILE_MANAGER.get_ring_file(self.view)
            self._initialized = True
        return self._ring_file

    def run(self):
        self.window.active_view().run_command('translate')

    def is_visible(self):
        return self.is_enabled()

    def is_enabled(self):
        return ((self.ring_file is not None) and self.ring_file.is_translatable())

class TranslateAllCommand(sublime_plugin.WindowCommand):
    """Command to translate all RingFiles open in the current window."""

    def run(self):
        """Translates all RingFiles open in the current window."""
        for v in self.window.views():
            f = FILE_MANAGER.get_ring_file(v)
            if (f is not None):
                v.run_command('translate')

    def is_enabled(self):
        """Returns True if there is at least one open file that is translatable."""
        enabled = False
        for v in self.window.views():
            f = FILE_MANAGER.get_ring_file(v)
            if ((f is not None) and (f.is_translatable())):
                enabled = True
                break
        return enabled

    def is_visible(self):
        return self.is_enabled()

class RunCommand(RingFileCommand):
    """Command to run a RingFile."""
    
    def run(self, edit):
        """Runs the RingFile if it is runnable."""
        if self.ring_file.is_runnable():
            if self.ring_file.run():
                sublime.status_message('Running %s' % self.filename)

    def is_enabled(self):
        result = False
        if (super(RingFileCommand, self).is_enabled() and self.ring_file.is_runnable()):
            result = True
        return result

class MatUpdateCurrentCommand(RingFileCommand):
    """Updates the ring for the current file"""

    def run(self, edit):
        """Runs the update command for the current RingFile's Ring."""
        if ((self.ring_file is not None) and (self.ring_object is not None) and 
            self.ring_object.local_ring):
            if self.ring_object.update():
                sublime.status_message('Launching Update for %s' % self.ring_object.name)

    def is_visible(self):
        """Returns True if the Ring is a local ring."""
        return (super(MatUpdateCurrentCommand, self).is_visible() and 
                (self.ring_object is not None) and self.ring_object.local_ring)

    def is_enabled(self):
        return self.is_visible()

class CopyFileToCacheCommand(RingFileCommand):
    """Command to copy a file from the ring server path to the local cache."""

    def run(self, edit, open_ = True):
        """Copies the RingFile to the local cache."""
        if self.is_enabled():
            ring_object = self.ring_object
            filename = self.filename
            partial_path = ring_object.partial_path(filename)
            dest = ring_object.copy_source_to_cache(filename, False)
            if (dest is None):
                overwrite_cache = sublime.ok_cancel_dialog('%s already exists in the cache.\nWould you like to overwrite it?' % partial_path)
                if overwrite_cache:
                    dest = ring_object.copy_source_to_cache(filename, True)
                else:
                    if (partial_path is not None):
                        dest = merge_paths(ring_object.cache_path, partial_path)

            if (open_ and (dest is not None) and os.path.isfile(dest)):
                self.view.window().open_file(dest)

    def is_visible(self):
        """Returns True if the Ring is not a local ring."""
        return ((self.ring_file is not None) and (self.ring_object is not None) and 
                (not self.ring_object.local_ring))

    def is_enabled(self):
        """Returns True if the file is on the server."""
        result = False
        if self.is_visible():
            ring_object = self.ring_object
            result = (ring_object.server_path in self.filename)
        return result

class DeleteFileFromCacheCommand(RingFileCommand):
    """Command to delete the file from the local cache."""

    def run(self, edit):
        """Deletes the cache copy of the file."""
        if self.is_enabled():
            ring_object = self.ring_object
            filename = self.filename
            partial_path = ring_object.partial_path(filename)
            if (partial_path is not None):
                cache_path = merge_paths(ring_object.cache_path, partial_path)
                are_you_sure = sublime.ok_cancel_dialog('Are you sure you want to delete %s from the cache?' % partial_path)
                if are_you_sure:
                    os.remove(cache_path)

    def is_visible(self):
        """Returns True if the Ring is not a local ring."""
        return ((self.ring_file is not None) and (self.ring_object is not None) and 
                (not self.ring_object.local_ring))

    def is_enabled(self):
        """Returns True if the file is in the cache."""
        result = False
        if self.is_visible():
            ring_object = self.ring_object
            result = ring_object.file_exists_in_cache(self.filename)
        return result

class OverrideReadOnlyCommand(RingFileCommand):
    """Command to override the read only attribute of a RingFile."""

    def run(self, edit):
        """Toggles the read only attribute of a RingFile."""
        if self.is_enabled():
            if (self.ring_file.override_read_only or self.check()):
                self.ring_file.override_read_only = not self.ring_file.override_read_only
                logger.debug('Override Read Only: %s', self.ring_file.override_read_only)
                if ((self.ring_file is not None) and self.ring_file.is_read_only()):
                    self.view.set_read_only(True)
                    self.view.set_status('focus_read_only', 'Read-only')
                    logger.info('Setting view for %s to read only', self.filename)
                    logger.debug('Read Only: %s' % self.view.is_read_only())
                else:
                    self.view.set_read_only(False)
                    self.view.erase_status('focus_read_only')

    def check(self):
        return sublime.ok_cancel_dialog('Are you sure you want to allow this server file to be edited?\n' + 
            'In general, files on the server should not be edited.')

    def description(self):
        desc = "Enable editing for this file"
        if ((self.ring_file is not None) and self.ring_file.override_read_only):
            desc = "Set file as read-only"
        return desc

    def is_visible(self):
        """Returns True if the file is on the server."""
        return ((self.ring_file is not None) and (self.ring_object is not None) and 
                (not self.ring_object.local_ring) and
                (self.ring_object.server_path in self.filename))

    def is_enabled(self):
        return self.is_visible()

class RingFileEventListener(sublime_plugin.EventListener):
    def on_activated(self, view):
        file = FILE_MANAGER.get_ring_file(view)
        if ((file is not None) and file.is_read_only()):
            view.set_read_only(True)
            view.set_status('focus_read_only', 'Read-only')
            logger.info('Setting view for %s to read only', file.filename)
            logger.debug('Read Only: %s' % view.is_read_only())
        else:
            view.set_read_only(False)
            view.erase_status('focus_read_only')

    def on_post_save_async(self, view):
        file = FILE_MANAGER.get_ring_file(view)
        if ((file is not None) and isinstance(file, XMLRingFile) and file.is_translatable()):
            view.run_command('translate')
