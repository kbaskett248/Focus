import functools
import imp
import inspect
import os
import re
import sys
import urllib

from bs4 import BeautifulSoup

import sublime

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

try:
    from EntitySelect.src.EntitySelector import EntitySelector
    from EntitySelect.src.DocLink import DocLink
    from EntitySelect.src.Highlight import Highlight, PreemptiveHighlight
    from EntitySelect.src.StatusIdentifier import StatusIdentifier
except ImportError as e:
    logger.error('EntitySelect package not installed')    
    raise e

import Focus
from .src.FocusFile import FocusFile, extract_focus_function, extract_focus_function_name, split_focus_function, extract_fs_function, extract_alias, CodeBlockDocumentation, CodeBlockSet
from .src.Managers.RingFileManager import RingFileManager
from .src.tools import MultiMatch, read_file
from .src import FocusLanguage

FILE_MANAGER = RingFileManager.getInstance()
FOCUS_WIKI = "http://stxwiki/wiki10/"
FS_WIKI = "http://stxwiki/magicfs6/"

def plugin_loaded():
    for c in EntitySelector.get_defined_classes(globals()):
        c.add_possible_selector()

def plugin_unloaded():
    for c in EntitySelector.get_defined_classes(globals()):
        c.remove_possible_selector()
    imp.reload(sys.modules[__name__])

def line_match_region(line_region, match_object, match_group):
    b = line_region.begin()
    s = match_object.span(match_group)
    return sublime.Region(b + s[0], b + s[1])


class FocusFunctionDocLink(DocLink, PreemptiveHighlight):
    """DocLink class for Focus functions. Shows the documentation for the 
    function on the wiki."""

    @classmethod
    def scope_view_enabler(cls):
        return Focus.scope_map('source')

    @classmethod
    def scope_selection_enabler(cls):
        return Focus.scope_map('focus_function_finder')
    
    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        match = extract_focus_function(view, sel)

        if match is not None:
            match = split_focus_function(match[0], match[1])

            if match is not None:
                search_string = '@' + match[0][0]
                search_region = match[0][1]
                search_region = sublime.Region(
                    search_region.begin()-1, search_region.end())
                return {'search_string': search_string, 
                        'search_region': search_region}

        return None

    def show_doc(self):
        sublime.status_message(self.open_status_message)
        self.show_doc_on_web(FOCUS_WIKI + self.search_string)

    def enable_highlight(self):
        if self.search_string == '@Break':
            return True
        else:
            return False

    def get_highlight_regions(self):
        return Focus.find_by_selector(self.view, 'debug_function')

    @classmethod
    def preemptive_highlight_id(cls):
        return 'focus_breaks'

    @classmethod
    def get_preemptive_highlight_selection(cls, view):
        regions = Focus.find_by_selector(view, 'debug_function')
        if not regions:
            return []
        point = regions[0].begin()
        return [sublime.Region(point, point)]

    def get_display_region(self, reg):
        return ['%s: %s' % (self.view.rowcol(reg.begin())[0] + 1,
                           self.view.substr(reg)),
                self.view.substr(self.view.line(reg))]


class FSFunctionDocLink(DocLink, Highlight, StatusIdentifier):
    """DocLink class for FS functions. Shows the documentation for the function
    on the wiki."""

    @classmethod
    def scope_view_enabler(cls):
        return Focus.scope_map('source') + ', source.fs'

    @classmethod
    def scope_selection_enabler(cls):
        return Focus.scope_map('fs_function')
    
    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        
        function = extract_fs_function(view, sel)
        if (function is not None):
            match = re.match(r"@[A-Z][A-Za-z0-9]", function[0])
            if match is not None:
                return {'search_string': function[0], 
                        'search_region': function[1]}

        return None

    def show_doc(self):
        doc = self.format_documentation()
        if doc is None:
            url = self.get_url()
            if (url is not None):
                sublime.status_message(self.open_status_message)
                self.show_doc_on_web(url)
            return

        window = self.view.window()
        output_panel = window.create_output_panel('fs_function_doc')
        output_panel.run_command('entity_select_insert_in_view', {'text': doc})
        window.run_command('show_panel', {'panel': 'output.fs_function_doc'})

    def get_url(self):
        match = re.match(r"@[A-Za-z]{1,2}", self.search_string)
        if (match is not None):
            return FS_WIKI + match.group(0)
        else:
            return None

    def enable_highlight(self):
        try:
            return self._enable_highlight
        except AttributeError:
            self._enable_highlight = self.is_listset_function()
            return self._enable_highlight

    def is_listset_function(self):
        sel = self.view.sel()[0]
        score_selector = functools.partial(Focus.score_selector, self.view, sel.begin())

        if score_selector('fs_set_function') <= 0:
            return False
        elif score_selector('subroutine') <= 0:
            return False
        
        fs_func, search_region = extract_fs_function(self.view, sel)
        set_number = fs_func[2:]
        # logger.debug('set_number = %s', set_number)
        upper_or_lower = CodeBlockSet.determine_upper(fs_func)
        # logger.debug('upper_or_lower = %s', upper_or_lower)
        search_string = CodeBlockSet.format_set(set_number, upper_or_lower)
        # logger.debug('self.search_string = %s', search_string)
        self.set = search_string
        return True

    def get_highlight_regions(self):
        regions = []
        codeblock, set_doc_region = self.setup(self.view)

        function_sets = codeblock.get_sets_from_function()
        regions.extend(function_sets[self.set].regions)

        doc_match = self.get_doc_match(self.set, set_doc_region)
        if (doc_match is not None):
            regions.append(doc_match)

        regions.sort()

        return regions

    @staticmethod
    def setup(view):
        ring_file = FILE_MANAGER.get_ring_file(view)
        if ring_file is None:
            return (None, None)

        codeblock = ring_file.get_codeblock(view)
        sets_doc_region = codeblock.documentation_region
        documentation = CodeBlockDocumentation(codeblock)

        try:
            sets_doc_region = documentation.doc_regions['Data Structures'].region
        except KeyError:
            pass

        return (codeblock, sets_doc_region)

    def get_doc_match(self, listset, region):
        r = None
        listset = "%s\(%s\)" % (listset[0], listset[2:-1])
        pattern = r"//\s*(%s)\s*[-=:]\s*" % listset

        doc_match = self.view.find(pattern, region.begin())
        if ((doc_match is not None) and region.intersects(doc_match)):
            substring = self.view.substr(doc_match)
            match = re.match(pattern, substring)
            
            if (match is not None):
                span = match.span(1)
                r = sublime.Region(doc_match.begin() + span[0], doc_match.begin() + span[1])
        return r

    @property
    def highlight_description_highlight(self):
        return 'Highlight: ' + self.set

    @property
    def highlight_description_forward(self):
        return 'Next instance of ' + self.set
    
    @property
    def highlight_description_backward(self):
        return 'Previous instance of ' + self.set
    
    @property
    def highlight_description_clear(self):
        return 'Clear highlights'
    
    @property
    def highlight_description_select_all(self):
        return 'Select all instances of ' + self.set

    @property
    def highlight_description_show_all(self):
        return 'Show all instances of ' + self.set

    def scrape_page(self):
        try:
            f = urllib.request.urlopen(self.get_url()) 
        except urllib.error.URLError:
            return None
        else:
            d = dict()
            soup = BeautifulSoup(f)
            content = soup.find('div', class_='mw-content-ltr')

            tab = content.table
            for r in tab.find_all('tr'):
                e = list(r.stripped_strings)
                if (('ide' in e[0]) and ('ffect' in e[0])):
                    e[0] = 'Side Effect'
                d[e[0].lower()] = ' '.join(e[1:])

            comments = content.find('div', text='Comments').parent
            comments = comments.find_next_sibling('div')
            comments = ''.join(list(comments.strings))
            d['comments'] = comments.strip()

            examples = content.find('div', text='Code Examples').parent
            examples = examples.find_next_sibling('div')
            examples = ''.join(list(examples.strings))
            d['examples'] = examples.strip()
            # logger.debug('scrape_page = %s', d)
            return d

    def format_documentation(self):
        d = self.scrape_page()
        if d is None:
            return None
        return ("\n{function}  {name}\n\n\n"
            "Function:         {function}\n"
            "Name:             {name}\n"
            "Group:            {group}\n"
            "Precondition:     {precondition}\n"
            "Return:           {return}\n"
            "Side effect:      {side effect}\n\n\n"
            "Comments\n"
            "--------\n"
            "{comments}\n\n\n"
            "Code Examples\n"
            "-------------\n"
            "{examples}\n").format(**d)

    @property
    def status_string(self):
        if self._status_string is not None:
            pass
        else:
            d = self.scrape_page()
            if d is None:
                return None
            self._status_string = "{function}: {name}".format(**d)
        return self._status_string
    @status_string.setter
    def status_string(self, value):
        self._status_string = value


class SetDocHighlighter(Highlight):

    @classmethod
    def scope_view_enabler(cls):
        return Focus.scope_map('source') + ', source.fs'

    @classmethod
    def scope_selection_enabler(cls):
        return Focus.scope_map('fs_set_doc_highlighter')
    
    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        score_selector = functools.partial(Focus.score_selector, view, sel.begin())
        
        codeblock, set_doc_region = cls.setup(view)

        if ((set_doc_region is not None) and sel.intersects(set_doc_region)):
            doc_matches = view.find_all(r"//\s*(L|U)\(\d+\)\s*[-=:]\s*[\s\S]*?\n(?=//\s*(L|U)\(\d+\)\s*[-=:]|//:Doc)")
            for r in doc_matches:
                if r.contains(sel):
                    match = re.search(r"//\s*((L|U)\(\d+\))\s*[-=:]\s*", view.substr(r))
                    if match:
                        region = line_match_region(r, match, 1)
                        return {'search_region': region}
        
        return None

    def get_highlight_regions(self):
        regions = []
        codeblock, set_doc_region = self.setup(self.view)

        function_sets = codeblock.get_sets_from_function()
        try:
            regions.extend(function_sets[self.search_string].regions)
        except KeyError:
            pass

        doc_match = self.get_doc_match(self.search_string, set_doc_region)
        if (doc_match is not None):
            regions.append(doc_match)

        regions.sort()

        return regions

    @staticmethod
    def setup(view):
        ring_file = FILE_MANAGER.get_ring_file(view)
        if ring_file is None:
            return (None, None)

        codeblock = ring_file.get_codeblock(view)
        sets_doc_region = codeblock.documentation_region
        documentation = CodeBlockDocumentation(codeblock)

        try:
            sets_doc_region = documentation.doc_regions['Data Structures'].region
        except KeyError:
            pass

        return (codeblock, sets_doc_region)

    def get_doc_match(self, listset, region):
        r = None
        listset = "%s\(%s\)" % (listset[0], listset[2:-1])
        pattern = r"//\s*(%s)\s*[-=:]\s*" % listset

        doc_match = self.view.find(pattern, region.begin())
        if ((doc_match is not None) and region.intersects(doc_match)):
            substring = self.view.substr(doc_match)
            match = re.match(pattern, substring)
            
            if (match is not None):
                span = match.span(1)
                r = sublime.Region(doc_match.begin() + span[0], doc_match.begin() + span[1])
        return r

    def highlight_status_message(self, total, selection = None):
        if (selection is not None):
            return "%s of %s highlighted instances of %s" % (selection, total, self.search_string)
        else:
            return "%s highlighted instances of %s" % (total, self.search_string)


class SubroutineDocLink(DocLink, Highlight):
    """DocLink class for Subroutines. Shows the subroutine definition. If the
    subroutine is contained in an include file, that file is opened."""

    @classmethod
    def scope_view_enabler(cls):
        return Focus.scope_map('source')

    @classmethod
    def scope_selection_enabler(cls):
        return Focus.scope_map('subroutine_name')

    @classmethod
    def enable_for_view(cls, view):
        focus_file = FILE_MANAGER.get_ring_file(view, 
                allowed_file_types = [FocusFile])
        if focus_file is None:
            return False
        return True
    
    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        region = view.extract_scope(sel.begin())
        if view.extract_scope(sel.end()) != region:
            return False
        string = view.substr(region)
        match = re.match(r":Code +(\S.*)", string.strip())
        if match is not None:
            region = line_match_region(region, match, 1)
            string = view.substr(region)
        return {'search_string': string, 'search_region': region}

    def enable_doc_link(self):
        try:
            return self._enable_doc_link
        except AttributeError:
            self._enable_doc_link = Focus.score_selector(self.view, self.regions[0].begin(), 'subroutine_header') <= 0
            return self._enable_doc_link

    def show_doc(self):
        sublime.status_message(self.open_status_message)
        focus_file = FILE_MANAGER.get_ring_file(self.view)
        file_, region = focus_file.find_subroutine(self.view, self.search_string)
        logger.debug('File: %s; Region: %s', file_, region)

        if isinstance(region, tuple):
            status_message_suffix = self.show_doc_in_file(file_, row = region[0], col = region[1])
        else:
            status_message_suffix = self.show_doc_in_file(file_, region)

        sublime.status_message(
            "Documentation for {0} {1}".format(self.search_string, 
                                               status_message_suffix)
            )

    def get_highlight_regions(self):
        return [r for r in Focus.find_by_selector(self.view, 'subroutine_name') if
                (self.view.substr(r) == self.search_string)]

    def highlight_status_message(self, total, selection = None):
        if (selection is not None):
            return "%s of %s highlighted instances of %s" % (selection, total, self.search_string)
        else:
            return "%s highlighted instances of %s" % (total, self.search_string)


class TranslatorDocLink(DocLink):
    """DocLink class for Translator keywords and attributes. Opens the
    documentation for the selected entity on the wiki."""

    @classmethod
    def scope_view_enabler(cls):
        return Focus.scope_map('source')

    @classmethod
    def scope_selection_enabler(cls):
        return Focus.scope_map('translator_finder')
    
    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        line_region = view.line(sel)
        preceding_line_region = sublime.Region(line_region.begin(), sel.end())

        line_text = view.substr(line_region)
        preceding_line_text = view.substr(preceding_line_region)

        match = re.match(r"^ *([A-Za-z#:]+)( |$)", line_text)
        if ((match is not None) and match.group(0).startswith(preceding_line_text)):
            search_region = sublime.Region(line_region.begin() + match.span(1)[0],
                                           line_region.begin() + match.span(1)[1])
            return {'search_string': match.group(1), 'search_region': search_region}

        return None

    def show_doc(self):
        sublime.status_message(self.open_status_message)
        if Focus.score_selector(self.view, self.regions[0].begin(), 'translator') > 0:
            url_arg = 'X-%s' % self.search_string[1:]
        else:
            translator = keyword = attribute = ''
            focus_file = FILE_MANAGER.get_ring_file(self.view)
            logger.debug(focus_file)
            for t in (t[0] for t in focus_file.build_translator_tree(self.view)):
                if (t[0] == '#'):
                    translator = 'X-%s' % t[1:]
                elif (t[0] == ':'):
                    keyword = '-%s' % t[1:]
                else:
                    attribute = '#%s' % t
            url_arg = translator + keyword + attribute
        self.show_doc_on_web(FOCUS_WIKI + url_arg)


class AliasDocLink(DocLink):
    """DocLink class for Home Care aliases. Displays the definition of the 
    alias. If in another file, that file is opened. If the alias is for a 
    subroutine, that subroutine is displayed."""

    @classmethod
    def scope_view_enabler(cls):
        return Focus.scope_map('source')

    @classmethod
    def scope_selection_enabler(cls):
        return Focus.scope_map('alias')
    
    @classmethod
    def enable_for_selection(cls, view):
        logger.debug('Alias scope matched')
        sel = view.sel()[0]
        alias = extract_alias(view, sel)
        logger.debug('alias = %s', alias)

        if alias is not None:
            return {'search_string': alias[0], 'search_region': alias[1]}
        return None

    def show_doc(self):
        sublime.status_message(self.open_status_message)
        file_ = region = row = col = None
        file_, region = self.find_alias_in_current_file()
        if (file_ is None):
            file_, row, col = self.find_alias_in_other_file()

        status_message_suffix = self.show_doc_in_file(file_, region = region, row = row, col = col)
        sublime.status_message(
            "Documentation for {0} {1}".format(self.search_string, 
                                               status_message_suffix)
            )

    def find_alias_in_current_file(self):
        file_ = self.view.file_name()
        focus_file = FILE_MANAGER.get_ring_file(self.view)
        region = focus_file.find_alias(self.view, self.search_string[2:-2])
        if (region is None):
            file_ = None
        yield file_
        yield region

    def find_alias_in_other_file(self):
        file_ = row = col = None
        region = None
        focus_file = FILE_MANAGER.get_ring_file(self.view)
        location = focus_file.ring_object.find_alias(self.search_string[2:-2])
        if (location is not None):
            file_ = location[0]
            row = location[1]
            col = location[2]

        yield file_
        yield row
        yield col


class IncludeFileDocLink(DocLink):
    """DocLink class for Included files and External Pagesets. Opens the file."""

    IncludeFileMatcher = MultiMatch(patterns = {'Folder': r" *Folder +([A-Za-z0-9._]+)", 
                'File': r" *File +([A-Za-z0-9._]+)"})

    ExternalPageMatcher = MultiMatch(patterns = {'Codebase': r" *Code[Bb]ase +([A-Za-z0-9]+)", 
                'Source': r" *Source +([\w._-]+)",
                'PageName': r' *PageName +([\w.-_]+)',
                'ContainerPage': r' *:ContainerPage +([\w._-]+)'
                })

    def __init__(self, view, search_string = None, search_region = None, type_ = None):
        super(IncludeFileDocLink, self).__init__(view, search_string, search_region)
        self.type_ = type_

    @classmethod
    def scope_view_enabler(cls):
        return Focus.scope_map('source')

    @classmethod
    def scope_selection_enabler(cls):
        return Focus.scope_map('include_file_finder')

    @classmethod
    def enable_for_view(cls, view):
        focus_file = FILE_MANAGER.get_ring_file(view, 
                allowed_file_types = [FocusFile])
        if focus_file is None:
            return False
        elif focus_file.ring is None:
            return False
        return True
    
    @classmethod
    def enable_for_selection(cls, view):
        logger.debug('Checking if IncludeFileDocLink is enabled for this selection')
        sel = view.sel()[0]
        line_region = view.line(sel)
        text = view.substr(line_region)

        if (Focus.score_selector(view, sel.begin(), '#Include') > 0):
            cls.IncludeFileMatcher.match_string = text
            if cls.IncludeFileMatcher.named_match("File"):
                search_string = cls.IncludeFileMatcher.group(1)
                search_region = line_match_region(line_region, cls.IncludeFileMatcher.current_match, 1)
                return {'search_string': search_string,
                        'search_region': search_region,
                        'type_': 'Include'}

        elif (Focus.score_selector(view, sel.begin(), '#ScreenPage') > 0):
            cls.ExternalPageMatcher.match_string = text
            if cls.ExternalPageMatcher.named_match("Source"):
                search_string = cls.ExternalPageMatcher.group(1)
                search_region = line_match_region(line_region, cls.ExternalPageMatcher.current_match, 1)
                return {'search_string': search_string,
                        'search_region': search_region,
                        'type_': 'External Pageset'}

        return None
        
    def show_doc(self):
        focus_file = FILE_MANAGER.get_ring_file(self.view)
        sublime.status_message(self.open_status_message)
        if self.type_ == 'Include':
            included_files = {os.path.basename(f): f for f in focus_file.get_include_files(self.view)}
        elif self.type_ == 'External Pageset':
            included_files = {os.path.basename(f)[:-6]: f for f in focus_file.get_externalpageset_files(self.view)}
        logger.debug(included_files)

        try:
            f = included_files[self.search_string]
        except KeyError:
            sublime.status_message(
                "{0} not found".format(self.search_string)
                )
        else:
            self.view.window().open_file(f)
            logger.info('Opening %s', f)
            sublime.status_message(
                "{0} found".format(self.search_string)
                )


class LocalDocLink(DocLink, Highlight):
    """DocLink class for Focus locals. Displays the definition of the local 
    from the #Locals section."""

    @classmethod
    def scope_view_enabler(cls):
        return Focus.scope_map('source')

    @classmethod
    def scope_selection_enabler(cls):
        return Focus.scope_map('focus_local')

    def enable_doc_link(self):
        try:
            return self._enable_doc_link
        except AttributeError:
            self._enable_doc_link = Focus.score_selector(self.view, self.regions[0].begin(), 'focus_function') > 0
            return self._enable_doc_link
    
    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        search_region = view.extract_scope(sel.begin())
        if view.extract_scope(sel.end()) != search_region:
            return False
        return {'search_region': search_region}

    def show_doc(self):
        sublime.status_message(self.open_status_message)
        focus_file = FILE_MANAGER.get_ring_file(self.view)
        file_, region = focus_file.find_local(self.view, self.search_string)
        
        status_message_suffix = self.show_doc_in_file(file_, region, 
                                                      show_at_top = False)

        sublime.status_message(
            "Documentation for {0} {1}".format(self.search_string, 
                                               status_message_suffix)
            )

    def get_highlight_regions(self):
        return [r for r in Focus.find_by_selector(self.view, 'focus_local') if
                (self.view.substr(r) == self.search_string)]

    def highlight_status_message(self, total, selection = None):
        if (selection is not None):
            return "%s of %s highlighted instances of %s" % (selection, total, self.search_string)
        else:
            return "%s highlighted instances of %s" % (total, self.search_string)


class ObjectDocLink(DocLink):
    """DocLink class for Focus objects. Displays the definition of the object 
    entity. If the definition is contained in an external file, the file is opened."""

    @classmethod
    def scope_view_enabler(cls):
        return Focus.scope_map('source')

    @classmethod
    def scope_selection_enabler(cls):
        return Focus.scope_map('focus_object')

    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        search_region = view.word(sel.begin())
        if view.word(sel.end()) != search_region:
            return False
        return {'search_region': search_region}

    def show_doc(self):
        sublime.status_message(self.open_status_message)
        string_parts = self.search_string.split('.')
        object_ = string_parts[0]
        parts = [('Object', object_)]
        region = self.regions[0]
        line_text = self.view.substr(self.view.line(region)).strip()

        if (len(string_parts) == 1):
            pass
        elif (Focus.score_selector(self.view, region.begin(), 'focus_function') > 0):
            function_name = extract_focus_function_name(self.view, region)[0]
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
        elif ((Focus.score_selector(self.view, region.begin(), 'keyword_line') > 0) or 
              (Focus.score_selector(self.view, region.begin(), 'attribute_line') > 0)):
            focus_file = FILE_MANAGER.get_ring_file(self.view)
            if line_text.startswith(':Element'):
                if self.search_string in focus_file.get_completions(self.view, ['Key'], True):
                    parts.append(('Key', string_parts[1]))
                else:
                    parts.append(('Field', string_parts[1]))
            elif line_text.startswith('Name'):
                tree = set([t[0] for t in focus_file.build_translator_tree(self.view)])
                if (':LongLock' in tree):
                    parts.append(('LongLock', string_parts[1]))
                elif ((':Record' in tree) or (':Records' in tree)):
                    parts.append(('Record', string_parts[1]))
            else:
                for t in ('File', 'Record', 'Index'):
                    if (line_text.startswith(t) or line_text.startswith(':' + t)):
                        parts.append((t, string_parts[1]))
                        break

        file_, region, row, col = self.find_object(object_, parts)
        # logger.debug('File: %s; Region: %s', file_, region)

        status_message_suffix = self.show_doc_in_file(file_, region,
                                    row, col, show_at_top = False)

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
        row = col = None

        if (file_ is None):
            focus_file = FILE_MANAGER.get_ring_file(self.view)
            if ((focus_file is not None) and (focus_file.ring_object is not None)):
                file_, row, col = self.find_object_in_ring(object_, parts, focus_file)

        if ((file_ is None) and (focus_file is not None) and (focus_file.ring_object is not None)):
            for f in focus_file.get_include_files(self.view):
                file_, row, col = self.find_object_in_other_file(f, parts)
                logger.debug('col = %s', col)
                logger.debug('row = %s', row)
                logger.debug('file_ = %s', file_)

                if file_ is not None:
                    break

        yield file_
        yield region
        yield row
        yield col

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
                file_ = self.view.file_name()
                break

        yield file_
        yield region

    def find_object_in_ring(self, object_, parts, focus_file):
        """Finds documentation for the object in a datadef defined in the ring."""
        file_ = os.path.join(focus_file.ring_object.datadefs_path, 
            'Standard', object_ + '.focus')
        file_, row, col = self.find_object_in_other_file(file_, parts)

        yield file_
        yield row
        yield col

    def find_object_in_other_file(self, file_, parts):
        """Finds documentation for the object in any given file."""
        row = col = None
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
                return (file_, line+1, match.start(2)+1)
       
        return (None, None, None)

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


class ScreenComponentDocLink(DocLink):
    """docstring for SubroutineFinder"""

    def __init__(self, view, type_ = None, **kwargs):
        super(ScreenComponentDocLink, self).__init__(view, **kwargs)
        self.type_ = type_

    @classmethod
    def scope_view_enabler(cls):
        return Focus.scope_map('source')

    @classmethod
    def scope_selection_enabler(cls):
        return Focus.scope_map('#ScreenPage')
    
    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        if Focus.score_selector(view, sel.begin(), 'other_attribute') > 0:
            focus_file = FILE_MANAGER.get_ring_file(view)
            tree = focus_file.build_translator_tree(view)
            attributes = [a[0] for a in tree]

            if ':Component' in attributes:
                line_region = view.line(sel)
                line_string = view.substr(line_region)
                match = re.match(r" *([:A-Za-z0-9]+) +(\S+)", line_string)
                if match is not None:
                    search_string = match.group(2)
                    search_region = line_match_region(line_region, match, 2)
                    return {'search_string': search_string,
                            'search_region': search_region,
                            'type_': match.group(1)}

        elif Focus.score_selector(view, sel.begin(), 'other_keyword') > 0:
            focus_file = FILE_MANAGER.get_ring_file(view)
            line_region = view.line(sel)
            line_string = view.substr(line_region)
            match = re.match(r" *(:Region) +(\S+)", line_string)
            if match is not None:
                search_string = match.group(2)
                search_region = line_match_region(line_region, match, 2)
                return {'search_string': search_string,
                        'search_region': search_region,
                        'type_': match.group(1)}

        return None

    def show_doc(self):
        sublime.status_message(self.open_status_message)
        focus_file = FILE_MANAGER.get_ring_file(self.view)
        file_, region = focus_file.find_screen_component(self.view, self.type_, 
                            self.search_string)
        logger.debug('File: %s; Region: %s', file_, region)
        if isinstance(region, tuple):
            row = region[0]
            col = region[1]
        else:
            row = col = None

        status_message_suffix = self.show_doc_in_file(file_, region, row, col)
        
        sublime.status_message(
            "Documentation for {0} {1}".format(self.search_string, 
                                               status_message_suffix)
            )


class FSLocalHighlighter(Highlight):

    def __init__(self, view, doc_region = None, **kwargs):
        super(FSLocalHighlighter, self).__init__(view, **kwargs)
        self.doc_region = doc_region

    @classmethod
    def scope_view_enabler(cls):
        return Focus.scope_map('source') + ', source.fs'

    @classmethod
    def scope_selection_enabler(cls):
        return Focus.scope_map('fs_local_highlighter')
    
    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        if (sel.size() > 1):
            return None

        codeblock, local_vars_doc_region, arg_doc_region = cls.setup(view)

        if (Focus.score_selector(view, sel.begin(), 'fs_local') > 0):
            region = sublime.Region(sel.begin(), sel.begin() + 1)
            return {'search_region': region}

        elif (Focus.score_selector(view, sel.begin(), 'comment') > 0):
            doc_matches = list()
            if (local_vars_doc_region and sel.intersects(local_vars_doc_region)):
                doc_matches = view.find_all(r"[A-Z]\s*[-=:]\s*[\s\S]*?\n(?=//\s*[A-Z]\s*[-=:]|//:Doc)")
            elif (arg_doc_region and sel.intersects(arg_doc_region)):
                doc_matches = view.find_all(r"[\{|]?[A-Z]\s*[-=:.]\s*[\s\S]*?\n(?=//\s*[\{|]?([A-Z]|\d{1,2})\s*[-=:]|//:Doc)")
            
            for r in doc_matches:
                if r.contains(sel):
                    match = re.search(r"([A-Z])\s*[-=:]\s*", view.substr(r))
                    if match:
                        string = match.group(1)
                        region = line_match_region(r, match, 1)
                        return {'search_string': string,
                                'search_region': region,
                                'doc_region': r}
        return None

    def get_highlight_regions(self):
        regions = list()
        codeblock, local_vars_doc_region, arg_doc_region = self.setup(self.view)
        function_variables = codeblock.get_variables_from_function()
        regions.extend(function_variables[self.search_string].regions)
        arg_match = self.get_arg_match(self.search_string, arg_doc_region)
        if (arg_match is not None):
            regions.append(arg_match)
        local_match = self.get_local_var_match(self.search_string, local_vars_doc_region)
        if (local_match is not None):
            regions.append(local_match)

        regions.sort()

        return regions

    @staticmethod
    def setup(view):
        focus_file = FILE_MANAGER.get_ring_file(view)
        if focus_file is None:
            return (None, None, None)

        codeblock = focus_file.get_codeblock(view)
        local_vars_doc_region = arg_doc_region = codeblock.documentation_region
        documentation = CodeBlockDocumentation(codeblock)

        try:
            local_vars_doc_region = documentation.doc_regions['Local Variables'].region
        except KeyError:
            pass

        try:
            arg_doc_region = documentation.doc_regions['Arguments'].region
        except KeyError:
            pass

        return (codeblock, local_vars_doc_region, arg_doc_region)

    def get_arg_match(self, var, region):
        r = None
        arg_match = self.view.find(r"[\{|]?" + var + r"\s*[-=:.]\s*[\s\S]*?(?=\n//\s*[\{|]?([A-Z]|\d{1,2})\s*[-=:.]|\n//:Doc)", region.begin())
        if ((arg_match is not None) and region.intersects(arg_match)):
            string = self.view.substr(arg_match)
            if (string[0] in "{|"):
                r = sublime.Region(arg_match.begin()+1, arg_match.begin()+2)
            else:
                r = sublime.Region(arg_match.begin(), arg_match.begin()+1)
        return r

    def get_local_var_match(self, var, region):
        r = None
        local_var_match = self.view.find(var + r"\s*[-=:]\s*[\s\S]*?(?=\n//\s*[A-Z]\s*[-=:]|\n//:Doc)", region.begin())
        if ((local_var_match is not None) and region.intersects(local_var_match)):
            r = sublime.Region(local_var_match.begin(), local_var_match.begin()+1)
        return r

    def highlight_status_message(self, total, selection = None):
        if (selection is not None):
            return "%s of %s highlighted instances of %s" % (selection, total, self.search_string)
        else:
            return "%s highlighted instances of %s" % (total, self.search_string)




