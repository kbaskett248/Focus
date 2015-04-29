import functools
import imp
import json
import logging
import os
import re
import sys
import urllib

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

from bs4 import BeautifulSoup

import sublime

try:
    from EntitySelect import EntitySelector, DocLink, Highlight
    from EntitySelect import PreemptiveHighlight, StatusIdentifier
except ImportError as e:
    logger.error('EntitySelect package not installed')
    raise e

from .classes.code_blocks import CodeBlockSet
from .tools.classes import get_ring_file, get_view
from .tools.focus import TRANSLATOR_SEPARATOR
from .tools.general import create_folder, string_search, string_match
from .tools.sublime import split_focus_function
from .tools.settings import (
    get_show_doc_setting,
    get_focus_wiki_setting,
    get_set_highlighter_setting,
    get_translator_doc_url_overrides_setting,
    get_focus_function_argument_type,
    get_fs_function_doc_url,
    get_focus_function_doc_url,
)


css = ''


def plugin_loaded():
    for c in EntitySelector.get_defined_classes(globals()):
        c.add_possible_selector()
    FSFunctionDocLink.load_doc_cache()
    FocusFunctionDocLink.load_doc_cache()
    init_css()


def plugin_unloaded():
    for c in EntitySelector.get_defined_classes(globals()):
        c.remove_possible_selector()
    imp.reload(sys.modules[__name__])


def init_css():
    """ Load up desired CSS """
    global css

    logger.debug("initializing css")

    settings = sublime.load_settings('Focus Package.sublime-settings')
    css_file = settings.get('documentation_css',
                            'Packages/Focus/resources/css/dark.css')
    try:
        css = sublime.load_resource(css_file).replace('\r', '')
    except:
        css = ''

    settings.clear_on_change('reload')
    settings.add_on_change('reload', init_css)


class FocusFunctionDocLink(DocLink, PreemptiveHighlight):
    """DocLink class for Focus functions. Shows the documentation for the
    function on the wiki."""

    DOC_CACHE_PARTIAL_PATH = os.path.join('User', 'Focus',
                                          'Focus_Doc_cache.json')
    DocumentationCache = dict()

    def __init__(self, *args, **kwargs):
        super(FocusFunctionDocLink, self).__init__(*args, **kwargs)
        self.doc_already_shown = False

    @classmethod
    def scope_view_enabler(cls):
        return 'source.focus'

    @classmethod
    def scope_selection_enabler(cls):
        return ("meta.function.focus - "
                "meta.function.arguments.translate-time.focus")

    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        focus_view = get_view(view)
        span, string = focus_view.extract_focus_function(sel)

        if span is not None:
            name, args = split_focus_function(string, span[0])
            if name[0] is not None:
                search_region = sublime.Region(name[0][0], name[0][1])
                return {'search_string': name[1],
                        'search_region': search_region}

        return None

    @classmethod
    def doc_cache_path(cls):
        """Return the path to the Documentation Cache file."""
        return os.path.join(sublime.packages_path(),
                            cls.DOC_CACHE_PARTIAL_PATH)

    @classmethod
    def load_doc_cache(cls):
        """Loads the documentation cache into memory."""
        cache_path = FocusFunctionDocLink.doc_cache_path()
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as cache_file:
                FocusFunctionDocLink.DocumentationCache = json.load(cache_file)

    @classmethod
    def save_doc_cache(cls):
        """Saves the Documentation Cache to disk."""
        cache_path = FocusFunctionDocLink.doc_cache_path()
        if not os.path.exists(cache_path):
            create_folder(os.path.dirname(cache_path))
        with open(cache_path, 'w') as cache_file:
            json.dump(FocusFunctionDocLink.DocumentationCache, cache_file,
                      indent='    ')

    def get_url(self):
        return get_focus_function_doc_url(self.search_string)

    def get_doc_from_cache(self):
        """Returns a doc dictionary from the cache.

        If the doc is not contained in the cache, the page is scraped. Then
        the documentation cache is saved.

        """
        wiki = get_focus_wiki_setting()
        url = self.get_url()
        if not url.startswith(wiki):
            return None

        doc = None
        try:
            doc = FocusFunctionDocLink.DocumentationCache[url]
        except KeyError:
            doc = self.scrape_page()
            if doc is not None:
                FocusFunctionDocLink.DocumentationCache[url] = doc
                FocusFunctionDocLink.save_doc_cache()
        return doc

    def show_doc(self):
        """Shows documentation for the currently selected FS function.

        If possible, documentation is scraped from the web page or retrieved
        from the documentation cache and shown in an output panel. Otherwise,
        the web page is opened in the default browser. If the key is pressed
        a second time, the web page is opened.

        """
        if self.doc_already_shown:
            show_doc_setting = 'source'
        else:
            show_doc_setting = get_show_doc_setting('focus_function')
            if show_doc_setting != 'source':
                doc = self.get_doc_from_cache()

        if (show_doc_setting == 'source') or (doc is None):
            url = self.get_url()
            if url is not None:
                sublime.status_message(self.open_status_message)
                self.show_doc_on_web(url)
        elif show_doc_setting == 'panel':
            doc = self.format_documentation(doc)
            self.show_doc_in_panel(doc)
            self.doc_already_shown = True
        elif show_doc_setting == 'popup':
            doc = self.format_documentation_for_popup(doc)
            self.show_doc_in_popup(doc)
            self.doc_already_shown = True

    def enable_highlight(self):
        if self.search_string == '@Break':
            return True
        else:
            return False

    def get_highlight_regions(self):
        return self.view.find_by_selector('meta.debug.focus')

    @classmethod
    def preemptive_highlight_id(cls):
        return 'focus_breaks'

    @classmethod
    def get_preemptive_highlight_selection(cls, view):
        regions = view.find_by_selector('meta.debug.focus')
        if not regions:
            return []
        point = regions[0].begin()
        return [sublime.Region(point, point)]

    def get_display_region(self, reg):
        return ['%s: %s' % (self.view.rowcol(reg.begin())[0] + 1,
                            self.view.substr(reg)),
                self.view.substr(self.view.line(reg))]

    def scrape_page(self):
        """
        Parses the contents of the documentation page and returns them as a
        dictionary.
        """
        wiki = get_focus_wiki_setting()
        url = self.get_url()
        if not url.startswith(wiki):
            return None

        logger.info('Scraping %s for documentation for %s', url,
                    self.search_string)
        try:
            f = urllib.request.urlopen(url)
        except urllib.error.URLError:
            return None
        else:
            d = dict()
            soup = BeautifulSoup(f)
            content = soup.find('div', class_='mw-content-ltr')
            # logger.debug('content = %s', content)

            first_div = content.div
            d['function'] = first_div.div.b.string

            second_div = first_div.find_next_sibling('div')
            d['usage'] = ''.join(list(second_div.code.stripped_strings))

            tab = second_div.find_next_sibling('div').table

            d['overview'] = ''
            for r in tab.find_all('tr'):
                e = list(r.stripped_strings)
                if (('ide' in e[0]) and ('ffect' in e[0])):
                    e[0] = 'Side Effect'
                elif (('untime' in e[0]) and ('arg' in e[0])):
                    e[0] = 'Runtime Arg'

                if ('ranslation' in e[0]) and ('rg' in e[0]):
                    try:
                        d['translation args'] = (d['translation args'] +
                                                 ', ' + ' '.join(e[1:]))
                    except KeyError:
                        d['translation args'] = ' '.join(e[1:])
                else:
                    d[e[0].lower()] = ' '.join(e[1:])

            table_elements = ['runtime arg', 'translation args',
                              'precondition', 'return', 'side effect']
            for e in table_elements:
                if e not in d.keys():
                    d[e] = 'None'

            if d['overview']:
                d['overview'] = 'Overview\n' + d['overview'] + '\n\n'

            try:
                examples = content.find('b', text='Example').parent
            except AttributeError:
                examples = ''
            else:
                examples = examples.find_next_sibling('pre')
                examples = ''.join(list(examples.strings))
            d['examples'] = examples.strip()

            d['extra info'] = ''
            for ei in content.find_all('dl'):
                ei = list(ei.stripped_strings)
                if len(ei) == 1:
                    continue
                d['extra info'] = (d['extra info'] + ei[0] + '\n' +
                                   ' '.join(ei[1:]) + '\n\n')

            soup.find('div', id='footer')
            credits = soup.find('li', id='credits')
            d['modified time'] = next(credits.stripped_strings)

            return d

    def format_documentation(self, doc):
        """Formats a documentation dictionary for display."""
        if doc is None:
            return None
        return ("\n{function}\n\n"
                "{overview}\n"
                "Usage:                {usage}\n"
                "Runtime Arg:          {runtime arg}\n"
                "Translation Args:     {translation args}\n"
                "Precondition:         {precondition}\n"
                "Return:               {return}\n"
                "Side effect:          {side effect}\n\n"
                "{extra info}\n"
                "Code Examples\n"
                "-------------\n"
                "{examples}\n").format(**doc)

    POPUP_DOC_TEMPLATE = (
        '''<style>{css}</style>
        <div class="content">
            <h1 class="header">{function}</h1>
            <p>{overview}</p>
            <p><a href="open_source" class="copy-link">(Open source)</a></p>
            <p><span class="key">Usage:</span> <span class="value">{usage}</span></p>
            <p><span class="key">Runtime Arg:</span> <span class="value">{runtime arg}</span></p>
            <p><span class="key">Translation Args:</span> <span class="value">{translation args}</span></p>
            <p><span class="key">Precondition:</span> <span class="value">{precondition}</span></p>
            <p><span class="key">Return:</span> <span class="value">{return}</span></p>
            <p><span class="key">Side Effect:</span> <span class="value">{side effect}</span></p>
            <p>{extra info}</p>
        '''
    )

    CODE_EXAMPLES_TEMPLATE = '''
        <div class="divider"></div>
        <h2 class="subheader">Code Examples</h2>
        <p>{examples}</p>
        '''

    def format_documentation_for_popup(self, doc):
        global css
        doc['css'] = css
        template = self.POPUP_DOC_TEMPLATE
        if doc['examples']:
            template += self.CODE_EXAMPLES_TEMPLATE
            doc['examples'] = doc['examples'].replace('\r', '').replace(
                '\n', '<br />')
        template += '</div>'
        return template.format(**doc)

    def popup_navigate(self, href):
        """ Execute link callback """
        logger.debug('href = %s', href)
        params = href.split(':')
        logger.debug('params = %s', params)
        key = params[0]
        logger.debug('key = %s', key)

        if key == 'open_source':
            self.doc_already_shown = True
            self.show_doc()


class FSFunctionDocLink(DocLink, Highlight, StatusIdentifier):
    """
    DocLink class for FS functions. Shows the documentation for the function
    on the wiki.

    """

    DocCachePartialPath = os.path.join('User', 'Focus', 'FS_Doc_cache.json')
    DocumentationCache = dict()

    def __init__(self, *args, **kwargs):
        super(FSFunctionDocLink, self).__init__(*args, **kwargs)
        self.doc_already_shown = False

    @classmethod
    def scope_view_enabler(cls):
        return 'source.focus, source.fs'

    @classmethod
    def scope_selection_enabler(cls):
        return ('meta.function.fs, meta.function.listset, '
                'keyword.operator')

    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        ring_view = get_view(view)
        span, string = ring_view.extract_fs_function(sel)

        if string is not None:
            search_region = sublime.Region(span[0], span[1])
            return {'search_string': string,
                    'search_region': search_region}

        span, string = ring_view.extract_operator(sel)
        if string is not None:
            search_region = sublime.Region(span[0], span[1])
            if string[0] != '@':
                string = '@' + string
            return {'search_string': string,
                    'search_region': search_region}

        return None

    @classmethod
    def doc_cache_path(cls):
        """Return the path to the Documentation Cache file."""
        return os.path.join(sublime.packages_path(), cls.DocCachePartialPath)

    @classmethod
    def load_doc_cache(cls):
        """Loads the documentation cache into memory."""
        cache_path = FSFunctionDocLink.doc_cache_path()
        if os.path.exists(cache_path):
            with open(cache_path, 'r') as cache_file:
                FSFunctionDocLink.DocumentationCache = json.load(cache_file)

    @classmethod
    def save_doc_cache(cls):
        """Saves the Documentation Cache to disk."""
        cache_path = FSFunctionDocLink.doc_cache_path()
        if not os.path.exists(cache_path):
            create_folder(os.path.dirname(cache_path))
        with open(cache_path, 'w') as cache_file:
            json.dump(FSFunctionDocLink.DocumentationCache, cache_file,
                      indent='    ')

    def get_doc_from_cache(self):
        """Returns a doc dictionary from the cache.

        If the doc is not contained in the cache, the page is scraped. Then
        the documentation cache is saved.

        """
        doc = None
        try:
            doc = FSFunctionDocLink.DocumentationCache[self.get_url()]
        except KeyError:
            doc = self.scrape_page()
            if doc is not None:
                FSFunctionDocLink.DocumentationCache[self.get_url()] = doc
                FSFunctionDocLink.save_doc_cache()
        return doc

    def show_doc(self):
        """Shows documentation for the currently selected FS function.

        If possible, documentation is scraped from the web page or retrieved
        from the documentation cache and shown in an output panel. Otherwise,
        the web page is opened in the default browser. If the key is pressed
        a second time, the web page is opened.

        """
        if self.doc_already_shown:
            show_doc_setting = 'source'
        else:
            show_doc_setting = get_show_doc_setting('fs_function')
            if show_doc_setting != 'source':
                doc = self.get_doc_from_cache()

        if (show_doc_setting == 'source') or (doc is None):
            url = self.get_url()
            if url is not None:
                sublime.status_message(self.open_status_message)
                self.show_doc_on_web(url)
        elif show_doc_setting == 'panel':
            doc = self.format_documentation(doc)
            self.show_doc_in_panel(doc)
            self.doc_already_shown = True
        elif show_doc_setting == 'popup':
            doc = self.format_documentation_for_popup(doc)
            self.show_doc_in_popup(doc)
            self.doc_already_shown = True

    def get_url(self):
        """Return the url for the documentation web page."""
        match = re.match((r"@[A-Za-z]{1,2}|"
                          r"@?\~?[\!\#\$\%\&\*\+\-\.\/\:\<\=\>\?\|\\]"),
                         self.search_string)
        if match is None:
            return None

        print(get_fs_function_doc_url(match.group(0)))

        return get_fs_function_doc_url(match.group(0))

    def enable_highlight(self):
        try:
            return self._enable_highlight
        except AttributeError:
            self._enable_highlight = self.is_listset_function()
            return self._enable_highlight

    def is_listset_function(self):
        """Return True if the selected FS function is a listset function."""
        sel = self.view.sel()[0]
        score_selector = functools.partial(self.view.score_selector,
                                           sel.begin())

        if score_selector('meta.function.listset') <= 0:
            return False
        elif score_selector('meta.subroutine') <= 0:
            return False

        ring_view = get_view(self.view)
        search_region, fs_func = ring_view.extract_fs_function(sel)
        set_number = fs_func[2:]
        upper_or_lower = CodeBlockSet.determine_upper(fs_func)
        search_string = CodeBlockSet.format_set(set_number, upper_or_lower)
        self.set = search_string
        return True

    def get_highlight_regions(self):
        regions = []
        codeblock, set_doc_region = self.setup(self.view)

        if get_set_highlighter_setting():
            if self.set[0] == 'U':
                upper_or_lower = r"\@[A-Z]"
            else:
                upper_or_lower = r"\@[a-z]"
            set_number = self.set[2:-1]
            reg_ex = upper_or_lower + set_number
            regions.extend(self.view.find_all(reg_ex))
        else:
            function_sets = codeblock.get_sets_from_function()
            regions.extend(function_sets[self.set].regions)

        doc_match = self.get_doc_match(self.set, set_doc_region)
        if (doc_match is not None):
            regions.append(doc_match)

        regions.sort()

        return regions

    @staticmethod
    def setup(view):
        ring_view = get_view(view)
        if ring_view is None:
            return (None, None)

        codeblock = ring_view.get_codeblock()
        sets_doc_region = codeblock.documentation_region
        documentation = codeblock.doc

        try:
            sets_doc_region = documentation.doc_regions[
                'Data Structures'].region
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
                r = sublime.Region(doc_match.begin() + span[0],
                                   doc_match.begin() + span[1])
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
        """
        Parses the contents of the documentation page and returns them as a
        dictionary.

        """
        url = self.get_url()

        logger.info('Scraping %s for documentation for %s',
                    url,
                    self.search_string)
        try:
            f = urllib.request.urlopen(url)
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

            try:
                comments = content.find('div', text='Comments').parent
            except AttributeError:
                comments = ''
            else:
                comments = comments.find_next_sibling('div')
                comments = ''.join(list(comments.strings))
            d['comments'] = comments.strip()

            try:
                examples = content.find('div', text='Code Examples').parent
            except AttributeError:
                examples = ''
            else:
                examples = examples.find_next_sibling('div')
                examples = ''.join(list(examples.strings))
            d['examples'] = examples.strip()
            # logger.debug('scrape_page = %s', d)
            return d

    def format_documentation(self, doc):
        """Formats a documentation dictionary for display."""
        if doc is None:
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
                "{examples}\n").format(**doc)

    POPUP_DOC_TEMPLATE = (
        '''<style>{css}</style>
        <div class="content">
            <h1 class="header">{function} {name}</h1>
            <p><a href="open_source" class="copy-link">(Open source)</a></p>
            <p><span class="key">Group:</span> <span class="value">{group}</span></p>
            <p><span class="key">Precondition:</span> <span class="value">{precondition}</span></p>
            <p><span class="key">Argument:</span> <span class="value">{argument}</span></p>
            <p><span class="key">Return:</span> <span class="value">{return}</span></p>
            <p><span class="key">Side Effect:</span> <span class="value">{side effect}</span></p>
        '''
    )

    COMMENT_TEMPLATE = '''
        <div class="divider"></div>
        <h2 class="subheader">Comments</h2>
        <p>{comments}</p>
        '''

    CODE_EXAMPLES_TEMPLATE = '''
        <div class="divider"></div>
        <h2 class="subheader">Code Examples</h2>
        <p>{examples}</p>
        '''

    def format_documentation_for_popup(self, doc):
        global css
        doc['css'] = css
        template = self.POPUP_DOC_TEMPLATE
        if doc['comments']:
            template += self.COMMENT_TEMPLATE
            doc['comments'] = doc['comments'].replace('\n\r', '\n').replace(
                '\n', '<br />')
        if doc['examples']:
            template += self.CODE_EXAMPLES_TEMPLATE
            doc['examples'] = doc['examples'].replace('\n\r', '\n').replace(
                '\n', '<br />')
        template += '</div>'
        return template.format(**doc)

    def popup_navigate(self, href):
        """ Execute link callback """
        logger.debug('href = %s', href)
        params = href.split(':')
        logger.debug('params = %s', params)
        key = params[0]
        logger.debug('key = %s', key)

        if key == 'open_source':
            self.doc_already_shown = True
            self.show_doc()

    @property
    def status_string(self):
        if self._status_string is None:
            d = self.get_doc_from_cache()
            if d is not None:
                self._status_string = "{function}: {name}".format(**d)
        return self._status_string

    @status_string.setter
    def status_string(self, value):
        self._status_string = value


class SetDocHighlighter(Highlight):

    @classmethod
    def scope_view_enabler(cls):
        return 'source.focus, source.fs'

    @classmethod
    def scope_selection_enabler(cls):
        return 'meta.subroutine.fs comment'

    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        codeblock, set_doc_region = cls.setup(view)

        if ((set_doc_region is not None) and sel.intersects(set_doc_region)):
            doc_matches = view.find_all(
                r"//\s*(L|U)\(\d+\)\s*[-=:]\s*[\s\S]*?\n"
                r"(?=//\s*(L|U)\(\d+\)\s*[-=:]|//:Doc)")
            for r in doc_matches:
                if r.contains(sel):
                    span, s = string_search(view.substr(r),
                                            r"//\s*((L|U)\(\d+\))\s*[-=:]\s*",
                                            base_point=r.begin())
                    if span is not None:
                        region = sublime.Region(span[0], span[1])
                        return {'search_region': region}
        return None

    def get_highlight_regions(self):
        regions = []
        codeblock, set_doc_region = self.setup(self.view)

        if get_set_highlighter_setting():
            if self.search_string[0] == 'U':
                upper_or_lower = r"\@[A-Z]"
            else:
                upper_or_lower = r"\@[a-z]"
            set_number = self.search_string[2:-1]
            reg_ex = upper_or_lower + set_number
            regions.extend(self.view.find_all(reg_ex))
        else:
            function_sets = codeblock.get_sets_from_function()
            regions.extend(function_sets[self.search_string].regions)

        doc_match = self.get_doc_match(self.search_string, set_doc_region)
        if doc_match is not None:
            regions.append(doc_match)

        regions.sort()

        return regions

    @staticmethod
    def setup(view):
        ring_view = get_view(view)
        if ring_view is None:
            return (None, None)

        codeblock = ring_view.get_codeblock()
        sets_doc_region = codeblock.documentation_region
        documentation = codeblock.doc

        try:
            sets_doc_region = documentation.doc_regions[
                'Data Structures'].region
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
                r = sublime.Region(doc_match.begin() + span[0],
                                   doc_match.begin() + span[1])
        return r

    def highlight_status_message(self, total, selection=None):
        if (selection is not None):
            return "%s of %s highlighted instances of %s" % (
                selection, total, self.search_string)
        else:
            return "%s highlighted instances of %s" % (
                total, self.search_string)


class SubroutineDocLink(DocLink, Highlight):
    """DocLink class for Subroutines. Shows the subroutine definition. If the
    subroutine is contained in an include file, that file is opened."""

    @classmethod
    def scope_view_enabler(cls):
        return 'source.focus, source.fs'

    @classmethod
    def scope_selection_enabler(cls):
        return 'entity.name.subroutine.fs, entity.name.list.fs'

    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        region = view.extract_scope(sel.begin())
        if view.extract_scope(sel.end()) != region:
            return False
        string = view.substr(region)
        span, match_string = string_match(string, r":(Code|List) +(\S.*)",
                                          match_group=2,
                                          base_point=region.begin())
        if span is not None:
            region = sublime.Region(span[0], span[1])
            string = match_string
        return {'search_string': string, 'search_region': region}

    def enable_doc_link(self):
        try:
            return self._enable_doc_link
        except AttributeError:
            self._enable_doc_link = self.view.score_selector(
                self.regions[0].begin(),
                'meta.subroutine.header.fs, meta.list.header.fs') <= 0
            return self._enable_doc_link

    def show_doc(self):
        sublime.status_message(self.open_status_message)

        for view_or_file, file_name in self.mt_file_or_view_iter():
            if self.find_and_show(view_or_file, file_name):
                sublime.status_message(
                    "Documentation for {0} found in {1}".format(
                        self.search_string, os.path.basename(file_name)))
                return

        sublime.status_message("Documentation for {0} not found".format(
            self.search_string))

    def find_and_show(self, view_or_file, file_name):
        if view_or_file is None:
            return False
        span = view_or_file.find_member(self.search_string)
        if span is not None:
            region = sublime.Region(span[0], span[1])
            self.show_doc_in_file(file_name, region)
            return True

        return False

    def mt_file_or_view_iter(self):
        """
        Generator that yields an MTView object or MTRingFile object along
        with the file name for each file that needs to be checked.

        """
        ring_view = get_view(self.view)
        if ring_view is None:
            return []
        file_name = self.view.file_name()
        yield (ring_view, file_name)

        ring_file = get_ring_file(file_name)
        if (ring_file is None) or (ring_file.ring is None):
            return

        for f in ring_file.get_include_files(current_file=False):
            inc_file = get_ring_file(f)
            if inc_file is not None:
                yield (inc_file, f)

    def get_highlight_regions(self):
        return [r for r in self.view.find_by_selector(
                'entity.name.subroutine.fs, entity.name.list.fs') if
                (self.view.substr(r) == self.search_string)]

    def highlight_status_message(self, total, selection=None):
        if selection is not None:
            return "%s of %s highlighted instances of %s" % (
                selection, total, self.search_string)
        else:
            return "%s highlighted instances of %s" % (total,
                                                       self.search_string)


class TranslatorDocLink(DocLink):
    """DocLink class for Translator keywords and attributes. Opens the
    documentation for the selected entity on the wiki."""

    @classmethod
    def scope_view_enabler(cls):
        return 'source.focus'

    @classmethod
    def scope_selection_enabler(cls):
        return ("keyword.other.translator.focus, keyword.other.keyword.focus, "
                "keyword.other.attribute.focus")

    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        line_region = view.line(sel)
        line_text = view.substr(line_region)

        span, string = string_match(line_text, r"^ *([A-Za-z#:]+)( |$)",
                                    base_point=line_region.begin())
        logger.debug("span: %s", span)
        logger.debug('string = %s', string)

        if span is not None:
            region = sublime.Region(span[0], span[1])
            if region.contains(sel):
                return {'search_string': string,
                        'search_region': region}

        return None

    def show_doc(self):
        sublime.status_message(self.open_status_message)
        point = self.regions[0].begin()
        if self.view.score_selector(point,
                                    'keyword.other.translator.focus') > 0:
            url_arg = 'X-%s' % self.search_string[1:]
        else:
            translator = keyword = attribute = ''
            ring_view = get_view(self.view)
            for t in (t[0] for t in ring_view.build_translator_tree(
                    point, trim_containers=True)):
                if (t[0] == '#'):
                    translator = 'X-%s' % t[1:]
                elif (t[0] == ':'):
                    keyword = '-%s' % t[1:]
                else:
                    attribute = '#%s' % t
            url_arg = translator + keyword + attribute

        overrides = get_translator_doc_url_overrides_setting()
        for k in overrides.keys():
            if k.lower() in url_arg.lower():
                url = overrides[k]
                break
        else:
            url = get_focus_wiki_setting() + url_arg
        self.show_doc_on_web(url)


class AliasDocLink(DocLink):
    """DocLink class for Home Care aliases. Displays the definition of the
    alias. If in another file, that file is opened. If the alias is for a
    subroutine, that subroutine is displayed."""

    @classmethod
    def scope_view_enabler(cls):
        return 'source.focus'

    @classmethod
    def scope_selection_enabler(cls):
        return 'meta.alias'

    @classmethod
    def enable_for_selection(cls, view):
        ring_view = get_view(view)
        span, alias = ring_view.extract_alias()

        if alias is not None:
            return {'search_string': alias,
                    'search_region': sublime.Region(span[0], span[1])}
        return None

    def show_doc(self):
        sublime.status_message(self.open_status_message)

        for view_or_file, file_name in self.mt_file_or_view_iter():
            if self.find_and_show(view_or_file, file_name):
                sublime.status_message(
                    "Documentation for {0} found in {1}".format(
                        self.search_string, os.path.basename(file_name)))
                return

        sublime.status_message("Documentation for {0} not found".format(
            self.search_string))

    def find_and_show(self, view_or_file, file_name):
        if view_or_file is None:
            return False
        span = view_or_file.find_alias_definition(self.search_string)
        if span is not None:
            region = sublime.Region(span[0], span[1])
            self.show_doc_in_file(file_name, region)
            return True

        return False

    def mt_file_or_view_iter(self):
        """
        Generator that yields an MTView object or MTRingFile object along
        with the file name for each file that needs to be checked.

        """
        ring_view = get_view(self.view)
        if ring_view is None:
            return []
        file_name = self.view.file_name()
        yield (ring_view, file_name)

        ring_file = get_ring_file(file_name)
        if (ring_file is None) or (ring_file.ring is None):
            return

        file_name = ring_file.ring.find_alias_definition(
            self.search_string)
        if file_name is not None:
            ring_file_2 = get_ring_file(file_name)
            if ring_file_2 is not None:
                yield (ring_file_2, file_name)
            return

        for f in ring_file.get_include_files(current_file=False):
            inc_file = get_ring_file(f)
            if inc_file is not None:
                yield (inc_file, f)


class IncludeFileDocLink(DocLink):
    """
    DocLink class for Included files and External Pagesets.
    Opens the file.

    """

    INCLUDE = 'Include'
    EXTERNAL_PAGESET = 'External Pageset'

    def __init__(self, view, search_string=None, search_region=None,
                 type_=None):
        super(IncludeFileDocLink, self).__init__(
            view, search_string, search_region)
        self.type_ = type_

    @classmethod
    def scope_view_enabler(cls):
        return 'source.focus'

    @classmethod
    def scope_selection_enabler(cls):
        return ('meta.translator.include.focus meta.value.attribute.focus, '
                'meta.translator.screenpage.focus meta.value.attribute.focus')

    @classmethod
    def enable_for_view(cls, view):
        ring_file = get_ring_file(view.file_name())
        if (ring_file is None) or (ring_file.ring is None):
            return False
        else:
            return True

    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        ring_file = get_ring_file(view.file_name())
        if ring_file is None:
            return None

        span = string = type_ = None
        if view.score_selector(sel.begin(),
                               'meta.translator.include.focus') > 0:
            span, string = ring_file.extract_include_file(sel.begin())
            type_ = IncludeFileDocLink.INCLUDE
        elif view.score_selector(sel.begin(),
                                 'meta.translator.screenpage.focus') > 0:
            span, string = ring_file.extract_external_pageset(sel.begin())
            type_ = IncludeFileDocLink.EXTERNAL_PAGESET

        if span is not None:
            region = sublime.Region(span[0], span[1])
            return {'search_string': string,
                    'search_region': region,
                    'type_': type_}
        else:
            return None

    def show_doc(self):
        sublime.status_message(self.open_status_message)
        ring_file = get_ring_file(self.view.file_name())

        if self.type_ == IncludeFileDocLink.INCLUDE:
            included_files = {os.path.basename(f): f for f in
                              ring_file.get_include_files()}
        elif self.type_ == IncludeFileDocLink.EXTERNAL_PAGESET:
            included_files = {os.path.basename(f)[:-6]: f for f in
                              ring_file.get_external_pageset_files()}

        try:
            f = included_files[self.search_string]
        except KeyError:
            sublime.status_message(
                "{0} not found".format(self.search_string))
        else:
            self.view.window().open_file(f)
            logger.info('Opening %s', f)
            sublime.status_message(
                "{0} found".format(self.search_string))


class LocalDocLink(DocLink, Highlight):
    """DocLink class for Focus locals. Displays the definition of the local
    from the #Locals section."""

    @classmethod
    def scope_view_enabler(cls):
        return 'source.focus'

    @classmethod
    def scope_selection_enabler(cls):
        return 'variable.other.local.focus'

    def enable_doc_link(self):
        return self.view.score_selector(
            self.regions[0].begin(),
            'meta.function.arguments.translate-time.focus') > 0

    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        search_region = view.extract_scope(sel.begin())
        if view.extract_scope(sel.end()) != search_region:
            return False
        return {'search_region': search_region}

    def show_doc(self):
        sublime.status_message(self.open_status_message)

        for view_or_file, file_name in self.mt_file_or_view_iter():
            if self.find_and_show(view_or_file, file_name):
                sublime.status_message(
                    "Documentation for {0} found in {1}".format(
                        self.search_string, os.path.basename(file_name)))
                return

        sublime.status_message("Documentation for {0} not found".format(
            self.search_string))

    def find_and_show(self, view_or_file, file_name):
        if view_or_file is None:
            return False
        span = view_or_file.find_local_definition(self.search_string)
        if span is not None:
            region = sublime.Region(span[0], span[1])
            self.show_doc_in_file(file_name, region)
            return True

        return False

    def mt_file_or_view_iter(self):
        """
        Generator that yields an MTView object or MTRingFile object along
        with the file name for each file that needs to be checked.

        """
        ring_view = get_view(self.view)
        if ring_view is None:
            return []
        file_name = self.view.file_name()
        yield (ring_view, file_name)

        ring_file = get_ring_file(file_name)
        if (ring_file is None) or (ring_file.ring is None):
            return

        for f in ring_file.get_include_files(current_file=False):
            inc_file = get_ring_file(f)
            if inc_file is not None:
                yield (inc_file, f)

    def get_highlight_regions(self):
        return [r for r in self.view.find_by_selector(
            'variable.other.local.focus') if
            (self.view.substr(r) == self.search_string)]

    def highlight_status_message(self, total, selection=None):
        if (selection is not None):
            return "%s of %s highlighted instances of %s" % (
                selection, total, self.search_string)
        else:
            return "%s highlighted instances of %s" % (
                total, self.search_string)

    def has_doc(self):
        ring_view = get_view(self.view)
        if ring_view is None:
            return False

        return (self.search_string in
                ring_view.get_locals(only_documented=True))

    def add_doc(self, edit, use_snippets=True):
        ring_view = get_view(self.view)
        if ring_view is None:
            return
        self._snippet_counter = 0
        create_locals_section = False
        indent = '  '

        try:
            locals_section = ring_view.get_translator_sections(
                'Locals', include_end_space=False)[-1][0]
            locals_section = sublime.Region(locals_section[0],
                                            locals_section[1])
        except IndexError:
            start = ring_view.get_translator_sections(
                'Magic')[0].begin()-1
            locals_section = sublime.Region(start, start)
            create_locals_section = True

        logger.debug('locals_section = %s', locals_section)

        lines_to_add = list()

        line = '{0}:Name                           {1}'.format(
            indent, self.search_string)
        line += '\n{0}// ${1}'.format(indent, self.snippet_counter)
        lines_to_add.append(line)

        content = '\n\n'.join(lines_to_add)
        logger.debug('content = %s', content)

        if create_locals_section:
            content = '\n{0}\n#Locals\n{1}\n\n'.format(
                TRANSLATOR_SEPARATOR, content)
        else:
            content = '\n' + content + '\n\n'

        logger.debug('content = %s', content)

        if use_snippets:
            selection = self.view.sel()
            selection.clear()
            selection.add(sublime.Region(locals_section.end(),
                                         locals_section.end()))
            self.view.run_command("insert_snippet", {"contents": content})

        else:
            self.view.insert(edit, locals_section.end(), content)

    @property
    def snippet_counter(self):
        self._snippet_counter += 1
        return self._snippet_counter


class ObjectDocLink(DocLink):
    """
    DocLink class for Focus objects. Displays the definition of the object
    entity. If the definition is contained in an external file, the file is
    opened.

    """

    @classmethod
    def scope_view_enabler(cls):
        return 'source.focus'

    @classmethod
    def scope_selection_enabler(cls):
        return 'variable.parameter.object.focus'

    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        search_region = view.word(sel.begin())
        # print(search_region)
        if view.word(sel.end()) != search_region:
            return False
        elif view.substr(search_region.begin()-1) == '!':
            return False
        elif view.score_selector(sel.begin(), 'meta.translator.datadef') > 0:
            line_text = view.substr(view.line(sel)).strip()
            if not (line_text.startswith('Pointer') or
                    line_text.startswith('Element') or
                    line_text.startswith('ElementDeleted')):
                return False
        return {'search_region': search_region}

    def show_doc(self):
        sublime.status_message(self.open_status_message)

        object_type = self.get_object_type()
        logger.debug('object_type = %s', object_type)
        if object_type is not None:
            for view_or_file, file_name in self.mt_file_or_view_iter():
                logger.debug('file_name = %s', file_name)
                if self.find_and_show(view_or_file, file_name, object_type):
                    return
                logger.debug("Didn't find in %s", file_name)

        sublime.status_message("Documentation for {0} not found".format(
            self.search_string))

    def get_object_type(self):
        """Return the type of object for the documentation lookup."""
        point = self.regions[0].begin()

        if self.view.score_selector(point, 'meta.function.focus') > 0:
            ring_view = get_view(self.view)
            ff_span, ff_str = ring_view.extract_focus_function(point)
            if ff_str is not None:
                function_name = split_focus_function(
                    ff_str, base_point=ff_span[0])[0][1]
                return get_focus_function_argument_type(function_name)

        elif self.view.score_selector(point,
                                      'meta.keyword, meta.attribute') > 0:
            line_text = self.view.substr(self.view.line(point)).strip()
            if line_text.startswith(':Element'):
                return 'Element'
            elif line_text.startswith('Name'):
                ring_view = get_view(self.view)
                tree = set([t[0] for t in ring_view.build_translator_tree(
                    point, trim_containers=True)])
                if (':LongLock' in tree):
                    return 'LongLock'
                elif ((':Record' in tree) or (':Records' in tree)):
                    return 'Record'
            elif line_text.startswith('Pointer'):
                return 'Object'
            else:
                for t in ('File', 'Record', 'Index'):
                    if (line_text.startswith(t) or
                            line_text.startswith(':' + t)):
                        return t

        return None

    def mt_file_or_view_iter(self):
        """
        Generator that yields an MTView object or MTRingFile object along
        with the file name for each file that needs to be checked.

        """
        ring_view = get_view(self.view)
        if ring_view is None:
            return []
        file_name = self.view.file_name()
        yield (ring_view, file_name)

        ring_file = get_ring_file(file_name)
        if (ring_file is None) or (ring_file.ring is None):
            return

        file_name = ring_file.ring.find_object_file(
            self.search_string)
        if file_name is not None:
            ring_file_2 = get_ring_file(file_name)
            if ring_file_2 is not None:
                yield (ring_file_2, file_name)

            return

        for f in ring_file.get_include_files(current_file=False):
            inc_file = get_ring_file(f)
            if inc_file is not None:
                yield (inc_file, f)

    def find_and_show(self, view_or_file, file_name, object_type):
        if view_or_file is None:
            return False
        span = view_or_file.find_object(object_type, self.search_string)
        if span is not None:
            region = sublime.Region(span[0], span[1])
            self.show_doc_in_file(file_name, region)
            sublime.status_message(
                "Documentation for {0} found in {1}".format(
                    self.search_string, os.path.basename(file_name)))
            return True

        return False


class ScreenComponentDocLink(DocLink):
    """
    DocLink class for Screen Components. Displays the definition of the screen
    component. If the definition is contained in an external file, the file is
    opened.

    """

    def __init__(self, view, component_type=None, **kwargs):
        super(ScreenComponentDocLink, self).__init__(view, **kwargs)
        self.component_type = component_type

    @classmethod
    def scope_view_enabler(cls):
        return 'source.focus'

    @classmethod
    def scope_selection_enabler(cls):
        return (
            'meta.translator.screenpage.focus meta.value.attribute.focus, ' +
            'meta.translator.screenpage.focus meta.value.keyword.focus')

    @classmethod
    def enable_for_selection(cls, view):
        point = view.sel()[0].begin()
        if view.score_selector(point, 'meta.attribute.focus') > 0:
            ring_view = get_view(view)
            attributes = [a[0] for a in ring_view.build_translator_tree(point)]

            if ':Component' in attributes:
                ((k_span, k_str),
                 (v_span, v_str)) = ring_view.get_keyword_and_value(point)
                if (k_span is not None) and (v_span is not None):
                    logger.debug(":Component - %s", ((k_span, k_str),
                                                     (v_span, v_str)))
                    reg = sublime.Region(v_span[0], v_span[1])
                    return {'search_string': v_str,
                            'search_region': reg,
                            'component_type': k_str}

        elif view.score_selector(point, 'meta.keyword.focus') > 0:
            ring_view = get_view(view)
            keyword, value = ring_view.get_keyword_and_value(point)
            if (keyword is not None) and (keyword[1] == ':Region'):
                reg = sublime.Region(value[0][0], value[0][1])
                logger.debug(":Region - %s", (value[1], reg))
                return {'search_string': value[1],
                        'search_region': reg,
                        'component_type': ':Region'}

        return None

    def show_doc(self):
        sublime.status_message(self.open_status_message)

        for view_or_file, file_name in self.mt_file_or_view_iter():
            if self.find_and_show(view_or_file, file_name):
                sublime.status_message(
                    "Documentation for {0} found in {1}".format(
                        self.search_string, os.path.basename(file_name)))
                return

        sublime.status_message("Documentation for {0} not found".format(
            self.search_string))

    def find_and_show(self, view_or_file, file_name):
        if view_or_file is None:
            return False
        if self.component_type == ':Region':
            span = view_or_file.find_container_region(self.search_string)
        else:
            span = view_or_file.find_screen_component(self.component_type,
                                                      self.search_string)

        if span is not None:
            region = sublime.Region(span[0], span[1])
            self.show_doc_in_file(file_name, region)
            return True

        return False

    def mt_file_or_view_iter(self):
        """
        Generator that yields an MTView object or MTRingFile object along
        with the file name for each file that needs to be checked.

        """
        ring_view = get_view(self.view)
        if ring_view is None:
            return []
        file_name = self.view.file_name()
        yield (ring_view, file_name)

        ring_file = get_ring_file(file_name)
        if (ring_file is None) or (ring_file.ring is None):
            return

        for f in ring_file.get_include_files(current_file=False):
            inc_file = get_ring_file(f)
            if inc_file is not None:
                yield (inc_file, f)


class FSLocalHighlighter(Highlight):

    def __init__(self, view, doc_region=None, **kwargs):
        super(FSLocalHighlighter, self).__init__(view, **kwargs)
        self.doc_region = doc_region

    @classmethod
    def scope_view_enabler(cls):
        return 'source.focus, source.fs'

    @classmethod
    def scope_selection_enabler(cls):
        return ('meta.subroutine.fs meta.variable.other, '
                'meta.subroutine.fs comment')

    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        if (sel.size() > 1):
            return None

        point = sel.begin()

        if view.score_selector(point, 'meta.variable.other') > 0:
            region = sublime.Region(point, point + 1)
            return {'search_region': region}

        elif view.score_selector(point, 'comment') > 0:
            codeblock, local_vars_doc_region, arg_doc_region = cls.setup(view)
            doc_matches = []

            if (local_vars_doc_region and
                    sel.intersects(local_vars_doc_region)):
                doc_matches = view.find_all(
                    r"[A-Z]\s*[-=:]\s*[\s\S]*?\n(?=//\s*[A-Z]\s*[-=:]|//:Doc)")
            elif (arg_doc_region and sel.intersects(arg_doc_region)):
                doc_matches = view.find_all(
                    r"[\{|]?[A-Z]\s*[-=:.]\s*[\s\S]*?\n"
                    r"(?=//\s*[\{|]?([A-Z]|\d{1,2})\s*[-=:]|//:Doc)")

            for r in doc_matches:
                if r.contains(sel):
                    span, string = string_search(view.substr(r),
                                                 r"([A-Z])\s*[-=:]\s*",
                                                 base_point=r.begin())
                    if span is not None:
                        reg = sublime.Region(span[0], span[1])
                        return {'search_string': string,
                                'search_region': reg,
                                'doc_region': r}
        return None

    def get_highlight_regions(self):
        regions = []
        codeblock, local_vars_doc_region, arg_doc_region = self.setup(
            self.view)
        if local_vars_doc_region.contains(arg_doc_region):
            arg_doc_region = None

        function_variables = codeblock.get_variables_from_function()
        try:
            regions.extend(function_variables[self.search_string].regions)
        except KeyError:
            pass

        arg_match = self.get_arg_match(self.search_string, arg_doc_region)
        if (arg_match is not None):
            regions.append(arg_match)

        local_match = self.get_local_var_match(self.search_string,
                                               local_vars_doc_region)
        if (local_match is not None):
            regions.append(local_match)

        regions.sort()
        return regions

    @staticmethod
    def setup(view):
        ring_view = get_view(view)
        if ring_view is None:
            return (None, None, None)

        codeblock = ring_view.get_codeblock()
        local_vars_doc_region = arg_doc_region = codeblock.documentation_region
        documentation = codeblock.doc

        try:
            local_vars_doc_region = documentation.doc_regions[
                'Local Variables'].region
        except KeyError:
            pass

        try:
            arg_doc_region = documentation.doc_regions['Arguments'].region
        except KeyError:
            pass

        return (codeblock, local_vars_doc_region, arg_doc_region)

    def get_arg_match(self, var, region):
        if region is None:
            return None
        r = None
        arg_match = self.view.find(
            (r"[\{|]?" + var +
             r"\s*[-=:.]\s*[\s\S]*?(?=\n//\s*[\{|]?([A-Z]|\d{1,2})\s*[-=:.]|" +
             r"\n//:Doc)"), region.begin())
        if ((arg_match is not None) and region.intersects(arg_match)):
            string = self.view.substr(arg_match)
            arg_match = arg_match.begin()
            if (string[0] in "{|"):
                r = sublime.Region(arg_match+1, arg_match+2)
            else:
                r = sublime.Region(arg_match, arg_match+1)
        return r

    def get_local_var_match(self, var, region):
        if region is None:
            return None
        r = None
        local_var_match = self.view.find(
            var + r"\s*[-=:]\s*[\s\S]*?(?=\n//\s*[A-Z]\s*[-=:]|\n//:Doc)",
            region.begin())
        if ((local_var_match is not None) and
                region.intersects(local_var_match)):
            r = sublime.Region(local_var_match.begin(),
                               local_var_match.begin()+1)
        return r

    def highlight_status_message(self, total, selection=None):
        if (selection is not None):
            return "%s of %s highlighted instances of %s" % (
                selection, total, self.search_string)
        else:
            return "%s highlighted instances of %s" % (
                total, self.search_string)


class RTToolDocLink(DocLink):
    """
    DocLink class for RT or TT Tool calls. Shows the RT tool definition.

    """

    @classmethod
    def scope_view_enabler(cls):
        return 'source.focus, source.fs'

    @classmethod
    def enable_for_view(cls, view):
        if cls.check_file_name(view):
            ring_view = get_view(view)
            if ring_view is not None:
                return True

        ring_file = get_ring_file(view.file_name())
        if ring_file is None:
            return False
        elif ring_file.ring is None:
            return False
        elif ring_file.ring.system_path is None:
            return False

        return True

    @classmethod
    def check_file_name(self, view):
        file_name = view.file_name()
        if file_name is None:
            return False

        match = re.match(r"[a-wz]", os.path.split(file_name)[1])
        logger.debug("file_name = %s", file_name)
        if match is not None:
            return True
        else:
            return False

    @classmethod
    def scope_selection_enabler(cls):
        return 'meta.tool.fs'

    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        ring_view = get_view(view)
        span, string = ring_view.extract_rt_tool(sel)

        if string is not None:
            file_name = view.file_name()
            ring_file = get_ring_file(file_name)
            if ((ring_file is not None) and (ring_file.ring is not None) and
                    (ring_file.ring.system_path is not None)):
                search_region = sublime.Region(span[0], span[1])
                return {'search_string': string,
                        'search_region': search_region}

            start_letter = string[1]
            file_name = os.path.split(file_name)[1]
            if file_name.startswith(start_letter):
                search_region = sublime.Region(span[0], span[1])
                return {'search_string': string,
                        'search_region': search_region}
        return None

    def show_doc(self):
        sublime.status_message(self.open_status_message)

        for view_or_file, file_name in self.mt_file_or_view_iter():
            if self.find_and_show(view_or_file, file_name):
                sublime.status_message(
                    "Documentation for {0} found in {1}".format(
                        self.search_string, os.path.basename(file_name)))
                return

        sublime.status_message("Documentation for {0} not found".format(
            self.search_string))

    def find_and_show(self, view_or_file, file_name):
        if view_or_file is None:
            return False
        second_letter = self.search_string[2]

        span = string_search(view_or_file.get_contents(),
                             r"^ *:Code +({name}.*)".format(name=second_letter),
                             match_group=1,
                             flags=re.MULTILINE)[0]
        if span is not None:
            region = sublime.Region(span[0], span[1])
            self.show_doc_in_file(file_name, region)
            return True

        return False

    def mt_file_or_view_iter(self):
        """
        Generator that yields an MTView object or MTRingFile object along
        with the file name for each file that needs to be checked.

        """
        start_letter = self.search_string[1]
        logger.debug('start_letter = %s', start_letter)
        file_name = self.view.file_name()
        logger.debug('file_name = %s', file_name)
        if os.path.split(file_name)[1].startswith(start_letter):
            ring_view = get_view(self.view)
            if ring_view is not None:
                yield (ring_view, file_name)

        tools_path = self.get_tools_path()
        if tools_path is None:
            return

        for f in os.listdir(tools_path):
            if f.startswith(start_letter):
                f = os.path.join(tools_path, f)
                ring_file_2 = get_ring_file(f)
                if ring_file_2 is not None:
                    yield (ring_file_2, f)

    def get_tools_path(self):
        file_name = self.view.file_name().lower()
        ring_file = get_ring_file(file_name)
        if ring_file is None:
            return None

        if ('translators' in file_name) or ('tttools' in file_name):
            path = os.path.join(ring_file.ring.system_path, 'TTTools')
        else:
            path = os.path.join(ring_file.ring.system_path, 'RTTools')

        if os.path.isdir(path):
            return path
        else:
            return None


class FileMatchDocLink(DocLink):
    """DocLink class for Translator keywords and attributes. Opens the
    documentation for the selected entity on the wiki."""

    def __init__(self, view, search_file=None, **kwargs):
        super(FileMatchDocLink, self).__init__(view, **kwargs)
        self.search_file = search_file

    @classmethod
    def scope_view_enabler(cls):
        return 'source.focus'

    @classmethod
    def scope_selection_enabler(cls):
        return ('string, meta.function.arguments.translate-time.focus, '
                'comment, meta.value.attribute.focus')

    @classmethod
    def enable_for_selection(cls, view):
        sel = view.sel()[0]
        ring_view = get_view(view)
        span, string = ring_view.extract_focus_file(sel)

        if string is None:
            return None

        app_match = re.match(r"[A-Z][a-z]{1,2}", string)
        if app_match is None:
            return None

        app = app_match.group(0)
        ring_file = get_ring_file(view.file_name())
        if ((ring_file is not None) and (ring_file.ring is not None)):
            file_name = os.path.join(ring_file.ring.pgmsource_path,
                                     app, string) + '.focus'
            if os.path.isfile(file_name):
                search_region = sublime.Region(span[0], span[1])
                return {'search_string': string,
                        'search_region': search_region,
                        'search_file': file_name}

        return None

    def show_doc(self):
        sublime.status_message(self.open_status_message)
        self.show_doc_in_file(self.search_file, row=0, col=0)
