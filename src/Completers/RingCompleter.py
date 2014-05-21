import sublime

from .Completer import Completer

class RingCompleter(Completer):
    """Loads completions from a View."""

    """The value to return for a matching completer when no completions are 
    found or the completions are not loaded. 

    Should be overridden by extending classes.

    Use None if no completions should allow showing the built-in sublime 
    completions. Use an empty list if no completions should block the 
    built-in sublime completions.
    """
    EmptyReturn = []

    """True to load completions asynchronously."""
    LoadAsync = True

    """A list of the types of completions returned by this Completer.

    Should be overridden by extending classes."""
    CompletionTypes = []

    @Completer.api_call
    def __init__(self, ring):
        super(RingCompleter, self).__init__()
        self.ring = ring

    @classmethod
    @Completer.api_call
    def enable_completer(cls, ring_file = None, ring = None, file_path = None):
        """Returns True if the completer should be enabled.

        Keyword arguments:
        view - A sublime.View object
        ring - A Focus.Ring object
        file_path - The path to a file

        This function must be overridden by extending classes.
        This function is called at several times throughout the Completer process:
        1. After the Completer classes are initially loaded, this is called
           with no arguments in case we can filter out the completer there.
        2. Before an instance of a RingCompleter is created, this is called
           with the ring argument.
        3. Before an instance of a ViewCompleter is created, this is called
           with the view and ring arguments.
        4. Before an instance of a FileCompleter is created, this is called
           with the ring and file_path arguments.

        """
        if (cls.__name__ == 'RingCompleter'):
            return False
        return True

    @Completer.api_call
    def load_completions(self, view = None, **kwargs):
        """Populate self.completions with the completions handled by this completer."""
        self.completions = set()

    @classmethod
    @Completer.api_call
    def is_ring_completer(cls):
        return True
        