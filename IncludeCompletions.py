import logging
import re

logger = logging.getLogger(__name__)

import sublime

try:
    from DynamicCompletions import FileLoader
except ImportError as e:
    logger.error('DynamicCompletions package not installed')
    raise e

from .tools.classes import get_ring_file
from .tools.settings import get_completion_source_enabled_setting

from .misc.completion_types import (
    CT_ALIAS,
    CT_FOCUS_LOCAL,
    CT_SUBROUTINE,
    CT_LIST,

    CT_OBJECT,
    CT_RECORD,
    # CT_FILE,
    CT_KEY,
    CT_FIELD,
    # CT_INDEX,
    # CT_INDEXKEY,
    # CT_LONGLOCK,
)


class IncludeFileLoader(FileLoader):
    """
    Parent class for CompletionLoaders that load completions from an Include
    file.
    """

    LoadAsync = True

    @classmethod
    def view_scope(cls):
        """
        Return a scope to determine if the CompletionLoader will be enabled
        for a view.

        """
        return 'source.focus'

    @classmethod
    def view_check(cls, view):
        n = view.file_name()
        if (n is None) or (n == ''):
            return False
        return (get_ring_file(n) is not None)

    @classmethod
    def instances_for_view(cls, view):
        """
        Returns a list of instances of the given class to be used for the
        given view.

        """
        ring_file = get_ring_file(view.file_name())
        if ring_file is None:
            return []

        include_files = ring_file.get_include_files()
        if not include_files:
            return []

        instances = set()
        for f in include_files:
            logger.debug('%s;  f = %s', cls, f)
            try:
                instances.add(cls.Instances[f])
            except KeyError:
                instances.add(cls(file_path=f))
            except AttributeError:
                instances.add(cls(file_path=f))
        return instances


class AliasIncludeLoader(IncludeFileLoader):
    """
    Loads aliases defined in an Include File.
    """

    EmptyReturn = ([], sublime.INHIBIT_WORD_COMPLETIONS |
                   sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    AliasMatcher = re.compile(r"^\s*:Alias\s+([^\n()\t]+?) *$", re.MULTILINE)

    @classmethod
    def completion_types(cls):
        """
        Return a set of completion types that this CompletionLoader can return.

        """
        return [CT_ALIAS]

    @classmethod
    def view_check(cls, view):
        if super().view_check(view):
            return get_completion_source_enabled_setting('Alias', 'Include')

    def load_completions(self, **kwargs):
        """
        Populate self.completions with Aliases from an Include file.

        """
        self.completions = set()
        ring_file = get_ring_file(self.file_path)
        for alias in ring_file.get_defined_aliases():
            alias = '@@' + alias + '()'
            self.completions.add((alias + '\tInclude', alias[2:]))


class LocalIncludeLoader(IncludeFileLoader):
    """
    Loads any locals used in an Include File.
    """

    EmptyReturn = ([], sublime.INHIBIT_WORD_COMPLETIONS |
                   sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    @classmethod
    def completion_types(cls):
        """
        Return a list of completion types that this CompletionLoader can
        return.

        """
        return [CT_FOCUS_LOCAL]

    @classmethod
    def view_check(cls, view):
        if super().view_check(view):
            return get_completion_source_enabled_setting('Local', 'Include')

    def load_completions(self, **kwargs):
        """
        Populate self.completions with Locals from an Include file.

        """
        self.completions = set()
        ring_file = get_ring_file(self.file_path)
        for local in (ring_file.get_used_locals() |
                      ring_file.get_defined_locals()):
            self.completions.add((local + '\tInclude', local))


class ObjectIncludeLoader(IncludeFileLoader):
    """
    Loads DataDef completions from an Include File.
    """

    EmptyReturn = ([], sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    @classmethod
    def completion_types(cls):
        """
        Return a list of completion types that this CompletionLoader can
        return.

        """
        return [CT_OBJECT, CT_RECORD, CT_KEY, CT_FIELD]

    @classmethod
    def view_check(cls, view):
        if super().view_check(view):
            return get_completion_source_enabled_setting('Object', 'Include')

    def load_completions(self, **kwargs):
        """
        Populate self.completions with objects from an Include file.

        """
        self.completions = dict()
        ring_file = get_ring_file(self.file_path)
        object_dict = ring_file.get_defined_objects()

        for key, object_set in object_dict.items():
            self.completions[key] = set(
                [(x + '\tInclude', x) for x in object_set])


class SubroutineIncludeLoader(IncludeFileLoader):
    """
    Loads subroutine completions from an Include File.
    """

    EmptyReturn = ([], sublime.INHIBIT_WORD_COMPLETIONS |
                   sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    @classmethod
    def completion_types(cls):
        """
        Return a list of completion types that this CompletionLoader can
        return.

        """
        return [CT_SUBROUTINE]

    @classmethod
    def view_check(cls, view):
        if super().view_check(view):
            return get_completion_source_enabled_setting('Subroutine',
                                                         'Include')

    def load_completions(self, **kwargs):
        """
        Populate self.completions with subroutines from an Include file.

        """
        ring_file = get_ring_file(self.file_path)
        self.completions = set(
            [(x + '\tInclude', x) for x in
             ring_file.get_defined_subroutines()])


class ListIncludeLoader(IncludeFileLoader):
    """
    Loads subroutine completions from an Include File.
    """

    EmptyReturn = ([], sublime.INHIBIT_WORD_COMPLETIONS |
                   sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    @classmethod
    def completion_types(cls):
        """
        Return a list of completion types that this CompletionLoader can
        return.

        """
        return [CT_LIST]

    @classmethod
    def view_check(cls, view):
        if super().view_check(view):
            return get_completion_source_enabled_setting('List',
                                                         'Include')

    def load_completions(self, **kwargs):
        """
        Populate self.completions with Lists from an Include file.

        """
        ring_file = get_ring_file(self.file_path)
        self.completions = set(
            [(x + '\tInclude', x) for x in ring_file.get_defined_lists()])
