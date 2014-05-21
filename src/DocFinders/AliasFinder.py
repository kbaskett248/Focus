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

class AliasFinder(DocFinder):
    """docstring for SubroutineFinder"""

    ScopeMap = 'alias'
    
    @classmethod
    @DocFinder.api_call
    def check(cls, view, ring_file):
        sel = view.sel()[0]
        for r in Focus.find_by_selector(view, 'alias'):
            if r.contains(sel):
                string = view.substr(r)
                match = re.search(r"@@([^\n()]+?)\(", string)
                if (match is not None):
                    return cls(match.group(1), r, ring_file, view)
                break

    @DocFinder.api_call
    def show(self):
        sublime.status_message("Looking up Alias: " + self.search_string)
        file_, region = self.find_alias_in_current_file()
        if (file_ is None):
            file_, region = self.find_alias_in_other_file()

        status_message_suffix = self.move_or_open(file_, region)
        sublime.status_message(
            "Documentation for {0} {1}".format(self.search_string, 
                                               status_message_suffix)
            )

    def find_alias_in_current_file(self):
        file_ = self.view.file_name()
        region = self.ring_file.find_alias(self.view, self.search_string)
        if (region is None):
            file_ = None
        yield file_
        yield region

    def find_alias_in_other_file(self):
        file_ = None
        region = None
        location = self.ring_file.ring_object.find_alias(self.search_string)
        if (location is not None):
            file_ = location[0]
            region = location[1:3]

        yield file_
        yield region
        
    @DocFinder.api_call
    def description(self):
        return 'Documentation for @@%s()' % self.search_string