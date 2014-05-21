import re

import sublime

from DynamicCompletions import CompletionTrigger, CompletionLoader, ViewLoader

import Focus
from .src.FocusFile import extract_focus_function, extract_focus_function_name, split_focus_function
from .src import FocusLanguage
from .src.Managers.RingFileManager import RingFileManager

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

CT_ALIAS = 'Alias'
CT_FOCUS_LOCAL = 'Local'
CT_SUBROUTINE = 'Subroutine'
CT_TRANSLATOR = 'Translator'

CT_OBJECT = "Object"
CT_RECORD = "Record"
CT_FILE = "File"
CT_KEY = "Key"
CT_FIELD = "Field"

# def add_loaders_to_focus_file(view, prefix, locations, completion_types):
#     if Focus.score_selector(view, locations[0], 'source') <= 0:
#         return

#     if not ViewLoader.get_loaders_for_view(view):
#         for l in ViewLoader.get_plugins():
#             if l.view_scope_check(view) and l.view_check(view):
#                 l.add_loader_to_view(view)

# CompletionLoader.add_on_before_load_callback(add_loaders_to_focus_file)



class FocusFunctionTrigger(CompletionTrigger):
    """Object to check focus functions to return completion types."""

    @classmethod
    def view_scope(cls):
        """Return a scope to determine if a CompletionTrigger will be enabled for a view."""
        return Focus.scope_map('source')

    def selection_scope(self):
        """Return a scope to determine if a CompletionTrigger will be enabled for the current selection."""
        return Focus.scope_map('focus_function_finder')

    def selection_check(self, prefix, locs):
        """Return a list of completion types for the current locations.

        If no completion types are handled for the current locations by this
        trigger, return an empty list.

        """
        focus_func = extract_focus_function(self.view, locs[0])
        if (focus_func is None):
            return []

        split_func = split_focus_function(focus_func[0], focus_func[1])
        if (not split_func[1][1].contains(locs[0])):
            return []

        func_name = split_func[0][0]
        try:
            return FocusLanguage.FOC_FUNC_COMP[func_name]
        except KeyError:
            return []

        return []


class AliasTrigger(CompletionTrigger):
    """Object to check focus functions to return completion types."""

    @classmethod
    def view_scope(cls):
        """Return a scope to determine if a CompletionTrigger will be enabled for a view."""
        return Focus.scope_map('source')

    def selection_scope(self):
        """Return a scope to determine if a CompletionTrigger will be enabled for the current selection."""
        return Focus.scope_map('source_no_comment')

    def selection_check(self, prefix, locs):
        """Return a list of completion types for the current locations.

        If no completion types are handled for the current locations by this
        trigger, return an empty list.

        """
        if ('!DictionarySource' in self.view.file_name()):
            return []

        end = locs[0]
        start = end - 2
        selection = sublime.Region(start, end)
        substring = self.view.substr(selection)

        if substring.startswith('@@'):
            return ['Alias']

        start = self.view.find_by_class(end, False, sublime.CLASS_WORD_START, "@") - 2
        selection = sublime.Region(start, end)
        substring = self.view.substr(selection)
        
        if substring.startswith('@@'):
            return [CT_ALIAS]

        return []


class TranslatorTrigger(CompletionTrigger):
    """Object to check translator keywords and attributes to return completion types."""

    @classmethod
    def view_scope(cls):
        """Return a scope to determine if a CompletionTrigger will be enabled for a view."""
        return Focus.scope_map('source')

    def selection_scope(self):
        """Return a scope to determine if a CompletionTrigger will be enabled for the current selection."""
        return Focus.scope_map('translator_completion_checker')

    def selection_check(self, prefix, locs):
        """Return a list of completion types for the current locations.

        If no completion types are handled for the current locations by this
        trigger, return an empty list.

        """
        preceding_line = sublime.Region(self.view.line(locs[0]).begin(), locs[0])
        preceding_line_string = self.view.substr(preceding_line)
        match = re.match(r'^(\s*)((:|#)[A-Za-z0-9]*|[A-Za-z0-9]+)(\s*)(.*)$', preceding_line_string)
        # logger.debug('match = %s', match)

        manager = RingFileManager.getInstance()
        focus_file = manager.get_ring_file(self.view)
        tree = focus_file.build_translator_tree(self.view, True)
        # logger.debug('tree = %s', tree)
        current_item = tree[-1]
        # logger.debug('current_item = %s', current_item)
        partial_completions = Focus.TranslatorCompletions

        for k, v in tree:
            try:
                translator = partial_completions[k]
                # print(k, translator)
            except KeyError:
                if ((k == current_item[0]) and (v == current_item[1])):
                    if ((match is None) or ((match.group(4) == '') and (match.group(5) == ''))):
                        return [CT_TRANSLATOR]
                return []
            else:
                partial_completions = translator.children
                # logger.debug('partial_completions = %s', partial_completions)

        if ((match is None) or ((match.group(4) == '') and (match.group(5) == ''))):
            return [CT_TRANSLATOR]
        else:
            return translator.completion_types


class AliasViewLoader(ViewLoader):
    """Loads aliases defined within a view."""

    EmptyReturn = ([], sublime.INHIBIT_EXPLICIT_COMPLETIONS | sublime.INHIBIT_WORD_COMPLETIONS)

    @classmethod
    def completion_types(cls):
        """Return a set of completion types that this CompletionLoader can return."""
        return [CT_ALIAS]

    @classmethod
    def view_scope(cls):
        """Return a scope to determine if the CompletionLoader will be enabled for a view."""
        return Focus.scope_map('source')

    @classmethod
    def view_check(cls, view):
        """Returns True if the CompletionLoader should be enabled for the given view."""
        n = view.file_name()
        if (n is not None) and (n != '') and ('!DictionarySource' in n):
            return False
        return True

    def load_completions(self, **kwargs):
        """Loads the aliases defined within the view."""
        self.completions = set()
        for x in [self.view.substr(x) for x in Focus.find_by_selector(self.view, 'alias_definition')]:
            self.completions.add(('@@%s()' % x, '%s()' % x))
        logger.debug('Alias Completions: %s', self.completions)


class LocalViewLoader(ViewLoader):
    """Loads focus Locals used within a view."""

    EmptyReturn = ([], sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    @classmethod
    def completion_types(cls):
        """Return a set of completion types that this CompletionLoader can return."""
        return [CT_FOCUS_LOCAL]

    @classmethod
    def view_scope(cls):
        """Return a scope to determine if the CompletionLoader will be enabled for a view."""
        return Focus.scope_map('source')

    def load_completions(self, **kwargs):
        """Loads the focus Locals used in the view."""
        self.completions = set()
        for x in [self.view.substr(x) for x in Focus.find_by_selector(self.view, 'focus_local')]:
            self.completions.add((x,))
        logger.debug('Local Completions: %s', self.completions)


class ObjectViewLoader(ViewLoader):
    """Loads object completions for Temp DataDefs defined within a view."""

    EmptyReturn = ([], sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    @classmethod
    def completion_types(cls):
        """Return a set of completion types that this CompletionLoader can return."""
        return [CT_OBJECT, CT_RECORD, CT_FILE, CT_KEY, CT_FIELD]

    @classmethod
    def view_scope(cls):
        """Return a scope to determine if the CompletionLoader will be enabled for a view."""
        return Focus.scope_map('source')

    @classmethod
    def view_check(cls, view):
        """Returns True if the CompletionLoader should be enabled for the given view."""
        n = view.file_name()
        if (n is not None) and (n != '') and ('!DictionarySource' in n):
            return False
        return True

    def load_completions(self, included_completions = [], **kwargs):
        """Loads object completions for Temp DataDefs defined within the view."""
        self.completions = set()
        manager = RingFileManager.getInstance()
        focus_file = manager.get_ring_file(self.view)
        for t in included_completions:
            self.completions.update([(x,) for x in focus_file.get_object_completions_from_file(self.view, t)])
        logger.debug('Object view completions: %s', self.completions)

    
class SubroutineViewLoader(ViewLoader):
    """Loads subroutine names defined within a view."""

    EmptyReturn = ([], sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    @classmethod
    def completion_types(cls):
        """Return a set of completion types that this CompletionLoader can return."""
        return [CT_SUBROUTINE]

    @classmethod
    def view_scope(cls):
        """Return a scope to determine if the CompletionLoader will be enabled for a view."""
        return Focus.scope_map('source')

    def load_completions(self, **kwargs):
        """Populate self.completions with the completions handled by this completer."""
        self.completions = set()
        for x in [self.view.substr(x) for x in Focus.find_by_selector(self.view, 'subroutine_header_name')]:
            self.completions.add((x, ))
        logger.debug('Subroutine Completions: %s', self.completions)

    
class TranslatorViewLoader(ViewLoader):
    """Loads object completions for Temp DataDefs defined within a view."""

    EmptyReturn = ([], )

    @classmethod
    def completion_types(cls):
        """Return a set of completion types that this CompletionLoader can return."""
        return [CT_TRANSLATOR]

    @classmethod
    def view_scope(cls):
        """Return a scope to determine if the CompletionLoader will be enabled for a view."""
        return Focus.scope_map('source')

    def load_completions(self, **kwargs):
        """Loads object completions for Temp DataDefs defined within the view."""
        self.completions = set()

        selection = self.view.sel()[0]
        preceding_line = sublime.Region(self.view.line(selection.begin()).begin(), selection.end())
        preceding_line_string = self.view.substr(preceding_line)
        match = re.match(r'^(\s*)((:|#)[A-Za-z0-9]*|[A-Za-z0-9]+)(\s*)(.*)$', preceding_line_string)
        if match and (match.group(3) == '#'):
            return

        manager = RingFileManager.getInstance()
        focus_file = manager.get_ring_file(self.view)
        tree = focus_file.build_translator_tree(self.view, True)
        # logger.debug('tree = %s', tree)
        current_item = tree[-1]

        partial_completions = Focus.TranslatorCompletions
        # logger.debug('partial_completions = %s', partial_completions)

        for k, v in tree:
            try:
                translator = partial_completions[k]
                print(k, translator)
            except KeyError:
                if ((k == current_item[0]) and (v == current_item[1])):
                    if ((match is None) or ((match.group(4) == '') and (match.group(5) == ''))):
                        self.completions = set([(x,) for x in translator.children.keys()])
                return
            else:
                partial_completions = translator.children
                # logger.debug('partial_completions = %s', partial_completions)

        if ((match is None) or ((match.group(4) == '') and (match.group(5) == ''))):
            # logger.debug('getting children')
            self.completions = set([(x,) for x in translator.children.keys()])
        else:
            # logger.debug('getting completions')
            self.completions = set([(x,) for x in translator.completions])

        logger.debug('Translator Completions: %s', self.completions)
