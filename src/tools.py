import errno
import inspect
import os
import re

DEBUG_ON = True
DETAIL_LEVEL = 3

def debug(value, level=2):
    if DEBUG_ON:
        if (level <= DETAIL_LEVEL):
            frm = inspect.stack()[1]
            mod = inspect.getmodule(frm[0])
            print( '[{0}.{1}(), {2}] {3}'.format(mod.__name__, frm[3], frm[2], value) )

def read_file(fileName, filter_out_empty_lines = True):
    """Reads in a file, returning each line in a list. Optionally removes empty lines."""
    elements = []
    f = open(fileName, 'r')
    for line in f:
        if ((line != '\n') or not filter_out_empty_lines):
            elements.append(line.replace('\n',''))
    f.close()
    return elements

def get_env(environ_name):
    temp = os.getenv(environ_name)
    if (temp is None):
        if ('ProgramFiles' in environ_name) or ('ProgramW6432' in environ_name):
            temp = os.getenv('ProgramFiles')
    return temp

def create_dir(dir):
    # Make the directory if it doesn't exist. If it does, just eat exception
    print("Creating dir " + dir)
    try:
        os.makedirs(dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

def merge_paths(base, *args):
    base = os.path.normpath(base)
    if ((args is not None) and isinstance(args[0], tuple)):
        args = args[0]

    if (args is None):
        return base
    else:
        if (len(args) > 1):
            suffix = merge_paths(args[0], args[1:])
        else:
            suffix = os.path.normpath(args[0])
        if (suffix[0] == os.sep):
            suffix = suffix[1:]
        suffix_dirs = suffix.split(os.sep)
        common_path = ''
        path = suffix_dirs.pop(0)
        while ((path in base) and suffix_dirs):
            common_path = path
            path = os.path.join(path, suffix_dirs.pop(0))
        if (path in base):
            common_path = path
        if base.endswith(common_path):
            base = base.replace(common_path, '')
        return os.path.join(base, suffix)

class MultiMatch(object):
    """Object that allows you to perform multiple matches against a single string."""

    def __init__(self, match_string = "", patterns = dict()):
        # super(MultiMatch, self).__init__()
        self.ordered_patterns = list()
        self.named_patterns = dict()
        self.match_string = match_string
        self.order_num = 0
        for k, v in patterns.items():
            self.add_pattern( k, v, True )
        
    def add_pattern(self, name, pattern, compiled = False):
        debug( self.named_patterns, 4 )

        m = MultiMatch.AgnosticMatch( pattern, compiled )

        if (name in self.named_patterns.keys()):
            i = self.named_patterns[name]
            debug( 'name: {0}, index: {1}, length: {2}'.format( 
                name, i, len(self.ordered_patterns) ), 4 )
            self.ordered_patterns[i] = m
        else:
            self.ordered_patterns.append( m )
            self.named_patterns[name] = len( self.ordered_patterns ) - 1

    @property
    def match_keys(self):
        return self.named_patterns.keys()

    def named_match(self, name):
        result = False

        if (name in self.named_patterns.keys()):
            i = self.named_patterns[name]
            result = self.index_match( i )

        return result

    def ordered_match(self):
        result = None

        if (self.order_num < len(self.ordered_patterns)):
            result = self.index_match(self.order_num)

        self.order_num += 1
        return result

    def index_match(self, index):
        p = self.ordered_patterns[index]
        self.rematch = p.match( self.match_string )
        return bool(self.rematch)

    def reset(self):
        self.order_num = 0

    def group(self, i):
        return self.rematch.group(i)

    def span(self, i):
        return self.rematch.span(i)

    @property
    def match_string(self):
        return self._match_string

    @match_string.setter
    def match_string(self, value):
        self._match_string = value
        self.reset()

    @property
    def num_patterns(self):
        return len(self.ordered_patterns)

    @property
    def current_pattern(self):
        return self.ordered_patterns[self.order_num]

    def named_pattern(self, name):
        return self.ordered_patterns[self.named_patterns[name]]

    @property
    def current_match(self):
        return self.rematch
    

    class AgnosticMatch(object):
        """An object that can match via compiled or non-compiled regular expressions."""
        def __init__(self, pattern, compiled = False):
            super(MultiMatch.AgnosticMatch, self).__init__()
            self._pattern = pattern
            self._compiled = None
            self.compiled = compiled
            
        @property
        def compiled(self):
            return self._compiled

        @compiled.setter
        def compiled(self, value):
            if ((not self._compiled) or (self._compiled == None)) and value:
                self._compiled = value
                self._matcher = re.compile(self.pattern)

        @property
        def pattern(self):
            return self._pattern

        def match(self, match_string):
            if self.compiled:
                return self._matcher.match( match_string )
            else:
                return re.match( self._pattern, match_string )

        def __str__(self):
            return 'Pattern: %s; compiled: %s' % (self.pattern, self.compiled)
