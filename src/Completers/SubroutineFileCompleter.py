import re

import sublime

from .FileCompleter import FileCompleter

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class SubroutineFileCompleter(FileCompleter):
    """Loads completions from a View."""

    EmptyReturn = ([], sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    LoadAsync = False

    CompletionTypes = [FileCompleter.CT_SUBROUTINE]

    SubroutineMatcher = re.compile(r":Code\s+([^\n()\t]+?) *$")

    @FileCompleter.api_call
    def load_completions(self, **kwargs):
        """Populate self.completions with subroutines from an Include file."""
        self.completions = []
        for l in self.file_contents:
            if (l[:2] == '//'):
                continue

            match = SubroutineFileCompleter.SubroutineMatcher.match(l)
            if match is not None:
                self.completions.append((match.group(1) + '\t\tInclude', match.group(1)))
        # logger.debug('Subroutine Completions: %s', self.completions)

        