import os

from .Managers.RingManager import RingManager
from .Exceptions import InvalidFileFormat

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

RING_MANAGER = RingManager.getInstance()

class RingFile(object):
    '''Parent class for files that can exist in an M-AT Ring. The constructor
       can throw InvalidRingErrors if the file exists outside of a valid ring.
       This should be handled by subclasses if you want to allow files that 
       are not in a ring.'''

    Extensions = (None,)
    '''This should be overloaded in RingFile subclasses. It should be a tuple
       of valid file extension strings for this file type without the 
       leading ".".'''

    FileType = 'Ring file'

    CompleterClasses = set()
    
    def __init__(self, view):
        '''Creates a RingFile instance. Throws an InvalidRingError if the file
           is not in a valid ring.'''

        self.filename = view.file_name()
        if (self.filename is None):
            raise InvalidFileFormat(view.name(), self.FileType, self.Extensions)
        ext = os.path.splitext(self.filename)[1][1:].lower()
        logger.debug('File extension: %s', ext)
        if (ext not in self.Extensions):
            raise InvalidFileFormat(self.filename, self.FileType, self.Extensions)
        self.override_read_only = False
        self.ring_object = RING_MANAGER.get_ring_by_path(self.filename)
        self.completers = None
        self.comp_checkers = None


    @property
    def ring_path(self):
        '''Returns the path to the ring folder that the file is in, or None if 
           it is not in a ring.'''
        try:
            return self.ring_object.ring_path
        except AttributeError:
            logger.detail('%s has no ring' % self.filename)
            return None

    @property
    def universe_path(self):
        '''Returns the path to the universe folder that the file is in, or None
           if it is not in a ring.'''
        try:
            return self.ring_object.universe_path
        except AttributeError:
            logger.debug('File has no ring.')
            return None
    
    @property
    def ring(self):
        '''Returns the name of the ring that the file is in, or None if it is 
           not in a ring.'''
        try:
            return self.ring_object.name
        except AttributeError:
            logger.debug('File has no ring.')
            return None
    
    @property
    def universe(self):
        '''Returns the name of the universe that the file is in, or None if it 
           is not in a ring.'''
        try:
            return self.ring_object.universe
        except AttributeError:
            logger.debug('File has no ring.')
            return None
    
    @property
    def partial_path(self):
        '''Returns the path of the file relative to the ring folder that the 
           file is in, or None if it is not in a ring.'''
        try:
            return self.ring_object.partial_path(self.filename)  
        except AttributeError:
            logger.debug('File has no ring.')
            return None

    @property
    def backup_ring(self):
        '''Returns a ring that can be used if no ring is associated with the file.'''
        if (self.ring_object is None):
            ring_list = RING_MANAGER.list_rings(local_only = True)
            if ring_list:
                ring_list.sort()
                return ring_list[-1]
            else:
                return None
        else:
            return self.ring_object
    

    def is_translatable(self):
        """Return True if the file can be translated."""
        return False

    def translate(self):
        '''Translates the file.'''
        pass

    def is_runnable(self):
        '''Return True if the file can be run.'''
        return False

    def run(self):
        '''Runs the file.'''
        pass

    def is_read_only(self):
        """Return True if the file should be read-only."""
        result = True
        if self.override_read_only:
            result = False
        elif (self.ring_object is None):
            result = False
        elif self.ring_object.local_ring:
            result = False
        elif (self.ring_object.cache_path.lower() in self.filename.lower()):
            result = False
        return result

    def __str__(self):
        """Return a representation of the Ring File."""
        return '{0}, Ring: {1}'.format(os.path.basename(self.filename), self.ring)

    @property
    def completers(self):
        return self._completers
    @completers.setter
    def completers(self, value):
        # logger.debug('Adding completers to RingFile')
        self._completers = set()
        if value:          
            for c in value:
                if (c.is_view_completer() and 
                    c.enable_completer(ring_file = self, 
                                       ring = self.ring_object)):
                    self._completers.add(c(self))

    @property
    def comp_checkers(self):
        return self._comp_checkers
    @comp_checkers.setter
    def comp_checkers(self, value):
        # logger.debug('Adding comp checkers to RingFile')
        self._comp_checkers = set()
        if value:          
            for c in value:
                if c.enable_checker(ring_file = self):
                    self._comp_checkers.add(c(self))
