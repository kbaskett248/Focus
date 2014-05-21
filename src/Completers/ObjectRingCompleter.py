import os
from queue import Queue
import re
import threading

import sublime

from .RingCompleter import RingCompleter
from ..tools import read_file

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class ObjectRingCompleter(RingCompleter):
    """Loads completions from a View."""

    EmptyReturn = ([], sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    CompletionTypes = [RingCompleter.CT_OBJECT,
                       RingCompleter.CT_RECORD,
                       RingCompleter.CT_FILE,
                       RingCompleter.CT_INDEX,
                       RingCompleter.CT_INDEXKEY,
                       RingCompleter.CT_KEY,
                       RingCompleter.CT_FIELD,
                       RingCompleter.CT_LONGLOCK]

    PartialAliasPath = os.path.join('System', 'Translators', 'AliasList.mtIo')

    @classmethod
    @RingCompleter.api_call
    def enable_completer(cls, ring_file = None, ring = None, file_path = None):
        """Returns True if the completer should be enabled.

        Keyword arguments:
        view - A sublime.View object
        ring - A Focus.Ring object
        file_path - The path to a file

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
        if ring is not None:
            datadefs_path = os.path.join(ring.datadefs_path, 'Standard')
            if not os.path.isdir(datadefs_path):
                return False
            else:
                for filename in os.listdir(datadefs_path):
                    if filename.lower().endswith('.focus'):
                        break
                else:
                    return False
        return True

    @RingCompleter.api_call
    def load_completions(self, **kwargs):
        """Loads the object completions from the ring.

        Gathers all the Datadef files and then spawns DatadefProcessor threads 
        to process them.

        """
        logger.debug('Running Object Loader thread')

        file_queue = Queue()

        datadefs_path = os.path.join(self.ring.datadefs_path, 'Standard')
        if not os.path.isdir(datadefs_path):
            return

        for filename in os.listdir(datadefs_path):
            if filename.lower().endswith('.focus'):
                file_queue.put(os.path.join(datadefs_path, filename))

        if file_queue.empty():
            return

        threads = set()
        completion_queue = Queue()
        for i in range(4):
            t = ObjectRingCompleter.DatadefProcessor(file_queue, completion_queue)
            t.start()
            threads.add(t)
        self.completions = dict()
        for t in threads:
            t.join()
            c = completion_queue.get()
            for t, s in c.items():
                try:
                    self.completions[t].update(s)
                except KeyError:
                    self.completions[t] = s

        logger.debug('Object Loader thread ending')

    class DatadefProcessor(threading.Thread):
        """Reads Datadef files and parses the relevant details."""
        
        def __init__(self, file_queue, completion_queue):
            """Creates a DatadefProcessor instance.

            Keyword arguments:
            file_queue - List of file paths for Datadef files.
            completion_queue - Once all files have been processed, completions
            gathered by this object are added to this queue.

            """
            super(ObjectRingCompleter.DatadefProcessor, self).__init__()
            self.file_queue = file_queue
            self.completion_queue = completion_queue
            self.completions = dict()

        def run(self):
            """Processes Datadefs until the queue is empty, then adds completions to the queue."""
            while not self.file_queue.empty():
                self.process_datadef(self.file_queue.get())
            self.completion_queue.put(self.completions)

        def process_datadef(self, filename):
            """Extracts relevant information from the given Datadef file."""
            check_order = ('Field', 'Key', 'IndexKey', 'Record', 'Index', 'File',
                           'LongLock', 'Object')
            check_line = re.compile(r'\s*:.+$')
            for l in read_file(filename):
                if check_line.match(l):
                    l = l.strip()
                    for t in check_order:
                        if l.startswith(':%s ' % t):
                            v = l[(len(t)+1):].strip()
                            if (t == 'Object'):
                                object_ = v
                            elif (t == 'Index'):
                                index = '%s.%s' % (object_, v)
                                v = index
                            elif (t == 'IndexKey'):
                                v = '%s.%s' % (index, v)
                            else:
                                v = '%s.%s' % (object_, v)
                            try:
                                self.completions[t].add((v,))
                            except KeyError:
                                self.completions[t] = set()
                                self.completions[t].add((v,))
                            break

        