import functools
import re

import sublime

import Focus
from ..FocusFile import CodeBlockDocumentation, CodeBlockSet, extract_fs_function
from .EntityHighlighter import EntityHighlighter

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class SetHighlighter(EntityHighlighter):
    
    @EntityHighlighter.api_call
    def check(self):
        score_selector = functools.partial(Focus.score_selector, self.view, self.sel.begin())
        if (score_selector('subroutine') <= 0):
            return self.match
        elif ((score_selector('fs_function') <= 0) and
              (score_selector('comment') <= 0)):
            return self.match
        
        self.codeblock, self.set_doc_region = self.setup()
        self.doc_region = None

        if score_selector('fs_function') > 0:
            logger.debug('Trying to get FS function')
            fs_func, self.search_region = extract_fs_function(self.view, self.sel)
            logger.debug('fs_func = %s', fs_func)
            set_number = fs_func[2:]
            logger.debug('set_number = %s', set_number)
            upper_or_lower = CodeBlockSet.determine_upper(fs_func)
            logger.debug('upper_or_lower = %s', upper_or_lower)
            self.search_string = CodeBlockSet.format_set(set_number, upper_or_lower)
            logger.debug('self.search_string = %s', self.search_string)
            self.match = True
        elif (score_selector('comment') > 0):
            doc_matches = list()
            if (self.set_doc_region and self.sel.intersects(self.set_doc_region)):
                doc_matches = self.view.find_all(r"//\s*(L|U)\(\d+\)\s*[-=:]\s*[\s\S]*?\n(?=//\s*(L|U)\(\d+\)\s*[-=:]|//:Doc)")
            for r in doc_matches:
                if r.contains(self.sel):
                    match = re.search(r"//\s*((L|U)\(\d+\))\s*[-=:]\s*", self.view.substr(r))
                    if match:
                        self.doc_region = r
                        self.search_string = match.group(1)
                        self.search_region = r
                        self.match = True
                        break
        return self.match

    @EntityHighlighter.api_call
    def get_regions(self):
        regions = list()

        if self.match:
            function_sets = self.codeblock.get_sets_from_function()
            regions.extend(function_sets[self.search_string].regions)

            doc_match = self.get_doc_match(self.search_string, self.set_doc_region)
            if (doc_match is not None):
                regions.append(doc_match)

        return regions

    @EntityHighlighter.api_call
    def description(self, command):
        if (self.match and (command == self.HIGHLIGHT)):
            return 'Highlight uses of %s in %s' % (self.search_string, self.codeblock.codeblock_name)
        elif (self.match and (command == self.SELECT_ALL)):
            return 'Select all uses of %s in %s' % (self.search_string, self.codeblock.codeblock_name)
        else:
            return super(SetHighlighter, self).description(command)

    def setup(self):
        codeblock = self.focus_file.get_codeblock(self.view)
        sets_doc_region = codeblock.documentation_region
        documentation = CodeBlockDocumentation(codeblock)

        try:
            sets_doc_region = documentation.doc_regions['Data Structures'].region
        except KeyError:
            pass

        yield codeblock
        yield sets_doc_region

    def get_doc_match(self, listset, region):
        r = None
        listset = "%s\(%s\)" % (listset[0], listset[2:-1])
        pattern = r"//\s*(%s)\s*[-=:]\s*" % listset

        doc_match = self.view.find(pattern, region.begin())
        if ((doc_match is not None) and region.intersects(doc_match)):
            substring = self.view.substr(doc_match)
            match = re.match(pattern, substring)
            
            if (match is not None):
                span = match.span(1)
                r = sublime.Region(doc_match.begin() + span[0], doc_match.begin() + span[1])
        return r
