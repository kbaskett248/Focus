import sublime

import Focus
from .ViewCompleter import ViewCompleter
from ..FocusFile import FocusFile

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class AliasViewCompleter(ViewCompleter):
    """Loads aliases defined within a view."""

    EmptyReturn = ([], sublime.INHIBIT_EXPLICIT_COMPLETIONS | sublime.INHIBIT_WORD_COMPLETIONS)

    CompletionTypes = [ViewCompleter.CT_ALIAS]

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
            if (ring_file.filename is not None):
                if ('!DictionarySource' in ring_file.filename):
                    return False
                elif not (isinstance(ring_file, FocusFile)):
                    return False

        return True

    @ViewCompleter.api_call
    def load_completions(self, view = None, **kwargs):
        """Loads the aliases defined within the view."""
        self.completions = set()
        for x in [view.substr(x) for x in Focus.find_by_selector(view, 'alias_definition')]:
            # if not x[:2] == '@@':
            self.completions.add(('@@%s()' % x, '%s()' % x))
        # logger.debug('Alias Completions: %s', self.completions)

        