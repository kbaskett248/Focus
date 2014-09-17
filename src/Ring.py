import os
import platform
import re
import shutil
import subprocess

from .tools import read_file, get_env, merge_paths, create_dir, MultiMatch
from .Exceptions import InvalidRingError
import sublime

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

ring_matcher = re.compile(r"((.*?\\([^:\\\/\n]+?)\.Universe)\\([^:\\\/\n]+?)\.Ring)(?![^\\])", 
    re.IGNORECASE)

def parse_ring_path(file_path):
    try:
        match = ring_matcher.match( file_path )
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

class Ring(object):
    """Represents a Focus Ring"""

    COMP_LOADER_CLASSES = []

    def __init__(self, path):
        logger.debug(path)
        self.ring_path, self.universe_path, self.ring, self.universe = parse_ring_path(path)
        
        if (self.ring_path is None):
            raise InvalidRingError(path)

        match = re.search(r'(\d+)$', self.ring)
        self.modern_ring = False
        if (match is not None):
            if (int(match.group(1)) >= 24):
                self.modern_ring = True
        elif (self.ring.lower() == 'fildev'):
            self.modern_ring = True

        self.system_path = None
        self.magic_path = None
        self.cache_path = None
        self.server_path = None

        self.development_ring = False

        if "DEV" in self.ring:
            self.development_ring = True

        self.completion_loaders = None
        self.alias_lookup = None

    @staticmethod
    def get_ring(path):
        if "SoloFocus" in path:
            return LocalRing(path)
        else:
            return ServerRing(path)

    @property
    def allow_running(self):
        return (self.magic_path is not None)

    @property
    def name(self):
        return self.ring

    @property
    def possible_paths(self):
        paths = []
        for p in (('Local Cache', self.ring_path), ('System', self.system_path)):
            if (p[1] is not None):
                paths.append(p)
        return paths

    def get_system_path(self):
        path = os.path.join(self.ring_path, '!Misc')
        if not os.path.isdir(path):
            path = os.path.join(self.ring_path, 'System')
            if not os.path.isdir(path):
                path = None
        return path

    def get_magic_path(self):
        path = None
        if (self.system_path is not None):
            path = os.path.join(self.system_path, 'magic.exe')
            if not os.path.exists(path):
                path = None
        return path

    def pgm_path(self, use_cache = False):
        return self.ring_path

    def run_file(self, partial_path=None, full_path=None,
                 parameters=None, separate_process=True, use_cache=False):
        """
        Runs a file in the Ring by calling it as an argument to magic.exe.
        """

        if not self.allow_running:
            return None

        path = None
        cmd = None

        if (partial_path is not None):
            path = self.get_file_path(partial_path)
        elif ((full_path is not None) and os.path.isfile(full_path)):
            path = full_path

        logger.debug('path = %s', path)

        if (path is not None):
            cmd = '{0} "{1}"'.format(self.magic_path, path)

            if (parameters is not None):
                if isinstance(parameters, list):
                    parameters = '  '.join(parameters)
                cmd = '{0}  {1}'.format(cmd, parameters)

            logger.debug('cmd = %s', cmd)

            if separate_process:
                logger.debug('separate_process = True')
                subprocess.Popen(cmd)
            else:
                logger.debug('separate_process = False')
                subprocess.call(cmd)

        return cmd

    def run_file_nice(self, partial_path=None, full_path=None,
                      parameters=None, separate_process=True,
                      use_cache=False):
        """
        Runs a file in the Ring using FocZ.TextPad.Run.P. If called
        with parameters, Omnilaunch is used because it supports arguments.
        """

        if not self.allow_running:
            return None

        logger.debug('allow_running = True')
        path = None

        if (partial_path is not None):
            path = self.get_file_path(partial_path)
        elif ((full_path is not None) and os.path.isfile(full_path)):
            path = full_path

        logger.debug('path = %s', path)
        logger.debug("parameters = %s", parameters)

        if (path is not None):
            if (parameters is None):
                run_path = os.path.join('PgmObject', 'Foc',
                                        'Focz.TextPad.Run.P.mps')
                parameters = '"{0}"'.format(path)
                logger.debug('run_path = %s', run_path)
                logger.debug('parameters = ' + parameters)
                return self.run_file(partial_path = run_path, 
                                     parameters = parameters, 
                                     separate_process = separate_process)
            else:
                run_path = self.get_file_path('OmniLaunch.mps')
                if (run_path is not None):
                    logger.debug('path = %s', path)
                    if isinstance(parameters, list):
                        parameters = '  '.join(parameters)
                    parameters = '{0}  "{1}"  {2}'.format(
                        os.sep + self.partial_path(path), 
                        path, 
                        parameters 
                        )
                    logger.debug('run_path = %s; parameters = %s', run_path, parameters)
                    return self.run_file(full_path = run_path, 
                                         parameters = parameters, 
                                         separate_process = separate_process)
                else:
                    logger.debug("Can't find OmniLaunch")



    # def build_object_lists(self, separate_process = True):
    #     """Builds the object lists for a ring and stores them in the given 
    #     path. If the BuildObjectLists.P file does not exist in the current 
    #     ring, this will attempt to create the source file, translate it, and 
    #     run it."""

    #     # for t in self.ring_completions.keys():
    #     #     self.ring_completions[t] = None
    #     self.load_ring_completions(reload = True)

    #     # partial_tool_path = os.path.join('PgmObject', 'HHA', 'HhaZt.BuildObjectLists.P.mps')
    #     # build_object_lists_path = os.path.join(self.pgm_path(True), 
    #     #                                        partial_tool_path)
    #     # logger.debug(build_object_lists_path)

    #     # file_existence = self.check_file_existence(partial_tool_path)

    #     # # If the tool does not exist, try to write it and translate it.
    #     # if (not file_existence):
    #     #     logger.debug('build_object_lists_path does not exist')
    #     #     file_source = os.path.join(self.pgm_path(True), 'PgmSource', 'HHA', 
    #     #         'HhaZt.BuildObjectLists.P.focus')
    #     #     logger.debug(file_source)

    #     #     # If the source does not exist, write the source file.
    #     #     if (not os.path.isfile(file_source)):
    #     #         logger.debug('Writing source file: %s', file_source)
    #     #         target = open(file_source, 'w')
    #     #         target.write(BuildObjectLists_source)
    #     #         target.close()

    #     #     # If the source exists now, translate it.
    #     #     if os.path.isfile(file_source):
    #     #         debug('translating source file')
    #     #         translate_path = os.path.join('PgmObject', 'Foc', 
    #     #                                       'FocZ.TextPad.Translate.P.mps')
    #     #         logger.debug(
    #     #             self.run_file(partial_path = translate_path, 
    #     #                           parameters = "{0}".format(file_source), 
    #     #                           separate_process = False)
    #     #             )

    #     # # If the tool exists now, run it.
    #     # if os.path.isfile(build_object_lists_path):
    #     #     debug('build_object_lists_path exists')
    #     #     self.need_to_load_completions = True
    #     #     path = '"' + self.object_lists_path + os.sep + '"'
    #     #     return self.run_file_nice(
    #     #         full_path = build_object_lists_path, 
    #     #         parameters = path, 
    #     #         separate_process = separate_process 
    #     #         )

    # @property
    # def completion_types(self):
    #     types = set()
    #     for cls in self.COMP_LOADER_CLASSES:
    #         types = types.union(set(cls.Types))
    #     return types
    

    # def initialize_completion_lists(self, type_ = None):
    #     # types = ('Object', 'Record', 'File', 'Index', 'IndexKey', 'Key',
    #     #          'Field', 'LongLock', 'Alias', 'Include', 'External Pageset',
    #     #          'System', 'State')
    #     types = self.completion_types
    #     logger.debug('types: %s', types)
    #     for t in types:
    #         self.ring_completions[t] = None
    #         self.completion_state[t] = 'Not Loaded'
    #     self.alias_lookup = None

    # def get_ring_completions(self, type_, return_empty = False):
    #     """Returns a set of the ring completions of the given types. t can be a 
    #     list of types or a separated string of types. If return_empty is true, 
    #     an empty set will be returned. Otherwise, None will be returned."""

    #     logger.debug('Getting completions from Ring')
    #     logger.debug('Completion type: %s', type_)

    #     elements = set()

    #     types = set(self.ring_completions.keys()).intersection(set(type_))

    #     need_to_load = set([x for x in types if self.completion_state[x] != 'Loaded'])
    #     logger.debug('need to load: %s', need_to_load)
    #     if need_to_load: 
    #         self.load_ring_completions(need_to_load)
        
    #     for x in types:
    #         if (self.completion_state[x] != 'Loaded'):
    #             continue
    #         elif (x == 'Include'):
    #             [elements.add(os.path.basename(i)) for i in self.ring_completions[x]]
    #         else:
    #             elements = elements.union(self.ring_completions[x])

    #     if (not return_empty):
    #         if (len(elements) == 0):
    #             del elements
    #             elements = None

    #     return elements
        
    # def load_ring_completions(self, type_ = None, reload = False, wait = False):
    #     """Loads a fresh copy of ring completions from the ring level folders."""

    #     logger.debug('load_ring_completions: %s', type_)

    #     types = set(type_)
    #     running_types = set()
    #     completed_types = set()
    #     loaders_to_remove = set()

    #     for t in self.running_loaders:
    #         running_types = running_types.union(t.Types)
    #         if reload:
    #             t.stop()
    #             pass
    #         elif not t.is_alive():
    #             t.store_completions()
    #             loaders_to_remove.add(t)
    #             for x in t.Types:
    #                 completed_types.add(x)
    #                 self.completion_state[x] = 'Loaded'

    #     self.running_loaders = self.running_loaders.difference(loaders_to_remove)

    #     if reload:
    #         self.running_loaders.clear()

    #     for cls in self.COMP_LOADER_CLASSES:
    #         if (reload or types.intersection(set(cls.Types)).difference(running_types)):
    #             t = cls(self)
    #             self.running_loaders.add(t)
    #             t.start()
    #             for x in t.Types:
    #                 self.completion_state[x] = 'Loading'
        
    #     if wait:
    #         loaders_to_remove.clear()
    #         for t in self.running_loaders:
    #             t.join()
    #             t.store_completions()
    #             loaders_to_remove.add(t)
    #             for x in t.Types:
    #                 completed_types.add(x)
    #                 self.completion_state[x] = 'Loaded'
    #         self.running_loaders = self.running_loaders.difference(loaders_to_remove)

    #     if self.running_loaders:
    #         status_list = []
    #         [status_list.extend(t.Types) for t in self.running_loaders]
    #         if status_list:
    #             sublime.status_message('Loading completions for %s' % status_list)

    #     result = False
    #     if (types.intersection(completed_types) or (completed_types and reload)):
    #         result = True
    #     return result

    @property
    def completion_loaders(self):
        return self._completion_loaders
    @completion_loaders.setter
    def completion_loaders(self, value):
        logger.debug('Adding completion_loaders to Ring')
        self._completion_loaders = set()
        if value:          
            for c in value:
                self._completion_loaders.add(c(self))

    def open_kingdom(self):
        if self.system_path:
            path = os.path.join(self.system_path, 'KingdomNice.mps')
            return self.run_file(full_path = path)

    def __str__(self):
        return "{0} ({1})".format(self.name, self.ring_path)

    def check_file_existence(self, partial_path):
        existing_paths = []
        for k, v in self.possible_paths:
            if (v is not None):
                path = merge_paths(v, partial_path)
                if os.path.exists(path):
                    existing_paths.append((k, path))
        return existing_paths

    def get_file_path(self, partial_path):
        result = None
        possible_paths = self.check_file_existence(partial_path)
        if possible_paths:
            result = possible_paths[0][1]

        return result

    def partial_path(self, path):
        partial_path = None
        for k, v in self.possible_paths:
            if path.lower().startswith(v.lower()):
                partial_path = path[len(v)+1:]
                break
        return partial_path

    @property
    def alias_list_path(self):
        """Return the full path to the AliasList file in the ring."""
        partial_path = os.path.join('System', 'Translators', 'AliasList.mtIo')
        path = self.get_file_path(partial_path)
        if path is not None:
            return path
        partial_path = os.path.join('System', 'Translators', 'AliasList0.mtIo')
        path = self.get_file_path(partial_path)
        if path is not None:
            return path
        return None

    def load_aliases(self):
        """Loads the alias lookup dictionary for the ring."""
        self.alias_lookup = dict()
        alias_list_path = self.alias_list_path
        if alias_list_path is None:
            logger.info('No alias list exists for %s', self.ring)
            return

        logger.info('Loading aliases for %s', self.ring)
        with open(alias_list_path, 'r') as f:
            contents = f.read()

        matches = re.findall(
            r'{start}(.+?){sep}.+?{sep}(.+?){sep}(.+?)({sep}.*?)?{end}'.format(
                start = chr(1), sep = chr(3), end = chr(2)),
            contents)

        self.alias_lookup = {a[0]: (a[2], a[1]) for a in matches}
        logger.info('Aliases loaded for %s', self.ring)

    def find_alias(self, alias):
        result = None

        if self.alias_lookup is None:
            self.load_aliases()

        if (alias in self.alias_lookup.keys()):
            alias_entry = self.alias_lookup[alias]
            logger.debug(alias_entry)
            file_ = self.get_file_path(os.path.join('PgmSource', 
                                                    alias_entry[0], 
                                                    alias_entry[1] + '.focus')
                                                    )
            file_contents = read_file(file_, False)
            line = 0
            match = None
            match_start = None
            alias_pattern = re.compile(r"^\s*(:?)Alias\s+(%s)\s*?$" % alias)

            for i, l in enumerate(file_contents):
                match = alias_pattern.match(l)
                if (match is not None):
                    line = i
                    break

            if (match is not None) and (match.group(1) != ':'):
                ep_pattern = re.compile(r"^:EntryPoint +(.+?) *$")
                match = ep_pattern.match(file_contents[line])
                while (match is None) and (line > 0):
                    line -= 1
                    match = ep_pattern.match(file_contents[line])

                if (match is not None):
                    sub_name = match.group(1)
                    line = 0
                    pattern = re.compile(r"^\s*:Code\s+(%s)$" % sub_name)

                    for i, l in enumerate(file_contents):
                        match = pattern.match(l)
                        if (match is not None):
                            line = i + 1
                            match_start = match.start(1) + 1
                            break
            else:
                line += 1
                match_start = match.start(2) + 1

            if (match is not None):
                result = (file_, line, match_start)

        return result

class LocalRing(Ring):
    """Represents a locally installed ring."""

    def __init__(self, path):
        super(LocalRing, self).__init__(path)

        self.development_ring = True

        # self.need_to_load_completions = True

        self.system_path = self.get_system_path()
        self.magic_path = self.get_magic_path()
        self.datadefs_path = os.path.join(self.ring_path, 'DataDefs')
        # self.initialize_completion_lists()

    @property
    def name(self):
        return '%s Local' % self.ring

    @property
    def local_ring(self):
        return True    

    def update(self):
        path = os.path.join('PgmSource', 'HHA', 'HhaZtSvn.CommandEe.S.focus')
        return self.run_file_nice(partial_path = path)

    
class ServerRing(Ring):
    """Represents a standard server ring."""

    def __init__(self, path):
        super(ServerRing, self).__init__(path)

        self.ring_path = os.path.join(get_env("ProgramFiles(x86)"),
                                      'Meditech',
                                      self.universe + '.Universe',
                                      self.ring + '.Ring')
        if os.path.isdir(self.ring_path):
            self.universe_path = os.path.dirname(self.ring_path)
            self.cache_path = os.path.join(self.cache_root, 
                                           self.universe + '.Universe',
                                           self.ring + '.Ring',
                                           '!AllUsers', 'Sys', 'PgmCache',
                                           'Ring')
            if not os.path.isdir(self.cache_path):
                self.cache_path = None
            # self.need_to_load_completions = True
        else:
            pass
            # self.ring_path = os.path.join(get_env("ProgramFiles(x86)"),
            #                               'Meditech',
            #                               self.universe + '.Universe',
            #                               self.ring + '.Ring')

        self.server_path = self.get_server_path()
        self.system_path = self.get_system_path()
        self.magic_path = self.get_magic_path()
        self.datadefs_path = os.path.join(self.server_path, 'DataDefs')
        # self.initialize_completion_lists()

    @property
    def cache_root(self):
        result = None
        try:
            result = self._cache_root
        except AttributeError:
            version = int(platform.win32_ver()[1].split('.', 1)[0])
            # logger.info(platform.win32_ver())
            # logger.debug(version)
            if (version <= 5):
                self._cache_root = os.path.join(get_env('ALLUSERSPROFILE'), 
                                                'Application Data', 
                                                'Meditech')
            else:
                self._cache_root = os.path.join(get_env('ALLUSERSPROFILE'), 
                                                'Meditech')
            # logger.debug(self._cache_root)
            result = self._cache_root
        finally:
            return result
    
    @property
    def local_ring(self):
        return False

    @property
    def possible_paths(self):
        paths = []
        for p in (('Local Cache', self.cache_path), 
                  ('Server', self.server_path), 
                  ('System', self.system_path)):
            if (p[1] is not None):
                paths.append(p)
        return paths
    
    def copy_source_to_cache(self, source, overwrite = True):
        partial_path = self.partial_path(source)
        if (partial_path is not None):
            source = os.path.join(self.server_path, partial_path)
            dest = os.path.join(self.cache_path, partial_path)
            if (overwrite or (not os.path.exists(dest))):
                logger.debug('Copying file to cache: %s', source)
                create_dir(os.path.dirname(dest))
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
        
    def pgm_path(self, use_cache = False):
        if use_cache:
            return self.cache_path
        else:
            return self.server_path

    def get_server_path(self):
        unv_server_drive = None
        ini_path = os.path.join(self.ring_path, 'System', 'Signon.ini')
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
                                    self.universe + '.Universe',
                                    self.ring + '.Ring')
                if not os.path.isdir(path):
                    path = None
        finally:
            return path

    def get_system_path(self):
        path = os.path.join(self.server_path, 'System')
        if not os.path.isdir(path):
            path = os.path.join(self.server_path, '!Misc')
            if not os.path.isdir(path):
                path = None
        return path

    def get_magic_path(self):
        path = None
        path = os.path.join(self.ring_path, 'System', 'magic.exe')
        if not os.path.exists(path):
            path = None
        return path

    @property
    def allow_running(self):
        return True

