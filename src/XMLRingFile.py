import os

from .RingFile import RingFile

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class XMLRingFile(RingFile):
    '''Class representing an XML file within an M-AT ring. The constructor
       will throw an InvalidRingError if the file exists outside of a valid 
       ring.'''

    Extensions = ('xml',)
    FileType = 'XML File'

    def is_translatable(self):
        return (self.ring_object is not None)

    def translate(self):
        '''Code to handle translates for XML files.'''
        if self.is_translatable():
            partial_path = os.path.join('PgmObject', 'Foc', 
                                        'Focz.Textpad.Translate.P.mps')
            parameters = '"%s"' % self.filename
            return self.ring_object.run_file(partial_path = partial_path, 
                                             parameters = parameters)
        else:
            return False