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

class IncludeRingCompleter(RingCompleter):
    """Loads completions from a View."""

    EmptyReturn = ([], sublime.INHIBIT_EXPLICIT_COMPLETIONS | sublime.INHIBIT_WORD_COMPLETIONS)

    CompletionTypes = [RingCompleter.CT_INCLUDE_FILE,
                       RingCompleter.CT_EXTERNAL_PAGESET]

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
            pgm_source = os.path.join(ring.pgm_path(False), 'PgmSource')
            if not os.path.isdir(pgm_source):
                return False
            else:
                for path, dirs, files in os.walk(pgm_source):
                    for f in files:
                        f_lower = f.lower()
                        if (f_lower.endswith('.i.focus') or 
                            f_lower.endswith('.d.focus') or 
                            f_lower.endswith('.e.focus')):
                            break
                    else:
                        continue
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
        logger.debug('Loading Include File Completions')
        self.completions = dict()
        self.completions[RingCompleter.CT_INCLUDE_FILE] = set()
        self.completions[RingCompleter.CT_EXTERNAL_PAGESET] = set()

        pgm_source = os.path.join(self.ring.pgm_path(False), 'PgmSource')

        for path, dirs, files in os.walk(pgm_source):
            for f in files:
                f_lower = f.lower()
                if (f_lower.endswith('.i.focus') or f_lower.endswith('.d.focus')):
                    self.completions[RingCompleter.CT_INCLUDE_FILE].add(os.path.join(path, f))
                elif f_lower.endswith('.e.focus'):
                    self.completions[RingCompleter.CT_EXTERNAL_PAGESET].add(os.path.join(path, f))

        logger.debug('Done Loading Include File Completions')

   

        