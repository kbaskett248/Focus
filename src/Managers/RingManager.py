import os
import re

from Focus.src.tools import get_env
from Focus.src.Ring import Ring, parse_ring_path
from Focus.src.singletonmixin import Singleton
from ..Exceptions import InvalidRingError

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class RingManager(Singleton):
    """Manager for the rings in memory."""

    def __init__(self):
        self.ring_list_by_path = dict()
        self.ring_list_by_ring = dict()
        self.completion_loaders = None
        
    def get_ring_by_path(self, file_path):
        ring_path, unused, unused, unused = parse_ring_path(file_path)
        # logger.debug('Ring path: %s', ring_path)

        try:
            ring = None
            if (ring_path is not None):
                ring = self.ring_list_by_path[ring_path.upper()]
        except KeyError:
            try:
                ring = self._add_ring(ring_path)
            except InvalidRingError:
                pass
        finally:
            return ring

    def get_ring_by_name(self, name):
        try:
            result = self.ring_list_by_ring[name]
        except KeyError:
            result = None
        finally:
            return result

    def _add_ring(self, file_path):
        ring = Ring.get_ring(file_path)
        if (ring is not None):
            self.ring_list_by_path[ring.ring_path.upper()] = ring
            for location, path in ring.possible_paths:
                try:
                    self.ring_list_by_path[path.upper()] = ring
                except AttributeError:
                    logger.debug('%s has no path for %s' % (ring.name, location))
            self.ring_list_by_ring[ring.name] = ring
            ring.completion_loaders = self.completion_loaders
            return ring

    def load_installed_local_rings(self):
        dirs_to_check = set()
        universes = ['PTCTDEV.Universe', 'FIL.Universe']
        directory = os.path.join(get_env("ProgramFiles(x86)"), 'PtCT-AP', 
                              'SoloFocus')
        paths = [os.path.join(directory, u) for u in universes]

        logger.debug(paths)
        for path in paths:
            if os.path.isdir(path):
                for folder in os.listdir(path):
                    if folder.lower().endswith('.ring'):
                        dir_ = os.path.join(path, folder)
                        if os.path.isdir(dir_):
                            dirs_to_check.add(dir_)

        logger.debug(dirs_to_check)

        for dir_ in dirs_to_check:
            try:
                self._add_ring(dir_)
            except InvalidRingError:
                pass

    def load_installed_server_rings(self):
        dirs_to_check = set()
        universes = ['PTCTDEV.Universe', 'PTCTQA.Universe']
        directory = os.path.join(get_env("ProgramFiles(x86)"), 'Meditech')
        paths = [os.path.join(directory, u) for u in universes]

        logger.debug(paths)
        for path in paths:
            if os.path.isdir(path):
                for folder in os.listdir(path):
                    if folder.lower().endswith('.ring'):
                        dir_ = os.path.join(path, folder)
                        if os.path.isdir(dir_):
                            dirs_to_check.add(dir_)

        logger.debug(dirs_to_check)

        for dir_ in dirs_to_check:
            try:
                self._add_ring(dir_)
            except InvalidRingError:
                pass

        debug_list = []
        for r in self.list_rings():
            debug_list.append(r.name)
            debug_list.append('    Ring_path: %s' % r.ring_path)
            debug_list.append('    Universe_path: %s' % r.universe_path)
            debug_list.append('    System Path: %s' % r.system_path)
            debug_list.append('    Magic Path: %s' % r.magic_path)
            debug_list.append('    Pgm Path: %s' % r.pgm_path())
            debug_list.append('    Cache_path: %s' % r.cache_path)
            debug_list.append('    Server_path: %s' % r.server_path)
            debug_list.append('    Modern Ring: %s' % r.modern_ring)
            debug_list.append('')
        logger.debug('\n'.join(debug_list))

                    
    def list_ring_names(self, local_only = False):
        result = [r.name for r in self.list_rings(local_only)]
        result.sort()
        return result

    def list_rings(self, local_only = False):
        result = set()
        for r in self.ring_list_by_path.values():
            if ((not local_only) or r.local_ring):
                result.add(r)
        return list(result)

    @property
    def num_rings(self):
        return len(self.ring_list_by_path)

    @property
    def completion_loaders(self):
        return self._completion_loaders
    @completion_loaders.setter
    def completion_loaders(self, value):
        self._completion_loaders = set()
        if value:          
            for c in value:
                self._completion_loaders.add(c)
        for f in self.list_rings():
            f.completion_loaders = self.completion_loaders
    
