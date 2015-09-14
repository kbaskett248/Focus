import glob
import logging
import re
import os
import platform

from .general import get_env, read_file


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


def read_ini(filename):
    elements = {}
    for line in read_file(filename):
        k, v = line.split('=', maxsplit=1)
        elements[k] = v
    return elements


def read_mls(filename):
    with open(filename, 'r') as f:
        contents = f.read()

    matches = re.findall(
        r'{start}(.+?){sep}(.*?){sep}(.*?){sep}(.*?){sep}(.*?){sep}(.*?){sep}(.*?){end}'.format(
            start=chr(1), sep=chr(3), end=chr(2)),
        contents)

    if os.path.basename(filename).lower() == 'root table.mls':
        elements = {}
        for m in matches:
            elements[m[0:2]] = m[2:]
    else:
        for m in matches:
            elements.append(m)

    return elements


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
    if not universe_name:
        raise NotADirectoryError('Missing universe name')
    elif not ring_name:
        raise NotADirectoryError('Missing ring name')

    ring_locations = []
    universe = universe_name + '.Universe'
    ring = ring_name + '.Ring'

    if is_local:
        ring_locations.append(os.path.join(
            get_env('ProgramFiles(x86)'), 'Ptct-AP',
            'SoloFocus', universe, ring))
        ring += '.Local'
        ring_locations.append(os.path.join(CACHE_ROOT, universe, ring))

    else:
        ring_locations.append(os.path.join(
            get_env('ProgramFiles(x86)'), 'Meditech', universe, ring))
        ring_locations.append(os.path.join(CACHE_ROOT, universe, ring))

    return tuple(ring_locations)


def get_translated_path(file_path, focus_possible_paths=None):
    extension_list = ('.mps', '.mcs', '.mts')
    name, ext = os.path.splitext(file_path)
    ext = ext.lower()
    logger.debug('name = %s; ext = %s', name, ext)

    if not os.path.isfile(file_path):
        return None

    elif ext == '.fs':
        for e in extension_list:
            path = name + e
            if os.path.isfile(path):
                return path

    elif ext == '.xml':
        return file_path.replace('PgmSource', 'PgmObject')

    elif ext == '.focus':
        if focus_possible_paths:
            name = os.path.basename(name)
            file_name_list = [os.path.join(p, name) for p in
                              focus_possible_paths]

        else:
            file_name_list = [name.replace('PgmSource', 'PgmObject'), name]
            if '.ring.local' in name.lower():
                universe_name, ring_name, is_local = parse_ring_path(name)
                logger.debug("universe_name, ring_name = %s, %s",
                             universe_name, ring_name)

                app_name, file_name = os.path.split(name)
                unused, app_name = os.path.split(app_name)

                local_ring_path = get_ring_locations(
                    ring_name, universe_name, True)[0]
                file_name_list.append(os.path.join(
                    local_ring_path, 'PgmObject', app_name, file_name))

        for path in file_name_list:
            logger.debug("path=%s", path)
            for f in sorted(glob.glob(path + '*.m?s'), reverse=True):
                logger.debug(f)
                if os.path.isfile(f):
                    return f

    return None
