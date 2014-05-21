import threading

from ..FocusPlugin import FocusPlugin

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class CompletionLoader(threading.Thread, FocusPlugin):

    Types = ()

    def __init__(self, ring):
        super(CompletionLoader, self).__init__(daemon = True)
        self.ring = ring
        self.completions = dict()
        for t in self.Types:
            self.completions[t] = set()
        self.stop_event = threading.Event()
    
    def run(self):
        self.load_completions()
        self.stop()

    def __str__(self):
        return self.__class__.__name__

    def load_completions(self):
        pass

    def store_completions(self):
        result = False
        if not self.is_alive():
            for t in self.Types:
                self.ring.ring_completions[t] = self.completions[t]
            result = True
        return result

    def stop(self):
        logger.debug('Stopping Completion Loader Thread')
        self.stop_event.set()

    def stopped(self):
        return self.stop_event.isSet()
