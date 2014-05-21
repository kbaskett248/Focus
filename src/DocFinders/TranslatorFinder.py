import re
import webbrowser

import sublime

import Focus
from .DocFinder import DocFinder

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class TranslatorFinder(DocFinder):
    """docstring for SubroutineFinder"""

    ScopeMap = 'translator_finder'
    
    @classmethod
    @DocFinder.api_call
    def check(cls, view, ring_file):
        sel = view.sel()[0]
        line_region = view.line(sel)
        preceding_line_region = sublime.Region(line_region.begin(), sel.end())

        line_text = view.substr(line_region)
        preceding_line_text = view.substr(preceding_line_region)

        # logger.debug(line_text)
        # logger.debug(preceding_line_text)

        match = re.match(r"^ *([A-Za-z#:]+)( |$)", line_text)
        # logger.debug(match.group(0))
        if ((match is not None) and match.group(0).startswith(preceding_line_text)):
            search_region = sublime.Region(line_region.begin() + match.span(1)[0],
                                           line_region.begin() + match.span(1)[1])
            return cls(match.group(1), search_region, ring_file, view)

    @DocFinder.api_call
    def show(self):
        if Focus.score_selector(self.view, self.search_region.begin(), 'translator') > 0:
            url_arg = 'X-%s' % self.search_string[1:]
        else:
            translator = keyword = attribute = ''
            for t in (t[0] for t in self.ring_file.build_translator_tree(self.view)):
                if (t[0] == '#'):
                    translator = 'X-%s' % t[1:]
                elif (t[0] == ':'):
                    keyword = '-%s' % t[1:]
                else:
                    attribute = '#%s' % t
            url_arg = translator + keyword + attribute
        sublime.status_message("Opening documentation for " + self.search_string)
        url = "http://stxwiki/wiki10/" + url_arg
        webbrowser.open(url)