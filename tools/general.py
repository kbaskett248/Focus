# Contains general purpose tools used by many modules

from collections import OrderedDict, namedtuple
import errno
import logging
import os
import re
import sys


logger = logging.getLogger(__name__)


class LimitedSizeDict(OrderedDict):
    """
    A dictionary with a limited number of slots. Items are removed in the order
    they were added.

    """

    def __init__(self, *args, **kwargs):
        self.size_limit = kwargs.pop("size_limit", None)
        super().__init__(*args, **kwargs)
        self._check_size_limit()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._check_size_limit()

    def __getitem__(self, key):
        self.move_to_end(key)
        return super().__getitem__(key)

    def _check_size_limit(self):
        if self.size_limit is not None:
            while len(self) > self.size_limit:
                self.popitem(last=False)

    def update(self, other):
        super().update(other)
        self._check_size_limit()


MatchResult = namedtuple("MatchResult", ['span', 'string'])


def read_file(filename, filter_out_empty_lines=True):
    """
    Reads in a file, returning each line in a list. Optionally removes empty
    lines.

    """
    return [line for line in read_file_iter(filename, filter_out_empty_lines)]


def read_file_iter(filename, filter_out_empty_lines=True):
    """Iterates over the lines in a file."""
    with open(filename, 'r') as f:
        for line in f:
            if ((line != '\n') or not filter_out_empty_lines):
                yield line.replace('\n', '')


def _get_match(reg_ex, string, op, flags=0):
    if isinstance(reg_ex, str):
        return getattr(re, op)(reg_ex, string, flags)
    elif hasattr(reg_ex, op):
        return getattr(reg_ex, op)(string)
    else:
        raise TypeError('reg_ex must be a regular expression string or a '
                        'regular expression object')


def _get_match_iter(reg_ex, string, flags=0):
    if isinstance(reg_ex, str):
        return re.finditer(reg_ex, string, flags)
    elif hasattr(reg_ex, 'match'):
        return reg_ex.finditer(string)
    else:
        raise TypeError('reg_ex must be a regular expression string or a '
                        'regular expression object')


def _update_span(span, base_point=0):
    return (span[0] + base_point, span[1] + base_point)


def string_match(string, reg_ex, match_group=1, base_point=0, flags=0):
    """
    Does a regex match on the string and returns the span and value of the
    group match_group.

    Keyword arguments:
    reg_ex - A compiled regular expression object or a regular expression
             string.
    string - A string
    base_point - If specified, this is subtracted from point before checking
                 and added to the resulting location before it is returned.
    match_group - The group containing the entity match. If this is iterable,
                  a list of results is returned for each item.
    flags - If reg_ex is a string, this can be used to pass flags to the
            match function.

    """
    match = _get_match(reg_ex, string, 'match', flags)

    if match is None:
        return MatchResult(None, None)

    if isinstance(match_group, int) or isinstance(match_group, str):
        span = _update_span(match.span(match_group), base_point)

        return MatchResult(span, match.group(match_group))
    else:
        results = []
        for i in match_group:
            span = _update_span(match.span(i), base_point)
            results.append(MatchResult(span, match.group(i)))
        return results


def string_search(string, reg_ex, match_group=1, base_point=0, flags=0):
    """
    Does a regex search on the string and returns the span and value of the
    group match_group.

    Keyword arguments:
    reg_ex - A compiled regular expression object or a regular expression
             string.
    string - A string
    base_point - If specified, this is subtracted from point before checking
                 and added to the resulting location before it is returned.
    match_group - The group containing the entity match. If this is iterable,
                  a list of results is returned for each item.
    flags - If reg_ex is a string, this can be used to pass flags to the
            match function.

    """
    match = _get_match(reg_ex, string, 'search', flags)

    if match is None:
        return MatchResult(None, None)

    if isinstance(match_group, int) or isinstance(match_group, str):
        span = _update_span(match.span(match_group), base_point)

        return MatchResult(span, match.group(match_group))
    else:
        results = []
        for i in match_group:
            span = _update_span(match.span(i), base_point)
            results.append(MatchResult(span, match.group(i)))
        return results


def extract_entity(reg_ex, string, point, base_point=0, match_group=0,
                   flags=0):
    """
    Extracts the text and region of the entity defined by regex in string
    containing point.

    Keyword arguments:
    reg_ex - A compiled regular expression object or a regular expression
             string.
    string - A string containing a FS function
    point - An int representing a location in the string or a tuple
            representing a selection. The point may be relative to an
            optional base point.
    base_point - If specified, this is subtracted from point before checking
                 and added to the resulting location before it is returned.
    match_group - The group containing the entity match.
    flags - If reg_ex is a string, this can be used to pass flags to the
            finditer function.

    """
    if isinstance(point, int):
        lower_bound = upper_bound = point - base_point
    else:
        lower_bound, upper_bound = [p - base_point for p in point]

    span = match_string = prev_match = None

    match_iter = _get_match_iter(reg_ex, string, flags)

    for match in match_iter:
        span = match.span(match_group)
        # If the end of the match is before the start of point, keep searching
        if span[1] < lower_bound:
            continue
        # If the start of the match is past the end of point, stop searching
        elif span[0] > upper_bound:
            break
        # If match includes the point, we found a match
        elif (span[0] <= lower_bound) and (span[1] >= upper_bound):
            match_string = match.group(match_group)
            if upper_bound == span[1]:
                prev_match = (span, match_string)
                span = match_string = None
                continue
            else:
                break

    if span and match_string:
        span = _update_span(span, base_point)
        return MatchResult(span, match_string)
    elif prev_match:
        span, match_string = prev_match
        span = _update_span(span, base_point)
        return MatchResult(span, match_string)
    else:
        return MatchResult(None, None)


def add_to_path(path):
    """
    Adds path to the system path.
    """
    if path not in sys.path:
        sys.path.append(path)
        logger.info("Added %s to sys.path.", path)


def get_env(environ_name):
    temp = os.getenv(environ_name)
    if (temp is None):
        if (('ProgramFiles' in environ_name) or
                ('ProgramW6432' in environ_name)):
            temp = os.getenv('ProgramFiles')
    return temp


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


def create_folder(folder_path):
    """
    Make the directory if it doesn't exist. If it does, just eat exception
    """
    try:
        os.makedirs(folder_path)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
