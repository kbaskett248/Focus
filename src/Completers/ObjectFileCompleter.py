import re

import sublime

from .FileCompleter import FileCompleter

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class ObjectFileCompleter(FileCompleter):
    """Loads completions from a an Include File."""

    EmptyReturn = ([], sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    CompletionTypes = [FileCompleter.CT_OBJECT,
                       FileCompleter.CT_RECORD,
                       FileCompleter.CT_KEY,
                       FileCompleter.CT_FIELD]

    CheckOrder = ('Object', 'Record', 'Field', 'Key')
    
    LineMatcher = re.compile(r'\s*:([A-Za-z0-9]+)\s*(.+?)\s*$')

    @FileCompleter.api_call
    def load_completions(self, **kwargs):
        """Populate self.completions with Locals from an Include file."""
        logger.debug('Loading object completions from %s', self.file_path)
        self.completions = dict()
        in_datadef = False
        for l in self.file_contents:
            if l[0] == '#':
                if l.startswith('#DataDef'):
                    in_datadef = True
                else:
                    in_datadef = False
                continue
            elif in_datadef:
                match = ObjectFileCompleter.LineMatcher.match(l)
                if match is not None:
                    for t in ObjectFileCompleter.CheckOrder:
                        if t == match.group(1):
                            v = match.group(2)
                            if (t == 'Object'):
                                object_ = v
                            else:
                                v = '%s.%s' % (object_, v)
                            try:
                                self.completions[t].add((v + '\t\tInclude', v))
                            except KeyError:
                                self.completions[t] = set()
                                self.completions[t].add((v + '\t\tInclude', v))
                            break
        logger.debug('Object Completions: %s', self.completions)

        