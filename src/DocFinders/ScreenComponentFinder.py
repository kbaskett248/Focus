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

class ScreenComponentFinder(DocFinder):
    """docstring for SubroutineFinder"""

    ScopeMap = '#ScreenPage'
    
    @classmethod
    @DocFinder.api_call
    def check(cls, view, ring_file):
        sel = view.sel()[0]
        if Focus.score_selector(view, sel.begin(), 'other_attribute') > 0:
            tree = ring_file.build_translator_tree(view)
            attributes = [a[0] for a in tree]

            if ':Component' in attributes:
                line_region = view.line(sel)
                line_string = view.substr(line_region)
                match = re.match(r" *([:A-Za-z0-9]+) +(\S+)", line_string)
                if match is not None:
                    search_string = match.group(2)
                    search_region = sublime.Region(line.begin() + match.span(2)[0],
                                                   line.begin() + match.span(2)[1])
                    d = cls(search_region, search_string, ring_file, view)
                    d.type_ = match.group(1)
                    return d
        elif Focus.score_selector(view, sel.begin(), 'other_keyword') > 0:
            line_region = view.line(sel)
            line_string = view.substr(line_region)
            match = re.match(r" *(:Region) +(\S+)", line_string)
            if match is not None:
                search_string = match.group(2)
                search_region = sublime.Region(line.begin() + match.span(2)[0],
                                               line.begin() + match.span(2)[1])
                d = cls(search_region, search_string, ring_file, view)
                d.type_ = match.group(1)
                return d

    @DocFinder.api_call
    def show(self):
        logger.debug(self.search_string)
        sublime.status_message("Looking up %s: %s" % (self.type_, self.search_string))
        file_, region = self.ring_file.find_screen_component(self.view, 
            self.type_, self.search_string)
        logger.debug('File: %s; Region: %s', file_, region)

        status_message_suffix = self.move_or_open(file_, region)
        
        sublime.status_message(
            "Documentation for {0} {1}".format(self.search_string, 
                                               status_message_suffix)
            )

    @DocFinder.api_call
    def description(self):
        return 'Show ScreenComponent definition for ' + self.search_string