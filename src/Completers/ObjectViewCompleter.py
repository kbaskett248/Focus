import sublime

from .ViewCompleter import ViewCompleter
from ..FocusFile import FocusFile

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class ObjectViewCompleter(ViewCompleter):
    """Loads object completions for Temp DataDefs defined within a view."""

    EmptyReturn = ([], sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    CompletionTypes = [ViewCompleter.CT_OBJECT,
                       ViewCompleter.CT_RECORD,
                       ViewCompleter.CT_FILE,
                       ViewCompleter.CT_KEY,
                       ViewCompleter.CT_FIELD]

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
    def load_completions(self, view = None, included_completions = [], **kwargs):
        """Loads object completions for Temp DataDefs defined within the view."""
        self.completions = set()
        for t in included_completions:
            self.completions.update([(x,) for x in self.ring_file.get_object_completions_from_file(view, t)])
        # logger.debug('Object view completions: %s', self.completions)

        