import sublime

from .Completer import Completer

class ViewCompleter(Completer):
    """Loads completions from a View."""

    """The value to return for a matching completer when no completions are 
    found or the completions are not loaded. 

    Should be overridden by extending classes.

    Use None if no completions should allow showing the built-in sublime 
    completions. Use an empty list if no completions should block the 
    built-in sublime completions.
    """
    EmptyReturn = ([], )

    """True to load completions asynchronously."""
    LoadAsync = False

    """A list of the types of completions returned by this Completer.

    Should be overridden by extending classes."""
    CompletionTypes = []

    @Completer.api_call
    def __init__(self, ring_file):
        # try:
        super(ViewCompleter, self).__init__()
        # except Exception as e:
        #     print(self)
        #     print(self.__class__)
        #     print(self.__class__.__mro__)
        #     print(self.__class__.__bases__)
        #     raise e
        self.ring_file = ring_file

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
        if (cls.__name__ == 'ViewCompleter'):
            return False
        return True

    @Completer.api_call
    def load_completions(self, view = None, **kwargs):
        """Populate self.completions with the completions handled by this completer."""
        self.completions = set()

    @Completer.api_call
    def filter_completions(self, completion_types, **kwargs):
        """Filters and returns the loaded completions based on the completion types requested.

        Keyword arguments:
        completion_types - The types of completions that should be returned in 
                           this instance.

        This function can be overridden by extending classes, but it usually
        will not need to be. self.completions can be either a dict datatype 
        or a standard iterable. Completions are cleared by this function since
        ViewCompleters usually won't cache them.

        """
        if isinstance(self.completions, dict):
            completions = set()
            for t in completion_types:
                completions.update(self.completions[t])
        else:
            completions = set(self.completions)

        self.completions = None
        return (completions,
                sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    @classmethod
    @Completer.api_call
    def is_view_completer(cls):
        return True
        