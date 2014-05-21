import Focus
from .EntityHighlighter import EntityHighlighter

class LocalHighlighter(EntityHighlighter):
    """docstring for DocLookup"""
    
    def check(self):
        if (Focus.score_selector(self.view, self.sel.begin(), 'focus_local') > 0):
            for r in Focus.find_by_selector(self.view, 'focus_local'):
                if r.contains(self.sel):
                    self.match = True
                    self.search_region = r
                    self.search_string = self.view.substr(r)
                    break

        return self.match

    def get_regions(self):
        regions = list()

        if self.match:
            for r in Focus.find_by_selector(self.view, 'focus_local'):
                substr = self.view.substr(r)
                if (substr == self.search_string):
                    regions.append(r)

        return regions

    def description(self, command):
        if self.match:
            if (command == self.HIGHLIGHT):
                return 'Highlight uses of %s' % self.search_string
            elif (command == self.SELECT_ALL):
                return 'Select all uses of %s' % self.search_string
            elif (command == self.MOVE_FORWARD):
                return 'Next instance of %s' % self.search_string
            elif (command == self.MOVE_BACKWARD):
                return 'Previous instance of %s' % self.search_string
            elif (command == self.CLEAR):
                return 'Clear Highlights'
            else:
                return 'Unsupported Command'
        else:
            return super(LocalHighlighter, self).description(command)
