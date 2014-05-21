import os
import re

from .CompletionLoader import CompletionLoader

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class AliasLoader(CompletionLoader):

    Types = ['Alias']

    def load_completions(self):
        logger.debug('Running Alias Loader thread')
        self.lookup = dict()

        partial_path = os.path.join('System', 'Translators', 'AliasList.mtIo')
        file_existence = self.ring.check_file_existence(partial_path)

        if file_existence:
            alias_list_path = self.ring.get_file_path(partial_path)
            
            f = open(alias_list_path, 'r')
            contents = f.read()
            f.close()

            if self.stopped():
                logger.debug('Alias Loader thread stopped')
                return

            matches = re.findall(
                r'{start}(.+?){sep}.+?{sep}(.+?){sep}(.+?)({sep}.*?)?{end}'.format(
                    start = chr(1), sep = chr(3), end = chr(2)),
                contents)

            self.lookup = {a[0]: (a[2], a[1]) for a in matches}
            self.completions[self.Types[0]] = set([a + '()' for a in self.lookup.keys()])
            logger.debug('Alias Loader thread ending')

    def store_completions(self):
        logger.debug('Storing completions for Aliases')
        result = False
        if not self.is_alive():
            for t in self.Types:
                self.ring.ring_completions[t] = self.completions[t]
            self.ring.alias_lookup = self.lookup
            result = True
        return result