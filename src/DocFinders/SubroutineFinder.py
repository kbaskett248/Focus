import sublime

import Focus
from .DocFinder import DocFinder

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class SubroutineFinder(DocFinder):
    """docstring for SubroutineFinder"""

    ScopeMap = 'subroutine_name'
    
    @classmethod
    @DocFinder.api_call
    def check(cls, view, ring_file):
        sel = view.sel()[0]
        for r in Focus.find_by_selector(view, 'subroutine_name'):
            if r.contains(sel):
                return cls(view.substr(r), r, ring_file, view)

    @DocFinder.api_call
    def show(self):
        sublime.status_message("Looking up subroutine: " + self.search_string)
        file_, region = self.ring_file.find_subroutine(self.view, self.search_string)
        logger.debug('File: %s; Region: %s', file_, region)

        status_message_suffix = self.move_or_open(file_, region)

        sublime.status_message(
            "Documentation for {0} {1}".format(self.search_string, 
                                               status_message_suffix)
            )

    # @DocFinder.api_call
    # def description(self):
    #     return 'Documentation for %s' % self.search_string