from abc import abstractmethod
from contextlib import contextmanager
import functools
import logging
import os
import re
import subprocess
import sys
import tempfile

import sublime
import sublime_plugin

from .classes.command_templates import CallbackCmdMeta
from .tools.classes import (
    get_ring,
    is_local_ring,
    get_ring_file,
    is_fs_file,
    is_focus_file,
    is_homecare_ring
)
from .tools.settings import (
    get_default_ring,
    get_translate_command,
    get_translate_include_settings
)

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

APPLICATION_PATTERN = re.compile(r"[A-Z][a-z]{1,2}")


@contextmanager
def updated_environ(env):
    old_env = os.environ.copy()
    for k, v in env.items():
        os.environ[k] = v
    try:
        yield
    finally:
        for k in env.keys():
            try:
                os.environ[k] = old_env[k]
            except KeyError:
                del os.environ[k]


class RingExecCommand(sublime_plugin.TextCommand, metaclass=CallbackCmdMeta):
    """
    Base class for commands that require a ring and run using an exec command.
    """

    @property
    def window(self):
        return self.view.window()

    @property
    def file_name(self):
        if self._file_name is None:
            return self.view.file_name()
        else:
            return self._file_name

    @property
    def ring_file(self):
        return get_ring_file(self.file_name)

    def determine_ring(self):
        logger.debug("determining ring for %s", self.__class__.__name__)
        self.ring = None
        self.default_flag = False

        self.target_ring = get_ring(self.file_name)

        default_ring = get_default_ring()
        if default_ring is not None:
            self.ring = get_ring(default_ring)
            if self.ring is not None:
                self.default_flag = True
                return

        self.ring = self.target_ring

    def replace_variables(self):
        new_kwargs = dict()
        logger.debug("ring: %s; path: %s", self.ring, self.ring.path)
        for k, v in self.kwargs.items():
            if isinstance(v, str):
                v = v.replace('<ring_path>', self.ring.path)
            new_kwargs[k] = v

        keys = new_kwargs.keys()
        if 'encoding' not in keys:
            new_kwargs['encoding'] = 'ascii'

        self.kwargs = new_kwargs

    def pre_check_callback(self, *args, file_name=None, **kwargs):
        self._file_name = file_name

    def pre_run_callback(self, *args, file_name=None, **kwargs):
        self.pre_check_callback(file_name=file_name)
        self.determine_ring()

    def post_run_callback(self, *args, **kwargs):
        # if 'env' not in self.kwargs.keys():
        #     self.kwargs['env'] = {}
        # self.kwargs['env']['RING_PATH'] = self.ring.path
        system_path = os.path.join(self.ring.path, 'System')
        try:
            self.kwargs['path'] = '{system_path};{path}'.format(
                system_path=system_path,
                path=self.kwargs['path'])
        except KeyError:
            self.kwargs['path'] = '{system_path};$PATH'.format(
                system_path=system_path)

        try:
            shell_cmd = self.kwargs['shell_cmd']
        except KeyError:
            logger.warning('no shell_cmd defined')
            return
        else:
            logger.debug("post_run_callback: self.exec_cmd: %s", self.exec_cmd)
            if isinstance(shell_cmd, str):
                self.replace_variables()
                self.window.run_command(self.exec_cmd, self.kwargs)
            elif hasattr(shell_cmd, '__iter__'):
                for cmd in shell_cmd:
                    self.kwargs['shell_cmd'] = cmd
                    self.replace_variables()
                    self.window.run_command(self.exec_cmd, self.kwargs)

    @abstractmethod
    def run(self, edit, **kwargs):
        pass

    def create_sublime_translate_file(self):
        logger.debug("ring.path = %s", self.ring.path)
        file_name = 'FocZ.Translate.Sublime.P.focus'
        logger.warning(('Translate code file: %s does not exist. '
                        'Trying to create'), file_name)
        sublime.run_command(
            'create_file_in_ring',
            {'ring_path': self.ring.path,
             'application': 'Foc',
             'package_path': ('Packages/Focus/resources/'
                              'FocZ.Translate.Sublime.P.focus')})

        translate_source = self.ring.get_file_path(os.path.join(
            'PgmSource', 'Foc', 'FocZ.Translate.Sublime.P.focus'))
        logger.debug('translate_source = %s', translate_source)
        translate_path = self.ring.get_translated_path(translate_source)
        if not translate_path:
            logger.error('creation of %s failed', file_name)
            return False
        else:
            return True


class RingRunCommand(RingExecCommand):
    """
    Base class for commands that require a ring and run using an exec command.
    """

    def pre_check_callback(self, *args, file_name=None, **kwargs):
        self._file_name = file_name

    def pre_run_callback(self, *args, file_name=None, **kwargs):
        self.pre_check_callback(file_name=file_name)
        self.determine_ring()

    def post_run_callback(self, *args, **kwargs):
        try:
            self.kwargs['shell_cmd']
        except KeyError:
            logger.warning('no shell_cmd defined')
            return
        logger.debug("post_run_callback: run_async")
        self.replace_variables()
        self.run_async(**self.kwargs)

    def run_async(self, cmd=None, shell_cmd=None, env={},
                  # "path" is an option in build systems
                  path="",
                  # "shell" is an option in build systems
                  shell=False,
                  # "results_file_path" is an option in build systems
                  results_file_path=None,
                  **kwargs):

        if not shell_cmd and not cmd:
            raise ValueError("shell_cmd or cmd is required")

        if shell_cmd and not isinstance(shell_cmd, str):
            raise ValueError("shell_cmd must be a string")

        self.results_file_path = results_file_path

        # Hide the console window on Windows
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        env['RING_PATH'] = self.ring.path

        with updated_environ(env):
            proc_env = os.environ.copy()
            if path:
                proc_env['PATH'] = path
            for k, v in proc_env.items():
                proc_env[k] = os.path.expandvars(v)

        if shell_cmd:
            if '<result_file>' in shell_cmd:
                if not self.results_file_path:
                    self.create_results_file()
                shell_cmd = shell_cmd.replace('<result_file>',
                                              self.results_file_path)
            self.launch_shell_command(shell_cmd, startupinfo, proc_env)
        else:
            if isinstance(cmd, str):
                if '<result_file>' in cmd:
                    if not self.results_file_path:
                        self.create_results_file()
                    cmd = cmd.replace('<result_file>', self.results_file_path)
            else:
                updated_cmd = []
                for a in cmd:
                    if '<result_file>' in a:
                        if not self.results_file_path:
                            self.create_results_file()
                        a.replace('<result_file>', self.results_file_path)
                    updated_cmd.append(a)
                cmd = updated_cmd

            subprocess.Popen(cmd, env=proc_env, shell=shell)

    @staticmethod
    def launch_shell_command(shell_cmd, startupinfo, env):
        logger.debug("shell_cmd: %s", shell_cmd)
        logger.debug("env:%s", env)
        if sys.platform == "win32":
            # Use shell=True on Windows, so shell_cmd is passed through
            # with the correct escaping
            subprocess.Popen(shell_cmd, startupinfo=startupinfo,
                             env=env, shell=True)
        elif sys.platform == "darwin":
            # Use a login shell on OSX, otherwise the users expected env
            # vars won't be setup
            subprocess.Popen(["/bin/bash", "-l", "-c", shell_cmd],
                             startupinfo=startupinfo, env=env,
                             shell=False)
        elif sys.platform == "linux":
            # Explicitly use /bin/bash on Linux, to keep Linux and OSX as
            # similar as possible. A login shell is explicitly not used for
            # linux, as it's not required
            subprocess.Popen(["/bin/bash", "-c", shell_cmd],
                             startupinfo=startupinfo, env=env,
                             shell=False)


    def create_results_file(self):
        """
        Create a temporary results file that can be monitored for results.
        Set a flag indicating that the file should be deleted when the process
        completes.

        """
        self.results_file_path = tempfile.NamedTemporaryFile(
            suffix='.txt', delete=False).name
        logger.debug('Creating Results File: %s', self.results_file_path)
        self._delete_results_file = True


class TranslateRingFileCommand(RingExecCommand):

    def run(self, edit, exec_cmd='exec', translate_all=False, **kwargs):
        logger.debug("File Version: running translate_ring_file")

        self.exec_cmd = exec_cmd
        self.kwargs = kwargs
        self.translate_all = translate_all

        if not translate_all and is_fs_file(self.ring_file):
            self.translate_fs()
            return

        translate_cmd = get_translate_command()
        logger.debug('translate_cmd = %s', translate_cmd)

        non_fs_translate = functools.partial(self.translate_other,
                                             translate_cmd)
        if self.default_flag:
            non_fs_translate = self.translate_other
        elif not is_homecare_ring(self.ring):
            non_fs_translate = self.translate_other
        elif 'focz.translate.sublime.p.mps' in translate_cmd.lower():
            non_fs_translate = self.translate_sublime

        if not translate_all:
            non_fs_translate()
            return

        self.ring_files = []
        shell_commands = []
        for rf in self.get_ring_files(all_windows=True):
            self._file_name = rf.file_name
            if is_fs_file(self.ring_file):
                self.translate_fs()
                shell_commands.append(self.kwargs['shell_cmd'])
            elif non_fs_translate == self.translate_sublime:
                self.ring_files.append(rf.file_name)
            else:
                non_fs_translate()
                shell_commands.append(self.kwargs['shell_cmd'])

        if self.ring_files and (non_fs_translate == self.translate_sublime):
            non_fs_translate()
            shell_commands.append(self.kwargs['shell_cmd'])

        self.kwargs['shell_cmd'] = shell_commands
        logger.debug("Shell Commands")
        [logger.debug("    %s", x) for x in shell_commands]

        self._file_name = None
        del self.ring_files

    def translate_sublime(self):
        tried_to_create = False
        translate_source = self.ring.get_file_path(os.path.join(
            'PgmSource', 'Foc', 'FocZ.Translate.Sublime.P.focus'))
        logger.debug('translate_source = %s', translate_source)

        if not translate_source:
            if not self.create_sublime_translate_file():
                self.translate_other()
                return
            tried_to_create = True
            translate_source = self.ring.get_file_path(os.path.join(
                'PgmSource', 'Foc', 'FocZ.Translate.Sublime.P.focus'))

        translate_path = self.ring.get_translated_path(translate_source)

        if not translate_path:
            if tried_to_create or not self.create_sublime_translate_file():
                self.translate_other()
                return
            tried_to_create = True
            translate_path = self.ring.get_translated_path(translate_source)

        logger.debug('translate_path = %s', translate_path)
        include_files, include_count = get_translate_include_settings()

        if self.translate_all:
            parameters = [self.ring_files]
        else:
            parameters = [self.file_name]
        parameters.extend(['<result_file>', '', '', include_files,
                           include_count])

        self.kwargs['shell_cmd'] = self.ring.get_shell_cmd(
            target_ring=self.target_ring,
            full_path=translate_path,
            parameters=parameters)

    def translate_other(self,
                        translate_cmd='Foc\\FocZ.Textpad.Translate.P.focus'):
        translate_cmd = os.path.join('PgmSource', translate_cmd)

        if ((translate_cmd != 'PgmSource\\Foc\\FocZ.Textpad.Translate.P.focus')
                and not self.ring.check_file_existence(translate_cmd)):
            self.translate_other()
            return

        translate_path = self.ring.get_file_path(translate_cmd)
        logger.debug('translate_path = %s', translate_path)
        include_files, include_count = get_translate_include_settings()

        if (not self.ring_file.is_includable()) or (not include_files):
            self.kwargs['shell_cmd'] = self.ring.get_shell_cmd(
                target_ring=self.target_ring, partial_path=translate_cmd,
                parameters=self.file_name)
            logger.debug("shell_cmd = %s", self.kwargs['shell_cmd'])
        else:
            shell_cmd_list = []
            logger.info('Instead of translating %s, ' +
                        'translating all open files that include it',
                        self.file_name)
            self.ring_files = self.get_ring_files(all_windows=True)
            for f in self.get_including_files(self.ring_file):
                shell_cmd = self.ring.get_shell_cmd(
                    target_ring=self.target_ring, partial_path=translate_cmd,
                    parameters=f.file_name)
                logger.debug("shell_cmd = %s", shell_cmd)
                shell_cmd_list.append(shell_cmd)
            self.kwargs['shell_cmd'] = shell_cmd_list
            del self.ring_files

        self.kwargs['quiet'] = True

    def translate_fs(self):

        if not self.target_ring.check_file_existence('magic.mas'):
            logger.error('magic.mas does not exist in ring %s', self.ring)
            return

        translate_path = self.target_ring.get_file_path('magic.mas')
        logger.debug('translate_path = %s', translate_path)

        self.kwargs['initial_message'] = 'Translating %s\n\n' % self.file_name
        self.kwargs['shell_cmd'] = self.ring.get_shell_cmd(
            target_ring=self.target_ring, full_path=translate_path,
            parameters=self.file_name)

    def get_including_files(self, include_file):
        """Returns a list of all open files that include the given file."""
        if not hasattr(self, 'ring_files'):
            self.ring_files = self.get_ring_files(all_windows=True)

        files_to_translate = set()
        files_to_translate.add(include_file)
        logger.debug('Getting including files for %s', include_file.file_name)

        if not include_file.ring:
            logger.debug('%s has no ring', include_file.file_name)
            return files_to_translate

        for ring_file in self.ring_files:
            if ring_file in files_to_translate:
                continue

            for inc_file in ring_file.get_include_files():
                if (include_file.file_name.lower() == inc_file.lower()):
                    logger.debug('%s is included in %s',
                                 include_file.file_name, ring_file.file_name)

                    if ring_file.is_includable():
                        files_to_translate = files_to_translate.union(
                            self.get_including_files(ring_file))
                    else:
                        files_to_translate.add(ring_file)
                    break

        return files_to_translate

    def get_ring_files(self, all_windows=False, different_rings=False,
                       most_common_ring=False):
        ring_files = set()
        if all_windows:
            win_set = sublime.windows()
        else:
            win_set = (self.window(), )

        if (most_common_ring or different_rings or (not self.ring_file) or
                (not self.ring_file.ring)):
            record_all = True
            ring_file_dict = dict()
        else:
            record_all = False
            match_ring = self.ring_file.ring

        for win in win_set:
            for view in win.views():
                if not view.file_name():
                    continue

                ring_file = get_ring_file(view.file_name())
                if (not ring_file) or (ring_file in ring_files):
                    continue

                if record_all:
                    ring_files.add(ring_file)
                    if not different_rings:
                        try:
                            ring_file_dict[ring_file.ring.key].add(ring_file)
                        except KeyError:
                            ring_file_dict[ring_file.ring.key] = set()
                            ring_file_dict[ring_file.ring.key].add(ring_file)
                elif ring_file.ring is match_ring:
                    ring_files.add(ring_file)

        if different_rings or (not record_all):
            return ring_files

        ring_count = 0
        for k, v in ring_file_dict:
            if len(v) > ring_count:
                ring_key = k
                ring_count = len(v)

        return ring_file_dict[ring_key]

    def is_enabled(self, *args, file_name=None, **kwargs):
        self._file_name = file_name
        logger.debug("checking is_enabled for translate for %s",
                     self.file_name)
        if self.ring_file is not None:
            logger.debug("self.ring_file = %s", self.ring_file)
            return self.ring_file.is_translatable()

        return False


class FormatRingFileCommand(RingExecCommand):

    def run(self, edit, exec_cmd='exec', **kwargs):
        self.exec_cmd = exec_cmd
        self.kwargs = kwargs

        translate_cmd = get_translate_command()

        if self.default_flag:
            self.format_other()
        elif 'focz.translate.sublime.p.mps' in translate_cmd.lower():
            self.format_sublime()
        else:
            self.format_other()

    def format_sublime(self):
        format_cmd = os.path.join('PgmObject', 'Foc',
                                  'FocZ.Translate.Sublime.P.mps')
        format_path = self.ring.get_file_path(format_cmd)
        logger.debug('format_path = %s', format_path)

        if not format_path:
            if not self.create_sublime_translate_file():
                self.format_default()
                return
            else:
                format_path = self.ring.get_file_path(format_cmd)

        parameters = [self.file_name, '<result_file>', '', 'Format Only']
        self.kwargs['shell_cmd'] = self.ring.get_shell_cmd(
            target_ring=self.target_ring,
            full_path=format_path,
            parameters=parameters)

    def format_other(self):
        format_cmd = os.path.join('PgmSource', 'Foc',
                                  'FocZ.Textpad.Format.P.focus')

        self.kwargs['shell_cmd'] = self.ring.get_shell_cmd(
            target_ring=self.target_ring, partial_path=format_cmd,
            parameters=self.file_name)
        self.kwargs['quiet'] = True

    def is_enabled(self, *args, file_name=None, **kwargs):
        if self.ring_file is not None:
            return self.ring_file.is_formattable()

        return False


class CodeExecutionTreeCommand(RingExecCommand):

    def run(self, edit, exec_cmd='exec', **kwargs):
        self.exec_cmd = exec_cmd
        self.kwargs = kwargs

        cmd = os.path.join('PgmSource', 'Hha',
                           'HhaZt.DisplayFunctionTree.P.focus')

        self.kwargs['shell_cmd'] = self.ring.get_shell_cmd(
            target_ring=self.target_ring, partial_path=cmd,
            parameters=self.file_name)
        self.kwargs['quiet'] = True

    def is_enabled(self, *args, file_name=None, **kwargs):
        return self.ring_file is not None


class RunRingFileCommand(RingRunCommand):
    """
    Runs the current file if it is runnable.
    """

    def run(self, edit, **kwargs):
        self.kwargs = kwargs

        self.kwargs['shell_cmd'] = self.ring.get_shell_cmd(
            target_ring=self.target_ring, full_path=self.file_name)

        logger.info('running %s', self.file_name)
        sublime.status_message('Running %s' % os.path.basename(self.file_name))

    def is_enabled(self, *args, file_name=None, **kwargs):
        logger.debug("is_enabled")
        if self.ring_file is not None:
            if not self.ring_file.is_runnable():
                logger.debug("is_enabled returning False", )
            return self.ring_file.is_runnable()
        logger.debug("is_enabled returning False", )
        return False


class CreateFileInRingCommand(sublime_plugin.ApplicationCommand):
    """
    Creates a file in the ring represented by ring_path with the given
    contents and file_name, then translates that file if it is translateable.
    if package_path is specified, the resource with that name is loaded and
    used.
    """

    def run(self, ring_path, application=None, package_path=None,
            contents=None, file_name=None, force=False):

        if not ring_path:
            logger.error('ring_path must be specified')
            return
        else:
            ring = get_ring(ring_path)
            if not ring:
                logger.error('ring_path does not refer to a valid ring')
                return

        if package_path:
            contents = sublime.load_resource(package_path)
            if not contents:
                logger.error(
                    'package_path: %s does not refer to a valid resource',
                    package_path)
                return
            else:
                contents = contents.replace('\r\n', '\n').replace('\r', '\n')
            if not file_name:
                file_name = os.path.basename(package_path)

        elif contents:
            if not file_name:
                logger.error(
                    'if contents specified, file_name must also be specified')
                return

        else:
            logger.error(
                'must specify either package_path or file_name and contents')
            return

        if not application:
            match = APPLICATION_PATTERN.match(file_name)
            if match is None:
                logger.error(
                    ('application could not be determined from filename: %s;'
                     ' application must be specified'), file_name)
                return
            else:
                application = match.group(1)

        if not force:
            if not sublime.ok_cancel_dialog(
                    ('Sublime Text will create file {file}\n'
                     'in application {app} in ring {ring}.\n'
                     'Would you like to create the file?').format(
                        file=file_name, app=application, ring=ring.name),
                    'Create'):
                return

        file_path = ring.create_file_in_ring(application, file_name, contents)
        if not file_path:
            logger.error('file: %s could not be created in ring: %s',
                         file_name, ring)
            if not force:
                sublime.error_message(
                    'File %s could not be created in ring %s.' % (file_name,
                                                                  ring.name))
            return

        ring_file = get_ring_file(file_path)
        if ring_file.is_translatable():
            ring_file.translate(separate_process=False)
            object_code_path = ring.get_translated_path(file_path)
            logger.debug('object_code_path = %s', object_code_path)
            if not object_code_path:
                logger.error('translated file could not be found for file: %s',
                             file_path)
                if not force:
                    sublime.error_message(
                        ('Translated file for %s could not be found in '
                         'ring %s.') % (file_name, ring.name))
