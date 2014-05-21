import os

import sublime

import Focus
from .DocFinder import DocFinder
from ..tools import MultiMatch

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class IncludeFileFinder(DocFinder):
    """Highlights Include Files and External PageSets and opens them."""

    ScopeMap = 'include_file_finder'

    IncludeFileMatcher = MultiMatch(patterns = {'Folder': r" *Folder +([A-Za-z0-9._]+)", 
                'File': r" *File +([A-Za-z0-9._]+)"})

    ExternalPageMatcher = MultiMatch(patterns = {'Codebase': r" *Code[Bb]ase +([A-Za-z0-9]+)", 
                'Source': r" *Source +([\w._-]+)",
                'PageName': r' *PageName +([\w.-_]+)',
                'ContainerPage': r' *:ContainerPage +([\w._-]+)'
                })
    
    @classmethod
    @DocFinder.api_call
    def check(cls, view, ring_file):
        sel = view.sel()[0]
        line_region = view.line(sel)
        text = view.substr(line_region)

        if (Focus.score_selector(view, sel.begin(), '#Include') > 0):
            cls.IncludeFileMatcher.match_string = text
            if cls.IncludeFileMatcher.named_match("File"):
                search_string = cls.IncludeFileMatcher.group(1)
                search_region = line_match_region(line_region, cls.IncludeFileMatcher.current_match, 1)
                d = cls(search_string, search_region, ring_file, view)
                d.type_ = 'Include'
                return d

        elif (Focus.score_selector(view, sel.begin(), '#ScreenPage') > 0):
            cls.ExternalPageMatcher.match_string = text
            if cls.ExternalPageMatcher.named_match("Source"):
                search_string = cls.ExternalPageMatcher.group(1)
                search_region = line_match_region(line_region, cls.ExternalPageMatcher.current_match, 1)
                d = cls(search_string, search_region, ring_file, view)
                d.type_ = 'External Pageset'
                return d
        

    @DocFinder.api_call
    def show(self):
        if self.type_ == 'Include':
            sublime.status_message("Opening Include File: " + self.search_string)
            included_files = {os.path.basename(f): f for f in self.ring_file.get_include_files(self.view)}
        elif self.type_ == 'External Pageset':
            sublime.status_message("Opening External Pageset: " + self.search_string)
            included_files = {os.path.basename(f)[:-6]: f for f in self.ring_file.get_externalpageset_files(self.view)}
        logger.debug(included_files)

        try:
            f = included_files[self.search_string]
        except KeyError:
            sublime.status_message(
                "{0} not found".format(self.search_string)
                )
        else:
            self.view.window().open_file(f)
            logger.info('Opening %s', f)
            sublime.status_message(
                "{0} found".format(self.search_string)
                )

    @DocFinder.api_call
    def description(self):
        return 'Open %s' % self.search_string

def line_match_region(line_region, match_object, match_group):
    b = line_region.begin()
    s = match_object.span(match_group)
    return sublime.Region(b + s[0], b + s[1])