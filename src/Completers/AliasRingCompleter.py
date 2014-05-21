import os
import re

import sublime

from .RingCompleter import RingCompleter

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class AliasRingCompleter(RingCompleter):
    """Loads completions from a View."""

    EmptyReturn = ([], sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    CompletionTypes = [RingCompleter.CT_ALIAS]

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
            # logger.debug('enable_completer = %s', ring.check_file_existence(cls.PartialAliasPath))
            if ring.check_file_existence(cls.PartialAliasPath):
                return True
            elif ring.check_file_existence(os.path.join('System', 'Translators', 'AliasList0.mtIo')):
                return True
            else:
                return False
        return True

    @RingCompleter.api_call
    def load_completions(self, **kwargs):
        """Loads alias completions from the ring."""
        logger.debug('Loading Alias Ring Completions')
        self.ring.load_aliases()
        self.completions = set([('@@%s()' % a, '%s()' % a) for a in self.ring.alias_lookup.keys()])
        logger.debug('Done Loading Alias Ring Completions')
        