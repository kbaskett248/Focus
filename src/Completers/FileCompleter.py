import os
import sublime

from ..tools import read_file
from .Completer import Completer

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class FileCompleter(Completer):
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

    CompleterInstances = dict()

    def __new__(cls, *args, **kwargs):
        if 'CompleterInstances' not in cls.__dict__.keys():
            cls.CompleterInstances = dict()
        return super().__new__(cls, *args, **kwargs)

    @classmethod
    @Completer.api_call
    def get_completer(cls, file_path, file_contents = None):
        try:
            c = cls.CompleterInstances[file_path]
            return cls.CompleterInstances[file_path]
        except KeyError:
            c = cls(file_path, file_contents)
            cls.CompleterInstances[file_path] = c
            return c

    @Completer.api_call
    def __init__(self, file_path, file_contents = None):
        super().__init__()
        self.file_path = file_path
        self.file_short_name = os.path.basename(self.file_path)
        self.file_contents = file_contents
        if self.file_contents is None:
            self.file_contents = read_file(file_path)
        self.file_update_time = self.get_file_update_time()

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
        if (cls.__name__ == 'FileCompleter'):
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
            completions = []
            for t in completion_types:
                completions.extend(self.completions[t])
        else:
            completions = list(self.completions)

        return (completions,
                sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    @classmethod
    @Completer.api_call
    def is_file_completer(cls):
        return True

    def get_file_update_time(self):
        return os.path.getmtime(self.file_path)

    @Completer.api_call
    def get_completions(self, completion_types, completion_queue, wait = False, **kwargs):
        """Populates completion_queue for Completers with matching completion_types.

        Keyword arguments:
        completion_types - A list of the requested completion types
        completion_queue - A Queue that holds the completions from each Completer
        wait - True to force completions to load synchronously.

        This function normally will not be overridden. 
        If the completer is set to load completions asynchronously (LoadAsync 
        is True), a thread is started to load the completions as long as wait
        is false. If completions should be loaded synchronously, or wait is
        True, completions are loaded in the current thread. load_completions 
        is called either way to load the completions. This implementation checks
        the modified date time of the file. If it has changed since the last
        time the contents of the file were loaded, the contents of the file are
        reloaded.

        """
        included_completions = set(completion_types).intersection(set(self.CompletionTypes))
        if not included_completions:
            return

        logger.debug('included_completions = %s', included_completions)

        t = self.get_file_update_time()
        if self.file_update_time != t:
            self.completions = None
            self.file_contents = read_file(file_path)
            self.file_update_time = t

        # If completions exist, put them on the queue
        if self.completions:
            completion_queue.put(self.filter_completions(included_completions, **kwargs))
            return
        # Otherwise, if we're not already loading completions, load them.
        elif not self.loading:
            # If completions should be loaded asynchronously, and we don't want 
            # to wait on them, spawn a thread to load them.
            if self.LoadAsync and not wait:
                self.loading = True
                kwargs['included_completions'] = included_completions
                self.loader_thread = threading.Thread(target = self.load_completions, kwargs = kwargs)
                self.loader_thread.start()
            # Otherwise, load them in the current thread
            else:
                self.loading = True
                self.load_completions(included_completions = included_completions, **kwargs)
                self.loading = False

        if self.loading:
            # If completions are loading and the thread is still active, return empty
            if ((self.loader_thread is None) or self.loader_thread.is_alive()):
                completion_queue.put(self.EmptyReturn)
                return
            # Otherwise, set loading to False
            else:
                self.loading = False
        # Add completions to queue and return
        completion_queue.put(self.filter_completions(included_completions, **kwargs))
        return

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.file_path)
        