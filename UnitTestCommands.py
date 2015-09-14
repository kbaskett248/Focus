import logging
import os
import re
import tempfile

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

import sublime
import sublime_plugin

from .classes.ring_files import InvalidFileFormat
from .classes.views import ViewTypeException
from .tools.classes import get_view, get_ring_file, is_focus_file
from .tools.focus import TRANSLATOR_SEPARATOR, get_translated_path
from .tools.sublime import display_in_output_panel, display_in_new_view
from .tools.general import read_file


class Subroutine(object):
    """Represents a subroutine containing unit tests"""

    MatTemplate = ('{{":Code {subroutine}"}}'
                   '@CallSub(UnitTestTemplate_LogResults),')

    def __init__(self, subroutine_name, unit_test_text):
        super(Subroutine, self).__init__()
        self.subroutine_name = subroutine_name
        # List of strings extracted from documentation
        self.unit_test_text = unit_test_text

        self.unit_tests = []
        self.errors = []

        for t in unit_test_text:
            try:
                self.unit_tests.append(UnitTest(subroutine_name, t))
            except IncompleteUnitTestException as e:
                self.errors.append(e)

    def format_for_unit_test(self):
        text = self.MatTemplate.format(subroutine=self.subroutine_name)
        for t in self.unit_tests:
            text += '\n' + t.format_for_unit_test()
        for e in self.errors:
            text += '\n' + e.format_for_unit_test()

        return text


class UnitTest(object):
    """Object to represent an M-AT Unit Test."""

    TestNameMatcher = re.compile(r"// *:Test *(.+)")
    InputMatcher = re.compile(r"// *Input *(.+)", re.IGNORECASE)
    OutputMatcher = re.compile(r"// *Output *(.+)", re.IGNORECASE)
    SetupMatcher = re.compile(r"// *Setup *(.+)", re.IGNORECASE)
    CleanupMatcher = re.compile(r"// *Cleanup *(.+)", re.IGNORECASE)
    CompareMatcher = re.compile(r"// *Compare *(.+)", re.IGNORECASE)

    # MatTemplate = ('{setup},{{"{name}",{input}^I,{output},'
    #                '[@MT^T]I@CallSub({subroutine_name}),@MT-T,{compare}}}'
    #                '@CallSub(UnitTestTemplate_FormatResults),{cleanup},')

    MatTemplate = ('{{"{name}"}}{setup},{{"{name}",{input},{output}}}'
                   '[@{{,@MT,|1@CallSub({subroutine_name}),@MT}}@JV'
                   '@{{|0,|1,|2,|4,@{{|5,|3}}@-,{compare}}}'
                   '@CallSub(UnitTestTemplate_FormatResults)]$2[{cleanup}],')
    CompareTemplate = (
        '@{{|0,|1,|4,@CallSub(UnitTestTemplate_GetLogMessages)}}{compare}')

    def __init__(self, subroutine_name, test):
        super(UnitTest, self).__init__()
        self.subroutine_name = subroutine_name
        self.text = test

        match = self.TestNameMatcher.match(test)
        if match is None:
            raise IncompleteUnitTestException(subroutine_name, 'UNKNOWN',
                                              "Missing name")
        else:
            self.name = match.group(1)

        self.input = None
        self.output = None
        self.setup = None
        self.cleanup = None
        self.compare = None

        for l in test.split('\n'):
            if self.input is None:
                match = self.InputMatcher.match(l)
                if match is not None:
                    self.input = match.group(1)
                    continue

            if self.output is None:
                match = self.OutputMatcher.match(l)
                if match is not None:
                    self.output = match.group(1)
                    if self.output == 'False':
                        self.output = '"False"'
                    elif self.output == 'True':
                        self.output = '"True"'
                    continue

            if self.setup is None:
                match = self.SetupMatcher.match(l)
                if match is not None:
                    self.setup = match.group(1)
                    continue

            if self.cleanup is None:
                match = self.CleanupMatcher.match(l)
                if match is not None:
                    self.cleanup = match.group(1)
                    continue

            if self.compare is None:
                match = self.CompareMatcher.match(l)
                if match is not None:
                    self.compare = match.group(1)
                    continue

        if self.input is None:
            raise IncompleteUnitTestException(subroutine_name, self.name,
                                              "Missing input")
        if (self.output is None) and (self.compare is None):
            raise IncompleteUnitTestException(subroutine_name, self.name,
                                              "Missing output")
        if self.setup is None:
            self.setup = '""'
        if self.cleanup is None:
            self.cleanup = '""'
        if self.compare is None:
            self.compare = '""'
        else:
            self.compare = self.CompareTemplate.format(compare=self.compare)

    def str(self):
        return "Test: {0}\n  Input: {1}\n  Output {2}".format(
            self.name, self.input, self.output)

    def format_for_unit_test(self):
        return self.MatTemplate.format(**self.__dict__)


class IncompleteUnitTestException(Exception):
    """Exception thrown if the unit test is incomplete. For example, if it is
    missing its input or output."""

    DescriptionTemplate = 'Incomplete unit test: {0} - {1}; Problem: {2}'
    MatTemplate = ('{{"     Unit Test: {unit_test_name} - Incomplete",'
                   '"          Problem:             {problem}",""}}'
                   '@CallSub(UnitTestTemplate_LogResults),')

    def __init__(self, subroutine_name, unit_test_name, problem):
        super(IncompleteUnitTestException, self).__init__()
        self.subroutine_name = subroutine_name
        self.unit_test_name = unit_test_name
        self.problem = problem
        self.description = self.DescriptionTemplate.format(subroutine_name,
                                                           unit_test_name,
                                                           problem)

    def format_for_unit_test(self):
        return self.MatTemplate.format(unit_test_name=self.unit_test_name,
                                       problem=self.problem)


class UnitTestCommand(sublime_plugin.TextCommand):
    """
    Parent class for TextCommands that rely on the file being a Ring File.

    """

    @property
    def mt_ring_file(self):
        """Returns a reference to the command's ring file."""
        return get_ring_file(self.file_name)

    @property
    def file_name(self):
        """Returns the filename of the file associated with the command."""
        return self.view.file_name()

    @property
    def mt_view(self):
        return get_view(self.view)

    def is_visible(self):
        try:
            if (self.mt_view is not None) and (self.mt_ring_file is not None):
                return True
        except ViewTypeException:
            return False
        except InvalidFileFormat:
            return False
        else:
            return False

    def is_enabled(self):
        return self.is_visible()


class FocusUnitTestCommand(UnitTestCommand):
    """
    Parent class for TextCommands that rely on the file being a Ring File.

    """

    @property
    def mt_focus_file(self):
        """Returns a reference to the command's ring file."""
        return self.mt_ring_file

    def is_visible(self):
        return (super(UnitTestCommand, self).is_visible() and
                is_focus_file(self.mt_ring_file))

    def is_enabled(self):
        return self.is_visible()


class UnitTestFocusFileCommand(FocusUnitTestCommand):

    MainTemplate = TRANSLATOR_SEPARATOR + """
#Magic
:Code Main
//:Doc Purpose
//     Runs each unit test
//:Doc Arguments
//     None
//:Doc Local Variables
//     None
//:Doc Returns
//     None
0@PutLocal(UnitTestTemplate_NumPassed)@PutLocal(UnitTestTemplate_NumFailed),
{tests}
{{"{file_name}","{results_file}"}}@CallSub(UnitTestTemplate_WriteResults),
"";
"""

    UnitTestLogTemplate = '[{message}@CallSub(UnitTestTemplate_LogMessage)]'
    LogMessageMatcher = re.compile(r" *// *Unit Test Log: *(.+)",
                                   re.IGNORECASE)

    def run(self, edit, display_unit_test=False):
        self.output_panel = display_in_output_panel(
            sublime.active_window(), 'focus_unit_test_results',
            text='Building Unit Test file for %s\n\n' % self.file_name)
        self.output_panel.set_syntax_file(
            'Packages/Focus/Focus Unit Test Results.hidden-tmLanguage')
        results_file_object = tempfile.NamedTemporaryFile(suffix='.txt',
                                                          mode='w',
                                                          delete=False)
        with results_file_object as f:
            f.write("testing")
        file_contents = self.build_unit_test_file_contents(
            results_file_object.name)
        unit_test_file_name = self.write_to_unit_test_file(file_contents)
        self.output_panel.run_command(
            'append',
            {'characters': 'Unit Test file: %s\n\n' % unit_test_file_name,
             'force': True})
        sublime.set_timeout_async(
            lambda: self.run_async(unit_test_file_name,
                                   results_file_object.name,
                                   display_unit_test), 0)

    def run_async(self, unit_test_file_name, results_file_name, display_unit_test):
        sublime.run_command('run_unit_test',
                            {'unit_test_file_name': unit_test_file_name,
                             'results_file_name': results_file_name,
                             'display_unit_test': display_unit_test,
                             # 'output_panel': self.output_panel
                             })

    def build_unit_test_file_contents(self, results_file):
        file_contents = sublime.load_resource(
            'Packages/Focus/resources/Unit Test Template.focus')
        file_contents += self.build_main_code_member(results_file)
        file_contents += os.linesep + self.read_and_filter_view()
        return file_contents

    def read_and_filter_view(self):
        lines = []

        line_matcher = re.compile(r"(\s*)(.+)")

        include_lines = False
        processing_magic = False
        processing_alias = False
        alias_lines = []
        include_alias = False

        for l in self.mt_view.get_lines_iterator():
            match = line_matcher.match(l)
            if match is None:
                lines.append(l)
                continue
            else:
                content = match.group(2)

            if content.startswith('#'):
                if processing_alias:
                    if include_alias and alias_lines:
                        lines.extend(alias_lines)
                    alias_lines = []
                    include_alias = False

                processing_alias = processing_magic = False

                if content.startswith('#Include'):
                    include_lines = True
                elif content.startswith('#ImportExport'):
                    include_lines = True
                elif content.startswith('#Locals'):
                    include_lines = True
                elif content.startswith('#Lock'):
                    include_lines = True
                elif content.startswith('#DataDef'):
                    include_lines = True
                elif content.startswith('#Alias'):
                    processing_alias = True
                    lines.append(l)
                    continue
                elif content.startswith('#Magic'):
                    processing_magic = True
                    lines.append(l)
                    continue
                else:
                    include_lines = False
                    continue

            if processing_alias:
                if content.startswith(':Alias'):
                    if include_alias and alias_lines:
                        lines.extend(alias_lines)
                    alias_lines = []
                    include_alias = False
                elif content.startswith('Scope'):
                    if 'Local' in content:
                        include_alias = True

                alias_lines.append(l)
                continue

            if processing_magic:
                if content.startswith(':EntryPoint'):
                    include_lines = False
                elif content.startswith(':'):
                    if content.startswith(':Code') and ('Main' in content):
                        include_lines = False
                    else:
                        include_lines = True
                else:
                    match = self.LogMessageMatcher.match(l)
                    if match is not None:
                        l = self.UnitTestLogTemplate.format(
                            message=match.group(1))

            if include_lines:
                lines.append(l)

        return os.linesep.join(lines)

    def build_main_code_member(self, results_file):
        test_lines = []
        for region in self.view.find_all(r"//:Doc Unit Test"):
            cb = self.mt_view.get_codeblock(region.begin())
            if cb is None:
                continue
            else:
                documentation = cb.doc

                if documentation.doc_regions['Unit Test'].unit_tests:
                    subroutine = Subroutine(
                        cb.codeblock_name,
                        documentation.doc_regions['Unit Test'].unit_tests)

                    test_lines.append(subroutine.format_for_unit_test())

        contents = self.MainTemplate.format(file_name=self.file_name,
                                            tests="\n".join(test_lines),
                                            results_file=results_file)

        contents = contents.replace('\n', os.linesep)
        return contents

    def write_to_unit_test_file(self, contents):
        ring = self.mt_ring_file.ring
        path, name = os.path.split(self.file_name)
        first_folder = os.path.basename(path)
        match = re.match(r"(.+?)(\.[A-Z])?\.focus", name)

        unit_test_file_name = os.path.join(
            ring.pgm_cache_path,
            'PgmSource',
            first_folder,
            '{0}.UnitTest.P.focus'.format(match.group(1)))
        with open(unit_test_file_name, 'w', newline='') as f:
            f.write(contents)
        return unit_test_file_name


class RunUnitTestCommand(sublime_plugin.ApplicationCommand):
    """
    Runs the Unit Test file specified in the argument and writes the results to
    the results file. Then it opens them.
    """

    def run(self, unit_test_file_name, results_file_name,
            display_unit_test=False):
        logger.debug("unit_test_file_name = %s", unit_test_file_name)
        logger.debug("results_file_name = %s", results_file_name)
        unit_test_file = get_ring_file(unit_test_file_name)
        sublime.status_message('Translating Unit Test')
        if not unit_test_file.translate(separate_process=False):
            logger.warning('Translating Unit Test file failed')
            sublime.status_message('Translating Unit Test file failed')
        else:
            sublime.status_message('Running Unit Test')
            unit_test_file.run(separate_process=False)

            # text = '\n'.join(read_file(results_file_name, False))
            # output_panel.run_command(
            #     'append', {'characters': text, 'force': True})
            v = display_in_output_panel(sublime.active_window(),
                                        'focus_unit_test_results',
                                        file_name=results_file_name)
            v.set_syntax_file('Packages/Focus/'
                              'Focus Unit Test Results.hidden-tmLanguage')
            v.run_command('fold_by_level', {'level': 2})
            v.show(0)
            # v = display_in_new_view(sublime.active_window(),
            #                         file_name=results_file_name)
            # v.set_syntax_file(
            #     'Packages/Focus/Focus Unit Test Results.hidden-tmLanguage')
            # v.run_command('fold_by_level', {'level': 2})
            # v.show(0)

        if display_unit_test:
            v = sublime.active_window().open_file(unit_test_file_name)
            v.set_syntax_file(
                'Packages/Focus/focus.tmLanguage')
        else:
            os.remove(unit_test_file_name)

        os.remove(results_file_name)
        trans_path = get_translated_path(unit_test_file_name)
        if trans_path:
            logger.debug("trans_path = %s", trans_path)
            os.remove(trans_path)
