import re

import sublime

import Focus
from ..FocusFile import CodeBlockDocumentation
from .EntityHighlighter import EntityHighlighter

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class FSLocalHighlighter(EntityHighlighter):
    
    @EntityHighlighter.api_call
    def check(self):
        logger.debug('self.scope_name = %s', self.scope_name)
        if (Focus.score_selector(self.view, self.sel.begin(), 'subroutine') <= 0):
            return self.match
        elif (self.sel.size() > 1):
            return self.match

        logger.debug('past initial checks')
        self.codeblock, self.local_vars_doc_region, self.arg_doc_region = self.setup()
        logger.debug('self.codeblock = %s', self.codeblock)
        self.doc_region = None

        if (Focus.score_selector(self.view, self.sel.begin(), 'fs_local') > 0):
            self.match = True
            self.search_region = self.sel
            if self.sel.empty():
                self.search_region = sublime.Region(self.sel.begin(), 
                                                    self.sel.begin() + 1)
            self.search_string = self.view.substr(self.search_region)
            logger.debug('self.search_string = %s', self.search_string)

        elif (Focus.score_selector(self.view, self.sel.begin(), 'comment') > 0):
            doc_matches = list()
            if (self.local_vars_doc_region and self.sel.intersects(self.local_vars_doc_region)):
                doc_matches = self.view.find_all(r"[A-Z]\s*[-=:]\s*[\s\S]*?\n(?=//\s*[A-Z]\s*[-=:]|//:Doc)")
            elif (self.arg_doc_region and self.sel.intersects(self.arg_doc_region)):
                doc_matches = self.view.find_all(r"[\{|]?[A-Z]\s*[-=:.]\s*[\s\S]*?\n(?=//\s*[\{|]?([A-Z]|\d{1,2})\s*[-=:]|//:Doc)")
            for r in doc_matches:
                if r.contains(self.sel):
                    match = re.search(r"([A-Z])\s*[-=:]\s*", self.view.substr(r))
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
            function_variables = self.codeblock.get_variables_from_function()
            regions.extend(function_variables[self.search_string].regions)
            arg_match = self.get_arg_match(self.search_string, self.arg_doc_region)
            if (arg_match is not None):
                regions.append(arg_match)
            local_match = self.get_local_var_match(self.search_string, self.local_vars_doc_region)
            if (local_match is not None):
                regions.append(local_match)

        return regions

    @EntityHighlighter.api_call
    def description(self, command):
        if (self.match and (command == self.HIGHLIGHT)):
            return 'Highlight uses of %s in %s' % (self.search_string, self.codeblock.codeblock_name)
        elif (self.match and (command == self.SELECT_ALL)):
            return 'Select all uses of %s in %s' % (self.search_string, self.codeblock.codeblock_name)
        else:
            return super(FSLocalHighlighter, self).description(command)

    def setup(self):
        codeblock = self.focus_file.get_codeblock(self.view)
        local_vars_doc_region = arg_doc_region = codeblock.documentation_region
        documentation = CodeBlockDocumentation(codeblock)

        try:
            local_vars_doc_region = documentation.doc_regions['Local Variables'].region
        except KeyError:
            pass

        try:
            arg_doc_region = documentation.doc_regions['Arguments'].region
        except KeyError:
            pass

        yield codeblock
        yield local_vars_doc_region
        yield arg_doc_region

    def get_arg_match(self, var, region):
        r = None
        arg_match = self.view.find(r"[\{|]?" + var + r"\s*[-=:.]\s*[\s\S]*?(?=\n//\s*[\{|]?([A-Z]|\d{1,2})\s*[-=:.]|\n//:Doc)", region.begin())
        if ((arg_match is not None) and region.intersects(arg_match)):
            string = self.view.substr(arg_match)
            if (string[0] in "{|"):
                r = sublime.Region(arg_match.begin()+1, arg_match.begin()+2)
            else:
                r = sublime.Region(arg_match.begin(), arg_match.begin()+1)
        return r

    def get_local_var_match(self, var, region):
        r = None
        local_var_match = self.view.find(var + r"\s*[-=:]\s*[\s\S]*?(?=\n//\s*[A-Z]\s*[-=:]|\n//:Doc)", region.begin())
        if ((local_var_match is not None) and region.intersects(local_var_match)):
            r = sublime.Region(local_var_match.begin(), local_var_match.begin()+1)
        return r
