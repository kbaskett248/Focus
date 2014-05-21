import os

from .CompletionLoader import CompletionLoader
from ..tools import read_file

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class StateLoader(CompletionLoader):

    Types = ['State']

    def load_completions(self):
        logger.debug('Running State Loader thread')
        if self.ring.modern_ring:
            state_variables_path = self.ring.get_file_path(
                os.path.join('Environment', 'StateVariables.txt')
                )
        else:
            state_variables_path = self.ring.get_file_path(
                os.path.join('!Focus', 'Environment', 'StateVariables.txt')
                )
        try:
            self.completions[self.Types[0]] = set(read_file(state_variables_path))
        except FileNotFoundError:
            logging.warning('%s could not be found', state_variables_path)
            logging.warning('State Variable completions could not be loaded.')

        logger.debug('State Loader thread ending')
