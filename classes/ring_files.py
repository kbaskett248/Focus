from abc import abstractmethod
import os
import re

import logging
logger = logging.getLogger(__name__)

from .metaclasses import MiniPluginMeta
from .compatibility import FSCompatibility, FocusCompatibility
from .rings import get_ring, get_backup_ring
from ..tools.general import read_file


def get_ring_file(file_name):
    return RingFile.get_ring_file(file_name)


class RingFile(object, metaclass=MiniPluginMeta):
    '''
    Parent class for files that can exist in an M-AT Ring. The constructor
    can throw InvalidRingErrors if the file exists outside of a valid ring.
    This should be handled by subclasses if you want to allow files that
    are not in a ring.

    '''

    Files = {}

    def __new__(cls, file_name):
        logger.debug("Running RingFile.__new__ for %s",
                     cls.__name__)
        if cls.valid_file(file_name):
            return super(RingFile, cls).__new__(cls)
        else:
            raise InvalidFileFormat(file_name, cls, cls.extensions)

    def __init__(self, file_name):
        logger.debug("Running RingFile.__init__ for %s",
                     self.__class__.__name__)
        super(RingFile, self).__init__()

        RingFile.Files[file_name.lower()] = self

        self.file_name = file_name
        self.override_read_only = False
        self.ring = get_ring(self.file_name)

        logger.debug('New %s: %s', self.__class__.__name__, self.file_name)
        logger.debug("self.ring=%s", self.ring)

    def __str__(self):
        """Return a representation of the Ring File."""
        return '{0}, Ring: {1}'.format(os.path.basename(self.file_name),
                                       self.ring)

    @classmethod
    def get_ring_file(cls, file_name):
        logger.debug("Getting ring file for %s", file_name)
        f = None
        try:
            f = cls.Files[file_name.lower()]
            if f is None:
                raise InvalidFileFormat(file_name)
        except KeyError:
            logger.debug("checking classes")
            for c in cls.get_plugins():
                try:
                    f = c(file_name)
                except InvalidFileFormat:
                    # logger.exception(
                    #     "InvalidFileFormat exception")
                    continue
                except Exception:
                    logger.exception("Other exception")
                    continue
                else:
                    break
            else:
                logger.debug("no suitable class found")
                cls.Files[file_name.lower()] = None
                raise InvalidFileFormat(file_name)
        finally:
            logger.debug("Ring file: %s", f)
            return f

    @classmethod
    def valid_file(cls, file_name):
        return os.path.splitext(file_name)[1][1:].lower() in cls.extensions()

    @classmethod
    @abstractmethod
    def extensions(cls):
        '''
        This should be overloaded in RingFile subclasses. It should be a
        tuple of valid file extension strings for this file type without the
        leading ".".

        '''
        return tuple()

    def is_read_only(self):
        """Return True if the file should be read-only."""
        if self.override_read_only:
            result = False
        elif os.path.splitdrive(self.file_name)[0].endswith(':'):
            result = False
        else:
            result = True

        return result

    def get_ring(self):
        if self.ring is None:
            return get_backup_ring()
        else:
            return self.ring

    def is_translatable(self):
        if not self.get_ring():
            return False

        try:
            return callable(self.translate)
        except AttributeError:
            pass
        return False

    def is_runnable(self):
        if not self.get_ring():
            return False

        try:
            return bool(callable(self.run))
        except AttributeError:
            pass
        return False

    def is_formattable(self):
        if not self.get_ring():
            return False

        try:
            return callable(self.format)
        except AttributeError:
            pass
        return False

    def get_file_contents(self, split_lines=True, omit_empty_lines=True):
        lines = read_file(self.file_name, omit_empty_lines)
        if not split_lines:
            lines = '\n'.join(lines)
        return lines

    def get_contents(self):
        return self.get_file_contents(split_lines=False,
                                      omit_empty_lines=False)

    def get_line(self, point):
        """
        Returns a tuple of the span of the line or lines at the specified point
        and the contents of those lines.

        Keyword arguments:
        point - Either an int representing a point in the file or a tuple
            representing a selection in the file.
        """
        if isinstance(point, int):
            start = end = point
        elif isinstance(point, tuple):
            start = point[0]
            end = point[1]
        else:
            return (None, None)

        line_start = line_end = 0
        return_start = return_end = 0
        lines = []
        capture = False
        for l in self.get_lines_iterator():
            line_start = line_end
            line_end = line_start + len(l)
            # print('%s, %s, %s' % (line_start, line_end, l))

            if (line_start <= start) and (line_end >= start):
                capture = True
                return_start = line_start
            elif not capture:
                continue

            if l[-1] == '\n':
                l = l[:-1]
                line_end -= 1

            if capture:
                lines.append(l)
            if line_end >= end:
                return_end = line_end
                break

            line_end += 1
        else:
            if capture:
                return_end = line_end - 1

        if capture:
            return ((return_start, return_end), '\n'.join(lines))
        else:
            return (None, None)

    def get_lines_iterator(self, skip_blanks=False):
        """
        Creates an iterator that returns the lines of a file or view.
        """

        with open(self.file_name, 'r') as f:
            for line in f:
                if (not skip_blanks) or (line != '\n'):
                    yield line

    def get_lines_from_iterator(self, point, reverse=False, skip_blanks=False):
        """
        Creates an iterator that returns the lines of a file or view from the
        line containing the specified point.

        Keyword arguments:
        reverse - If false, return the lines from the line containing the
            specified point to the end. If True, return the lines from the
            line containing the specified point to the beginning.
        skip_blanks - If true, do not return empty lines.

        """
        if reverse:
            prev_lines = []
        line_start = line_end = 0

        for line in self.get_lines_iterator(skip_blanks):
            if reverse:
                prev_lines.append(line)
            else:
                yield line

            line_start = line_end
            line_end = line_start + len(line)
            if (line_start <= point) and (line_end >= point):
                break

        if reverse:
            for line in reversed(prev_lines):
                yield line


class FocusFile(RingFile, FocusCompatibility):
    """Class for Focus files that exist within a ring."""

    PRODUCT_TYPE_MATCHER = re.compile(r"(\.[A-Za-z])?\.focus$")
    INCLUDE_TRANSLATOR_MATCHER = re.compile(
        r"^#Include\n(.+?)^#[A-Za-z]+$", re.MULTILINE | re.DOTALL)
    INCLUDE_CONTENT_MATCHER = re.compile(
        r"(?P<source>:Source)|Folder\s+(?P<folder>.+)|File\s+(?P<filename>.+)")
    PAGESET_CONTENT_MATCHER = re.compile(
        r"(?P<pageset>:ExternalPageSet)|Code[Bb]ase\s+(?P<codebase>.+)|"
        r"Source\s+(?P<source>.+)")

    @classmethod
    def extensions(cls):
        '''
        This should be overloaded in RingFile subclasses. It should be a
        tuple of valid file extension strings for this file type without the
        leading ".".

        '''
        return ('focus',)

    TranslationErrorMatcher = re.compile(r"\d+ +[A-Za-z]+ +Errors?",
                                         re.IGNORECASE)

    def translate(self, separate_process=True):
        if not self.is_translatable():
            logger.warning('File: %s cannot be translated', self.file_name)
            return False

        ring = self.get_ring()
        if not ring:
            logger.warning('No ring configured to translate %s',
                           self.file_name)
            return False

        partial_path = os.path.join(
            'PgmObject', 'Foc', 'FocZ.Textpad.Translate.P.mps')

        if not ring.check_file_existence(partial_path):
            partial_path = os.path.join(
                'PgmObject', 'FocZ.Textpad.Translate.P.mps')
            if not ring.check_file_existence(partial_path):
                logger.warning('Translate file (%s) not found in ring: %s',
                               partial_path, ring)
                return False

        logger.info('Translating file: %s', self.file_name)

        # logger.info('Using %s for Translate command', partial_path)

        return ring.run_file(partial_path=partial_path,
                             parameters=self.file_name,
                             separate_process=separate_process)

        # else:
        #     partial_path = os.path.join(
        #         'PgmObject', 'Hha', 'HhaZt.Translate.P.mps')
        #     if results_file is None:
        #         results_file_name = tempfile.NamedTemporaryFile(
        #             suffix='.txt', delete=False).name
        #     else:
        #         results_file_name = results_file

        #     with open(results_file_name, 'a') as f:
        #         f.write('Translating file: {0}\n\n'.format(self.file_name))

        #     parameters = [self.file_name, results_file_name]
        #     parameters = chr(1) + chr(3).join(parameters) + chr(2)
        #     if not self.ring.run_file(partial_path=partial_path,
        #                               parameters=parameters,
        #                               separate_process=separate_process):
        #         logger.warning('Failed to launch translation')
        #         if results_file is not None:
        #             with open(results_file_name, 'a') as f:
        #                 f.write('Failed to launch translation\n\n')
        #         else:
        #             os.remove(results_file_name)

        #         return False

        #     if separate_process:
        #         return True

        #     error_found = False
        #     for l in read_file(results_file_name):
        #         match = self.TranslationErrorMatcher.match(l)
        #         if match is not None:
        #             error_found = True
        #             logger.error('Translation error encountered')
        #             break
        #     else:
        #         with open(results_file_name, 'a') as f:
        #             f.write('No errors\n\n')

        #     if results_file is None:
        #         os.remove(results_file_name)

        #     return not error_found

    def is_runnable(self):
        match = FocusFile.PRODUCT_TYPE_MATCHER.search(self.file_name.lower())
        if match is None:
            result = False
        elif match.group(1) is None:
            result = True
        elif match.group(1) in ('.p', '.s', ''):
            result = True
        else:
            result = False
        return result and bool(self.get_ring())

    def run(self, separate_process=True):
        if not self.is_runnable():
            logger.warning('File: %s cannot be translated', self.file_name)
            return False
        else:
            logger.info('Running file: %s', self.file_name)
            return self.get_ring().run_file_nice(
                full_path=self.file_name, separate_process=separate_process)

    def format(self):
        if not self.is_formattable():
            logger.warning('File: %s cannot be formatted', self.file_name)
            return False

        ring = self.get_ring()
        if not ring:
            logger.warning('No ring configured to format %s',
                           self.file_name)
            return False

        partial_path = os.path.join(
            'PgmObject', 'Foc', 'FocZ.Textpad.Format.P.mps')

        if not ring.check_file_existence(partial_path):
            logger.warning('Format file (%s) not found in ring: %s',
                           partial_path, ring)
            return False

        logger.info('Formatting file: %s', self.file_name)

        return ring.run_file(partial_path=partial_path,
                             parameters=self.file_name)

    def is_includable(self):
        l = self.file_name.lower()
        return (l.endswith('.i.focus') or l.endswith('.d.focus'))

    def includes(self, include_file):
        if self.ring is include_file.ring:
            logger.debug('Current File: %s', self.file_name)

            for f in self.get_include_files():
                if include_file.file_name.lower() == f.lower():
                    logger.debug('%s includes %s',
                                 self.file_name,
                                 include_file.file_name)
                    return True

        return False

    def get_include_files(self, current_file=True):
        """Returns a list of the include files in the file"""
        logger.debug('Getting include files for ' + self.file_name)

        if self.ring is None:
            return []

        include_source = '\n'.join(
            [s[1] for s in self.get_translator_sections('Include')])

        if not include_source:
            return []

        files = []

        for m in FocusFile.INCLUDE_CONTENT_MATCHER.finditer(include_source):
            if m.group('source'):
                folder = file_ = None
            elif m.group('folder'):
                folder = m.group('folder')
            elif m.group('filename'):
                file_ = m.group('filename')

            if folder and file_:
                include = self.ring.get_file_path(
                    os.path.join('PgmSource', folder, file_))
                if include is not None:
                    files.append(include)
                    yield include
                folder = file_ = include = None

        if not current_file:
            for f in files:
                inc_file = RingFile.get_ring_file(f)
                if inc_file is None:
                    continue

                for i in inc_file.get_include_files(current_file):
                    if i not in files:
                        files.append(i)
                        yield i

        return

    def get_external_pageset_files(self, current_file=True):
        """Returns a list of the External PageSets in a file."""

        if self.ring is None:
            return []

        screenpage_source = '\n'.join(
            [s[1] for s in self.get_translator_sections('ScreenPage')])

        if not screenpage_source:
            return []

        for m in FocusFile.PAGESET_CONTENT_MATCHER.finditer(
                screenpage_source):
            if m.group('pageset'):
                codebase = source = None
            elif m.group('codebase'):
                codebase = m.group('codebase')
            elif m.group('source'):
                source = m.group('source') + '.focus'

            if codebase and source:
                pageset = self.ring.get_file_path(
                    os.path.join('PgmSource', codebase, source))
                if pageset is not None:
                    yield pageset
                codebase = source = pageset = None

        if not current_file:
            for f in self.get_include_files(current_file=False):
                inc_file = RingFile.get_ring_file(f)
                if inc_file is None:
                    continue

                for i in inc_file.get_include_files(False):
                    yield i


class FSFile(RingFile, FSCompatibility):
    """docstring for FocusFile"""

    COMPILED_EXTENSIONS = ('mps', 'mcs', 'mts')

    @classmethod
    def extensions(cls):
        return ('fs',)

    def translate(self):
        if not self.is_translatable():
            logger.warning('File: %s cannot be translated', self.file_name)
            return False

        ring = self.get_ring()
        if not ring:
            logger.warning('No ring configured to translate %s',
                           self.file_name)
            return False

        full_path = ring.get_file_path('magic.mas')

        if not os.path.isfile(full_path):
            logger.warning('Magic.mas not found in ring: %s', ring)
            return False

        logger.info('Translating file: %s', self.file_name)

        return ring.run_file(full_path=full_path, parameters=self.file_name)

    def is_runnable(self):
        if not super(FSFile, self).is_runnable():
            return False

        return bool(self.get_compiled_path())

    def run(self):
        if not self.is_runnable():
            return False

        ring = self.get_ring()
        if ring is None:
            return False

        path = self.get_compiled_path()
        return ring.run_file(full_path=path)

    def get_compiled_path(self):
        leading = os.path.splitext(self.file_name)[0]
        for ext in FSFile.COMPILED_EXTENSIONS:
            result = leading + '.' + ext
            if os.path.isfile(result):
                return result

        return None


class XMLFile(RingFile):
    """docstring for FocusFile"""

    @classmethod
    def extensions(cls):
        return ('xml',)

    @classmethod
    def valid_file(cls, file_name):
        if super(XMLFile, cls).valid_file(file_name):
            return (get_ring(file_name) is not None)

        return False

    def translate(self):
        if not self.is_translatable():
            logger.warning('File: %s cannot be translated', self.file_name)
            return False

        ring = self.get_ring()
        if not ring:
            logger.warning('No ring configured to translate %s',
                           self.file_name)
            return False

        partial_path = os.path.join(
            'PgmObject', 'Foc', 'FocZ.Textpad.Translate.P.mps')

        if not ring.check_file_existence(partial_path):
            logger.warning('Translate file (%s) not found in ring: %s',
                           partial_path, ring)
            return False

        logger.info('Translating file: %s', self.file_name)

        return ring.run_file(partial_path=partial_path,
                             parameters=self.file_name)


class InvalidFileFormat(Exception):
    """
    Exception that is thrown when trying to create a RingFile instance from
    a file that is not supported.

    """

    def __init__(self, file_name, file_type=None, supported_extensions=None):
        super(InvalidFileFormat, self).__init__()
        self.file_name = file_name
        self.file_type = file_type
        self.supported_extensions = supported_extensions

    @property
    def description(self):
        try:
            return self._description
        except AttributeError:
            if ((self.file_type is not None) and
                    (self.supported_extensions is not None)):
                self._description = (
                    '%s is not a supported RingFile type.') % self.file_name
            else:
                self._description = (
                    '%s is not a supported %s type. Supported extensions: %s' %
                    (self.file_name, self.file_type.__name__,
                     self.supported_extensions))
            return self._description

    def __str__(self):
        return self.description
