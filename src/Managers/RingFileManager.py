import os

from ..FocusFile import FocusFile
from ..XMLRingFile import XMLRingFile
from ..FSFile import FSFile
from ..singletonmixin import Singleton
from ..Exceptions import *

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class RingFileManager(Singleton):
    '''Manager for the Ring Files in memory. The object is a singleton, so 
       only one instance of the object will exist.'''

    def __init__(self):
        '''Constructor for the RingFileManager. Initializes data structures to
           maintain valid and invalid files. Do not call this directly. 
           Instead, call the class's getInstance method.'''
        self.file_list = dict()
        self.exclude_set = set()
        self.completers = None
        self.comp_checkers = None

    def get_ring_file(self, view, allowed_file_types = []):
        '''Returns a reference to the RingFile object for the given view.

        Keyword arguments:
        view - A sublime view object
        allowed_file_types - A list of RingFile subclasses to filter the 
                             results by. Only files of the specified subclasses
                             will be returned.

        Returns a reference to the ring file object for the given view if 
        the view is for a valid RingFile. If the file already exists in the
        manager, a reference to the existing object is returned. Otherwise,
        the file is added to the manager and a RingFile instance is created
        and returned.

        '''
        f = None
        name = view.file_name()

        try:
            if ((name is not None) and (name.lower() not in self.exclude_set)):
                f = self.file_list[name.lower()]
        except KeyError:
            try:
                f = self.add_file(view)
            except InvalidFileFormat as e:
                self.exclude_set.add(name.lower())
                logger.debug(e)
            except InvalidRingError as e:
                self.exclude_set.add(name.lower())
                logger.debug(e)
        finally:
            if ((f is not None) and allowed_file_types):
                for t in allowed_file_types:
                    if isinstance(f, t):
                        break
                else:
                    f = None

        return f

    def get_ring_file_by_path(self, file_path):
        '''Returns a reference to the existing RingFile object with the given
           file_path.'''
        try:
            result = self.file_list[file_path.lower()]
        except KeyError:
            result = None
        finally:
            return result

    def add_file(self, view):
        '''If the view is for a valid RingFile, an instance of the appropriate 
           RingFile object is created and added to the file list.'''
        f = RingFileManager._get_typed_file(view)
        if (f is not None):
            self.file_list[view.file_name().lower()] = f
            f.completers = self.completers
            f.comp_checkers = self.comp_checkers
        return f

    def _get_typed_file(view):
        '''Tries to return an instance of a subclass of RingFile. If the 
           extension does not match the supported extensions for any of the 
           subclasses, an InvalidFileFormat exception is raised.'''
        name = view.file_name()
        logger.debug('Getting typed file for %s', name)
        if (name is None):
            return None
        types = (FocusFile, XMLRingFile, FSFile)
        for c in types:
            logger.debug('Testing for %s', c.FileType)
            try:
                return c(view)
            except InvalidFileFormat:
                logger.debug('No match')
                continue
            else:
                break
            # for e in c.Extensions:
            #     if name.endswith('.' + e):
            #         return c(view)
            #         break
        else:
            format_list = [e for c in types for e in c.Extensions]
            raise InvalidFileFormat(name, 'Ring File', format_list)
            return None
        

    def list_file_names(self, extensions = tuple()):
        '''Returns a list of filenames for files managed by the RingFileManager. 
           You can optionally limit it to only the files with specific 
           extensions by passing in a list of extensions.'''
        result = list(self.file_list.keys())
        result.sort()
        if extensions:
            extensions = ["." + e.lower() for e in extensions]
            return [a for a in result if (os.path.splitext(a)[1] in extensions)]
        else:
            return result

    def list_files(self, extensions = tuple()):
        '''Returns a list of the files managed by the RingFileManager. You can 
           optionally limit it to only the files with specific extensions by 
           passing in a list of extensions.'''
        if extensions:
            extensions = [e.lower() for e in extensions]
            return [self.file_list[a] for a in self.file_list.keys() if (os.path.splitext(a)[1][1:] in extensions)]
        else:
            return list(self.file_list.values())

    @property
    def num_files(self):
        '''Returns the number of files managed by the RingFileManager.'''
        return len(self.file_list)

    @property
    def completers(self):
        return self._completers
    @completers.setter
    def completers(self, value):
        logger.debug('Adding completers to File Manager')
        self._completers = set()
        if value:          
            for c in value:
                if c.is_view_completer() and c.enable_completer():
                    self._completers.add(c)
        print(self._completers)
        for f in self.list_files():
            f.completers = self._completers

    @property
    def comp_checkers(self):
        return self._comp_checkers
    @comp_checkers.setter
    def comp_checkers(self, value):
        logger.debug('Adding comp_checkers to File Manager')
        self._comp_checkers = set()
        if value:          
            for c in value:
                if c.enable_checker():
                    self._comp_checkers.add(c)
        for f in self.list_files():
            f.comp_checkers = self._comp_checkers
    
