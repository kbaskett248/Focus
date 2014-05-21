import Focus
from ..FocusPlugin import FocusPlugin

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class CompChecker(FocusPlugin):
    """Superclass for objects used to determine what types of completions to return."""

    """A scope selector that will be filtered through SublimeMapper before
    score_selector is called to determine matching CompCheckers. Used prior to 
    check() to quickly filter non-matching completers.
    """
    ScopeMap = ''

    @FocusPlugin.api_call
    def __init__(self, ring_file):
        super(CompChecker, self).__init__()
        self.ring_file = ring_file

    @classmethod
    @FocusPlugin.api_call
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
        return True

    @FocusPlugin.api_call
    def scope_check(self, view):
        """Returns the score for a selection matching ScopeMap.

        Keyword arguments:
        view - A sublime.View object

        This is used as a quick check to filter out CompCheckers with 
        non-matching scopes. Any CompChecker returning a value > 0 will then 
        have it's check() method called.
        This normally will not be overridden.

        """
        return Focus.score_selector(view, view.sel()[0].begin(), self.ScopeMap)

    @FocusPlugin.api_call
    def check(self, view, loc):
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
        return []


        