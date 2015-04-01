from abc import ABCMeta
import logging
import re
import sys

import sublime
import sublime_plugin

from .ring_files import (
    FocusFile,
    InvalidFileFormat,
    get_ring_file
)
from .views import (
    FocusView,
    ViewTypeException,
    get_view
)
from .rings import Ring, is_local_ring
from ..tools.settings import get_sort_local_rings

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')


class WindowTextCommandMeta(ABCMeta):
    """
    A TextCommand can use this as its metaclass to automatically create a
    window command that runs the text command for the active view. Useful when
    writing a text command that you want to run as a build system.
    """

    def __new__(cls, classname, bases, dictionary):
        """
        Creates a WindowCommand that will run this text command. If an
        is_enabled attribute is defined, the window command will call it as a
        condition before running the text command.

        """
        logger.debug("bases=%s", bases)
        if not cls.check_bases(bases):
            raise TypeError(
                "Class %s is not a subclass of TextCommand" % classname)

        win_class_name, win_class = WindowTextCommandMeta.make_window_version(
            classname, dictionary)

        c = super(WindowTextCommandMeta, cls).__new__(
            cls, classname, bases, dictionary)

        if c and win_class_name and win_class:
            module_dict = sys.modules[c.__module__].__dict__
            module_dict[win_class_name] = win_class

        app_class_name, app_class = (
            WindowTextCommandMeta.make_application_version(
                classname, dictionary))
        if c and app_class_name and app_class:
            module_dict = sys.modules[c.__module__].__dict__
            module_dict[app_class_name] = app_class

        return c

    @classmethod
    def check_bases(cls, bases):
        if sublime_plugin.TextCommand in bases:
            return True
        else:
            for c in bases:
                if cls.check_bases(c.__bases__):
                    return True
            else:
                return False

    def make_window_version(classname, dictionary):
        command_name = WindowTextCommandMeta.determine_command_name(classname)

        if command_name is None:
            return

        @property
        def view(self):
            return self.window.active_view()

        def run(self, **kwargs):
            logger.debug("Window Version: running %s",
                         self.__class__.__name__)
            self.view.run_command(command_name, kwargs)

        return ('Window' + classname, type('Window' + classname,
                                           (sublime_plugin.WindowCommand,),
                                           {'view': view,
                                            'run': run}))

    def make_application_version(classname, dictionary):
        command_name = WindowTextCommandMeta.determine_command_name(classname)

        if command_name is None:
            return

        @property
        def view(self):
            return sublime.active_window().active_view()

        def run(self, **kwargs):
            logger.debug("Application Version: running %s",
                         self.__class__.__name__)
            self.view.run_command(command_name, kwargs)

        return ('App' + classname, type('App' + classname,
                                        (sublime_plugin.ApplicationCommand,),
                                        {'view': view,
                                         'run': run}))

    def determine_command_name(classname):
        logger.debug("classname=%s", classname)
        if classname.endswith('Command'):
            classname = classname[:-7]

        command_name_groups = re.findall(r"[A-Z]+[a-z]+", classname)
        if command_name_groups:
            command_name = '_'.join(command_name_groups).lower()
            logger.debug("command_name=%s", command_name)
            return command_name


class CallbackCmdMeta(WindowTextCommandMeta):
    """
    Modifies a command class to optionally call a pre_run_callback and/or a
    post_run_callback automatically.

    """

    def __new__(cls, classname, bases, dictionary):
        """
        Creates a Ring Dependent Command class.

        Modifies the run command to call determine_ring before running.

        """
        old_run_method = CallbackCmdMeta.find_attribute(
            'run', classname, bases, dictionary)
        pre_check_callback = CallbackCmdMeta.find_attribute(
            'pre_check_callback', classname, bases, dictionary)

        if old_run_method:
            logger.debug("found run command")

            pre_run_callback = CallbackCmdMeta.find_attribute(
                'pre_run_callback', classname, bases, dictionary)

            post_run_callback = CallbackCmdMeta.find_attribute(
                'post_run_callback', classname, bases, dictionary)

            if pre_run_callback and post_run_callback:
                logger.debug("found pre_run_callback command")
                logger.debug("found post_run_callback command")

                def run(self, *args, **kwargs):
                    self.pre_run_callback(*args, **kwargs)
                    old_run_method(self, *args, **kwargs)
                    self.post_run_callback(*args, **kwargs)

            elif pre_run_callback:
                logger.debug("found pre_run_callback command")

                def run(self, *args, **kwargs):
                    self.pre_run_callback(*args, **kwargs)
                    old_run_method(self, *args, **kwargs)

            elif post_run_callback:
                logger.debug("found post_run_callback command")

                def run(self, *args, **kwargs):
                    old_run_method(self, *args, **kwargs)
                    self.post_run_callback(*args, **kwargs)

            if pre_run_callback or post_run_callback:
                dictionary['run'] = run

        if pre_check_callback:
            logger.debug("found pre_check_callback command")
            is_enabled_method = CallbackCmdMeta.find_attribute(
                'is_enabled', classname, bases, dictionary)
            if is_enabled_method:
                logger.debug("found is_enabled command")

                def is_enabled(self, *args, **kwargs):
                    self.pre_check_callback(*args, **kwargs)
                    return is_enabled_method(self, *args, **kwargs)

                dictionary['is_enabled'] = is_enabled

            is_visible_method = CallbackCmdMeta.find_attribute(
                'is_visible', classname, bases, dictionary)
            if is_visible_method:
                logger.debug("found is_visible command")

                def is_visible(self, *args, **kwargs):
                    self.pre_check_callback(*args, **kwargs)
                    return is_visible_method(self, *args, **kwargs)

                dictionary['is_visible'] = is_enabled

        return super(CallbackCmdMeta, cls).__new__(
            cls, classname, bases, dictionary)

    def find_attribute(attribute, classname, bases, dictionary, require=False):
        logger.debug("attribute=%s", attribute)
        att = None
        try:
            att = dictionary[attribute]
        except KeyError:
            for c in bases:
                try:
                    att = c.__dict__[attribute]
                except KeyError:
                    pass
        finally:
            if (att is None) and require:
                raise AttributeError('cannot find %s in class %s',
                                     attribute,
                                     classname)
            return att


class RingFileCommand(sublime_plugin.TextCommand):
    """
    Parent class for TextCommands that rely on the file being a Ring File.

    """

    @property
    def ring_file(self):
        """Returns a reference to the command's ring file."""
        return get_ring_file(self.file_name)

    @property
    def file_name(self):
        """Returns the filename of the file associated with the command."""
        return self.view.file_name()

    def is_visible(self):
        try:
            return self.ring_file is not None
        except InvalidFileFormat:
            return False

    def is_enabled(self):
        return self.is_visible()


class FocusFileCommand(RingFileCommand):
    """
    Parent class for TextCommands that rely on the file being a Focus File.

    """

    @property
    def focus_file(self):
        """Returns a reference to the command's ring file."""
        return self.ring_file

    def is_visible(self):
        return super(FocusFileCommand, self).is_visible() and isinstance(
            self.ring_file, FocusFile)

    def is_enabled(self):
        return self.is_visible()


class RingViewCommand(sublime_plugin.TextCommand):
    """
    Parent class for all the commands that rely on the file being a Focus File
    """

    @property
    def ring_view(self):
        return get_view(self.view)

    def is_visible(self):
        try:
            self.ring_view
        except ViewTypeException:
            return False
        else:
            return True

    def is_enabled(self):
        return self.is_visible()


class FocusViewCommand(RingViewCommand):

    @property
    def ring_view(self):
        v = get_view(self.view)
        if not isinstance(v, FocusView):
            raise ViewTypeException(self.view, FocusView)
        else:
            return v

    @property
    def focus_view(self):
        return self.ring_view


class RingCommand(sublime_plugin.ApplicationCommand):
    """Parent class for commands that operate on loaded rings."""

    InstalledRingFilters = {}

    def run(self, current=False, **kwargs):
        if current:
            file_name = self.active_file_name()
            ring = Ring.get_ring(file_name)
            if ring is None:
                logger.critical('current view is not part of a ring (%s)',
                                file_name)
                return

            self.ring_run_command(ring, **kwargs)
        else:
            self.choose_installed_ring(
                lambda ring: self.ring_run_command(ring, **kwargs),
                **self.InstalledRingFilters)

    def choose_installed_ring(self, function, local_only=False,
                              rings_to_remove=None, ring_filter_callback=None):
        """Allows the user to select a ring and runs a specified command on it.

        Keyword arguments:
        function - the method to run with the ring as it's argument
        local_only - True to display only local rings
        rings_to_remove - list of rings to remove from the quick list

        """
        if function is not None:
            rings = Ring.list_rings(local_only=local_only)

            if rings_to_remove is not None:
                for r in rings_to_remove:
                    try:
                        rings.remove(r)
                    except ValueError:
                        pass

            if ring_filter_callback is not None:
                rings = [r for r in rings if ring_filter_callback(r)]

            logger.debug('Rings after filtering: %s', rings)

            if not rings:
                return

            if len(rings) == 1:
                function(rings[0])

            current_ring = None
            view = sublime.active_window().active_view()
            ring_file = get_ring_file(view.file_name())
            if (ring_file is not None):
                current_ring = ring_file.ring

            sort_locals = get_sort_local_rings()

            def ring_sort_callback(ring):
                if ((current_ring is not None) and (ring is current_ring)):
                    return "  " + ring.id
                elif (sort_locals and is_local_ring(ring)):
                    return " " + ring.id
                else:
                    return ring.id

            rings.sort(key=ring_sort_callback)

            sublime.active_window().show_quick_panel(
                [r.id for r in rings],
                lambda num: self._ring_chooser_handler(function, rings, num))

    def ring_run_command(self, ring, **kwargs):
        pass

    def _ring_chooser_handler(self, function, rings, num):
        """
        Runs the function passed into choose_installed_ring for the selected
        ring.

        """
        if num != -1:
            ring = rings[num]
            if function and ring:
                function(rings[num])

    def active_view(self):
        return sublime.active_window().active_view()

    def active_file_name(self):
        return self.active_view().file_name()

    def is_visible(self, current=False, **kwargs):
        if current:
            return bool(Ring.get_ring(self.active_file_name()))
        else:
            return (len(Ring.list_rings()) > 0)

    def is_enabled(self, **kwargs):
        return self.is_visible(**kwargs)
