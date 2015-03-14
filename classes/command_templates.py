from abc import ABCMeta
import logging
import re
import sys

import sublime_plugin

from MTFocusCommon.classes.ring_files import (
    MTFocusFile,
    InvalidFileFormat,
    get_mt_ring_file
)

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
        return get_mt_ring_file(self.file_name)

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
            self.ring_file, MTFocusFile)

    def is_enabled(self):
        return self.is_visible()
