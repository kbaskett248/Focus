import re

import sublime

import Focus
from .CompChecker import CompChecker
from ..FocusFile import FocusFile
from .. import FocusLanguage

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class TranslatorCompChecker(CompChecker):
    """Object to check translator keywords and attributes to return completion types."""

    """A scope selector that will be filtered through SublimeMapper before
    score_selector is called to determine matching completers. Used prior to 
    check() to quickly filter non-matching completers.
    """
    ScopeMap = 'translator_completion_checker'

    @classmethod
    @CompChecker.api_call
    def enable_checker(cls, ring_file = None):
        """Returns True if the completer should be enabled.

        Keyword arguments:
        ring_file - A Focus.RingFile object

        This function is called at the following times:
        1. After the CompChecker classes are initially loaded, this is called
           with no arguments in case we can filter it out there.
        2. Before an instance of a CompChecker is created, this is called
           with the ring_file argument.

        """
        if (ring_file is not None):
            if not (isinstance(ring_file, FocusFile)):
                return False
        return True

    @CompChecker.api_call
    def check(self, view, ring_file, loc):
        """Returns a list of completion types that should be returned for the current point.

        Keyword arguments:
        view - A sublime.View object
        ring_file - A Focus.RingFile object
        loc - A list of (sublime.Region, line number)

        This function should be overridden by extending classes.
        This function will be called for any CompChecker assigned to a RingFile
        that passes the scope_check.This function should check the current 
        locations to determine what types of completions should be returned
        and then return a list of those types. If no completions should be
        returned from this CompChecker for the given point, return an empty 
        list.

        """
        selection = loc[0][0]
        preceding_line = sublime.Region(view.line(selection.begin()).begin(), selection.end())
        preceding_line_string = view.substr(preceding_line)
        match = re.match(r'^(\s*)((:|#)[A-Za-z0-9]*|[A-Za-z0-9]+)(\s*)(.*)$', preceding_line_string)
        # logger.debug('match = %s', match)

        tree = ring_file.build_translator_tree(view, True)
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
                        return ['Translator']
                return []
            else:
                partial_completions = translator.children
                # logger.debug('partial_completions = %s', partial_completions)

        if ((match is None) or ((match.group(4) == '') and (match.group(5) == ''))):
            return ['Translator']
        else:
            return translator.completion_types

        