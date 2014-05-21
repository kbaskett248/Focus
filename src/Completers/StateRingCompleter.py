import os

import sublime

from .RingCompleter import RingCompleter
from ..tools import read_file

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class StateRingCompleter(RingCompleter):
    """Loads completions from a View."""

    EmptyReturn = ([], sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    CompletionTypes = [RingCompleter.CT_STATE]

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
            if StateRingCompleter.get_state_variables_path(ring) is None:
                return False
        return True

    @RingCompleter.api_call
    def load_completions(self, **kwargs):
        """Loads state variable completions from the ring."""
        try:
            self.completions = set([(v, ) for v in read_file(StateRingCompleter.get_state_variables_path(self.ring))])
        except FileNotFoundError:
            logging.warning('%s could not be found', state_variables_path)
            logging.warning('State Variable completions could not be loaded.')

    @staticmethod
    def get_state_variables_path(ring):
        """Returns the path to the list of state variables in the ring."""
        if ring.modern_ring:
            state_variables_path = ring.get_file_path(
                os.path.join('Environment', 'StateVariables.txt')
                )
        else:
            state_variables_path = ring.get_file_path(
                os.path.join('!Focus', 'Environment', 'StateVariables.txt')
                )
        logger.debug('state_variables_path = %s', state_variables_path)
        try:
            if os.path.exists(state_variables_path):
                return state_variables_path
        except TypeError:
            return None
        