import os
import re

import sublime
import sublime_plugin

import Focus
from .src.Managers.RingFileManager import RingFileManager
from .src.FocusFile import FocusFile
from .src import FocusLanguage


FILE_MANAGER = RingFileManager.getInstance()

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class FocusCommand(sublime_plugin.TextCommand):
    """
    Parent class for all the commands that rely on the file being a Focus File
    """

    def __init__(self, view):
        super(FocusCommand, self).__init__(view)
        self._focus_file = None
        self._initialized = False

    @property
    def focus_file(self):
        if (not self._initialized):
            self._focus_file = FILE_MANAGER.get_ring_file(
                self.view, allowed_file_types=[FocusFile])
            self._initialized = True
        return self._focus_file

    @property
    def filename(self):
        """Returns the filename of the file associated with the command."""
        return self.focus_file.filename

    @property
    def ring_object(self):
        """Returns a reference to the ring file's ring object."""
        return self.focus_file.ring_object

    def is_visible(self):
        return (self.focus_file is not None)

    def is_enabled(self):
        return self.is_visible()


class FormatCommand(FocusCommand):
    """Formats a Focus file"""

    def run(self, edit):
        """Formats the focus file."""
        self.focus_file.format()


class TranslatorIndentCommand(sublime_plugin.TextCommand):
    """
    Command to indent the right side of translator sections to the correct
    point.
    """

    def run(self, edit):
        """Indents the right side of translator sections to 34 spaces."""
        pattern = re.compile(r"(\s*[:#]?\w+)(\s*)(.*)")
        for r in self.view.sel():
            point = r.begin()
            row, col = self.view.rowcol(point)
            line = self.view.line(point)
            if point == line.end():
                s = (34 - col) * ' '
                self.view.insert(edit, point, s)
            else:
                result = pattern.match(self.view.substr(line))
                if (result):
                    if (len(result.group(1)) < 34):
                        s = (34 - (len(result.group(1)))) * " "
                        s = result.group(1) + s
                        point = self.view.text_point(
                            row, (len(result.group(1)) + len(result.group(2))))
                        r = sublime.Region(line.begin(), point)
                        self.view.replace(edit, r, s)
                    else:
                        s = result.group(1) + "  "
                        point = self.view.text_point(
                            row, (len(result.group(1)) + len(result.group(2))))
                        r = sublime.Region(line.begin(), point)
                        self.view.replace(edit, r, s)


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

    CommentPattern = re.compile(r'(//\s*)[^\s].*')

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


class GenerateDocCommand(FocusCommand):
    """Command for generating documentation for a code member."""

    def run(self, edit, update_only=False, use_snippets=False):
        """
        Parse and update existing doc sections, and add new ones if needed.
        """
        codeblock = self.focus_file.get_codeblock(self.view)
        contents = codeblock.update_documentation(update_only, use_snippets)
        if use_snippets:
            # Move to the end of the code header
            self.view.run_command('move_to', {'to': 'hardbol'})
            while (
                    (not self.view.sel()[0].intersects(
                        codeblock.header_region)
                     ) and
                    (self.view.sel()[0].begin() >
                        codeblock.header_region.begin()
                     )
                    ):
                self.view.run_command(
                    'move', {'by': 'lines', 'forward': False}
                    )
            self.view.run_command('move_to', {'to': 'hardeol'})

            # If there was no doc, we need to add a new line for the doc
            if (codeblock.documentation_region.empty()):
                contents = '\n' + contents
            # Otherwise, we need to remove the old doc and move down to the
            # empty line
            else:
                # Remove the old doc
                self.view.replace(edit, codeblock.documentation_region, '')
                self.view.run_command('move', {'by': 'lines', 'forward': True})

            self.view.run_command("insert_snippet", {"contents": contents})
        else:
            if (codeblock.documentation_region.empty()):
                contents += '\n'
            self.view.replace(edit, codeblock.documentation_region, contents)

    def is_enabled(self):
        return (Focus.score_selector(
            self.view, self.view.sel()[0].begin(), 'subroutine'
            ) > 0)


class DocumentLocalsCommand(FocusCommand):
    """Command to find all undocumented locals and add them to the #Locals section."""

    def run(self, edit, use_snippets = True):
        """Finds undocumented locals and adds them to the #Locals section.

        Keyword arguments:
        use_snippets - If True, snippets will be used to ease populating the 
                       documentation.

        """
        self._snippet_counter = 0
        used_locals = self.focus_file.get_locals(self.view, 
                                                 only_undocumented = True)
        create_locals_section = False
        indent = ''
        if used_locals:
            try:
                locals_section = self.focus_file.get_translator_regions(self.view, '#Locals')[0]
            except IndexError:
                start = self.focus_file.get_translator_regions(self.view, '#Magic')[0].begin()-1
                locals_section = sublime.Region(start, start)
                create_locals_section = True
                if use_snippets:
                    indent = '  '

            lines_to_add = list()

            for l in used_locals:
                line = '%s:Name                           %s' % (indent, l)
                if use_snippets:
                    line += '\n{0}// ${1}'.format(indent, self.snippet_counter)
                lines_to_add.append(line)


            content = '\n\n'.join(lines_to_add)
            if create_locals_section:
                content = '\n{0}\n#Locals\n{1}\n\n'.format(FocusLanguage.TRANSLATOR_SEPARATOR,
                                                           content)
            else:
                content = '\n\n' + content

            logger.debug(content)

            if use_snippets:
                selection = self.view.sel()
                selection.clear()
                selection.add(sublime.Region(locals_section.end(), locals_section.end()))
                self.view.run_command("insert_snippet", {"contents": content})

            else:
                self.view.insert(edit, locals_section.end(), content)

    @property
    def snippet_counter(self):
        self._snippet_counter += 1
        return self._snippet_counter
    
    
class FoldSubroutineCommand(FocusCommand):
    """Command to fold subroutines."""

    def run(self, edit, all_regions = False):
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
            for reg in Focus.find_by_selector(view, 'subroutine_header'):
                r = self.get_region(reg)
                for s in sel:
                    if r.intersects(s):
                        break
                else:
                    fold_regions.append(self.get_region(reg))
        else:
            for sel in view.sel():
                if (Focus.score_selector(view, sel.begin(), 'subroutine') > 0):
                    fold_regions.append(self.get_region(sel))
        return fold_regions

    def get_region(self, region):
        """Expands the selected region to include the entire subroutine."""
        codeblock = self.focus_file.get_codeblock(self.view, region)
        r = sublime.Region(codeblock.header_region.end(), 
                           codeblock.codeblock_region.end())
        return r

    def is_enabled(self, all_regions = False):
        """Returns True if folding all regions or if a subroutine is selected."""
        e = False
        if super(FoldSubroutineCommand, self).is_enabled():
            if all_regions:
                e = True
            else:
                view = self.view
                for sel in view.sel():
                    if (Focus.score_selector(view, sel.begin(), 'subroutine') > 0):
                        e = True
                        break
        return e

    def description(self, all_regions = False):
        """Returns the description for the command."""
        desc = ''
        if all_regions:
            desc = 'Fold all subroutines'
        else:
            view = self.view
            count = 0
            for sel in view.sel():
                if (Focus.score_selector(view, sel.begin(), 'subroutine') > 0):
                    count += 1
            if (count <= 1):
                desc = 'Fold selected subroutine'
            else:
                desc = 'Fold selected subroutines'
        return desc

# class AtCodeCheckerCommand(FocusCommand):
#     """Command to run the At Code Checker."""

#     def run(self, edit):
#         """Runs the AT Code Checker and outputs its results."""
#         path = os.path.join(sublime.packages_path(), 'SublimeLinter-contrib-at_code_checker', 'at_code_checker', 'at_code_checker.exe')
#         filename = self.view.file_name()
#         working_directory = os.path.dirname(filename)
#         cmd = '%s "%s"' % (path, filename)
#         logger.debug(cmd)
#         window = self.view.window()
#         output_panel = window.create_output_panel('at_code_checker')
#         window.run_command('show_panel', {'panel': 'output.at_code_checker'})
#         AtCodeCheckerCommand.RunToConsole(cmd, edit, output_panel, current_dir = working_directory)
#         # proc = ''
#         # proc = subprocess.Popen(cmd, cwd=working_directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#         # while proc.poll() is None:
#         #     try:
#         #         data = proc.stdout.readline().decode(encoding='UTF-8')
#         #         output_panel.insert(edit, output_panel.size(), data)
#         #     except:
#         #         # print("process ended...")
#         #         break
#         # logger.info('Code check complete')

#     def RunToConsole(args, edit, output_panel, current_dir = None):
#         """Helper routine to run the AT Code Checker in the background.

#         Keyword arguments:
#         output_panel - The name of the panel to get output.
#         current_dir - The working directory for the command.

#         """
#         sublime.set_timeout_async(lambda: AtCodeCheckerCommand.run_in_background(args, edit, output_panel, current_dir), 0)
        
#     def run_in_background(args, edit, output_panel, current_dir):
#         """Runs the AT Code checker and outputs results to the given output panel.

#         Keyword arguments:
#         output_panel - The name of the panel to get output.
#         current_dir - The working directory for the command.
        
#         """
#         proc = ''
#         if current_dir is None:
#             proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#         else:
#             proc = subprocess.Popen(args, cwd=current_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        
#         while proc.poll() is None:
#             # try:
#             data = proc.stdout.readline().decode(encoding='UTF-8')
#             output_panel.run_command('insert_in_view', {'string': data})
#             # except:
#             #     print("process ended...")
#                 # return;
#         print("process ended...")

class InsertBreakCommand(FocusCommand):
    """Command to insert a break at the current insertion points."""

    def run(self, edit):
        """Inserts a break at the current insertion points."""
        view = self.view
        for sel in view.sel():
            label = view.name()
            if (label is None) or (label == ""):
                label = os.path.basename(view.file_name())
                label = ".".join(label.split(".")[-3:-1])
            scope_name = view.scope_name(sel.begin()).strip()
            if (Focus.score_selector(view, sel.begin(), 'subroutine') > 0):
                cb = self.focus_file.get_codeblock(view, sel)
                label += " " + cb.codeblock_name
            row, col = view.rowcol(sel.begin())
            label += " %s %s" % (row+1, col+1)
            view.replace(edit, sel, "@Break(%s)" % label)

class ListSubroutinesCommand(FocusCommand):
    """Lists the subroutines contained in the current file in an output panel."""
    
    def run(self, edit):
        """Lists the subroutines contained in the current file in an output panel."""
        view = self.view
        subroutine_names = [view.substr(sel) for sel in Focus.find_by_selector(view, 'subroutine_header_name')]
        print(subroutine_names)
        if subroutine_names:
            window = view.window()
            output_text = [view.file_name() + ':']
            output_text.extend(['\t' + name for name in subroutine_names])

            output_panel = window.create_output_panel('subroutine_names')
            output_panel.insert(edit, output_panel.size(), '\n'.join(output_text))
            window.run_command('show_panel', {'panel': 'output.subroutine_names'})

class FocusFileDebugCommand(FocusCommand):
    """Formats a Focus file"""

    def run(self, edit):
        """Formats the focus file."""
        print(self.focus_file.build_translator_tree(self.view))
        
