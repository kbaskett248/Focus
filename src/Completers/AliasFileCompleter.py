import re

import sublime

from .FileCompleter import FileCompleter

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class AliasFileCompleter(FileCompleter):
    """Loads completions from a View."""

    EmptyReturn = ([], sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    CompletionTypes = [FileCompleter.CT_ALIAS]

    AliasMatcher = re.compile(r"\s*:Alias\s+([^\n()\t]+?) *$")

    @FileCompleter.api_call
    def load_completions(self, **kwargs):
        """Populate self.completions with Locals from an Include file."""
        self.completions = []
        for l in self.file_contents:
            if (l[:2] == '//'):
                continue

            match =AliasFileCompleter.AliasMatcher.match(l)
            if match is not None:
                self.completions.append(('@@%s()\t\tInclude' % match.group(1), '%s()' % match.group(1)))
        # logger.debug('Alias Completions: %s', self.completions)

        