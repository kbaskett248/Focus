from abc import abstractmethod
import os
from queue import Queue
import re
import threading

import sublime

from DynamicCompletions import FileLoader, PathLoader, StaticLoader

import Focus
from .src import FocusLanguage
from .src.Managers.RingFileManager import RingFileManager
from .src.Managers.RingManager import RingManager
from .src.tools import read_file

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

CT_ALIAS = 'Alias'
CT_FOCUS_LOCAL = 'Local'
CT_SUBROUTINE = 'Subroutine'
CT_TRANSLATOR = 'Translator'
CT_INCLUDE_FILE = 'Include'
CT_EXTERNAL_PAGESET = 'ExternalPageSet'
CT_STATE = 'State'
CT_SYSTEM = 'System'

CT_OBJECT = "Object"
CT_RECORD = "Record"
CT_FILE = "File"
CT_KEY = "Key"
CT_FIELD = "Field"
CT_INDEX = "Index"
CT_INDEXKEY = "IndexKey"
CT_LONGLOCK = "LongLock"

class RingLoader(PathLoader):
    """Parent class for CompletionLoaders that load completions based on a Ring."""
    
    def __init__(self, ring = None, **kwargs):
        self.ring = ring
        if ('path' not in kwargs.keys()):
            kwargs['path'] = self.__class__.get_path_from_ring(ring)
        super(RingLoader, self).__init__(**kwargs)

    @classmethod
    def view_scope(cls):
        """Return a scope to determine if the CompletionLoader will be enabled for a view."""
        return Focus.scope_map('source')

    @classmethod
    def view_check(cls, view):
        n = view.file_name()
        if (n is None) or (n == ''):
            return False
        manager = RingManager.getInstance()
        ring = manager.get_ring_by_path(n)
        if ring is None:
            return False
        if cls.get_path_from_ring(ring) is None:
            return False

        return True

    @classmethod
    @abstractmethod
    def get_path_from_ring(self):
        pass

    @classmethod
    def instances_for_view(cls, view):
        """Returns a list of instances of the given class to be used for the given view."""
        n = view.file_name()
        manager = RingManager.getInstance()
        ring = manager.get_ring_by_path(n)
        if ring is None:
            return []

        try:
            return [cls.Instances[cls.get_path_from_ring(ring)]]
        except KeyError:
            pass
        except AttributeError:
            pass
        if cls.full_view_check(view):
            return [cls(ring = ring)]
        else:
            return []

class AliasRingLoader(RingLoader, FileLoader):
    """Loads completions from a View."""

    EmptyReturn = ([], sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)
    LoadAsync = True

    def __init__(self, ring = None, **kwargs):
        path = self.__class__.get_path_from_ring(ring)
        logger.debug('path = %s', path)
        super(AliasRingLoader, self).__init__(ring = ring,
                                              path = path, 
                                              file_path = path, 
                                              **kwargs)

    @classmethod
    def completion_types(cls):
        """Return a set of completion types that this CompletionLoader can return."""
        return [CT_ALIAS]

    @classmethod
    def view_check(cls, view):
        if not super(AliasRingLoader, cls).view_check(view):
            return False
        elif ('!DictionarySource' in view.file_name()):
            return False
        else:
            return True

    @classmethod
    def get_path_from_ring(cls, ring):
        return ring.alias_list_path

    def load_completions(self, **kwargs):
        """Loads alias completions from the ring."""
        logger.debug('Loading Alias Ring Completions')
        self.ring.load_aliases()
        self.completions = set([('@@%s()' % a, '%s()' % a) for a in self.ring.alias_lookup.keys()])
        logger.debug('Done Loading Alias Ring Completions')


class IncludeLoader(RingLoader):
    """Loads completions from a View."""

    EmptyReturn = ([], sublime.INHIBIT_EXPLICIT_COMPLETIONS | sublime.INHIBIT_WORD_COMPLETIONS)
    LoadAsync = True

    @classmethod
    def completion_types(cls):
        """Return a set of completion types that this CompletionLoader can return."""
        return [CT_INCLUDE_FILE, CT_EXTERNAL_PAGESET]

    @classmethod
    def view_check(cls, view):
        if not super(IncludeLoader, cls).view_check(view):
            return False
        elif ('!DictionarySource' in view.file_name()):
            return False
        else:
            return True

    @classmethod
    def get_path_from_ring(cls, ring):
        return os.path.join(ring.pgm_path(False), 'PgmSource')

    def load_completions(self, **kwargs):
        """Loads the Include and ExternalPageSet completions from the ring.

        Walks through the PgmSource directory, finding all the Include files,
        DataDef files, and ExternalPageSet files.

        """
        logger.debug('Loading Include File Completions')
        self.completions = dict()
        self.completions[CT_INCLUDE_FILE] = set()
        self.completions[CT_EXTERNAL_PAGESET] = set()
        self.modified_dict = self.build_modified_dict()

        for path, dirs, files in os.walk(self.path):
            for f in files:
                f_lower = f.lower()
                if (f_lower.endswith('.i.focus') or f_lower.endswith('.d.focus')):
                    self.completions[CT_INCLUDE_FILE].add((f,))
                elif f_lower.endswith('.e.focus'):
                    self.completions[CT_EXTERNAL_PAGESET].add((f,))

        logger.debug('Done Loading Include File Completions')

    def refresh_completions(self):
        """Return True if the completions need to be reloaded.

        Iterates through the folders in the DataDef folders. If any of them 
        have been modified since the last time the completions were loaded,
        return True. Else return False.

        """
        logger.debug('Should Include File Completions be Refreshed?')
        try:
            m1 = self.modified_dict
        except AttributeError:
            logger.debug('Refresh Include File Completions')
            return True
        else:
            m2 = self.build_modified_dict()
            keys1 = set(m1.keys())
            keys2 = set(m2.keys())
            if keys1.symmetric_difference(keys2):
                logger.debug('Refresh Include File Completions')
                return True
            keys = keys1.union(keys2)
            if len(keys) == 0:
                logger.debug("Don't Refresh Include File Completions")
                return False

            for k in keys:
                try:
                    if m2[k] > m1[k]:
                        logger.debug('Refresh Include File Completions')
                        return True
                except KeyError:
                    logger.debug('Refresh Include File Completions')
                    return True
            logger.debug("Don't Refresh Include File Completions")
            return False
                    

    def build_modified_dict(self):
        mod_dict = dict()
        for d in os.listdir(self.path):
            full_path = os.path.join(self.path, d)
            if os.path.isdir(full_path):
                mod_dict[d] = os.path.getmtime(full_path)
        return mod_dict


class ObjectRingLoader(RingLoader):
    """Loads completions from a View."""

    EmptyReturn = ([], sublime.INHIBIT_EXPLICIT_COMPLETIONS)
    LoadAsync = True

    @classmethod
    def completion_types(cls):
        """Return a set of completion types that this CompletionLoader can return."""
        return [CT_OBJECT, CT_RECORD, CT_FILE, CT_KEY, CT_FIELD, CT_INDEX, CT_INDEXKEY, CT_LONGLOCK]

    @classmethod
    def get_path_from_ring(cls, ring):
        return os.path.join(ring.datadefs_path, 'Standard')

    def refresh_completions(self):
        """Return True if the completions need to be reloaded."""
        logger.debug("Should Ring Object Completions Be Refreshed?")
        try:
            if self.get_path_update_time() <= self.last_modified_time:
                logger.debug("Don't Refresh Ring Object Completions")
                return False
            logger.debug("Refresh Ring Object Completions")
            return True
        except AttributeError:
            logger.debug("Refresh Ring Object Completions")
            return True

    def get_path_update_time(self):
        """Return the last time the file was modified."""
        return os.path.getmtime(self.path)

    def load_completions(self, **kwargs):
        """Loads the object completions from the ring.

        Gathers all the Datadef files and then spawns DatadefProcessor threads 
        to process them.

        """
        logger.debug('Running Object Loader thread')

        if not os.path.isdir(self.path):
            return

        file_queue = Queue()
        for filename in os.listdir(self.path):
            if filename.lower().endswith('.focus'):
                file_queue.put(os.path.join(self.path, filename))

        if file_queue.empty():
            return

        self.last_modified_time = self.get_path_update_time()
        threads = set()
        completion_queue = Queue()
        for i in range(4):
            t = ObjectRingLoader.DatadefProcessor(file_queue, completion_queue)
            t.start()
            threads.add(t)
        
        self.completions = dict()
        for t in threads:
            t.join()
            c = completion_queue.get()
            for t, s in c.items():
                try:
                    self.completions[t].update(s)
                except KeyError:
                    self.completions[t] = s

        logger.debug('Object Loader thread ending')

    class DatadefProcessor(threading.Thread):
        """Reads Datadef files and parses the relevant details."""
        
        def __init__(self, file_queue, completion_queue):
            """Creates a DatadefProcessor instance.

            Keyword arguments:
            file_queue - List of file paths for Datadef files.
            completion_queue - Once all files have been processed, completions
            gathered by this object are added to this queue.

            """
            super(ObjectRingLoader.DatadefProcessor, self).__init__()
            self.file_queue = file_queue
            self.completion_queue = completion_queue
            self.completions = dict()

        def run(self):
            """Processes Datadefs until the queue is empty, then adds completions to the queue."""
            while not self.file_queue.empty():
                self.process_datadef(self.file_queue.get())
            self.completion_queue.put(self.completions)

        def process_datadef(self, filename):
            """Extracts relevant information from the given Datadef file."""
            check_order = ('Field', 'Key', 'IndexKey', 'Record', 'Index', 'File',
                           'LongLock', 'Object')
            check_line = re.compile(r'\s*:.+$')
            for l in read_file(filename):
                if check_line.match(l):
                    l = l.strip()
                    for t in check_order:
                        if l.startswith(':%s ' % t):
                            v = l[(len(t)+1):].strip()
                            if (t == 'Object'):
                                object_ = v
                            elif (t == 'Index'):
                                index = '%s.%s' % (object_, v)
                                v = index
                            elif (t == 'IndexKey'):
                                v = '%s.%s' % (index, v)
                            else:
                                v = '%s.%s' % (object_, v)
                            try:
                                self.completions[t].add((v,))
                            except KeyError:
                                self.completions[t] = set()
                                self.completions[t].add((v,))
                            break


class StateRingLoader(RingLoader, FileLoader):
    """Loads completions from a View."""

    EmptyReturn = ([], sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)

    def __init__(self, ring = None, **kwargs):
        self.ring = ring
        path = self.__class__.get_path_from_ring(ring)
        super(RingLoader, self).__init__(path = path, file_path = path, **kwargs)

    @classmethod
    def completion_types(cls):
        """Return a set of completion types that this CompletionLoader can return."""
        return [CT_STATE]

    @classmethod
    def get_path_from_ring(cls, ring):
        """Returns the path to the list of state variables in the ring."""
        if ring.modern_ring:
            state_variables_path = ring.get_file_path(
                os.path.join('Environment', 'StateVariables.txt')
                )
        else:
            state_variables_path = ring.get_file_path(
                os.path.join('!Focus', 'Environment', 'StateVariables.txt')
                )
        logger.debug('state_variables_path = %s', state_variables_path)
        try:
            if os.path.exists(state_variables_path):
                return state_variables_path
        except TypeError:
            pass
        
        return None

    def load_completions(self, **kwargs):
        """Loads state variable completions from the ring."""
        try:
            self.completions = set([(v, ) for v in read_file(self.path)])
        except FileNotFoundError:
            logging.warning('%s could not be found', state_variables_path)
            logging.warning('State Variable completions could not be loaded.')


class SystemLoader(StaticLoader):
    """Loads completions from a View."""

    EmptyReturn = ([], sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS)
    LoadAsync = False
    SystemVariables = ("AboutBoxProgram",
                       "AccessLocalData",
                       "ANPTimeServer",
                       "AppCallbackExternalSub",
                       "AuditCode",
                       "AuditExternalSub",
                       "AuditProcessOff",
                       "AuditReadOff",
                       "AuditReadOn",
                       "AuditWriteOff",
                       "AuditWriteOn",
                       "BaseWindowSize",
                       "Client",
                       "ClientType",
                       "CodeUpdateRequired",
                       "CurrentProgram",
                       "DataDefProgram",
                       "DisableClientMessaging",
                       "DisableDataCache",
                       "DisableObjectLogging",
                       "DisableTransactionProcessing",
                       "DisconnectedSuffix",
                       "EmailProgram",
                       "EmulatedUser",
                       "ErrorProcess",
                       "Font",
                       "GlobalScreenStylesProgram",
                       "GlobalWebStylesProgram",
                       "HCIS",
                       "HelpProgram",
                       "MastScanServer",
                       "MaximizeExtraLargeWindow",
                       "MeditorLinkExternalSub",
                       "MeditorPrintExternalSub",
                       "OverrideClientName",
                       "Palette",
                       "PrintPrefProgram",
                       "PrintScrnProgram",
                       "ProcessControlledBy",
                       "ProcessGroup",
                       "ProcessIcon",
                       "ProcessMessage",
                       "PropertiesBoxProgram",
                       "ReferencesProgram",
                       "ReservedFilenameConversion",
                       "RetainErrorTrap",
                       "RingIndexType",
                       "RingSystemOIDBucketing",
                       "RootAccessViolationExternalSub",
                       "ServerCurrentRecordFilteringDisabled",
                       "SessionTempEncryptionOff",
                       "ShiftF4Program",
                       "ShowScreenDelayTimes",
                       "SignonUserMnemonic",
                       "SignonUserName",
                       "SpyExternalSub",
                       "SuppressHoverPointer",
                       "SuspendProgram",
                       "TimeInProgram",
                       "Timeout",
                       "TimeoutProgram",
                       "UnvIndexType",
                       "UnvSystemOIDBucketing",
                       "UserMnemonic",
                       "UserName",
                       "ViewOnlyMode",
                       "WebValidationProgram",
                       "WindowTitleSuffixExternalSub")

    @classmethod
    def completion_types(cls):
        """Return a set of completion types that this CompletionLoader can return."""
        return [CT_SYSTEM]

    @classmethod
    def view_scope(cls):
        """Return a scope to determine if the CompletionLoader will be enabled for a view."""
        return Focus.scope_map('source')

    def load_completions(self, **kwargs):
        """Loads system variable completions."""
        self.completions = set([(v, ) for v in SystemLoader.SystemVariables])

