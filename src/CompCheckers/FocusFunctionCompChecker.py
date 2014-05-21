from .CompChecker import CompChecker
from ..FocusFile import FocusFile, extract_focus_function, split_focus_function
from .. import FocusLanguage

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class FocusFunctionCompChecker(CompChecker):
    """Object to check focus functions to return completion types."""

    """A scope selector that will be filtered through SublimeMapper before
    score_selector is called to determine matching completers. Used prior to 
    check() to quickly filter non-matching completers.
    """
    ScopeMap = 'focus_function'

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
        focus_func = extract_focus_function(view, loc[0][0])
        if (focus_func is None):
            return []

        split_func = split_focus_function(focus_func[0], focus_func[1])
        if (not split_func[1][1].contains(loc[0][0])):
            return []

        func_name = split_func[0][0]
        try:
            return FocusLanguage.FOC_FUNC_COMP[func_name]
        except KeyError:
            return []

        return []

        