import re

import sublime

from .CompChecker import CompChecker
from ..FocusFile import FocusFile
from .. import FocusLanguage

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class AliasCompChecker(CompChecker):
    """Object to check focus functions to return completion types."""

    """A scope selector that will be filtered through SublimeMapper before
    score_selector is called to determine matching completers. Used prior to 
    check() to quickly filter non-matching completers.
    """
    ScopeMap = 'source_no_comment'

    @classmethod
    @CompChecker.api_call
    def enable_checker(cls, ring_file = None):
        """Returns True if the completer should be enabled.

        Keyword arguments:
        ring_file - A Focus.RingFile object

        This function must be overridden by extending classes.
        This function is called at the following times:
        1. After the CompChecker classes are initially loaded, this is called
           with no arguments in case we can filter it out there.
        2. Before an instance of a CompChecker is created, this is called
           with the ring_file argument.

        """
        if (ring_file is not None):
            if ((ring_file.filename is not None) and ('!DictionarySource' in ring_file.filename)):
                return False
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
        end = loc[0][0].end()
        start = end - 2
        selection = sublime.Region(start, end)
        substring = view.substr(selection)

        logger.debug(selection)
        logger.debug(substring)
        
        if substring.startswith('@@'):
            return ['Alias']

        start = view.find_by_class(end, False, sublime.CLASS_WORD_START, "@") - 2
        selection = sublime.Region(start, end)
        substring = view.substr(selection)
        
        logger.debug(selection)
        logger.debug(substring)

        if substring.startswith('@@'):
            return ['Alias']

        return []

        