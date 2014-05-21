import sublime

from ..FocusPlugin import FocusPlugin

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    
class EntityHighlighter(FocusPlugin):
    """docstring for DocLookup"""

    HIGHLIGHT = 'highlight'
    MOVE_FORWARD = 'move_forward'
    MOVE_BACKWARD = 'move_backward'
    CLEAR = 'clear'
    SELECT_ALL = 'select_all'

    HIGHLIGHT_DESCRIPTION = 'Highlight'
    MOVE_FORWARD_DESCRIPTION = 'Next Instance'
    MOVE_BACKWARD_DESCRIPTION = 'Previous Instance'
    CLEAR_DESCRIPTION = 'Clear Highlights'
    SELECT_ALL_DESCRIPTION = 'Select All Instances'

    @FocusPlugin.api_call
    def __init__(self, view, sel, scope_name, focus_file):
        self.view = view
        self.sel = sel
        self.scope_name = scope_name
        self.focus_file = focus_file
        self.match = False
        self.search_region = None
        self.search_string = None

    @FocusPlugin.api_call
    def check(self, view, sel, scope_name, focus_file):
        return self.match

    @FocusPlugin.api_call
    def get_regions(self):
        return list()

    def highlight(self):
        if self.match:
            regions = self.get_regions()
            self.add_regions(regions)
            settings = self.view.settings()
            settings.set('focus_highlight', True)

    def add_regions(self, regions):
        self.view.add_regions('focus_highlighter', regions, 'string', 'circle',
                              sublime.DRAW_NO_FILL | sublime.PERSISTENT)

    def move(self, forward = True):
        settings = self.view.settings()
        if settings.get('focus_highlight', False):
            selection = self.view.sel()
            sel = selection[0]
            regions = self.view.get_regions('focus_highlighter')
            regions.sort()
            next = regions[0]
            prev = regions[-1]
            begin = sel.begin()
            end = sel.end()
            regions_to_remove = list()

            for r in regions:
                if r.empty():
                    regions_to_remove.append(r)
                elif r.end() <= begin:
                    prev = r
                elif r.begin() >= end:
                    next = r
                    break

            if regions_to_remove:
                for r in regions_to_remove:
                    regions.remove(r)
                self.add_regions(regions)

            selection.clear()
            if forward:
                selection.add(next)
            else:
                selection.add(prev)
            self.view.show(selection[0], True)


    def clear_regions(self):
        settings = self.view.settings()
        if settings.get('focus_highlight', False):
            self.view.erase_regions('focus_highlighter')
            settings.erase('focus_highlight')
            self.highlight_on = False

    def select_all(self):
        settings = self.view.settings()
        if settings.get('focus_highlight', False):
            regions = self.view.get_regions('focus_highlighter')
            sel = self.view.sel()
            sel.clear()
            sel.add_all(regions)

    def __str__(self):
        return self.__class__.__name__

    def description(self, command):
        if (command == self.HIGHLIGHT):
            return self.HIGHLIGHT_DESCRIPTION
        elif (command == self.MOVE_FORWARD):
            return self.MOVE_FORWARD_DESCRIPTION
        elif (command == self.MOVE_BACKWARD):
            return self.MOVE_BACKWARD_DESCRIPTION
        elif (command == self.CLEAR):
            return self.CLEAR_DESCRIPTION
        elif (command == self.SELECT_ALL):
            return self.SELECT_ALL_DESCRIPTION
        else:
            return 'Unsupported Command'
