from .CompletionLoader import CompletionLoader
from .. import FocusLanguage

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class SystemLoader(CompletionLoader):

    Types = ['System']

    def load_completions(self):
        logger.debug('Running System Loader thread')
        self.completions[self.Types[0]] = set(FocusLanguage.SYSTEM_VARIABLES)
        logger.debug('System Loader thread ending')
