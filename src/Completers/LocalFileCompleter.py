import re

import sublime

from .FileCompleter import FileCompleter

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class LocalFileCompleter(FileCompleter):
    """Loads completions from a View."""

    EmptyReturn = ([], sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    CompletionTypes = [FileCompleter.CT_FOCUS_LOCAL]

    LocalMatcher = re.compile(r"@(Get|Put)Local\(([A-Za-z0-9._\-]+)\)")

    @FileCompleter.api_call
    def load_completions(self, **kwargs):
        """Populate self.completions with Locals from an Include file."""
        self.completions = []
        for l in self.file_contents:
            if (l[:2] == '//'):
                continue

            match = LocalFileCompleter.LocalMatcher.match(l)
            if match is not None:
                self.completions.append((match.group(2) + '\t\tInclude', match.group(2)))
        # logger.debug('Local Completions: %s', self.completions)

        