from abc import abstractmethod
import itertools
import logging
import os
import re
import shutil
import subprocess

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

from .metaclasses import MiniPluginMeta
from ..tools.focus import CACHE_ROOT, parse_ring_path, convert_to_focus_lists
from ..tools.general import (
    get_env,
    merge_paths,
    read_file,
    create_folder
)
from ..tools.settings import (
    get_server_access,
    get_default_ring,
    get_tool_file_names
)
from ..tools.sublime import strip_alias


focus_extension_list = ('.mcs', '.mps', '.mts')


def get_ring(path):
    return Ring.get_ring(path)


def get_backup_ring():
    return Ring.get_backup_ring()


def is_local_ring(ring):
    return isinstance(ring, LocalRing)


def is_homecare_ring(ring):
    return isinstance(ring, HomeCareRing)


class Ring(object, metaclass=MiniPluginMeta):
    """Represents a Focus Ring"""

    Rings = {}
    ManageSourceCmd = os.path.join('Foc', 'FocSource.Process.S.focus')

    def __new__(cls, universe_name, ring_name, is_local, path):
        if cls.valid_ring(universe_name, ring_name, is_local):
            return super(Ring, cls).__new__(cls)
        else:
            raise InvalidRingError(universe_name, ring_name, path, cls)

    def __init__(self, universe_name, ring_name, is_local, path):
        super(Ring, self).__init__()

        self.universe_name = universe_name
        self.name = ring_name
        self.populate_paths()
        logger.debug("__init__: path = %s", self.path)
        if not os.path.isdir(self.path):
            raise InvalidRingError(universe_name, ring_name, path)

        Ring.Rings[self.key] = self

    def __str__(self):
        return '{0}.Universe\\{1}.Ring'.format(self.universe_name,
                                               self.name)

    @classmethod
    def ring_dict_key(cls, universe_name, ring_name, is_local):
        return (universe_name.lower(), ring_name.lower(), is_local)

    @classmethod
    @abstractmethod
    def valid_ring(cls, universe_name, ring_name, is_local):
        pass

    @classmethod
    def get_ring(cls, path):
        logger.debug(".get_ring: getting ring for %s", path)
        r = None
        ring_info = parse_ring_path(path)
        if not (ring_info[0] and ring_info[1]):
            return None

        ring_key = Ring.ring_dict_key(*ring_info)
        logger.debug('ring_key = %s', ring_key)

        try:
            r = Ring.Rings[ring_key]
        except KeyError:
            ring_info = list(ring_info)
            ring_info.append(path)
            ring_info = tuple(ring_info)
            logger.debug(".get_ring: ring_info = %s", ring_info)

            for c in cls.get_plugins():
                logger.debug(".get_ring: checking classes")
                try:
                    r = c(*ring_info)
                except InvalidRingError:
                    # logger.exception(".get_ring: InvalidRingError exception")
                    continue
                except Exception:
                    # logger.exception(".get_ring: Other exception")
                    continue
                else:
                    break
            else:
                Ring.Rings[ring_key] = None
        finally:
            logger.debug(".get_ring: returning ring - %s", r)
            return r

    @classmethod
    def get_backup_ring(cls):
        ring = None
        default_ring_path = get_default_ring()
        if default_ring_path:
            ring = cls.get_ring(default_ring_path)

        if not ring:
            ring = None
            for r in Ring.Rings.values():
                if is_local_ring(r):
                    ring = r
                    break
                elif not ring:
                    ring = r

        return ring

    @classmethod
    def get_ring_by_id(cls, id_):
        id_ = id_.lower()
        for ring in cls.Rings.values():
            if ring.id_.lower() == id_:
                return ring
        return None

    @classmethod
    def list_rings(cls, local_only=False, server_only=False,
                   homecare_only=False, acute_only=False):
        result = set()
        for ring in cls.Rings.values():
            if ((not (local_only or server_only)) or
                    (local_only and is_local_ring(ring)) or
                    (server_only and isinstance(ring, ServerRing))):
                if ((not (homecare_only or acute_only)) or
                        (homecare_only and is_homecare_ring(ring)) or
                        (acute_only and not is_homecare_ring(ring))):
                    result.add(ring)
        return list(result)

    @classmethod
    def list_ring_names(cls, **kwargs):
        result = [r.name for r in cls.list_rings(**kwargs)]
        result.sort()
        return result

    @classmethod
    def num_rings(cls, **kwargs):
        return len(cls.list_rings(**kwargs))

    @property
    def key(self):
        return self.__class__.ring_dict_key(
            self.universe_name, self.name, False)

    @property
    def id(self):
        return self.name

    def populate_paths(self):
        self.universe_path = self.get_universe_path()
        self.path = self.get_ring_path()
        self.system_path = self.get_system_path()
        self.magic_path = self.get_magic_path()
        self.system_programs_path = self.get_system_programs_path()
        self.system_pgmobject_path = self.get_system_pgmobject_path()

        self.cache_path = self.get_cache_path()
        self.pgm_cache_path = self.get_pgm_cache_path()

        self.server_path = self.get_server_path()
        self.datadefs_path = self.get_datadefs_path()
        self.pgmsource_path = self.get_pgmsource_path()
        self.alias_list_path = self.get_alias_list_path()

    def get_universe_path(self):
        universe_path = os.path.join(
            get_env("ProgramFiles(x86)"), 'Meditech',
            self.universe_name + '.Universe')

        if os.path.isdir(universe_path):
            return universe_path
        else:
            return None

    def get_ring_path(self):
        if not self.universe_path:
            return None

        ring_path = os.path.join(self.universe_path, self.name + '.Ring')
        if os.path.isdir(ring_path):
            return ring_path
        else:
            return None

    def get_system_path(self):
        if self.path is None:
            return None

        system_path = os.path.join(self.path, '!Misc')
        if not os.path.isdir(system_path):
            system_path = os.path.join(self.path, 'System')
            if not os.path.isdir(system_path):
                system_path = None
        return system_path

    def get_magic_path(self):
        if self.system_path is None:
            return None
        else:
            return os.path.join(self.system_path, 'magic.exe')

    def get_system_programs_path(self):
        if self.system_path is None:
            return None
        else:
            return os.path.join(self.system_path, 'Programs')

    def get_system_pgmobject_path(self):
        if self.system_path is None:
            return None

        path = os.path.join(self.system_path, 'PgmObject')
        if os.path.isdir(path):
            return path

        return False

    def get_cache_path(self):
        path = os.path.join(CACHE_ROOT,
                            self.universe_name + '.Universe',
                            self.name + '.Ring',
                            '!AllUsers')
        if not os.path.isdir(path):
            path = None

        return path

    def get_pgm_cache_path(self):
        if self.cache_path is None:
            return None
        else:
            return os.path.join(self.cache_path, 'Sys', 'PgmCache', 'Ring')

    def get_server_path(self):
        return None

    def get_datadefs_path(self):
        if self.server_path is None:
            return None
        else:
            path = os.path.join(self.server_path, 'DataDefs', 'Standard')
            if os.path.isdir(path):
                return path
        return None

    def get_pgmsource_path(self):
        if self.server_path is None:
            return None
        else:
            path = os.path.join(self.server_path, 'PgmSource')
            if os.path.isdir(path):
                return path
        return None

    def get_alias_list_path(self):
        return None

    def possible_paths(self):
        paths = [p for p in (
                 ('Local Cache', self.pgm_cache_path),
                 ('Ring', self.path),
                 ('System', self.system_path),
                 ('System Programs', self.system_programs_path),
                 ('System PgmObject', self.system_pgmobject_path),
                 ('Server', self.server_path))
                 if p[1] is not None]
        return paths

    def check_file_existence(self, partial_path, multiple_matches=False):
        file_name = os.path.basename(partial_path)
        if multiple_matches:
            results = []
        logger.debug("check_file_existence")
        for k, v in self.possible_paths():
            logger.debug("%s: %s", k, v)

            if k == 'System Programs':
                path = merge_paths(v, file_name)
            elif k == 'System PgmObject':
                path = merge_paths(v, file_name)
            else:
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
        logger.debug("getting file path for %s", partial_path)
        possible_paths = self.check_file_existence(partial_path)
        if possible_paths:
            return possible_paths[1]
        # If we don't have server access and no match was found, give the
        # benefit of the doubt and return a possible path.
        # elif self.server_path is None:
        #     return merge_paths(self.path, partial_path)
        else:
            return None

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

        return None

    def get_app_and_filename(self, file_path):
        a, n = os.path.split(file_path)
        unused, a = os.path.split(a)
        return (a, n)

    def partial_path(self, path):
        for k, v in self.possible_paths():
            if path.lower().startswith(v.lower()):
                return path[len(v)+1:]
                break
        return None

    def allow_running(self):
        return (self.magic_path is not None)

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
    def alias_lookup(self):
        return None

    def load_aliases(self):
        pass

    def find_alias_definition(self, alias):
        return None

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
                pos_paths=self.possible_paths(), type=self.__class__.__name__)

    def get_shell_cmd(self, target_ring=None, partial_path=None,
                      full_path=None, parameters=None):
        if target_ring is None:
            target_ring = self
        if not full_path and partial_path:
            full_path = target_ring.get_file_path(partial_path)
            if not full_path:
                logger.error(
                    '.get_shell_cmd: file (%s) does not exist in ring (%s)',
                    partial_path,
                    target_ring)
                return None
        elif not full_path and not partial_path:
            logger.error('.get_shell_cmd: '
                         'either full path or partial path must be specified')
            return None

        logger.debug("get_shell_cmd: self = %s", self.__repr__())
        logger.debug("get_shell_cmd: target_ring = %s", target_ring.__repr__())

        if not full_path.lower().endswith('.focus'):
            return self.get_shell_cmd_direct(full_path, parameters)
        elif self == target_ring:
            return self.get_shell_cmd_tool(full_path, parameters)
        else:
            return self.get_shell_cmd_target(
                target_ring, full_path, parameters)

        # if self is target_ring:
        #     if not full_path and partial_path:
        #         full_path = self.get_file_path(partial_path)
        #     logger.debug(".get_shell_cmd: full_path = %s", full_path)
        #     full_path = self.get_translated_path(full_path)
        #     logger.debug(".get_shell_cmd: full_path = %s", full_path)
        #     shell_cmd = 'magic.exe "{full_path}"'.format(full_path=full_path)
        #     if parameters:
        #         shell_cmd += ' ' + parameters
        #     logger.debug(".get_shell_cmd: shell_cmd = %s", shell_cmd)
        #     return shell_cmd

        # elif (is_local_ring(self) and is_local_ring(target_ring)):
        #     omnilaunch = self.get_file_path('Omnilaunch.mps')
        #     if omnilaunch:
        #         if not full_path and partial_path:
        #             full_path = target_ring.get_file_path(partial_path)
        #         full_path = target_ring.get_translated_path(full_path)
        #         logger.debug(".get_shell_cmd: full_path = %s", full_path)
        #         partial_path = target_ring.partial_path(full_path)
        #         logger.debug(".get_shell_cmd: partial_path = %s", partial_path)
        #         shell_cmd = 'magic.exe "{omnilaunch}"  {partial_path}'.format(
        #             omnilaunch=omnilaunch, partial_path=partial_path)
        #         if parameters:
        #             shell_cmd += '  ' + parameters
        #         logger.debug(".get_shell_cmd: shell_cmd = %s", shell_cmd)
        #         return shell_cmd

        # tools_path = self.ring.get_file_path(os.path.join(
        #     'PgmObject', 'Foc', 'FocZ.TextPadTools.P.mps'))
        # if tools_path:
        #     if not full_path and partial_path:
        #         full_path = self.get_file_path(partial_path)
        #     shell_cmd = 'magic.exe "{tools_path}" {tool_cmd} "{full_path}"'
        #     shell_cmd = shell_cmd.format(
        #         tools_path=tools_path, tool_cmd=tool_cmd, full_path=full_path)
        #     if parameters:
        #         shell_cmd += ' ' + parameters
        #     return shell_cmd

        # return None

    def get_shell_cmd_direct(self, full_path, parameters=None):
        ext = os.path.splitext(full_path)[1]
        if ext not in focus_extension_list:
            run_path = self.get_translated_path(full_path)
            if not run_path:
                logger.error('.get_shell_cmd_direct: ' +
                             'failed to get translated oath for %s in %s',
                             full_path, self)
                return None
        else:
            run_path = full_path

        logger.debug(".get_shell_cmd_direct: run_path = %s", run_path)
        shell_cmd = 'magic.exe "{run_path}"'.format(run_path=run_path)

        if parameters:
            shell_cmd += ' ' + convert_to_focus_lists(parameters)
        logger.debug(".get_shell_cmd: shell_cmd = %s", shell_cmd)

        return shell_cmd

    def get_tools_path(self):
        logger.debug("running get_tools_path")
        return self.get_file_path(
            os.path.join('PgmObject', 'Foc', 'FocZ.TextPadTools.P.mps'))

    def format_shell_cmd_for_tool(self, run_path, tool_cmd, full_path,
                                  parameters):
        logger.debug('parameters = %s', parameters)
        if parameters:
            if isinstance(parameters, str):
                parameters = [tool_cmd, full_path, parameters]
            elif hasattr(parameters, '__iter__'):
                new_parameters = parameters
                parameters = [tool_cmd, full_path]
                parameters.extend(new_parameters)
            else:
                parameters = [tool_cmd, full_path, parameters]
            logger.debug('parameters = %s', parameters)
            parameters = convert_to_focus_lists(parameters)
            shell_cmd = 'magic.exe "{run_path}" {parameters}'.format(
                run_path=run_path, full_path=full_path, parameters=parameters)
        else:
            shell_cmd = 'magic.exe "{run_path}" {tool_cmd} "{full_path}"'.format(
                run_path=run_path, tool_cmd=tool_cmd, full_path=full_path)

        return shell_cmd

    def get_shell_cmd_tool(self, full_path, parameters=None):
        logger.debug('get_shell_cmd_tool')
        run_path = self.get_tools_path()
        logger.debug('run_path = %s', run_path)
        if run_path is None:
            logger.error('.get_shell_cmd_tool: could not find tools path')
            return None

        logger.debug(".get_shell_cmd_tool: run_path = %s", run_path)
        name = os.path.basename(full_path)
        tool_cmd = 'RUN'
        if name in get_tool_file_names():
            tool_cmd = 'RUNRING'

        shell_cmd = self.format_shell_cmd_for_tool(run_path, tool_cmd,
                                                   full_path, parameters)
        logger.debug(".get_shell_cmd_tool: shell_cmd = %s", shell_cmd)

        return shell_cmd

    def get_shell_cmd_target(self, target_ring, full_path, parameters=None):
        logger.debug('get_shell_cmd_target')
        run_path = self.get_tools_path()
        logger.debug('run_path = %s', run_path)
        if run_path is None:
            logger.error('.get_shell_cmd_tool: could not find tools path')
            return None

        logger.debug("'.get_shell_cmd_tool: run_path = %s", run_path)
        name = os.path.basename(full_path)
        tool_cmd = 'RUNTOOL'
        if name in get_tool_file_names:
            tool_cmd = 'RUNRINGTOOL'

        shell_cmd = self.format_shell_cmd_for_tool(run_path, tool_cmd,
                                                   full_path, parameters)
        logger.debug(".get_shell_cmd_target: shell_cmd = %s", shell_cmd)

        return shell_cmd


class HomeCareRing(Ring):
    """docstring for HomeCareRing"""

    def get_alias_list_path(self):
        if not self.system_path:
            return None

        alias_list_path = os.path.join(
            self.system_path, 'Translators', 'AliasList.mtIo')
        if not os.path.isfile(alias_list_path):
            alias_list_path = os.path.join(
                self.system_path, 'Translators', 'AliasList0.mtIo')
            if not os.path.isfile(alias_list_path):
                alias_list_path = None

        return alias_list_path

    @property
    def alias_lookup(self):
        try:
            return self._alias_lookup
        except AttributeError:
            self._alias_lookup = None
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


class LocalRing(HomeCareRing):
    """Represents a locally installed ring."""

    def __str__(self):
        return '{0}.Universe\\{1}.Ring Local'.format(self.universe_name,
                                                     self.name)

    @classmethod
    def valid_ring(cls, universe_name, ring_name, is_local):
        return (bool(universe_name) and bool(ring_name) and is_local)

    @property
    def id(self):
        return self.name + " Local"

    @property
    def key(self):
        return self.__class__.ring_dict_key(
            self.universe_name, self.name, True)

    @property
    def ManageSourceCmd(self):
        if self.key == ('ptctdev', 'dev25', True):
            return os.path.join('Foc', 'FocSource.Process.Ptct.S.focus')
        else:
            return os.path.join('Foc', 'FocSource.Process.S.focus')

    def get_universe_path(self):
        path = os.path.join(
            get_env("ProgramFiles(x86)"), 'PTCT-AP', 'SoloFocus',
            self.universe_name + '.Universe')
        if os.path.isdir(path):
            return path
        else:
            return None

    def get_cache_path(self):
        path = os.path.join(
            CACHE_ROOT, self.universe_name + '.Universe',
            self.name + '.Ring.Local', '!AllUsers')
        if os.path.isdir(path):
            return path
        else:
            return None

    def get_server_path(self):
        return self.path

    def update(self):
        path = os.path.join('PgmSource', 'HHA', 'HhaZtSvn.CommandEe.S.focus')
        return self.run_file_nice(partial_path=path)

    # def possible_paths(self):
    #     paths = [p for p in (
    #              ('Ring', self.path),
    #              ('System', self.system_path),
    #              ('System Programs', self.system_programs_path),
    #              ('Server', self.server_path))
    #              if p[1] is not None]
    #     return paths

    def get_shell_cmd_target(self, target_ring, full_path, parameters=None):
        if (self != target_ring) and is_local_ring(target_ring):
            omnilaunch = self.get_file_path('Omnilaunch.mps')
            if omnilaunch:
                run_path = target_ring.get_translated_path(full_path)
                if not run_path:
                    logger.error('.get_shell_cmd_target: ' +
                                 'failed to get translated path for %s in %s',
                                 full_path, target_ring)
                    return super(LocalRing, self).get_shell_cmd_target(
                        target_ring, full_path, parameters)
                logger.debug('.get_shell_cmd_target: run_path = %s', run_path)

                partial_path = target_ring.partial_path(run_path)
                if not partial_path:
                    logger.error('.get_shell_cmd_target: ' +
                                 'failed to get partial path for %s in %s',
                                 run_path, target_ring)
                    return super(LocalRing, self).get_shell_cmd_target(
                        target_ring, full_path, parameters)
                else:
                    partial_path = os.sep + partial_path

                logger.debug('.get_shell_cmd_target: partial_path = %s',
                             partial_path)
                shell_cmd = 'magic.exe "{omnilaunch}"  {partial_path}'.format(
                    omnilaunch=omnilaunch, partial_path=partial_path)

                if parameters:
                    if hasattr(parameters, '__iter__'):
                        parameters = '  '.join(
                            ['"{0}"'.format(convert_to_focus_lists(x))
                             for x in parameters])
                    else:
                        parameters = '"{0}"'.format(parameters)
                    shell_cmd += '  ' + parameters

                logger.debug('.get_shell_cmd_target: shell_cmd = %s',
                             shell_cmd)

                return shell_cmd

        return super(LocalRing, self).get_shell_cmd_target(
            target_ring, full_path, parameters)


class ServerRing(Ring):
    """Represents a standard server ring."""

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


class ServerAcuteRing(ServerRing):
    """Represents a standard server ring."""

    @classmethod
    def valid_ring(cls, universe_name, ring_name, is_local):
        if is_local:
            return False

        u = universe_name.lower()
        return not (('ptct' in u) or ('fil' in u))


class ServerHCRing(ServerRing, HomeCareRing):
    """Represents a standard server ring."""

    @classmethod
    def valid_ring(cls, universe_name, ring_name, is_local):
        if is_local:
            return False

        u = universe_name.lower()
        return (('ptct' in u) or ('fil' in u))


class InvalidRingError(Exception):
    """
    Raised when trying to create a Ring for a path that is not a Ring.

    """

    def __init__(self, universe_name, ring_name, path, ring_type=None):
        super(InvalidRingError, self).__init__()
        self.universe_name = universe_name
        self.ring_name = ring_name
        self.path = path
        self.ring_type = ring_type
        self.description = self.get_description()

    def __str__(self):
        return self.description

    def get_description(self):
        if self.ring_type is not None:
            return '{0} does not represent a valid {1}'.format(
                self.path, self.ring_type.__name__)
        else:
            return '{0} does not represent a valid M-AT Ring'.format(
                self.path)
