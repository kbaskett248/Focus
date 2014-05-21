import re
import webbrowser

import sublime

import Focus
from .DocFinder import DocFinder
from ..FocusFile import extract_fs_function

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class FSFunctionFinder(DocFinder):
    """docstring for SubroutineFinder"""

    ScopeMap = 'fs_function'
    
    @classmethod
    @DocFinder.api_call
    def check(cls, view, ring_file):
        sel = view.sel()[0]
        
        function = extract_fs_function(view, sel)
        if (function is not None):
            return cls(function[0], function[1], ring_file, view)


    @DocFinder.api_call
    def show(self):
        match = re.match(r"@[A-Za-z]{1,2}", self.search_string)
        if (match is not None):
            sublime.status_message("Opening documentation for " + self.search_string)
            url = "http://stxwiki/magicfs6/" + match.group(0)
            webbrowser.open(url)