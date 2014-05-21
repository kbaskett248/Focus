import os
import re

import sublime

import Focus
from .DocFinder import DocFinder
from .. import FocusLanguage
from ..tools import read_file
from ..FocusFile import extract_focus_function_name

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class ObjectFinder(DocFinder):
    """DocFinder class for finding documentation for objects."""

    ScopeMap = 'focus_object'
    
    @classmethod
    @DocFinder.api_call
    def check(cls, view, ring_file):
        sel = view.sel()[0]
        search_region = view.word(sel)
        search_string = view.substr(search_region)
        return cls(search_string, search_region, ring_file, view)

    @DocFinder.api_call
    def show(self):
        sublime.status_message("Looking up definition of %s" % self.search_string)
        string_parts = self.search_string.split('.')
        object_ = string_parts[0]
        parts = [('Object', object_)]
        line_text = self.view.substr(self.view.line(self.search_region)).strip()

        if (len(string_parts) == 1):
            pass
        elif (Focus.score_selector(self.view, self.search_region.begin(), 'focus_function') > 0):
            function_name = extract_focus_function_name(self.view, self.search_region)[0]
            if (function_name != ''):
                function_name = function_name[1:]
                try:
                    type_ = FocusLanguage.FOC_FUNC_COMP[function_name][0]
                except KeyError:
                    pass
                else:
                    if (type_ == 'IndexKey'):
                        parts.extend([('Index', string_parts[1]), 
                                      ('IndexKey', string_parts[2])])
                    else:
                        parts.append((type_, string_parts[1]))
        elif ((Focus.score_selector(self.view, self.search_region.begin(), 'keyword_line') > 0) or 
              (Focus.score_selector(self.view, self.search_region.begin(), 'attribute_line') > 0)):
            if line_text.startswith(':Element'):
                if self.search_string in self.ring_file.get_completions(self.view, ['Key'], True):
                    parts.append(('Key', string_parts[1]))
                else:
                    parts.append(('Field', string_parts[1]))
            elif line_text.startswith('Name'):
                tree = set([t[0] for t in self.ring_file.build_translator_tree(self.view)])
                if (':LongLock' in tree):
                    parts.append(('LongLock', string_parts[1]))
                elif ((':Record' in tree) or (':Records' in tree)):
                    parts.append(('Record', string_parts[1]))
            else:
                for t in ('File', 'Record', 'Index'):
                    if (line_text.startswith(t) or line_text.startswith(':' + t)):
                        parts.append((t, string_parts[1]))
                        break
        # logger.debug(object_)
        # logger.debug(parts)

        file_, region = self.find_object(object_, parts)
        logger.debug('File: %s; Region: %s', file_, region)

        status_message_suffix = self.move_or_open(file_, region, show_at_top = False)

        sublime.status_message(
            "Documentation for {0} {1}".format(self.search_string, 
                                               status_message_suffix)
            )

    def find_object(self, object_, parts):
        """Finds documentation for the object it exists.

        Keyword arguments:
        object_ - Name of object
        parts - List of (type, value) where type can be a string or a list of
                strings: Object, Record, Field, etc.

        Function first checks the current file, then the ring datadefs, then
        the include files.

        """
        logger.debug('Parts: %s', parts)
        file_, region = self.find_object_in_open_file(parts)

        if ((file_ is None) and (self.ring_file.ring_object is not None)):
            file_, region = self.find_object_in_ring(object_, parts)

        if (file_ is None):
            for f in self.ring_file.get_include_files(self.view):
                file_, region = self.find_object_in_other_file(f, parts)
                if region is not None:
                    break

        yield file_
        yield region

    def find_object_in_open_file(self, parts):
        """Finds documentation for the object in the currently opened file."""
        file_ = None
        region = None
        datadef_regions = Focus.find_by_selector(self.view, '#DataDef')
        for r in datadef_regions:
            start = r.begin()
            for p in parts:
                pattern = self.get_object_match_pattern(p[0], p[1])
                logger.debug(pattern)
                region = self.view.find(pattern, start)
                if ((region is None) or region.empty()):
                    region = None
                    break
                elif r.contains(region):
                    start = region.end()
                    continue
                else:
                    region = None
                    break
            if (region is not None):
                file_ = self.ring_file.filename
                break

        yield file_
        yield region

    def find_object_in_ring(self, object_, parts):
        """Finds documentation for the object in a datadef defined in the ring."""
        file_ = os.path.join(self.ring_file.ring_object.datadefs_path, 
            'Standard', object_ + '.focus')
        file_, region = self.find_object_in_other_file(file_, parts)

        yield file_
        yield region

    def find_object_in_other_file(self, file_, parts):
        """Finds documentation for the object in any given file."""
        region = None
        if os.path.isfile(file_):
            logger.debug(file_)
            file_contents = read_file(file_, False)
            object_matchers = (re.compile(self.get_object_match_pattern(p[0], p[1])) for p in parts)
            matcher = next(object_matchers)
            logger.debug(matcher.pattern)
            match = None
            for line, text in enumerate(file_contents):
                match = matcher.match(text)
                if (match is not None):
                    logger.debug('Match on line %s', line)
                    logger.debug('Match with text %s', text)
                    try:
                        matcher = next(object_matchers)
                        logger.debug(matcher.pattern)
                    except StopIteration:
                        logger.debug('Done on line %s', line)
                        logger.debug('Done with text %s', text)
                        break
            if (match is not None):
                region = (line+1, match.start(2)+1)
                logger.debug(region)
        else:
            file_ = None

        yield file_
        yield region

    def get_object_match_pattern(self, types, value):
        """Returns a RegEx pattern given the types and value.
        
        Keyword arguments:
        types - String or list of strings: Object, record, field, etc.
        value - Value for that item

        """
        if (isinstance(types, list) or isinstance(types, tuple) or isinstance(types, set)):
            return r'^ *:(%s) +(%s) *$' % ('|'.join(types), value)
        else:
            return r'^ *:(%s) +(%s) *$' % (types, value)

    @DocFinder.api_call
    def description(self):
        return 'Show definition of ' + self.search_string

