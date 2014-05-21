import os

from .RingFile import RingFile
from .Managers.RingManager import RingManager
from .Exceptions import InvalidRingError

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

RING_MANAGER = RingManager.getInstance()

class FSFile(RingFile):
    '''Class representing an FS file within an M-AT ring.'''

    Extensions = ('fs',)
    FileType = 'FS file'

    def __init__(self, view):
        '''Creates an FSFile instance if the file is a .fs file. Otherwise, 
           throws an InvalidFileFormat exception.'''
        try:
            super(FSFile, self).__init__(view)
        except InvalidRingError:
            self.ring_object = None

    def is_translatable(self):
        '''Returns True if the file can be translated.'''
        return (self.backup_ring is not None)

    def translate(self):
        '''Code to handle translates for FS files. Returns True if the file
           was translated or False otherwise.'''
        if not self.is_translatable():
            return False
        ring_object = self.ring_object
        if (ring_object is None):
            ring_object = self.backup_ring

        if (ring_object is None):
            return False
        else:
            translate_path = os.path.join(ring_object.system_path, 'magic.mas')
            return ring_object.run_file(full_path = translate_path, 
                                        parameters = self.filename)

    def is_runnable(self):
        '''Returns true if the file can be run.'''
        return self.is_translatable()

    def run(self):
        '''Handles runs for FS files. Returns True if the file was run or 
           False otherwise.'''
        if not self.is_runnable():
            return False
        ring_object = self.ring_object
        if (ring_object is None):
            ring_object = self.backup_ring

        if (ring_object is None):
            return False
        else:
            return ring_object.run_file(full_path = self.filename)