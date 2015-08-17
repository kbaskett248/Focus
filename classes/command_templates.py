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


class HybridCommandMeta(ABCMeta):
    """
    A TextCommand can use this as its metaclass to automatically create a
    window command and an application command that will run the given text
    command for the active window and view. Useful when writing a text command
    that you want to run as a build system.
    """

    def __new__(cls, classname, bases, dictionary):
        """
        Creates a WindowCommand that will run this text command. If an
        is_enabled attribute is defined, the window command will call it as a
        condition before running the text command.

        """
        if not cls.check_bases(bases):
            raise TypeError(
                "Class %s is not a subclass of TextCommand" % classname)

        # Construct this class
        c = super(HybridCommandMeta, cls).__new__(
            cls, classname, bases, dictionary)

        if c:
            # Generate the WindowCommand and ApplicationCommand versions of the
            # class
            win_class = HybridCommandMeta.make_window_version(
                classname, dictionary)
            app_class = HybridCommandMeta.make_application_version(
                classname, dictionary)

            # Add the classes to the module of the original class
            module_dict = sys.modules[c.__module__].__dict__
            module_dict[win_class.__name__] = win_class
            module_dict[app_class.__name__] = app_class

        return c

    @classmethod
    def check_bases(cls, bases):
        '''
        Function: check_bases
        Summary: Checks to see if this function is a subclass of
        sublime_plugin.TextCommand
        Attributes:
            @param (cls):This class
            @param (bases):The list of the class's base classes
        Returns: True if TextCommand is a base class of the current class or
                 any of its base classes
        '''

        if sublime_plugin.TextCommand in bases:
            return True
        else:
            # Recursively check each of the base classes to see if they
            # subclass TextCommand
            for c in bases:
                if cls.check_bases(c.__bases__):
                    return True
            else:
                return False

    def make_window_version(classname, dictionary):
        '''
        Function: make_window_version
        Summary: Returns a new WindowCommand class that calls the current
                 command on the active view in the given window.
        Attributes:
            @param (classname):Name of the current class
            @param (dictionary):Dictionary of the current class
        Returns: A WindowCommand class
        '''

        command_name = HybridCommandMeta.determine_command_name(classname)

        @property
        def view(self):
            return self.window.active_view()

        def run(self, **kwargs):
            logger.debug("Window Version: running %s",
                         self.__class__.__name__)
            self.view.run_command(command_name, kwargs)

        return type('Window' + classname, (sublime_plugin.WindowCommand,),
                    {'view': view, 'run': run})

    def make_application_version(classname, dictionary):
        '''
        Function: make_application_version
        Summary: Returns a new ApplicationCommand class that calls the current
                 command on the active view in the active window.
        Attributes:
            @param (classname):Name of the current class
            @param (dictionary):Dictionary of the current class
        Returns: An ApplicationCommand class
        '''

        command_name = HybridCommandMeta.determine_command_name(classname)

        @property
        def view(self):
            return sublime.active_window().active_view()

        def run(self, **kwargs):
            logger.debug("Application Version: running %s",
                         self.__class__.__name__)
            self.view.run_command(command_name, kwargs)

        return type('App' + classname, (sublime_plugin.ApplicationCommand,),
                    {'view': view, 'run': run})

    def determine_command_name(classname):
        '''
        Function: determine_command_name
        Summary: Determines the name of the command to be called in sublime
                 based on the name of the class.
        Attributes:
            @param (classname):Name of the class being created.
        Returns: The name of the command as a string.
        Raises: ValueError if command name cannot be determined
        '''
        # Remove Command if present since it isn't included in the command name
        logger.debug("classname=%s", classname)
        if classname.endswith('Command'):
            classname = classname[:-7]

        # Group the name into groups starting with uppercase letters, then join
        # the groups with an underscore and convert to lowercase.
        command_name_groups = re.findall(r"[A-Z]+[a-z]+", classname)
        if command_name_groups:
            command_name = '_'.join(command_name_groups).lower()
            logger.debug("command_name=%s", command_name)
            return command_name

        raise ValueError(
            'Command name could not be determined for {0}'.format(classname))


class CallbackCmdMeta(HybridCommandMeta):
    """
    Modifies a command class to run callbacks before or after the standard
    methods defined in the API. The following callbacks are supported:
     - pre_run_callback: Called before the run method
     - post_run_callback: Called after the run method
     - pre_check_callback: Called before the is_enabled and is_visible methods

    """

    def __new__(cls, classname, bases, dictionary):
        """
        Creates a Ring Dependent Command class.

        Modifies the run command to call determine_ring before running.

        """
        cls.build_new_run_command(classname, bases, dictionary)

        try:
            cls.build_new_check_commands(classname, bases, dictionary)
        except AttributeError:
            logger.info("No pre_check_callback attribute specified")

        return super(CallbackCmdMeta, cls).__new__(
            cls, classname, bases, dictionary)

    @classmethod
    def build_new_run_command(cls, classname, bases, dictionary):
        '''
        Function: build_new_run_command
        Summary: Builds a new run command by calling the pre_run_callback or
                 post_run_callback.
        Attributes:
            @param (cls):A reference to the current class
            @param (classname):The name of the current class
            @param (bases):The base classes of the current class
            @param (dictionary):The dictionary of attributes of the current
                                class
        Returns: None

        '''
        old_run_method = CallbackCmdMeta.find_attribute(
            'run', classname, bases, dictionary)
        mode = ''

        # Try to get the pre_run_callback
        try:
            pre_run_callback = CallbackCmdMeta.find_attribute(
                'pre_run_callback', classname, bases, dictionary)
        except AttributeError:
            pass
        else:
            logger.debug("found pre_run_callback command")
            mode = 'pre'

        # Try to get the post_run_callback
        try:
            post_run_callback = CallbackCmdMeta.find_attribute(
                'post_run_callback', classname, bases, dictionary)
        except AttributeError:
            pass
        else:
            logger.debug("found post_run_callback command")
            if mode == 'pre':
                mode = 'both'
            else:
                mode = 'post'

        # Define a new run method
        if mode == 'both':
            def run(self, *args, **kwargs):
                self.pre_run_callback(*args, **kwargs)
                old_run_method(self, *args, **kwargs)
                self.post_run_callback(*args, **kwargs)
        elif mode == 'pre':
            def run(self, *args, **kwargs):
                self.pre_run_callback(*args, **kwargs)
                old_run_method(self, *args, **kwargs)
        elif mode == 'post':
            def run(self, *args, **kwargs):
                old_run_method(self, *args, **kwargs)
                self.post_run_callback(*args, **kwargs)

        if mode:
            dictionary['run'] = run

    @classmethod
    def build_new_check_commands(cls, classname, bases, dictionary):
        '''
        Function: build_new_check_commands
        Summary: Builds new is_visible and is_enabled commands that call the
                 pre_check_callback method beforehand.
        Attributes:
            @param (cls):A reference to the current class
            @param (classname):The name of the current class
            @param (bases):The base classes of the current class
            @param (dictionary):The dictionary of attributes of the current
                                class
        Returns: None

        '''
        pre_check_callback = CallbackCmdMeta.find_attribute(
            'pre_check_callback', classname, bases, dictionary)
        logger.debug("found pre_check_callback command")

        try:
            is_enabled_method = CallbackCmdMeta.find_attribute(
                'is_enabled', classname, bases, dictionary)
        except AttributeError:
            pass
        else:
            logger.debug("found is_enabled command")

            def is_enabled(self, *args, **kwargs):
                self.pre_check_callback(*args, **kwargs)
                return is_enabled_method(self, *args, **kwargs)

            dictionary['is_enabled'] = is_enabled

        try:
            is_visible_method = CallbackCmdMeta.find_attribute(
                'is_visible', classname, bases, dictionary)
        except AttributeError:
            pass
        else:
            logger.debug("found is_visible command")

            def is_visible(self, *args, **kwargs):
                self.pre_check_callback(*args, **kwargs)
                return is_visible_method(self, *args, **kwargs)

            dictionary['is_visible'] = is_enabled

    def find_attribute(attribute, classname, bases, dictionary):
        '''
        Function: find_attribute
        Summary: Searches for an attribute with the specified name in the
                 current class or in one of the base classes.
        Attributes:
            @param (attribute):Name of the attribute as a string
            @param (classname):Name of the current class
            @param (bases):Base classes of the current class
            @param (dictionary):Dictionary containing the attributes for the
                                current class
            @param (require) default=False: True if the
        Returns: The value of the specified attribute
        Raises: AttributeError if the specified attribute cannot be found
        '''

        logger.debug("attribute=%s", attribute)
        att = None
        try:
            att = dictionary[attribute]
        except KeyError:
            for c in bases:
                try:
                    att = c.__dict__[attribute]
                    break
                except KeyError:
                    continue
        finally:
            if (att is None):
                raise AttributeError(
                    'cannot find {att} in class {name}'.format(att=attribute,
                                                               name=classname))
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
