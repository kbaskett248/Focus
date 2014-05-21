import os
from queue import Queue
import re
import threading

from .CompletionLoader import CompletionLoader
from ..tools import read_file

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class ObjectLoader(CompletionLoader):

    Types = ['Object', 'Record', 'File', 'Index', 'IndexKey', 'Key',
             'Field', 'LongLock']

    def __init__(self, ring):
        super(ObjectLoader, self).__init__(ring)
        self.file_queue = Queue()

    def load_completions(self):
        logger.debug('Running Object Loader thread')

        datadefs_path = os.path.join(self.ring.datadefs_path, 'Standard')
        if os.path.isdir(datadefs_path):
            for filename in os.listdir(datadefs_path):
                if self.stopped():
                    logger.debug('Stopping Object Loader thread')
                    return
                elif (filename.lower().endswith('.focus')):
                    self.file_queue.put(os.path.join(datadefs_path, filename))

        logger.debug('Added all Datadefs to file queue')
        logger.debug('Datadefs: %s', self.file_queue)

        if not self.file_queue.empty():
            threads = set()
            for i in range(2):
                t = ObjectLoader.DatadefProcessor(self)
                t.start()
                threads.add(t)
            for t in threads:
                t.join()

        logger.debug('Object Loader thread ending')

    class DatadefProcessor(threading.Thread):
        """docstring for DatadefProcessor"""
        
        def __init__(self, parent):
            super(ObjectLoader.DatadefProcessor, self).__init__()
            self.file_queue = parent.file_queue
            self.completions = parent.completions

        def run(self):
            while not self.file_queue.empty():
                self.process_datadef(self.file_queue.get())

        def process_datadef(self, filename):
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
                            self.completions[t].add(v)
                            break

            