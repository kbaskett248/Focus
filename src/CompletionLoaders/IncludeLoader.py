import os

from .CompletionLoader import CompletionLoader

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class IncludeLoader(CompletionLoader):

    Types = ['Include', 'External Pageset']

    def load_completions(self):
        logger.debug('Running Include Loader thread')
        pgm_source = os.path.join(self.ring.pgm_path(False), 'PgmSource')

        for path, dirs, files in os.walk(pgm_source):
            for f in files:
                f_lower = f.lower()
                if self.stopped():
                    logger.debug('Include Loader thread stopped')
                    return
                elif (f_lower.endswith('.i.focus') or f_lower.endswith('.d.focus')):
                    self.completions[self.Types[0]].add(os.path.join(path, f))
                elif f_lower.endswith('.e.focus'):
                    self.completions[self.Types[1]].add(os.path.join(path, f))
                    
        logger.debug('Include Loader thread ending')