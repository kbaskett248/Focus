import itertools
import re
import os
import platform

from .general import get_env


RING_MATCHER = re.compile(
    r"((.*?\\([^:\\\/\n]+?)\.Universe)\\([^:\\\/\n]+?)\.Ring(.Local)?)(?![^\\])",
    re.IGNORECASE)
TRANSLATOR_SEPARATOR = '//' + ('-' * 77)
TRANSLATOR_LINE_SPLITTER = re.compile(
    r'^\s*(?P<translator>(:|#)[A-Za-z0-9]*|[A-Za-z0-9]+)'
    r'(?P<separator>\s*)(?P<value>.*)$')


def parse_ring_path(file_path):
    try:
        match = RING_MATCHER.match(file_path)
        yield match.group(1)
        yield match.group(2)
        yield match.group(4)
        yield match.group(3)

    except TypeError:
        yield None
        yield None
        yield None
        yield None

    except AttributeError:
        yield None
        yield None
        yield None
        yield None


def get_cache_root():
    version = int(platform.win32_ver()[1].split('.', 1)[0])
    if (version <= 5):
        path = os.path.join(get_env('ALLUSERSPROFILE'),
                            'Application Data',
                            'Meditech')
    else:
        path = os.path.join(get_env('ALLUSERSPROFILE'),
                            'Meditech')
    return path

CACHE_ROOT = get_cache_root()


def convert_to_focus_lists(args):
    if isinstance(args, str):
        return args
    elif hasattr(args, '__iter__'):
        return (chr(1) +
                chr(3).join([convert_to_focus_lists(x) for x in args]) +
                chr(2))
    elif isinstance(args, bool):
        if args:
            return '"True"'
        else:
            return '""'
    else:
        return args


def get_translated_path(file_path):
    name, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext == '.fs':
        for e in ('.mps', '.mcs', '.mts'):
            path = name + e
            if os.path.isfile(path):
                return path
    elif ext == '.xml':
        name = name.replace('PgmSource', 'PgmObject')
        return name + ext
    elif ext == '.focus':
        for n, e in itertools.product(
                (name.replace('PgmSource', 'PgmObject'), name),
                ('.mps', '.mcs', '.mts')):
            path = n + e
            print(path)
            if os.path.exists(path):
                return path

    return None
