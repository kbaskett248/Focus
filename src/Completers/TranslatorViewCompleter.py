import re

import sublime

from .ViewCompleter import ViewCompleter
from ..FocusFile import FocusFile
import Focus

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class TranslatorViewCompleter(ViewCompleter):
    """Loads object completions for Temp DataDefs defined within a view."""

    EmptyReturn = ([], )

    CompletionTypes = [ViewCompleter.CT_TRANSLATOR]

    @classmethod
    @ViewCompleter.api_call
    def enable_completer(cls, ring_file = None, ring = None, file_path = None):
        """Returns True if the completer should be enabled.

        Keyword arguments:
        ring_file - A Focus.RingFile object
        ring - A Focus.Ring object
        file_path - The path to a file

        This function is called at several times throughout the Completer process:
        1. After the Completer classes are initially loaded, this is called
           with no arguments in case we can filter out the completer there.
        2. Before an instance of a RingCompleter is created, this is called
           with the ring argument.
        3. Before an instance of a ViewCompleter is created, this is called
           with the ring_file and ring arguments.
        4. Before an instance of a FileCompleter is created, this is called
           with the ring and file_path arguments.

        """
        if (ring_file is not None):
            if not (isinstance(ring_file, FocusFile)):
                return False

        return True

    @ViewCompleter.api_call
    def load_completions(self, view = None, included_completions = [], **kwargs):
        """Loads object completions for Temp DataDefs defined within the view."""
        self.completions = set()

        selection = view.sel()[0]
        preceding_line = sublime.Region(view.line(selection.begin()).begin(), selection.end())
        preceding_line_string = view.substr(preceding_line)
        match = re.match(r'^(\s*)((:|#)[A-Za-z0-9]*|[A-Za-z0-9]+)(\s*)(.*)$', preceding_line_string)
        if match and (match.group(3) == '#'):
            return

        tree = self.ring_file.build_translator_tree(view, True)
        # logger.debug('tree = %s', tree)
        current_item = tree[-1]

        partial_completions = Focus.TranslatorCompletions
        # logger.debug('partial_completions = %s', partial_completions)

        for k, v in tree:
            try:
                translator = partial_completions[k]
                print(k, translator)
            except KeyError:
                if ((k == current_item[0]) and (v == current_item[1])):
                    if ((match is None) or ((match.group(4) == '') and (match.group(5) == ''))):
                        self.completions = set([(x,) for x in translator.children.keys()])
                return
            else:
                partial_completions = translator.children
                # logger.debug('partial_completions = %s', partial_completions)

        if ((match is None) or ((match.group(4) == '') and (match.group(5) == ''))):
            # logger.debug('getting children')
            self.completions = set([(x,) for x in translator.children.keys()])
        else:
            # logger.debug('getting completions')
            self.completions = set([(x,) for x in translator.completions])
        logger.debug(self.completions)
        return
        