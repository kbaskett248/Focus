from abc import abstractmethod
import itertools
import logging
import os
import re
import shutil
import subprocess

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

import sublime

from .metaclasses import MiniPluginMeta
from ..tools import (
    CACHE_ROOT,
    get_env,
    merge_paths,
    read_file,
    parse_ring_path,
    strip_alias,
    create_folder,
    get_server_access,
)


focus_extension_list = ('.mcs', '.mps', '.mts')


def get_mt_ring(path):
    return MTRing.get_mt_ring(path)


def is_local_ring(ring):
    return isinstance(ring, LocalRing)


class MTRing(object, metaclass=MiniPluginMeta):
    """Represents a Focus Ring"""

    Rings = {}
    HomeCareRing = False

    def __new__(cls, ring_path, universe_path, ring_name, universe_name):
        if ((ring_path is not None) and
                cls.valid_ring(ring_path, ring_name, universe_name)):
            return super(MTRing, cls).__new__(cls)
        else:
            raise InvalidRingError(ring_path, cls)

    def __init__(self, ring_path, universe_path, ring_name, universe_name):
        super(MTRing, self).__init__()

        self.name = ring_name
        self.universe_name = universe_name
        self.universe_path = self.get_universe_path()
        self.path = os.path.join(self.universe_path, ring_name + '.Ring')
        self.cache_path = self.get_cache_path()
        self.server_path = None

        MTRing.Rings[self.path.lower()] = self

    @classmethod
    @abstractmethod
    def valid_ring(cls, ring_path, ring_name, universe_name):
        pass

    @classmethod
    def get_mt_ring(cls, path):
        r = None
        (ring_path, universe_path,
         ring_name, universe_name) = parse_ring_path(path)

        if ring_path is None:
            return None
        else:
            try:
                r = MTRing.Rings[ring_path.lower()]
            except KeyError:
                for c in cls.get_plugins():
                    try:
                        r = c(ring_path, universe_path,
                              ring_name, universe_name)
                    except InvalidRingError:
                        # logger.exception('Failed to create Ring Type %s',
                        #                  c.__name__)
                        continue
                    else:
                        if not os.path.isdir(r.path):
                            r = None
                        break
                else:
                    MTRing.Rings[ring_path.lower()] = None
            finally:
                # logger.debug("MTRing.Rings: %s", MTRing.Rings)
                # logger.debug("MTRing: %s", MTRing)
                return r

    @classmethod
    def get_backup_ring(cls):
        ring = None

        settings = sublime.load_settings('MT-Focus.sublime-settings')
        if settings.has('default_ring'):
            path = settings.get('default_ring')
            ring = cls.get_mt_ring(path)

        return ring

    @classmethod
    def get_mt_ring_by_name(cls, name):
        for ring in cls.Rings.values():
            if ring.name.lower() == name:
                return ring
        return None

    @classmethod
    def list_rings(cls, local_only=False, server_only=False,
                   homecare_only=False, acute_only=False):
        result = set()
        for ring in cls.Rings.values():
            if ((not (local_only or server_only)) or
                    (local_only and isinstance(ring, LocalRing)) or
                    (server_only and isinstance(ring, ServerRing))):
                if ((not (homecare_only or acute_only)) or
                        (homecare_only and ring.HomeCareRing) or
                        (acute_only and not ring.HomeCareRing)):
                    result.add(ring)
        return list(result)

    @classmethod
    def list_ring_names(cls, local_only=False, server_only=False,
                        homecare_only=False, acute_only=False):
        result = [r.name for r in cls.list_rings(local_only, server_only)]
        result.sort()
        return result

    @classmethod
    def num_rings(cls, local_only=False, server_only=False,
                  homecare_only=False, acute_only=False):
        return len(cls.list_rings(local_only, server_only))

    @property
    def system_path(self):
        try:
            return self._system_path
        except AttributeError:
            if self.path is None:
                return None

            self._system_path = os.path.join(self.path, '!Misc')
            if not os.path.isdir(self._system_path):
                self._system_path = os.path.join(self.path, 'System')
                if not os.path.isdir(self._system_path):
                    self._system_path = None
            return self._system_path

    @property
    def magic_path(self):
        try:
            return self._magic_path
        except AttributeError:
            if self.system_path is None:
                return None
            else:
                self._magic_path = os.path.join(self.system_path, 'magic.exe')
            return self._magic_path

    @property
    def datadefs_path(self):
        try:
            return self._datadefs_path
        except AttributeError:
            if self.server_path is None:
                return None
            else:
                self._datadefs_path = os.path.join(self.server_path,
                                                   'DataDefs',
                                                   'Standard')
            return self._datadefs_path

    @property
    def pgmsource_path(self):
        try:
            return self._pgmsource_path
        except AttributeError:
            if self.server_path is None:
                return None
            else:
                path = os.path.join(self.server_path, 'PgmSource')
                logger.debug('path = %s', path)
                if os.path.exists(path):
                    self._pgmsource_path = path
                else:
                    self._pgmsource_path = None

            return self._pgmsource_path

    @property
    def pgm_cache_path(self):
        try:
            return self._pgmsource_cache_path
        except AttributeError:
            if self.cache_path is None:
                return None
            else:
                self._pgmsource_cache_path = os.path.join(
                    self.cache_path, 'Sys', 'PgmCache', 'Ring')

            return self._pgmsource_cache_path

    @property
    def system_programs_path(self):
        try:
            return self._system_programs_path
        except AttributeError:
            if self.system_path is None:
                return None
            else:
                self._system_programs_path = os.path.join(
                    self.system_path, 'Programs')

            return self._system_programs_path

    @property
    def possible_paths(self):
        try:
            return self._possible_paths
        except AttributeError:
            paths = [p for p in (
                     ('Local Cache', self.pgm_cache_path),
                     ('Ring', self.path),
                     ('System', self.system_path),
                     ('System Programs', self.system_programs_path),
                     ('Server', self.server_path))
                     if p[1] is not None]
            if paths:
                self._possible_paths = paths
            return paths

    def get_universe_path(self):
        path = os.path.join(get_env("ProgramFiles(x86)"),
                            'Meditech',
                            self.universe_name + '.Universe')
        if not os.path.isdir(path):
            path = None

        return path

    def get_cache_path(self):
        path = os.path.join(CACHE_ROOT,
                            self.universe_name + '.Universe',
                            self.name + '.Ring',
                            '!AllUsers')
        if not os.path.isdir(path):
            path = None

        return path

    def allow_running(self):
        return (self.magic_path is not None)

    def check_file_existence(self, partial_path, multiple_matches=False):
        if multiple_matches:
            results = []
        for k, v in self.possible_paths:
            path = merge_paths(v, partial_path)
            if os.path.exists(path):
                if multiple_matches:
                    results.append((k, path))
                else:
                    return (k, path)
        if multiple_matches:
            return results
        else:
            return None

    def get_file_path(self, partial_path):
        result = None
        possible_paths = self.check_file_existence(partial_path)
        if possible_paths:
            result = possible_paths[1]
        return result

    def get_translated_path(self, file_path):
        name, ext = os.path.splitext(file_path)
        ext = ext.lower()

        if ext == '.xml':
            path = file_path.replace('PgmSource', 'PgmObject')
            if os.path.isfile(path):
                return path
            return None

        if ext == '.fs':
            for e in focus_extension_list:
                path = name + e
                if os.path.isfile(path):
                    return path
            return None

        app, name = self.get_app_and_filename(file_path)
        name, unused = os.path.splitext(name)

        if ext == '.focus':
            for f, e in itertools.product(('PgmSource', 'PgmObject'),
                                          focus_extension_list):
                partial_path = os.path.join(f, app, name + e)
                logger.debug('partial_path = %s', partial_path)
                path = self.get_file_path(partial_path)
                if path:
                    return path
            return None

    def get_app_and_filename(self, file_path):
        a, n = os.path.split(file_path)
        unused, a = os.path.split(a)
        return (a, n)

    def partial_path(self, path):
        partial_path = None
        for k, v in self.possible_paths:
            if path.lower().startswith(v.lower()):
                partial_path = path[len(v)+1:]
                break
        return partial_path

    def run_file(self, partial_path=None, full_path=None,
                 parameters=None, separate_process=True, use_cache=False):
        """
        Runs a file in the Ring by calling it as an argument to magic.exe.
        """

        if not self.allow_running():
            return None

        path = None
        cmd = None

        print(self)

        if (partial_path is not None):
            logger.debug("partial_path=%s", partial_path)
            path = self.get_file_path(partial_path)
            logger.debug("Path=%s", path)
        elif ((full_path is not None) and os.path.isfile(full_path)):
            path = full_path

        if (path is not None):
            cmd = '{0} "{1}"'.format(self.magic_path, path)

            if (parameters is not None):
                logger.debug("parameters=%s", parameters)
                cmd = '{0} {1}'.format(cmd, parameters)

            logger.debug('Running cmd = %s', cmd)

            if separate_process:
                logger.debug('separate_process = True')
                subprocess.Popen(cmd)
            else:
                subprocess.call(cmd)

        return cmd

    def run_file_nice(self, partial_path=None, full_path=None, cmd='RUN',
                      parameters=None, separate_process=True,
                      use_cache=False):
        """
        Runs a file in the Ring using FocZ.TextPad.Run.P. If called
        with parameters, Omnilaunch is used because it supports arguments.
        """

        if not self.allow_running():
            return None

        path = None

        if (partial_path is not None):
            path = self.get_file_path(partial_path)
        elif ((full_path is not None) and os.path.isfile(full_path)):
            path = full_path
        logger.debug('path = %s', path)

        if (path is not None):
            run_path = os.path.join('PgmObject', 'Foc',
                                    'FocZ.TextPadTools.P.mps')

            run_parameters = '{0} "{1}"'.format(cmd, path)
            if parameters is not None:
                if isinstance(parameters, list):
                    parameters = ' '.join(parameters)
                run_parameters += ' ' + parameters
            logger.debug('run_parameters = %s', run_parameters)

            return self.run_file(partial_path=run_path,
                                 parameters=run_parameters,
                                 separate_process=separate_process)

    def open_kingdom(self):
        if self.system_path:
            path = self.get_file_path('KingdomNice.mps')
            return self.run_file(full_path=path)

    @property
    def alias_list_path(self):
        try:
            return self._alias_list_path
        except AttributeError:
            if self.HomeCareRing:
                partial_path = os.path.join('System', 'Translators',
                                            'AliasList.mtIo')
                self._alias_list_path = self.get_file_path(partial_path)
                if self._alias_list_path is None:
                    partial_path = os.path.join('System', 'Translators',
                                                'AliasList0.mtIo')
                    self._alias_list_path = self.get_file_path(partial_path)
            else:
                self._alias_list_path = None

            return self._alias_list_path

    @property
    def alias_lookup(self):
        try:
            return self._alias_lookup
        except AttributeError:
            self._alias_lookup = None
            if self.HomeCareRing:
                self.load_aliases()
            return self._alias_lookup

    def load_aliases(self):
        """Loads the alias lookup dictionary for the ring."""
        self._alias_lookup = dict()

        if self.alias_list_path is None:
            logger.info('No alias list exists for %s', self.name)
            return

        logger.info('Loading aliases for %s', self.name)
        with open(self.alias_list_path, 'r') as f:
            contents = f.read()

        matches = re.findall(
            r'{start}(.+?){sep}.+?{sep}(.+?){sep}(.+?)({sep}.*?)?{end}'.format(
                start=chr(1), sep=chr(3), end=chr(2)),
            contents)

        self._alias_lookup = {a[0]: (a[2], a[1]) for a in matches}
        logger.info('Aliases loaded for %s', self.name)

    def find_alias_definition(self, alias):
        alias = strip_alias(alias)
        if alias is None:
            return None

        if (alias in self.alias_lookup.keys()):
            alias_entry = self.alias_lookup[alias]
            logger.debug(alias_entry)
            return self.get_file_path(
                os.path.join('PgmSource', alias_entry[0],
                             alias_entry[1] + '.focus'))

    def find_object_file(self, object_name):
        object_name = object_name.split('.')[0]
        logger.debug('object_name = %s', object_name)

        logger.debug('self.datadefs_path = %s', self.datadefs_path)
        if self.datadefs_path is None:
            return None
        else:
            return self.get_file_path(os.path.join(
                self.datadefs_path, object_name + '.focus'))

    def create_file_in_ring(self, application, file_name, file_contents='',
                            in_cache=True):
        if not application:
            return False
        elif not file_name:
            return False
        elif not in_cache:
            logger.warning('Files may only be created in cache.')
            return False

        file_path = os.path.join(self.pgm_cache_path, 'PgmSource',
                                 application, file_name)
        folder = os.path.dirname(file_path)
        create_folder(folder)
        with open(file_path, 'w') as f:
            f.write(file_contents)

        if os.path.isfile(file_path):
            return file_path
        else:
            return False

    def ring_info(self):
        return (
            'Universe: {universe}\t\tRing: {ring}\t\tType: {type}\n'
            '\tPath:                 {ring_path}\n'
            '\tServer Path:          {server_path}\n'
            '\tProgram Cache Path:   {pgm_cache_path}\n'
            '\tPossible Paths:       {pos_paths}').format(
                universe=self.universe_name, ring=self.name,
                ring_path=self.path, server_path=self.server_path,
                pgm_cache_path=self.pgm_cache_path,
                pos_paths=self.possible_paths, type=self.__class__.__name__)

    def __str__(self):
        return '{0}.Universe\\{1}.Ring'.format(self.universe_name,
                                               self.name)


class LocalRing(MTRing):
    """Represents a locally installed ring."""

    HomeCareRing = True

    def __init__(self, ring_path, universe_path, ring_name, universe_name):
        super(LocalRing, self).__init__(ring_path, universe_path,
                                        ring_name, universe_name)

        self.server_path = self.path
        self.name = ring_name + " Local"

    def get_universe_path(self):
        path = os.path.join(get_env("ProgramFiles(x86)"),
                            'PTCT-AP',
                            'SoloFocus',
                            self.universe_name + '.Universe')
        if not os.path.isdir(path):
            path = None

        return path

    def get_cache_path(self):
        path = os.path.join(CACHE_ROOT,
                            self.universe_name + '.Universe',
                            self.name + '.Ring.Local',
                            '!AllUsers')
        if not os.path.isdir(path):
            path = None

        return path

    def update(self):
        path = os.path.join('PgmSource', 'HHA', 'HhaZtSvn.CommandEe.S.focus')
        return self.run_file_nice(partial_path=path)

    @property
    def possible_paths(self):
        try:
            return self._possible_paths
        except AttributeError:
            paths = [p for p in (
                     ('Ring', self.path),
                     ('System', self.system_path),
                     ('System Programs', self.system_programs_path),
                     ('Server', self.server_path))
                     if p[1] is not None]
            if paths:
                self._possible_paths = paths
            return paths

    @classmethod
    def valid_ring(cls, ring_path, ring_name, universe_name):
        r = ring_path.lower()
        print(r)
        return (('solofocus' in r) or ('ring.local' in r))


class ServerRing(MTRing):
    """Represents a standard server ring."""

    def __init__(self, ring_path, universe_path, ring_name, universe_name):
        super(ServerRing, self).__init__(ring_path, universe_path,
                                         ring_name, universe_name)

        self.server_path = self.get_server_path()

    def copy_source_to_cache(self, source, overwrite=True):
        partial_path = self.partial_path(source)
        if partial_path is not None:
            source = os.path.join(self.server_path, partial_path)
            dest = os.path.join(self.pgm_cache_path, partial_path)
            if (overwrite or (not os.path.exists(dest))):
                logger.debug('Copying file to cache: %s', source)
                create_folder(os.path.dirname(dest))
                shutil.copyfile(source, dest)
                return dest

    def file_exists_in_cache(self, source):
        result = False
        logger.debug('source: %s', source)
        partial_path = self.partial_path(source)
        logger.debug('partial_path: %s', partial_path)
        file_existence = self.check_file_existence(partial_path)
        if file_existence:
            for t, p in file_existence:
                if (t == 'Local Cache'):
                    result = True
                    break
        return result

    def get_server_path(self):
        unv_server_drive = None
        ini_path = os.path.join(self.system_path, 'Signon.ini')
        try:
            for l in read_file(ini_path):
                if 'universeserverdrive' in l.lower():
                    unv_server_drive = l.split('=')[1]
                    break
        except Exception:
            path = None
        else:
            if unv_server_drive is None:
                path = None
            else:
                path = os.path.join(unv_server_drive,
                                    self.universe_name + '.Universe',
                                    self.name + '.Ring')
                drive = os.path.splitdrive(path)[0].lower()
                if not drive.endswith(':'):
                    for d in get_server_access():
                        if drive == d.lower():
                            break
                    else:
                        path = None

            if (path is not None) and (not os.path.isdir(path)):
                path = None
        finally:
            logger.debug('path = %s', path)
            return path


class ServerAcuteRing(ServerRing):
    """Represents a standard server ring."""

    @classmethod
    def valid_ring(cls, ring_path, ring_name, universe_name):
        u = universe_name.lower()
        r = ring_path.lower()
        return (('ring.local' not in r) and
                (not (('ptct' in u) or ('fil' in u))))


class ServerHCRing(ServerRing):
    """Represents a standard server ring."""

    HomeCareRing = True

    @classmethod
    def valid_ring(cls, ring_path, ring_name, universe_name):
        u = universe_name.lower()
        r = ring_path.lower()
        return (('ring.local' not in r) and (('ptct' in u) or ('fil' in u)))


class InvalidRingError(Exception):
    """
    Raised when trying to create a Ring for a path that is not a Ring.

    """

    def __init__(self, path, ring_type=None):
        super(InvalidRingError, self).__init__()
        self.path = path
        self.ring_type = ring_type

    def __str__(self):
        return self.description

    @property
    def description(self):
        try:
            return self._description
        except AttributeError:
            if self.ring_type is not None:
                self._description = (
                    '{0} does not represent a valid {1}').format(
                    self.path, self.ring_type.__name__)
            else:
                self._description = ('{0} does not represent a '
                                     ' valid M-AT Ring').format(self.path)
            return self._description
