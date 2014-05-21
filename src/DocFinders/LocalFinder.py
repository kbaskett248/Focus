import re

import sublime

import Focus
from .DocFinder import DocFinder

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class LocalFinder(DocFinder):
    """docstring for SubroutineFinder"""

    ScopeMap = 'called_local'
    
    @classmethod
    @DocFinder.api_call
    def check(cls, view, ring_file):
        search_region = view.extract_scope(view.sel()[0].begin())
        search_string = view.substr(search_region)
        return cls(search_string, search_region, ring_file, view)

    @DocFinder.api_call
    def show(self):
        logger.debug(self.search_string)
        sublime.status_message("Looking up Local: %s" % self.search_string)
        file_, region = self.ring_file.find_local(self.view, 
                                                   self.search_string)
        
        status_message_suffix = self.move_or_open(file_, region, show_at_top = False)

        sublime.status_message(
            "Documentation for {0} {1}".format(self.search_string, 
                                               status_message_suffix)
            )

    @DocFinder.api_call
    def description(self):
        return 'Documentation for Local %s' % self.search_string