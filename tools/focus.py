import itertools
import logging
import re
import os
import platform

from .general import get_env


logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')


RING_MATCHER = re.compile(
    r".*?(Ptct-AP\\SoloFocus)?\\([^:\\\/\n]+?)\.Universe" +
    r"\\([^:\\\/\n]+?)\.Ring(.Local)?(\\|$)",
    re.IGNORECASE)
TRANSLATOR_SEPARATOR = '//' + ('-' * 77)
TRANSLATOR_LINE_SPLITTER = re.compile(
    r'^\s*(?P<translator>(:|#)[A-Za-z0-9]*|[A-Za-z0-9]+)'
    r'(?P<separator>\s*)(?P<value>.*)$')


def parse_ring_path(file_path):
    is_local = False
    try:
        match = RING_MATCHER.match(file_path)
        if match.group(1) or match.group(4):
            is_local = True
        return (match.group(2), match.group(3), is_local)
    except TypeError:
        pass
    except AttributeError:
        pass
    return (None, None, False)


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
            return 'True'
        else:
            return ''
    else:
        return str(args)


def get_ring_locations(universe_name, ring_name, is_local):
    ring_locations = []
    universe = universe_name + '.Universe'
    ring = ring_name + '.Ring'

    if is_local:
        ring_locations.append(os.path.join(
            get_env('ProgramFiles'), 'Ptct-AP', 'SoloFocus', universe, ring))
        ring += '.Local'
        ring_locations.append(os.path.join(CACHE_ROOT, universe, ring))

    else:
        ring_locations.append(os.path.join(
            get_env('ProgramFiles'), 'Meditech', universe, ring))
        ring_locations.append(os.path.join(CACHE_ROOT, universe, ring))

    return tuple(ring_locations)


def get_translated_path(file_path):
    extension_list = ('.mps', '.mcs', '.mts')
    name, ext = os.path.splitext(file_path)
    ext = ext.lower()

    if ext == '.fs':
        for e in extension_list:
            path = name + e
            if os.path.isfile(path):
                return path
    elif ext == '.xml':
        name = name.replace('PgmSource', 'PgmObject')
        return name + ext
    elif ext == '.focus':
        logger.debug('name = %s', name)
        file_name_list = [name.replace('PgmSource', 'PgmObject'), name]
        if '.ring.local' in name.lower():
            universe_name, ring_name, is_local = parse_ring_path(name)
            logger.debug("universe_name, ring_name = %s, %s", universe_name,
                         ring_name)
            app_name, file_name = os.path.split(name)
            unused, app_name = os.path.split(app_name)
            local_ring_path = get_ring_locations(
                ring_name, universe_name, True)[0]
            file_name_list.append(os.path.join(
                local_ring_path, 'PgmObject', app_name, file_name))

        for path, extension in itertools.product(file_name_list,
                                                 extension_list):
            path += extension
            logger.debug(path)
            if os.path.isfile(path):
                return path

    return None
