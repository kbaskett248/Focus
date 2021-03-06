import logging
logger = logging.getLogger(__name__)

import sublime

try:
    from DynamicCompletions import CompletionTrigger, ViewLoader
except ImportError as e:
    logger.error('DynamicCompletions package not installed')
    raise e

from .classes.views import ViewTypeException
from .classes.code_blocks import InvalidCodeBlockError
from .tools.classes import get_view
from .tools.focus import TRANSLATOR_LINE_SPLITTER
from .tools.load_translator_completions import get_translator_completions
from .tools.settings import (
    get_focus_function_argument_type,
    get_completion_trigger_enabled_setting,
    get_completion_source_enabled_setting
)
from .tools.sublime import split_focus_function

from .misc.completion_types import (
    CT_ALIAS,
    CT_FOCUS_LOCAL,
    CT_SUBROUTINE,
    CT_LIST,
    CT_TRANSLATOR,
    CT_SUBROUTINE_LOCAL,

    CT_OBJECT,
    CT_RECORD,
    CT_FILE,
    CT_KEY,
    CT_FIELD,
    # CT_ELEMENT,
    # CT_INDEX,
    # CT_INDEXKEY,
    # CT_LONGLOCK,
)


class FocusFunctionTrigger(CompletionTrigger):
    """Object to check focus functions to return completion types."""

    @classmethod
    def view_scope(cls):
        """
        Return a scope to determine if a CompletionTrigger will be enabled for
        a view.

        """
        return 'source.focus'

    def selection_scope(self):
        """
        Return a scope to determine if a CompletionTrigger will be enabled for
        the current selection.

        """
        return 'meta.function.focus'

    def selection_check(self, prefix, locs):
        """Return a list of completion types for the current locations.

        If no completion types are handled for the current locations by this
        trigger, return an empty list.

        """
        if not get_completion_trigger_enabled_setting('Focus Function'):
            return []

        ring_view = get_view(self.view)
        span, string = ring_view.extract_focus_function(locs[0])
        logger.debug("span=%s, string=%s", span, string)

        if span is not None:
            name, args = split_focus_function(string, span[0])
            logger.debug("name=%s, args=%s", name, args)
            first_arg = next(self.split_args(*args))
            logger.debug("first_arg=%s", first_arg)
            if first_arg[0][0] <= locs[0] <= first_arg[0][1]:
                try:
                    comp = get_focus_function_argument_type(name[1])
                    return [comp]
                except KeyError:
                    pass

        return []

    @staticmethod
    def split_args(range_, value):
        start = range_[0]
        for v in value.split(','):
            yield((start, start + len(v)), v)
            start += len(v) + 1


class AliasTrigger(CompletionTrigger):
    """Object to check focus functions to return completion types."""

    @classmethod
    def view_scope(cls):
        """
        Return a scope to determine if a CompletionTrigger will be enabled for
        a view.

        """
        return 'source.focus'

    def selection_scope(self):
        """
        Return a scope to determine if a CompletionTrigger will be enabled for
        the current selection.

        """
        return 'source.focus - comment'

    def selection_check(self, prefix, locs):
        """
        Return a list of completion types for the current locations.

        If no completion types are handled for the current locations by this
        trigger, return an empty list.

        """
        if ('!DictionarySource' in self.view.file_name()):
            return []
        elif not get_completion_trigger_enabled_setting('Alias'):
            return []

        end = locs[0]
        start = end - 2
        selection = sublime.Region(start, end)
        substring = self.view.substr(selection)

        if substring.startswith('@@'):
            return [CT_ALIAS]

        start = self.view.find_by_class(
            end, False, sublime.CLASS_WORD_START, "@") - 2
        selection = sublime.Region(start, end)
        substring = self.view.substr(selection)

        if substring.startswith('@@'):
            return [CT_ALIAS]

        return []


class TranslatorTrigger(CompletionTrigger):
    """
    Object to check translator keywords and attributes to return completion
    types.
    """

    @classmethod
    def view_scope(cls):
        """
        Return a scope to determine if a CompletionTrigger will be enabled for
        a view.

        """
        return 'source.focus'

    def selection_scope(self):
        """
        Return a scope to determine if a CompletionTrigger will be enabled for
        the current selection.

        """
        return 'meta.translator - meta.keyword.code - meta.keyword.list'

    def selection_check(self, prefix, locs):
        """
        Return a list of completion types for the current locations.

        If no completion types are handled for the current locations by this
        trigger, return an empty list.

        """
        if not get_completion_trigger_enabled_setting('Translator'):
            return []

        preceding_line = sublime.Region(
            self.view.line(locs[0]).begin(), locs[0])
        preceding_line_string = self.view.substr(preceding_line)
        match = TRANSLATOR_LINE_SPLITTER.match(preceding_line_string)

        ring_view = get_view(self.view)
        tree = ring_view.build_translator_tree(locs[0], trim_containers=True)
        logger.debug('tree = %s', tree)

        current_item = tree[-1]
        partial_completions = get_translator_completions()

        for k, v in tree:
            logger.debug('k = %s', k)
            logger.debug('partial_completions = %s', partial_completions)
            try:
                translator = partial_completions[k]
                logger.debug('translator = %s', translator)
                logger.debug('%s %s', k, translator)
            except KeyError:
                if ((k == current_item[0]) and (v == current_item[1])):
                    if ((match is None) or ((match.group('separator') == '')
                                            and (match.group('value') == ''))):
                        return [CT_TRANSLATOR]
                return []
            else:
                try:
                    partial_completions = translator.children
                    logger.debug('partial_completions = %s', partial_completions)
                except AttributeError:
                    return []

        if ((match is None) or ((match.group('separator') == '') and
                                (match.group('value') == ''))):
            return [CT_TRANSLATOR]
        else:
            return translator.completion_types


class VariablesTrigger(CompletionTrigger):
    """Trigger to include subroutine variables."""

    @classmethod
    def view_scope(cls):
        """
        Return a scope to determine if a CompletionTrigger will be enabled for
        a view.

        """
        return 'source.focus'

    def selection_scope(self):
        """
        Return a scope to determine if a CompletionTrigger will be enabled for
        the current selection.

        """
        return 'meta.keyword.code - string'

    def selection_check(self, prefix, locs):
        """
        Return a list of completion types for the current locations.

        If no completion types are handled for the current locations by this
        trigger, return an empty list.

        """
        return [CT_SUBROUTINE_LOCAL]


class AliasViewLoader(ViewLoader):
    """
    Loads aliases defined within a view.
    """

    EmptyReturn = ([], sublime.INHIBIT_EXPLICIT_COMPLETIONS |
                   sublime.INHIBIT_WORD_COMPLETIONS)

    @classmethod
    def completion_types(cls):
        """
        Return a set of completion types that this CompletionLoader can return.

        """
        return [CT_ALIAS]

    @classmethod
    def view_scope(cls):
        """
        Return a scope to determine if the CompletionLoader will be enabled
        for a view.

        """
        return 'source.focus'

    @classmethod
    def view_check(cls, view):
        """
        Returns True if the CompletionLoader should be enabled for the given
        view.

        """
        n = view.file_name()
        if (n is not None) and (n != '') and ('!DictionarySource' in n):
            return False
        return get_completion_source_enabled_setting('Alias', 'View')

    def load_completions(self, **kwargs):
        """Loads the aliases defined within the view."""
        self.completions = set()
        ring_view = get_view(self.view)
        for alias in ring_view.get_defined_aliases():
            alias = '@@' + alias + '()'
            self.completions.add((alias, alias[2:]))


class LocalViewLoader(ViewLoader):
    """
    Loads focus Locals used within a view.
    """

    EmptyReturn = ([], sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    @classmethod
    def completion_types(cls):
        """
        Return a set of completion types that this CompletionLoader can return.

        """
        return [CT_FOCUS_LOCAL]

    @classmethod
    def view_scope(cls):
        """
        Return a scope to determine if the CompletionLoader will be enabled
        for a view.

        """
        return 'source.focus'

    @classmethod
    def view_check(cls, view):
        """
        Returns True if the CompletionLoader should be enabled for the given
        view.

        """
        return get_completion_source_enabled_setting('Local', 'View')

    def load_completions(self, **kwargs):
        """Loads the focus Locals used in the view."""
        ring_view = get_view(self.view)
        self.completions = (ring_view.get_used_locals(for_completions=True) |
                            ring_view.get_defined_locals(for_completions=True))


class SubroutineViewLoader(ViewLoader):
    """
    Loads subroutine names defined within a view.
    """

    EmptyReturn = ([], sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    @classmethod
    def completion_types(cls):
        """
        Return a set of completion types that this CompletionLoader can return.

        """
        return [CT_SUBROUTINE]

    @classmethod
    def view_scope(cls):
        """
        Return a scope to determine if the CompletionLoader will be enabled
        for a view.

        """
        return 'source.focus, source.fs'

    @classmethod
    def view_check(cls, view):
        """
        Returns True if the CompletionLoader should be enabled for the given
        view.

        """
        return get_completion_source_enabled_setting('Subroutine', 'View')

    def load_completions(self, **kwargs):
        """
        Populate self.completions with the completions handled by this
        completer.

        """
        ring_view = get_view(self.view)
        self.completions = ring_view.get_defined_subroutines(
            for_completions=True)


class ListViewLoader(ViewLoader):
    """
    Loads subroutine names defined within a view.
    """

    EmptyReturn = ([], sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    @classmethod
    def completion_types(cls):
        """
        Return a set of completion types that this CompletionLoader can return.

        """
        return [CT_LIST]

    @classmethod
    def view_scope(cls):
        """
        Return a scope to determine if the CompletionLoader will be enabled
        for a view.

        """
        return 'source.focus, source.fs'

    @classmethod
    def view_check(cls, view):
        """
        Returns True if the CompletionLoader should be enabled for the given
        view.

        """
        return get_completion_source_enabled_setting('List', 'View')

    def load_completions(self, **kwargs):
        """
        Populate self.completions with the completions handled by this
        completer.

        """
        ring_view = get_view(self.view)
        self.completions = ring_view.get_defined_lists(
            for_completions=True)


class ObjectViewLoader(ViewLoader):
    """
    Loads object completions for Temp DataDefs defined within a view.
    """

    EmptyReturn = ([], sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    @classmethod
    def completion_types(cls):
        """
        Return a set of completion types that this CompletionLoader can return.

        """
        return [CT_OBJECT, CT_RECORD, CT_FILE, CT_KEY, CT_FIELD]

    @classmethod
    def view_scope(cls):
        """
        Return a scope to determine if the CompletionLoader will be enabled
        for a view.

        """
        return 'source.focus'

    @classmethod
    def view_check(cls, view):
        """
        Returns True if the CompletionLoader should be enabled for the given
        view.

        """
        n = view.file_name()
        if (n is not None) and (n != '') and ('!DictionarySource' in n):
            return False
        return get_completion_source_enabled_setting('Object', 'View')

    def load_completions(self, included_completions=[], **kwargs):
        """
        Loads object completions for Temp DataDefs defined within the view.

        """
        ring_view = get_view(self.view)
        if len(included_completions) > 1:
            type_ = 'All'
        else:
            type_ = included_completions.pop()

        self.completions = ring_view.get_defined_objects(type_,
                                                         for_completions=True)


class TranslatorViewLoader(ViewLoader):
    """
    Loads completions for populating translators.
    """

    EmptyReturn = ([], )

    @classmethod
    def completion_types(cls):
        """
        Return a set of completion types that this CompletionLoader can return.
        """
        return [CT_TRANSLATOR]

    @classmethod
    def view_scope(cls):
        """
        Return a scope to determine if the CompletionLoader will be enabled
        for a view.

        """
        return 'source.focus'

    def load_completions(self, **kwargs):
        """
        Loads object completions for Temp DataDefs defined within the view.

        """
        logger.debug("Returning completions from %s", self.__class__.__name__)
        sel = self.view.sel()[0]
        preceding_line = sublime.Region(
            self.view.line(sel).begin(), sel.end())
        preceding_line_string = self.view.substr(preceding_line)
        match = TRANSLATOR_LINE_SPLITTER.match(preceding_line_string)

        ring_view = get_view(self.view)
        tree = ring_view.build_translator_tree(sel.end(), trim_containers=True)

        current_item = tree[-1]
        partial_completions = get_translator_completions()

        if match and (match.group(3) == '#'):
            self.completions = set([(x,) for x in partial_completions])
            return

        for k, v in tree:
            try:
                translator = partial_completions[k]
                logger.debug('%s %s', k, translator)
            except KeyError:
                logger.debug("KeyError")
                if ((k == current_item[0]) and (v == current_item[1])):
                    if ((match is None) or ((match.group('separator') == '')
                                            and (match.group('value') == ''))):
                        self.completions = set(
                            [(x,) for x in translator.children.keys()])
                        logger.debug('self.completions = %s', self.completions)
                return
            else:
                try:
                    partial_completions = translator.children
                except AttributeError:
                    logger.debug("AttributeError")
                    return

        if ((match is None) or ((match.group('separator') == '') and
                                (match.group('value') == ''))):
            self.completions = set([(x,) for x in translator.children.keys()])
        else:
            self.completions = set([(x,) for x in translator.completions])

        logger.debug('Translator Completions: %s', self.completions)


class VariableViewLoader(ViewLoader):
    """
    Loads completions for populating translators.
    """

    EmptyReturn = ([], )

    @classmethod
    def completion_types(cls):
        """
        Return a set of completion types that this CompletionLoader can return.
        """
        return [CT_SUBROUTINE_LOCAL]

    @classmethod
    def view_scope(cls):
        """
        Return a scope to determine if the CompletionLoader will be enabled
        for a view.

        """
        return 'source.focus'

    def load_completions(self, **kwargs):
        """Load variable completions for the current code block.

        """
        selections = set(s.begin() for s in self.view.sel())
        try:
            focus_view = get_view(self.view)
            codeblock = focus_view.get_codeblock(self.view.sel()[0].begin())
        except ViewTypeException:
            pass
        except InvalidCodeBlockError:
            pass
        else:
            var_dict = codeblock.get_variables_from_function()
            # Exclude variables that show up due to the character that was typed
            var_list = [v for v in var_dict.values() if
                        set(s.end() for s in v.regions) != selections]
            if any(len(v.var) > 1 for v in var_list):
                self.completions = set((v.var,) for v in var_list
                                       if len(v.var) > 0)

    def filter_completions(self, completion_types, **kwargs):
        """Override the return to replace the flags value."""
        return (super().filter_completions(completion_types, **kwargs)[0], 0)
