import time

import sublime

import Focus
from ..FocusPlugin import FocusPlugin

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class DocFinder(FocusPlugin):
    """docstring for DocLookup"""

    ScopeMap = ''

    """Persistent storage for the DocFinder assigned to a View."""
    DocFinderForView = dict()

    @classmethod
    @FocusPlugin.api_call
    def scope_check(cls, view):
        """Returns the score for a selection matching ScopeMap.

        Keyword arguments:
        view - A sublime.View object

        This is used as a quick check to filter out CompCheckers with 
        non-matching scopes. Any CompChecker returning a value > 0 will then 
        have it's check() method called.
        This normally will not be overridden.

        """
        s = view.sel()[0]
        return Focus.score_selector(view, s.begin(), cls.ScopeMap)
    
    @classmethod
    @FocusPlugin.api_call
    def check(cls, view, ring_file):
        """If this class is a match for the selection, return an instance of the class.
        Otherwise, return None.

        """
        return None

    @classmethod
    def assign_finder_to_view(cls, view, doc_finder):
        cls.DocFinderForView[view.id()] = doc_finder

    @classmethod
    def get_finder_for_view(cls, view):
        """Helper function to get the DocFinder assigned to a View."""
        try:
            return cls.DocFinderForView[view.id()]
        except KeyError:
            return None

    @FocusPlugin.api_call
    def __init__(self, search_string, search_region, ring_file, view):
        super().__init__()
        self.search_string = search_string
        self.search_region = search_region
        self.ring_file = ring_file
        self.view = view

    @FocusPlugin.api_call
    def show(self):
        pass

    @FocusPlugin.api_call
    def move_or_open(self, file_, region, show_at_top = True):
        logger.debug('File: %s; Region: %s', file_, region)
        status_message_suffix = ''

        if (file_ is None):
            status_message_suffix = 'not found'
        elif (file_ == self.ring_file.filename):
            self.view.show(region, True)
            self.view.sel().clear()
            self.view.sel().add(region)
            if show_at_top:
               line = self.view.line(region)
               line = self.view.line(line.begin() - 1)
               v = self.view.text_to_layout(line.begin())
               self.view.set_viewport_position(v, True)
            status_message_suffix = 'found in current file'
        else:
            status_message_suffix = 'found in other file'
            if (region is None):
                self.view.window().open_file(file_)
            else:
                view = self.view.window().open_file(
                    "{0}:{1}:{2}".format(file_, region[0], region[1]),
                    sublime.ENCODED_POSITION)
                sublime.set_timeout_async(
                    lambda: self.show_and_select_opened_file(view, region, show_at_top), 0)

        return status_message_suffix

    @FocusPlugin.api_call
    def show_and_select_opened_file(self, view, region, show_at_top):
        while view.is_loading():
            time.sleep(0.01)

        s = view.sel()
        s.clear()
        p = view.text_point(region[0]-1, region[1]-1)
        line = view.line(p)
        selection = sublime.Region(p, line.end())
        s.add(selection)

        if show_at_top:
            previous_line = view.line(line.begin()-1)
            v = view.text_to_layout(previous_line.begin())
            view.set_viewport_position(v, False)

    def __str__(self):
        return self.__class__.__name__

    @FocusPlugin.api_call
    def description(self):
        try:
            if self.search_string:
                return 'Documentation for %s' % self.search_string
        except AttributeError:
            pass
        
        return 'Documentation Lookup'
