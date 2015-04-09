from collections import deque
import os
import re

import logging
logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

import sublime
import sublime_plugin

from .classes.command_templates import RingViewCommand, FocusViewCommand
from .tools.classes import get_view, is_focus_view, is_fs_view
from .tools.snippets import insert_compound_snippet
from .tools.focus import TRANSLATOR_SEPARATOR
from .tools.settings import get_disable_translator_indent


IN_METHOD_DOC_KEY = 'in_method_doc'
ENABLE_TRANSLATOR_INDENT_KEY = 'enable_translator_indent'

ATTRIBUTE_PATTERN = re.compile(r"(\s*:?\w+)(\s*)(.*)")
INDENTATION_PATTERN = re.compile(r"(^.+//(( *$)| *))|"
                                 r"( +$)|([\[\{\( ])|([\]\}\);])")


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

    logger.debug("direction = ", direction)

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
            return False

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
        st = get_disable_translator_indent()
        if not st:
            self.disable_for_certain_strings = False
            return
        elif isinstance(st, list) and st:
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
            return False

        print('querying context for InMethodDoc')

        args = list(args)
        args.append(self.check_selection_in_method_doc)
        print(args)
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

        ring_view = get_view(view)
        if ring_view is None:
            return False

        print('still checking 2')

        cb = ring_view.get_codeblock(points[0])
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
        logger.debug('Running Focus smart indent')
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
                print(match.groups())
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


class CommentHomeCommand(sublime_plugin.TextCommand):
    """
    When the home key is pressed on a comment-only line, this will imitate
    the behavior of pressing the home key on an indented line. The cursor
    will first move to the beginning of the comment (after the // and any
    indentation). If the cursor is already at that position, or the home
    key is pressed a second time, the cursor will move to the beginning of
    the line. There is also support for shift + home to highlight the
    comment.
    """

    CommentPattern = re.compile(r'(\s*//\s*)[^\s].*')

    def run(self, edit, extend=False):
        regions_to_add = []
        regions_to_remove = []
        view = self.view
        sel = view.sel()
        for r in sel:
            point = r.begin()
            col = view.rowcol(point)[1]
            line = view.line(point)
            line_string = view.substr(line)
            line_pre_string = view.substr(sublime.Region(line.begin(), point))

            move_forward = start = None
            if (col == 0) and self.CommentPattern.match(line_string):
                move_forward = len(
                    self.CommentPattern.match(line_string).group(1)
                    )
                start = point
            elif self.CommentPattern.match(line_pre_string):
                move_forward = len(
                    self.CommentPattern.match(line_pre_string).group(1)
                    )
                start = line.begin()
            elif (line_pre_string.strip() == '//'):
                move_forward = 0
                start = line.begin()

            if start is not None:
                regions_to_remove.append(r)
                end = start + move_forward
                if extend:
                    begin = r.a
                    if r.b == end:
                        end = r.a
                else:
                    begin = end
                regions_to_add.append(sublime.Region(begin, end))

        for r in regions_to_remove:
            sel.subtract(r)
        for r in regions_to_add:
            sel.add(r)


class GenerateDocCommand(FocusViewCommand):
    """Command for generating documentation for a code member."""

    def run(self, edit, update_only=False, use_snippets=False):
        """
        Parse and update existing doc sections, and add new ones if needed.
        """
        codeblock = self.focus_view.get_codeblock(self.view.sel()[0].begin())
        contents = codeblock.doc.update(update_only, use_snippets)
        if use_snippets:
            # Move to the end of the code header
            self.view.sel().clear()
            self.view.sel().add(
                sublime.Region(codeblock.header_region.end(),
                               codeblock.documentation_region.end()))

            contents = '\n' + contents
            if codeblock.documentation_region.empty():
                contents += '\n'

            self.view.run_command("insert_snippet", {"contents": contents})
        else:
            if (codeblock.documentation_region.empty()):
                contents += '\n'

            self.view.replace(edit, codeblock.documentation_region, contents)

    def is_enabled(self):
        if super(GenerateDocCommand, self).is_enabled():
            return (self.view.score_selector(
                self.view.sel()[0].begin(), 'meta.subroutine.fs') > 0)
        else:
            return False


class FoldSubroutineCommand(RingViewCommand):
    """Command to fold subroutines."""

    def run(self, edit, all_regions=False):
        """Folds regions for all or selected subroutines.

        Keyword arguments:
        all_regions - If True, all regions other than the currently selected
                      one are folded.

        """
        fold_regions = self.get_regions(all_regions)
        self.view.fold(fold_regions)

    def get_regions(self, all_regions):
        """Returns a list of regions to fold."""
        view = self.view
        sel = self.view.sel()
        fold_regions = list()
        if all_regions:
            for reg in view.find_by_selector(
                    'meta.subroutine.header.fs, meta.list.header.fs'):
                r = self.get_region(reg)
                for s in sel:
                    if r.intersects(s):
                        break
                else:
                    fold_regions.append(self.get_region(reg))
        else:
            for sel in view.sel():
                if view.score_selector(sel.begin(),
                                       'meta.subroutine.fs, meta.list.fs') > 0:
                    fold_regions.append(self.get_region(sel))
        return fold_regions

    def get_region(self, region):
        """Expands the selected region to include the entire subroutine."""
        member_region = self.ring_view.get_member_region(region.begin())
        header_line = self.view.line(member_region.begin())
        r = sublime.Region(header_line.end(),
                           member_region.end())
        return r

    def is_enabled(self, all_regions=False):
        """
        Returns True if folding all regions or if a subroutine is selected.
        """
        e = False
        if super(FoldSubroutineCommand, self).is_enabled():
            if all_regions:
                e = True
            else:
                view = self.view
                for sel in view.sel():
                    if view.score_selector(
                            sel.begin(),
                            'meta.subroutine.fs, meta.list.fs') > 0:
                        e = True
                        break
        return e

    def is_visible(self, all_regions=False):
        result = False
        if super(FoldSubroutineCommand, self).is_visible():
            v = self.ring_view
            if is_focus_view(v):
                result = True
            elif is_fs_view(v):
                result = True

        return result

    def description(self, all_regions=False):
        """Returns the description for the command."""
        desc = ''
        if all_regions:
            desc = 'Fold all subroutines'
        else:
            view = self.view
            count = 0
            for sel in view.sel():
                if view.score_selector(sel.begin(),
                                       'meta.subroutine.fs, meta.list.fs') > 0:
                    count += 1
            if (count <= 1):
                desc = 'Fold selected subroutine'
            else:
                desc = 'Fold selected subroutines'
        return desc


class InsertBreakCommand(FocusViewCommand):
    """Command to insert a break at the current insertion points."""

    Counter = 0

    def run(self, edit):
        """Inserts a break at the current insertion points."""
        view = self.view

        settings = sublime.load_settings('MT-Focus.sublime-settings')
        break_label = settings.get('break_label', '{counter}')

        filename = view.name()
        if (filename is None) or (filename == ""):
            filename = os.path.basename(view.file_name())
        if filename.endswith('.focus'):
            filename = filename[0:-6]

        object_name = ' '
        if '.' in filename:
            object_name = filename.split('.')[0] + ' '

        region_snippets = []

        user_selection = view.sel()
        for sel in user_selection:
            row, col = view.rowcol(sel.begin())
            row += 1
            col += 1

            cb = self.focus_view.get_codeblock(sel.begin())
            if cb:
                subroutine = cb.codeblock_name + ' '
            else:
                subroutine = ' '

            label = break_label.format(file=filename,
                                       object=object_name,
                                       subroutine=subroutine,
                                       row=row,
                                       col=col,
                                       counter=self.get_counter())

            region_snippets.append((sel, '@Break(%s)' % label))

        insert_compound_snippet(view, edit, user_selection, region_snippets)

    def get_counter(self):
        InsertBreakCommand.Counter += 1
        return InsertBreakCommand.Counter


class ListEntitiesCommand(RingViewCommand):
    """
    Lists the subroutines contained in the current file in an output panel.
    """

    def run(self, edit, entity_id=None):
        """
        Lists the subroutines contained in the current file in an output panel.
        """
        settings = sublime.load_settings('MT-Focus.sublime-settings')
        list_entities = settings.get('list_entity_commands', {})
        if not list_entities:
            sublime.status_message("No list entities defined")
            return

        if entity_id is not None:
            entity = self.get_entity_definition(entity_id)
            if entity is None:
                sublime.status_message('No list entity defined for ' +
                                       entity_id)
            else:
                entities = self.gather_entities(entity)

                if entities:
                    window = self.view.window()
                    file_name = self.view.name()
                    if file_name == '' or file_name is None:
                        file_name = self.view.file_name()
                    output_text = [file_name + ':']
                    try:
                        output_text[0] += '  ' + entity['list_entity_name']
                    except KeyError:
                        pass

                    output_text[0] += ' ({0})'.format(len(entities))
                    output_text.extend(['\t' + name for name in entities])

                    output_panel = window.create_output_panel(
                        'list_of_entities')
                    output_panel.assign_syntax(
                        "Packages/Text/Plain text.tmLanguage")
                    output_panel.insert(edit,
                                        output_panel.size(),
                                        '\n'.join(output_text))
                    window.run_command('show_panel',
                                       {'panel': 'output.list_of_entities'})
                else:
                    try:
                        sublime.status_message(
                            'No ' + entity['list_entity_name'] +
                            ' defined in file')
                    except KeyError:
                        sublime.status_message(
                            'Specified entity not defined in file')

    def gather_entities(self, entity):
        view = self.view
        try:
            scope = entity['list_entity_scope']
        except KeyError:
            entities = []
        else:
            entities = [view.substr(sel) for sel in
                        view.find_by_selector(scope)]

        try:
            regex = entity['list_entity_regex']
        except KeyError:
            pass
        else:
            matcher = re.compile(regex)
            try:
                group = entity['list_entity_group']
            except KeyError:
                group = 0

            new_entities = []
            for item in entities:
                m = matcher.match(item)
                if m is not None:
                    new_entities.append(m.group(group))
            entities = new_entities

        try:
            if entity['list_entity_unduplicate']:
                entities = list(set(entities))
        except KeyError:
            pass

        try:
            if entity['list_entity_sort']:
                entities.sort()
        except KeyError:
            pass

        return entities

    def get_entity_definition(self, entity_id):
        settings = sublime.load_settings('MT-Focus.sublime-settings')
        list_entities = settings.get('list_entity_commands', {})
        try:
            entity = list_entities[entity_id]
        except KeyError:
            entity = None

        return entity

    def is_visible(self, entity_id=None):
        result = False
        if super(ListEntitiesCommand, self).is_visible():
            v = self.ring_view
            if is_focus_view(v):
                result = True
            elif is_fs_view(v):
                result = True

        if result and (entity_id is not None):
            entity = self.get_entity_definition(entity_id)
            if entity is None:
                result = False
            else:
                try:
                    scope = entity['list_entity_file_scope']
                except KeyError:
                    pass
                else:
                    if self.view.score_selector(
                            self.view.sel()[0].begin(), scope) <= 0:
                        result = False

        return result


class DocumentAllLocalsCommand(FocusViewCommand):
    """
    Command to find all undocumented locals and add them to the #Locals
    section.

    """

    def run(self, edit, use_snippets=True):
        """Finds undocumented locals and adds them to the #Locals section.

        Keyword arguments:
        use_snippets - If True, snippets will be used to ease populating the
                       documentation.

        """
        self._snippet_counter = 0

        used_locals = self.focus_view.get_locals(only_undocumented=True)
        create_locals_section = False
        indent = '  '
        if used_locals:
            try:
                locals_section = self.focus_view.get_translator_sections(
                    'Locals')[-1][0]
                locals_section = sublime.Region(locals_section[0],
                                                locals_section[1])
            except IndexError:
                start = self.focus_view.get_translator_sections(
                    'Magic')[0].begin()-1
                locals_section = sublime.Region(start, start)
                create_locals_section = True

            lines_to_add = list()

            for l in used_locals:
                line = '%s:Name                           %s' % (indent, l)
                if use_snippets:
                    line += '\n{0}// ${1}'.format(indent, self.snippet_counter)
                lines_to_add.append(line)

            content = '\n\n'.join(lines_to_add)

            if create_locals_section:
                content = '\n{0}\n#Locals\n{1}\n\n'.format(
                    TRANSLATOR_SEPARATOR, content)
            else:
                content = '\n\n' + content + '\n\n'

            logger.debug(content)

            if use_snippets:
                selection = self.view.sel()
                selection.clear()
                selection.add(sublime.Region(locals_section.end(),
                                             locals_section.end()))
                self.view.run_command("insert_snippet", {"contents": content})

            else:
                self.view.insert(edit, locals_section.end(), content)

    @property
    def snippet_counter(self):
        self._snippet_counter += 1
        return self._snippet_counter
