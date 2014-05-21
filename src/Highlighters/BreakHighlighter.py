import Focus
from .EntityHighlighter import EntityHighlighter

class BreakHighlighter(EntityHighlighter):

    HIGHLIGHT_DESCRIPTION = 'Highlight all Breaks'
    MOVE_FORWARD_DESCRIPTION = 'Next Break'
    MOVE_BACKWARD_DESCRIPTION = 'Previous Break'
    SELECT_ALL_DESCRIPTION = 'Select All Instances'
    
    @EntityHighlighter.api_call
    def check(self):
        if (Focus.score_selector(self.view, self.sel.begin(), 'debug_function') > 0):
            self.match = True
            self.search_region = self.sel
            self.search_string = 'Break'

        return self.match

    @EntityHighlighter.api_call
    def get_regions(self):
        regions = list()

        if self.match:
            regions = Focus.find_by_selector(self.view, 'debug_function')

        return regions
