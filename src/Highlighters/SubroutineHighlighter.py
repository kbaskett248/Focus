import Focus
from .EntityHighlighter import EntityHighlighter

class SubroutineHighlighter(EntityHighlighter):
    """docstring for DocLookup"""
    
    @EntityHighlighter.api_call
    def check(self):
        if (Focus.score_selector(self.view, self.sel.begin(), 'subroutine_name') > 0):
            for r in Focus.find_by_selector(self.view, 'subroutine_name'):
                if r.contains(self.sel):
                    self.match = True
                    self.search_region = r
                    self.search_string = self.view.substr(r)
                    break

        return self.match

    @EntityHighlighter.api_call
    def get_regions(self):
        regions = list()

        if self.match:
            for r in Focus.find_by_selector(self.view, 'subroutine_name'):
                substr = self.view.substr(r)
                if (substr == self.search_string):
                    regions.append(r)

        return regions

    @EntityHighlighter.api_call
    def description(self, command):
        if (self.match and (command == self.HIGHLIGHT)):
            return 'Highlight uses of %s' % self.search_string
        elif (self.match and (command == self.SELECT_ALL)):
            return 'Select all uses of %s' % self.search_string
        else:
            return super(SubroutineHighlighter, self).description(command)
