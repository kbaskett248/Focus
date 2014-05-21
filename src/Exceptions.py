class InvalidFileFormat(Exception):
    """Exception that is thrown when trying to create a RingFile instance from 
       a file that is not supported."""

    def __init__(self, file_name, file_type, supported_extensions):
        super(InvalidFileFormat, self).__init__()
        self.file_name = file_name
        self.file_type = file_type
        self.supported_extensions = supported_extensions
        self.description = '%s is not a supported %s type. Supported extensions: %s' % (file_name, file_type, supported_extensions)

    def __str__(self):
        return self.description

class InvalidRingError(Exception):
    """Raised when trying to create a Ring for a path that is not a Ring."""
    def __init__(self, path):
        super(InvalidRingError, self).__init__()
        self.description = '{0} does not represent an M-AT Ring'.format(path)
        
    def __str__(self):
        return self.description

class InvalidCodeblockError(Exception):
    """Raised when trying to create a codeblock when not in a codeblock."""

    def __init__(self, view, point):
        super(InvalidCodeblockError, self).__init__()
        self.view = view
        self.filename = self.view.file_name()
        if self.filename is None:
            self.filename = self.view.name()
        self.point = point
        self.row, self.col = self.view.rowcol(self.point)
        self.line = self.view.line(point)
        self.line_text = self.view.substr(self.line)
        self.description = ('Point %s is not within a valid codeblock.\n' + 
                            'File: %s\n' +
                            '%s, %s: %s') % (self.point, self.filename, self.row+1, self.col+1, self.line_text)
        
    def __str__(self):
        return self.description