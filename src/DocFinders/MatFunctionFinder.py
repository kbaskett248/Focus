import re
import webbrowser

import sublime

import Focus
from ..FocusFile import extract_focus_function, split_focus_function
from .DocFinder import DocFinder

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class MatFunctionFinder(DocFinder):
    """DocFinder to open documentation for an M-AT function."""

    ScopeMap = 'focus_function_finder'
    
    @classmethod
    @DocFinder.api_call
    def check(cls, view, ring_file):
        sel = view.sel()[0]
        match = extract_focus_function(view, sel)

        if match is not None:
            match = split_focus_function(match[0], match[1])

            if match is not None:
                search_string = '@' + match[0][0]
                search_region = match[0][1]
                search_region = sublime.Region(
                    search_region.begin()-1, search_region.end())
                return cls(search_string, search_region, ring_file, view)

        return None

    @DocFinder.api_call
    def show(self):
        sublime.status_message("Opening documentation for " + self.search_string)
        url = "http://stxwiki/wiki10/" + self.search_string
        webbrowser.open(url)
