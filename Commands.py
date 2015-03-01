from collections import deque
import logging
import os
import re

import sublime
import sublime_plugin

from .classes.views import get_mt_view
from .classes.rings import get_mt_ring
from .classes.ring_files import get_mt_ring_file
from .tools import get_translated_path


logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')


ATTRIBUTE_PATTERN = re.compile(r"(\s*:?\w+)(\s*)(.*)")
INDENTATION_PATTERN = re.compile(r"(^.+//(( *$)| *))|"
                                 r"( +$)|([\[\{\( ])|([\]\}\);])")
APPLICATION_PATTERN = re.compile(r"[A-Z][a-z]{1,2}")
IN_METHOD_DOC_KEY = 'in_method_doc'


def get_member_region(view, point):
    """Gets the region containing the function surrounding the current point"""
    if view.score_selector(point, 'meta.subroutine.fs, meta.list.fs') <= 0:
        return None

    line = view.line(point)
    point = line.end()
    if view.score_selector(point, 'meta.subroutine.fs, meta.list.fs') <= 0:
        point = line.begin() - 1

    while view.score_selector(point, 'meta.subroutine.fs, meta.list.fs') > 0:
        region = view.extract_scope(point)
        point = region.end()

    if view.score_selector(region.begin(), 'meta.list.fs') > 0:
        region = sublime.Region(region.begin(), region.end()-1)
    return region


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


class EnableTranslatorIndentCommand(sublime_plugin.EventListener):
    """
    on_query_context command for the enable_translator_indent context.
    """

    def on_query_context(self, view, key, operator, operand, match_all):
        # Wrong key
        if key != 'enable_translator_indent':
            return None

        # Wrong syntax
        if view.score_selector(view.sel()[0].begin(), 'source.focus') <= 0:
            return False

        # Wrong operator
        if operator == sublime.OP_EQUAL:
            direction = (True == operand)
        elif operator == sublime.OP_NOT_EQUAL:
            direction = (False == operand)
        else:
            return None

        # Loop through the selections and store 1 for a match or 0 for
        # non-matches.
        match_list = []
        self.compute_disable_string()
        for r in view.sel():
            if self.check_selection(view, r):
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

    def check_selection(self, view, selection):
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


class InMethodDocCommand(sublime_plugin.EventListener):
    """
    on_query_context command for the in_method_doc context for focus and fs
    syntaxes.
    """

    def on_query_context(self, view, key, operator, operand, match_all):
        # Wrong key
        if key != IN_METHOD_DOC_KEY:
            return None

        # Wrong syntax
        if view.score_selector(view.sel()[0].begin(),
                               'source.focus, source.fs') <= 0:
            return None

        print('querying context for InMethodDoc')
        return boolean_query_context_per_selection(
            view, operator, operand, match_all, self.check_selection)

    def check_selection(self, view, selection):
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


class FocusExecWrapperCommand(sublime_plugin.WindowCommand):

    def run(self, exec_cmd='exec', ring='file', **kwargs):
        _ring = None
        if ring == 'file':
            # Determine the ring object based on the active view
            logger.warning('ring option (%s) not yet supported', ring)
        elif ring == 'choose':
            # Determine the ring by picking one from a quick panel
            logger.warning('ring option (%s) not yet supported', ring)
        elif ring == 'default':
            # Get the default ring from the settings
            logger.warning('ring option (%s) not yet supported', ring)
        else:
            logger.warning('ring option (%s) not supported', ring)
            return

        self.replace_variables_and_run(exec_cmd, _ring, kwargs)

    def replace_variables_and_run(self, exec_cmd, ring, kwargs):
        new_kwargs = dict()
        for k, v in kwargs:
            if isinstance(v, str):
                v = v.replace('$ring_path', ring.path)
            new_kwargs[k] = v

        try:
            path = new_kwargs['path']
            path += ';' + ring.system_path
        except KeyError:
            path = ring.system_path
        finally:
            new_kwargs['path'] = path

        self.window.run_command(exec_cmd, new_kwargs)


class CreateFileInRingCommand(sublime_plugin.ApplicationCommand):
    """
    Creates a file in the ring represented by ring_path with the given
    contents and file_name, then translates that file if it is translateable.
    if package_path is specified, the resource with that name is loaded and
    used.
    """

    def run(self, ring_path, application=None, package_path=None,
            contents=None, file_name=None):

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
                print(contents)
                contents = contents.replace('\r\n', '\n').replace('\r', '\n')
                print(contents)
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

        file_path = ring.create_file_in_ring(application, file_name, contents)
        if not file_path:
            logger.error('file: %s could not be created in ring: %s',
                         file_name, ring)
            return

        ring_file = get_mt_ring_file(file_path)
        if ring_file.is_translatable():
            ring_file.translate(separate_process=False)
            if not os.path.isfile(get_translated_path(file_path)):
                logger.error('translated file could not be found for file: %s',
                             file_path)
