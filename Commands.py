from abc import abstractmethod
from collections import deque
import logging
import os
import re
import subprocess
import sys
import tempfile

import sublime
import sublime_plugin

from .classes.views import get_mt_view
from .classes.rings import get_mt_ring, is_local_ring
from .classes.ring_files import get_mt_ring_file
from .classes.command_templates import (
    CallbackCmdMeta,
    RingFileCommand
)
from .tools import (
    get_default_ring,
    get_translate_command,
    get_translate_include_settings,
    convert_to_focus_lists
)

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

ATTRIBUTE_PATTERN = re.compile(r"(\s*:?\w+)(\s*)(.*)")
INDENTATION_PATTERN = re.compile(r"(^.+//(( *$)| *))|"
                                 r"( +$)|([\[\{\( ])|([\]\}\);])")
APPLICATION_PATTERN = re.compile(r"[A-Z][a-z]{1,2}")
IN_METHOD_DOC_KEY = 'in_method_doc'
ENABLE_TRANSLATOR_INDENT_KEY = 'enable_translator_indent'


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
        return get_mt_ring_file(self.file_name)

    def determine_ring(self):
        logger.debug("determining ring for %s", self.__class__.__name__)
        self.ring = None
        self.default_flag = False

        default_ring = get_default_ring()
        if default_ring is not None:
            self.ring = get_mt_ring(default_ring)
            if self.ring is not None:
                self.default_flag = True
                return

        self.ring = get_mt_ring(self.file_name)

    def replace_variables(self):
        new_kwargs = dict()
        logger.debug("ring: %s; path: %s", self.ring, self.ring.path)
        for k, v in self.kwargs.items():
            if isinstance(v, str):
                v = v.replace('<ring_path>', self.ring.path)
            new_kwargs[k] = v

        try:
            path = new_kwargs['path']
            path += ';' + self.ring.system_path
        except KeyError:
            path = self.ring.system_path
        finally:
            new_kwargs['path'] = path

        logger.debug("kwargs=%s", new_kwargs)

        self.kwargs = new_kwargs

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

        self.replace_variables()
        self.window.run_command(self.exec_cmd, self.kwargs)

    @abstractmethod
    def run(self, edit, **kwargs):
        pass

    def get_tools_path(self):
        tools_path = os.path.join('PgmObject', 'Foc',
                                  'FocZ.TextPadTools.P.mps')
        return self.ring.get_file_path(tools_path)

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

        translate_path = self.ring.get_file_path(os.path.join(
            'PgmObject', 'Foc', 'FocZ.Translate.Sublime.P.mps'))
        if not translate_path:
            logger.error('creation of %s failed', file_name)
            return False
        else:
            return True

    def build_default_shell_cmd(self, partial_path):
        file_ring = get_mt_ring(self.file_name)
        if is_local_ring(file_ring) and is_local_ring(self.ring):
            shell_cmd = ('magic.exe "<ring_path>\System\OmniLaunch.mps"  '
                         '{0}{1}  "{2}"').format(os.sep,
                                                 partial_path,
                                                 self.file_name)
        else:
            shell_cmd = 'magic.exe "{0}" RUNRINGTOOL "{1}" "{2}"'.format(
                self.get_tools_path(), self.ring.get_file_path(partial_path),
                self.file_name)

        return shell_cmd


class RingRunCommand(RingExecCommand):
    """
    Base class for commands that require a ring and run using an exec command.
    """

    def replace_variables_and_run(self):
        try:
            self.kwargs['shell_cmd']
        except KeyError:
            logger.warning('no shell_cmd defined')
            return
        new_kwargs = dict()
        logger.debug("ring: %s", self.ring)
        logger.debug("ring.path: %s", self.ring.path)
        for k, v in self.kwargs.items():
            if isinstance(v, str):
                v = v.replace('<ring_path>', self.ring.path)
            new_kwargs[k] = v

        try:
            path = new_kwargs['path']
            path += ';' + self.ring.system_path
        except KeyError:
            path = self.ring.system_path
        finally:
            new_kwargs['path'] = path

        logger.debug("kwargs=%s", new_kwargs)

        self.run_async(**new_kwargs)

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

        self.replace_variables()
        self.run_async(**self.kwargs)

    def run_async(self, cmd=None, shell_cmd=None, env={},
                  # startup_info is an option in build systems
                  startup_info=True,
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
        if startup_info and os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        # Set temporary PATH to locate executable in cmd
        if path:
            old_path = os.environ["PATH"]
            # The user decides in the build system whether he wants to append
            # $PATH or tuck it at the front: "$PATH;C:\\new\\path",
            # "C:\\new\\path;$PATH"
            os.environ["PATH"] = os.path.expandvars(path)

        proc_env = os.environ.copy()
        proc_env.update(env)
        for k, v in proc_env.items():
            proc_env[k] = os.path.expandvars(v)

        if shell_cmd:
            if '<result_file>' in shell_cmd:
                if not self.results_file_path:
                    self.create_results_file()
                shell_cmd = shell_cmd.replace('<result_file>',
                                              self.results_file_path)

            if sys.platform == "win32":
                # Use shell=True on Windows, so shell_cmd is passed through
                # with the correct escaping
                subprocess.Popen(shell_cmd, startupinfo=startupinfo,
                                 env=proc_env, shell=True)
            elif sys.platform == "darwin":
                # Use a login shell on OSX, otherwise the users expected env
                # vars won't be setup
                subprocess.Popen(["/bin/bash", "-l", "-c", shell_cmd],
                                 startupinfo=startupinfo, env=proc_env,
                                 shell=False)
            elif sys.platform == "linux":
                # Explicitly use /bin/bash on Linux, to keep Linux and OSX as
                # similar as possible. A login shell is explicitly not used for
                # linux, as it's not required
                subprocess.Popen(["/bin/bash", "-c", shell_cmd],
                                 startupinfo=startupinfo, env=proc_env,
                                 shell=False)
        else:
            if isinstance(cmd, str):
                if '<result_file>' in shell_cmd:
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

            # Old style build system, just do what it asks
            subprocess.Popen(cmd, env=proc_env, shell=shell)

        if path:
            os.environ["PATH"] = old_path

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


def boolean_query_context_per_selection(view, operator, operand, match_all,
                                        check_selection):
    """
    Helper function for on_query_context functions that operate in a boolean
    manner, i.e., supported operators are equal and not equal, and supported
    operands are True and False.

    Keyword arguments:
    check_selection - A function accepting a view argument followed by a
                      Region argument, that returns True if the region matches
                      the check and false if it doesn't.
    """
    # Wrong operator
    # Determine the direction:
    #   Operator   | Operand | Direction
    # ----------------------------------
    #   OP_EQUAL   |  True   |   True
    #   OP_EQUAL   |  False  |   False
    # OP_NOT_EQUAL |  True   |   False
    # OP_NOT_EQUAL |  False  |   True
    if operator == sublime.OP_EQUAL:
        direction = (True == operand)
    elif operator == sublime.OP_NOT_EQUAL:
        direction = (False == operand)
    else:
        return None

    # Loop through the selections and store 1 for a match or 0 for non-matches.
    match_list = []
    for r in view.sel():
        if check_selection(view, r):
            if (not match_all) and direction:
                return True
            elif match_all and (not direction):
                return False
            else:
                match_list.append(1)
        else:
            if (not match_all) and (not direction):
                return True
            elif match_all and direction:
                return False
            else:
                match_list.append(0)

    if match_all:
        result = min(match_list)
    else:
        result = max(match_list)
    return (direction == (result == 1))


class QueryContextCommand(sublime_plugin.EventListener):

    def on_query_context(self, view, key, operator, operand, match_all):
        logger.debug("key: %s", key)
        if key == ENABLE_TRANSLATOR_INDENT_KEY:
            return self.on_query_context_translator_indent(
                view, operator, operand, match_all)
        elif key == IN_METHOD_DOC_KEY:
            return self.on_query_context_in_method_doc(
                view, operator, operand, match_all)
        else:
            return None

    def on_query_context_translator_indent(self, view, *args):
        # Wrong syntax
        if view.score_selector(view.sel()[0].begin(), 'source.focus') <= 0:
            return False

        self.compute_disable_string()
        print('querying context for EnableTranslatorIndent')
        args = list(args)
        args.append(self.check_selection_translator_indent)
        return boolean_query_context_per_selection(view, *args)

    def compute_disable_string(self):
        settings = sublime.load_settings('MT-Focus.sublime-settings')
        settings2 = sublime.load_settings('MT-Focus-Snippets.sublime-settings')

        self.disable_for_certain_strings = False

        # Give preference to settings from MT-Focus because it is an override.
        if settings.has('disable_translator_indent_for'):
            st = settings.get('disable_translator_indent_for')
        elif settings2.has('disable_translator_indent_for'):
            st = settings2.get('disable_translator_indent_for')
        else:
            return

        if isinstance(st, list) and st:
            self.disable_for_certain_strings = True
            s = r"^\s*({0})$".format('|'.join(st))
            # print(s)
            self.disable_pattern = re.compile(s)
        elif isinstance(st, str) and st:
            self.disable_for_certain_strings = True
            # print(st)
            self.disable_pattern = re.compile(st)

    def check_selection_translator_indent(self, view, selection):
        """
        Check individual regions. Return True to enable translator indent for
        the specified region or False to disable it.

        """
        if not selection.empty():
            return False

        point = selection.begin()

        if view.score_selector(
                point,
                ('keyword.other.keyword.focus,'
                 'keyword.other.attribute.focus')) > 0:
            return False

        if view.score_selector(
                point-1,
                ('meta.value.keyword.focus,'
                 'meta.value.attribute.focus')) > 0:
            return False

        line = view.line(point)
        preceding_line_string = view.substr(
            sublime.Region(line.begin(), point))

        if self.disable_for_certain_strings:
            match = self.disable_pattern.match(preceding_line_string)
            if match is not None:
                return False

        match = ATTRIBUTE_PATTERN.match(preceding_line_string)
        if match is None:
            return False
        else:
            return True

    def on_query_context_in_method_doc(self, view, *args):
        # Wrong syntax
        if view.score_selector(view.sel()[0].begin(),
                               'source.focus, source.fs') <= 0:
            return None

        print('querying context for InMethodDoc')
        args = list(args)
        args.append(self.check_selection_in_method_doc)
        return boolean_query_context_per_selection(view, *args)

    def check_selection_in_method_doc(self, view, selection):
        """
        Check individual regions. Return True if the given selection is in
        the documentation for a subroutine. Documentation must be below the
        subroutine header to be correctly detected.

        """
        points = [selection.begin()]
        if not selection.empty():
            points.append(selection.end()-1)

        for p in points:
            if view.score_selector(p, 'comment') <= 0:
                return False

        print('still checking 1')

        mt_view = get_mt_view(view)
        if mt_view is None:
            return False

        print('still checking 2')

        cb = mt_view.get_codeblock(points[0])
        print(cb.documentation_region)
        if cb.documentation_region.contains(selection):
            return True
        else:
            return False


class TranslatorIndentCommand(sublime_plugin.TextCommand):
    """
    Command to indent the right side of translator sections to the correct
    point.
    """

    def run(self, edit):
        """Indents the right side of translator sections to 34 spaces."""
        for r in self.view.sel():
            point = r.begin()
            line = self.view.line(point)
            pre_line = sublime.Region(line.begin(), point)
            post_line = sublime.Region(point, line.end())
            line_string = self.view.substr(line)

            match = ATTRIBUTE_PATTERN.match(line_string)

            if match is not None:
                self.view.replace(edit, post_line, match.group(3))
                s = match.group(1)
                l = len(s)
                if l <= 33:
                    s += (34 - l) * ' '
                else:
                    s += (2 - (l % 2)) * ' '
                self.view.replace(edit, pre_line, s)


class IndentNewLineCommand(sublime_plugin.TextCommand):
    """
    Command to make the enter key a bit smarter by indenting the next line
    to the correct column.

    """

    def run(self, edit):
        self.new_region_set = []

        selection = self.view.sel()
        for sel in selection:
            self.process_selection(edit, sel)

        selection.clear()
        selection.add_all(self.new_region_set)

    def process_selection(self, edit, sel):
        # Current location of the cursor
        point = sel.begin()
        # New location of the cursor after enter is pressed
        new_point = point + 1
        self.operation_stack = deque()
        # Flag that we are processing the first line
        first_line = True
        line_score = 0
        line_indentation = None

        while ((first_line or (line_score < 0)) and
                (self.view.score_selector(point, 'meta.subroutine.fs') > 0)):
            line_indentation = ''
            preceding_line = sublime.Region(self.view.line(point).begin(),
                                            point)
            preceding_line_string = self.view.substr(preceding_line)
            # print(preceding_line_string)

            for match in INDENTATION_PATTERN.finditer(
                    preceding_line_string[::-1]):
                # print(match.groups())
                current_point = point - match.span(0)[1]
                if match.group(1) is not None:
                    if match.group(3) is not None:
                        line_indentation = match.group(3)
                    else:
                        continue
                elif self.view.score_selector(current_point, 'string') > 0:
                    continue
                elif match.group(4) is not None:
                    prev_operator = self.pop_prev_operator()
                    if prev_operator == ';':
                        pass
                    else:
                        line_indentation = match.group(4)
                    self.append_operator(prev_operator)
                elif match.group(5) is not None:
                    operator = match.group(5)
                    prev_operator = self.pop_prev_operator()

                    if operator == ' ':
                        if prev_operator != ';':
                            self.append_operator(prev_operator)
                        if ((prev_operator != '}') and
                            self.view.score_selector(
                                current_point,
                                'meta.function.arguments.translate-time.focus'
                                ) <= 0):
                            line_score += 1
                    elif operator == '{' and prev_operator == ';':
                        line_score += 2
                    else:
                        line_score += 1
                elif match.group(6) is not None:
                    operator = match.group(6)
                    # We don't want more than one ; on the stack at a time
                    if operator == ';':
                        prev_operator = self.pop_prev_operator()

                        if prev_operator == ';':
                            line_score += 1
                        else:
                            self.append_operator(prev_operator)

                    line_score -= 1
                    self.append_operator(operator)

                # print(line_score)
                # print(self.operation_stack)

                if line_score > 0:
                    line_indentation = (current_point + 1 -
                                        preceding_line.begin()) * ' '
                    break
            else:
                point = preceding_line.begin() - 1
            first_line = False

        if line_score >= 0:
            new_point += len(line_indentation)
            self.view.replace(edit, sel, '\n' + line_indentation)
        else:
            self.view.replace(edit, sel, '\n')
        self.new_region_set.append(sublime.Region(new_point, new_point))

    def append_operator(self, operator):
        if operator != '':
            self.operation_stack.append(operator)

    def pop_prev_operator(self):
        try:
            return self.operation_stack.pop()
        except IndexError:
            return ''


class TranslateRingFileCommand(RingExecCommand):

    def run(self, edit, exec_cmd, **kwargs):
        logger.debug("File Version: running translate_ring_file")

        self.exec_cmd = exec_cmd
        self.kwargs = kwargs

        translate_cmd = get_translate_command()
        logger.debug('translate_cmd = %s', translate_cmd)

        if self.default_flag:
            self.translate_other()
        elif 'focz.translate.sublime.p.mps' in translate_cmd.lower():
            self.translate_sublime()
        else:
            self.translate_other(translate_cmd)

    def translate_sublime(self):
        translate_cmd = os.path.join('PgmObject', 'Foc',
                                     'FocZ.Translate.Sublime.P.mps')
        translate_path = self.ring.get_file_path(translate_cmd)
        logger.debug('translate_path = %s', translate_path)

        if not translate_path:
            if not self.create_sublime_translate_file():
                self.translate_default()
                return
            else:
                translate_path = self.ring.get_file_path(translate_cmd)

        include_files, include_count = get_translate_include_settings()
        parameters = convert_to_focus_lists([self.file_name,
                                             '<result_file>',
                                             '',
                                             '',
                                             include_files,
                                             include_count])
        shell_cmd = 'magic.exe "{0}" {1}'.format(translate_path, parameters)

        self.kwargs['shell_cmd'] = shell_cmd

    def translate_other(self,
                        translate_cmd='Foc\\FocZ.Textpad.Translate.P.mps'):
        translate_cmd = os.path.join('PgmObject', translate_cmd)
        translate_path = self.ring.get_file_path(translate_cmd)
        logger.debug('translate_path = %s', translate_path)

        if not translate_path:
            self.translate_default()
            return

        if self.default_flag:
            shell_cmd = self.build_default_shell_cmd(translate_cmd)
        else:
            shell_cmd = 'magic.exe "{0}" "{1}"'.format(translate_path,
                                                       self.file_name)

        self.kwargs['shell_cmd'] = shell_cmd
        logger.debug('shell_cmd = %s', shell_cmd)
        self.kwargs['quiet'] = True

    def is_enabled(self, *args, file_name=None, **kwargs):
        self._file_name = file_name
        if self.ring_file is not None:
            return self.ring_file.is_translatable()

        return False


class FormatRingFileCommand(RingExecCommand):

    def run(self, edit, exec_cmd, **kwargs):
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
            if not self.create_sublime_translate_file(self.ring):
                self.format_default()
                return
            else:
                format_path = self.ring.get_file_path(format_cmd)

        parameters = convert_to_focus_lists([self.file_name, '<result_file>',
                                             '', 'Format Only'])
        shell_cmd = 'magic.exe "{0}" {1}'.format(format_path, parameters)

        self.kwargs['shell_cmd'] = shell_cmd

    def format_other(self):
        format_cmd = os.path.join('PgmObject', 'Foc',
                                  'FocZ.TextPad.Format.P.mps')
        format_path = self.ring.get_file_path(format_cmd)
        logger.debug('format_path = %s', format_path)

        if self.default_flag:
            shell_cmd = self.build_default_shell_cmd(format_cmd)
        else:
            shell_cmd = 'magic.exe "{0}" "{1}"'.format(format_path,
                                                       self.file_name)

        self.kwargs['shell_cmd'] = shell_cmd
        self.kwargs['quiet'] = True

    def is_enabled(self, *args, file_name=None, **kwargs):
        if self.ring_file is not None:
            return self.ring_file.is_formattable()

        return False


class RunRingFileCommand(RingRunCommand):
    """
    Runs the current file if it is runnable.
    """

    def run(self, edit, exec_cmd, **kwargs):
        self.exec_cmd = exec_cmd
        self.kwargs = kwargs

        if self.default_flag:
            if is_local_ring(self.ring):
                partial_path = os.sep + os.path.join('PgmObject', 'Foc',
                                                     'FocZ.Textpad.Run.P.mps')
                shell_cmd = ('magic.exe "<ring_path>\System\OmniLaunch.mps"  '
                             '{0}  "{1}"').format(partial_path,
                                                  self.file_name)
            else:
                shell_cmd = 'magic.exe "{0}" RUN "{1}"'.format(
                    self.get_tools_path(), self.file_name)
        else:
            shell_cmd = 'magic.exe "{0}" RUN "{1}"'.format(
                self.get_tools_path(), self.file_name)

        self.kwargs['shell_cmd'] = shell_cmd

        logger.info('running %s', self.file_name)
        sublime.status_message('Running %s' % os.path.basename(self.file_name))

    def is_enabled(self, *args, file_name=None, **kwargs):
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
            ring = get_mt_ring(ring_path)
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
            sublime.ok_cancel_dialog(
                ('Sublime Text will create file %s\n'
                 'in application %s in ring %s.\n'
                 'Would you like to create the file?') % (file_name,
                                                          application,
                                                          ring.name),
                'Create')

        file_path = ring.create_file_in_ring(application, file_name, contents)
        if not file_path:
            logger.error('file: %s could not be created in ring: %s',
                         file_name, ring)
            if not force:
                sublime.error_message(
                    'File %s could not be created in ring %s.' % (file_name,
                                                                  ring.name))
            return

        ring_file = get_mt_ring_file(file_path)
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
