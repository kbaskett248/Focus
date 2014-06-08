import os
import re

import sublime_plugin
import sublime

import Focus
from .RingFile import RingFile
from Focus.src.tools import debug, read_file, MultiMatch
from Focus.src.Ring import Ring
from Focus.src.Managers.RingManager import RingManager
from Focus.src import FocusLanguage
from .Exceptions import *

subroutine_matcher = re.compile(r":Code\s+([^\n()\t]+?) *$")
local_matcher = re.compile(r"@(Get|Put)Local\(([A-Za-z0-9._\-]+)\)")
alias_matcher = re.compile(r"\s*:Alias\s+([^()\n\t]+?) *$")
argument_matcher = MultiMatch(patterns = {"Single": r"\^([A-Z])",
                                          "List": r"(\^?)\{([A-Z,]*)(\{[A-Z,{}]*\},?)([A-Z,]*)\}"})

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

def previous_line(view, r):
    l = view.line(r)
    return view.line(l.begin()-1)

# Class represents a .focus or .fs file
class FocusFile(RingFile):

    Extensions = ('focus',)
    FileType = 'Focus file'
    
    RingManager = RingManager.getInstance()
    
    include_file_matcher = MultiMatch(patterns = {'Folder': r"\s*Folder\s+([A-Za-z0-9._]+)", 
                'File': r"\s*File\s+([A-Za-z0-9._]+)"}
                )

    page_matcher = MultiMatch(patterns = {'Codebase': r"\s*Code[Bb]ase\s+([A-Za-z0-9]+)", 
                'Source': r"\s*Source\s+([\w._-]+)",
                'PageName': r'\s*PageName\s+([\w.-_]+)',
                'ContainerPage': r'\s*:ContainerPage\s+([\w._-]+)'
                })

    object_matcher = MultiMatch(patterns = {'Object': r"\s*:Object\s+([A-Za-z0-9._]+)",
                                            'Subroutine': r":Code\s+([^\n()\t]+?) *$",
                                            'Local': r"@(Get|Put)Local\(([A-Za-z0-9._\-]+)\)",
                                            'Alias': r"\s*:Alias\s+([^\n()\t]+?) *$"
                                            })

    def __init__(self, view):
        '''Creates a FocusFile instance if the file is a .focus file. Otherwise, throws an
           InvalidFileFormat exception.'''
        try:
            super(FocusFile, self).__init__(view)
        except InvalidRingError:
            self.ring_object = None
    
    @property
    def magic_path(self):
        return self.ring_object.magic_path
    
    @property
    def system_path(self):
        return self.ring_object.system_path

    def get_translator_regions(self, view, translator = 'translator_section', current_region = False):
        # translator_regions = list()
        # translator_string = None

        # regions = []

        # if current_region:
        #     sel = view.sel()
        #     for region in Focus.find_by_selector(view, 'translator_section'):
        #         for s in sel:
        #             if region.contains(s):
        #                 regions.append(region)
        #                 break
        # else:
        #     regions = Focus.find_by_selector(view, translator)
        
        # for region in regions:
        #     start = region.begin()
        #     start_line_reg = view.line(start)
        #     end = region.end()
        #     end_line_reg = view.line(end)
        #     end_line_str = view.substr(end_line_reg)

        #     shrink = True
        #     while (shrink and (not end_line_reg.intersects(start_line_reg))):
        #         if end_line_str.startswith('#'):
        #             end = end_line_reg.begin()-1
        #             end_line_reg = view.line(end)
        #             end_line_str = view.substr(end_line_reg)
        #         elif end_line_str.strip() == '':
        #             end = end_line_reg.begin()-1
        #             end_line_reg = view.line(end)
        #             end_line_str = view.substr(end_line_reg)
        #         elif end_line_str.startswith('//--'):
        #             end = end_line_reg.begin()-1
        #             end_line_reg = view.line(end)
        #             end_line_str = view.substr(end_line_reg)
        #         else:
        #             shrink = False

        #     previous_line = view.line(start-1)
        #     if view.substr(previous_line).startswith('//--'):
        #         start = previous_line.begin()

        #     translator_regions.append(sublime.Region(start, end))

        # logger.debug(translator_regions)
        # return translator_regions

        translator_regions = []
        prev_header = next_header = None
        header_regions = Focus.find_by_selector(view, 'translator_line')
        # Add the end of the file to catch the last region
        header_regions.append(sublime.Region(view.size(), view.size()))

        for r in header_regions:
            next_header = r

            # Include the separator in the section below it
            prev_line = previous_line(view, next_header)
            if view.substr(prev_line).startswith('//----'):
                next_header = sublime.Region(prev_line.begin(), next_header.end())

            if prev_header is not None:
                tran_region = sublime.Region(prev_header.begin(), next_header.begin()-1)

                # If we want the current region, continue if none of the selections
                # are contained within tran_region
                if current_region:
                    for s in view.sel():
                        if tran_region.contains(s):
                            break
                    else:
                        prev_header = next_header
                        continue

                # If we want a specific translator, continue if this one doesn't match
                if translator and Focus.score_selector(view, prev_header.end(), translator) <= 0:
                    prev_header = next_header
                    continue

                translator_regions.append(tran_region)
            prev_header = next_header

        logger.debug('translator_regions = %s', translator_regions)
        return translator_regions


    def get_include_files(self, view):
        """Returns a list of the include files in the file"""

        include_files = list()

        if self.ring_object is None:
            return include_files

        for i in Focus.find_by_selector(view, '#Include'):
            folder = None
            file = None

            for l in view.lines(i):
                FocusFile.include_file_matcher.match_string = view.substr(l)

                if FocusFile.include_file_matcher.named_match( 'Folder' ):
                    folder = FocusFile.include_file_matcher.group(1)
                elif ':Source' in FocusFile.include_file_matcher.match_string:
                    folder = None
                elif bool(folder) and FocusFile.include_file_matcher.named_match('File'):
                    partial_path = os.path.join('PgmSource', 
                                                folder, 
                                                FocusFile.include_file_matcher.group(1))
                    file_name = self.ring_object.get_file_path(partial_path)
                    if (file_name is not None):
                        logger.debug(file_name)
                        include_files.append(file_name)
                
        return include_files

    def get_externalpageset_files(self, view):
        """Returns a list of the ExternalPageSets in a file."""

        external_page_sets = list()

        for i in Focus.find_by_selector(view, '#ScreenPage'):
            codebase = source = None
            in_pageset = False
            
            for l in view.lines(i):
                self.page_matcher.match_string = view.substr(l)

                if (self.page_matcher.match_string == ''):
                    continue
                elif ':ExternalPageSet' in self.page_matcher.match_string:
                    codebase = source = None
                    in_pageset = True
                    continue
                elif (self.page_matcher.match_string.strip()[0] == ':'):
                    in_pageset = False
                    continue
                elif (in_pageset and self.page_matcher.named_match('Codebase')):
                    codebase = self.page_matcher.group(1)
                elif (in_pageset and self.page_matcher.named_match('Source')):
                    source = self.page_matcher.group(1) + '.focus'

                if (in_pageset and (codebase is not None) and (source is not None)):
                    logger.debug('Codebase: %s     Source: %s', codebase, source)
                    partial_path = os.path.join('PgmSource', codebase, source)
                    file_name = self.ring_object.get_file_path(partial_path)
                    if (file_name is not None):
                        external_page_sets.append(file_name)
                        in_pageset = False
                
        logger.debug(external_page_sets)
        return external_page_sets

    def get_locals(self, view, only_undocumented = False, with_documentation = False):
        used_locals = None
        if with_documentation:
            pass
        else:
            if only_undocumented:
                locals_sections = self.get_translator_regions(view, '#Locals')
                documented_locals = set()
            used_locals = set()
            for r in Focus.find_by_selector(view, 'focus_local'):
                local = view.substr(r)
                used_locals.add(local)
                if only_undocumented:
                    for ls in locals_sections:
                        if ls.contains(r):
                            documented_locals.add(local)
                            break
            logger.debug('Locals used in file: %s', used_locals)
            
            if only_undocumented:
                used_locals = used_locals - documented_locals
                logger.debug('Undefined Locals in file: %s', used_locals)

            used_locals = list(used_locals)
            used_locals.sort()

        return used_locals

    def get_completions(self, view, t, return_empty = False):
        """Returns a list of completions of the given type in the file"""

        logger.debug("type = %s", t)
        elements = set()
        skip = False

        if (self.ring_object is not None):
            ring_types = set(t).intersection(set(self.ring_object.completion_state.keys()))
            for x in ring_types:
                if self.ring_object.completion_state[x] in ('Not Loaded', 'Loading'):
                    skip = True
            elements = self.ring_object.get_ring_completions(t, return_empty = True)
        logger.debug('skip: %s', skip)

        if skip:
            if return_empty:
                return [('', '')]
            else:
                return None
            
        for x in ('Object', 'Record', 'Key', 'Field'):
            if x in t:
                elements = elements.union(self.get_object_completions_from_file(view, x))

        for x in ('Object', 'Record', 'Key', 'Field', 'Subroutine', 'Local', 'Alias'):
            if x in t:
                elements = elements.union(self.get_completions_from_include_files(view, x))

        if 'Subroutine' in t:
            for x in [view.substr(x) for x in Focus.find_by_selector(view, 'subroutine_name')]:
                elements.add(x)
        if 'Local' in t:
            for x in [view.substr(x) for x in Focus.find_by_selector(view, 'focus_local')]:
                elements.add(x)
        if 'Alias' in t:
            for x in Focus.find_by_selector(view, 'alias'):
                w = view.substr(x)
                if (w[:2] == '@@'):
                    w = w[2:]
                if (w[-2:] != '()'):
                    w = w + '()'
                elements.add(w)
        if 'Doc Heading' in t:
            for x in ('Purpose','Arguments','Preconditions','Local Variables',
                    'Data Structures','Side Effects','Returns','Additional Notes'):
                elements.add(x)
        
        if ((not elements) and (not return_empty)):
            del elements
            elements = None
        else:
            elements = [(x,) * 2 for x in elements]

        return elements

    def get_object_completions_from_file(self, view, completion_type):
        """Appends the object completions defined in the file to the completion list"""

        FocusFile.object_matcher.add_pattern(
            'Type', r"\s*:" + completion_type + r"\s+([A-Za-z0-9._]+)", True)

        elements = set()

        for d in Focus.find_by_selector(view, '#DataDef'):
            lines = view.lines(d)
            completion_object = None

            for l in lines:
                FocusFile.object_matcher.match_string = view.substr(l)

                if FocusFile.object_matcher.named_match('Object'):
                    if (completion_type == 'Object'):
                        elements.add(FocusFile.object_matcher.group(1))
                    else:
                        completion_object = FocusFile.object_matcher.group(1)
                elif ((completion_object is not None) and 
                    FocusFile.object_matcher.named_match('Type')):
                    elements.add(
                        '%s.%s' % (completion_object, 
                                   FocusFile.object_matcher.group(1))
                        )

        return elements                       

    def get_completions_from_include_files(self, view, completion_type):
        elements = set()

        for f in self.get_include_files(view):
            elements = elements.union(
                FocusFile.get_completions_from_other_file(f, completion_type))

        logger.debug(elements)

        return elements

    @staticmethod
    def get_completions_from_other_file(file_name, completion_type):
        """Appends completions defined in another file to the completion list"""

        logger.info('Loading %s completions from %s', completion_type, file_name)

        elements = set()
        in_datadef = False
        completion_object = None

        if (completion_type not in ['Subroutine','Local','Alias']):
            FocusFile.object_matcher.add_pattern('Type', 
                r"\s*:" + completion_type + r"\s+([A-Za-z0-9._\-]+)")

        try:
            file_contents = read_file(file_name)
        except FileNotFoundError:
            logger.warning('%s could not be found', file_name)
            logger.warning('%s completions could not be loaded from %s', 
                           completion_type, file_name
                           )
        else:
            for l in file_contents:
                FocusFile.object_matcher.match_string = l

                if (l[:2] == '//'):
                    pass
                elif ((completion_type == 'Subroutine') and 
                      FocusFile.object_matcher.named_match('Subroutine')):
                    elements.add( FocusFile.object_matcher.group(1) )
                elif ((completion_type == 'Local') and 
                      FocusFile.object_matcher.named_match('Local')):
                    elements.add( FocusFile.object_matcher.group(2) )
                elif ((completion_type == 'Alias') and 
                      FocusFile.object_matcher.named_match('Alias')):
                    elements.add(FocusFile.object_matcher.group(1))
                else:
                    if (l[:8] == '#DataDef'):
                        in_datadef = True
                    elif (in_datadef):
                        if (l[0] == '#'):
                            in_datadef = False
                        elif FocusFile.object_matcher.named_match('Object'):
                            if (completion_type == 'Object'):
                                elements.add(FocusFile.object_matcher.group(1))
                            else:
                                completion_object = FocusFile.object_matcher.group(1)
                        elif ((completion_object is not None) and 
                              FocusFile.object_matcher.named_match('Type')):
                            elements.add('{0}.{1}'.format(completion_object, 
                                FocusFile.object_matcher.group(1)))

        return elements

    def build_translator_tree(self, view, trim_containers = False):
        """Builds a list of (Translator option, Value)"""
        try:
            tran_region = self.get_translator_regions(view, current_region = True)[0]
        except IndexError:
            logger.info('Not within a translator region')
            return None        

        translator_tree = list()

        current_line = view.line(view.sel()[0])
        current_line_text = view.substr(current_line)
        pattern = r'^(\s*)((:|#)[A-Za-z0-9]*|[A-Za-z0-9]+)(\s*)(.*)$'
        match = re.match(pattern, current_line_text)
        
        if match is None:
            translator_tree.append(('', ''))
            pattern = r"^(\s*)((:|#)[A-Za-z0-9]*)(\s*)(.*)$"

        proceed = True
        found_container = False
        while proceed:
            if match is not None:
                # Only include the last container block since they can be nested
                if (trim_containers and (match.group(2) == ':Container')):
                    if not found_container:
                        translator_tree.append((match.group(2), match.group(5)))
                        found_container = True
                else:
                    if ((match.group(4) == '') and (match.group(5) != '')):
                        translator_tree.append(('',match.group(2) + match.group(5)))
                    else:
                        translator_tree.append((match.group(2), match.group(5)))


                # If we found the translator, stop. Otherwise, update the pattern
                if match.group(3) == '#':
                    proceed = False
                else:
                    pattern = r"^(\s{0,%s})((:|#)[A-Za-z0-9]*)(\s*)(.*)$" % (len(match.group(1)) - 2)
                    # logger.debug('pattern = %s', pattern)

            # If at the beginning of the file, stop. Otherwise, move to the previous line.
            if current_line.begin() <= 0:
                proceed = False
            else:
                current_line = previous_line(view, current_line)
                # If not within the tran_region, stop.
                if not tran_region.intersects(current_line):
                    proceed = False
                else:
                    current_line_text = view.substr(current_line)
                    match = re.match(pattern, current_line_text)

        translator_tree.reverse()
        logger.debug('translator_tree = %s', translator_tree)
        return translator_tree


    # def build_translator_tree(self, view, trim_containers = False):
    #     """Builds a list of (Translator option, Value)"""

    #     tran_region = self.get_translator_regions(view, current_region = True)[0]
    #     print(tran_region)

    #     translator_tree = list()
    #     tran_key = tran_value = None
    #     current_line = view.line(view.sel()[0].begin())
    #     current_line_text = view.substr(current_line)
    #     pattern = r'^(\s*)([A-Za-z0-9:#]+)\s*(.*)$'
    #     if (current_line_text.strip() == ''):
    #         while ((len(current_line_text.strip()) == 0) or (current_line_text.strip()[0] != ':')) and (current_line.begin() > 0):
    #             current_line = view.line(current_line.begin() - 1)
    #             current_line_text = view.substr(current_line)

    #     # logger.debug('current_line = %s', current_line)
    #     # logger.debug('current_line_text = %s', current_line_text)
    #     found_container = False
    #     proceed = True
    #     while ((tran_key == None) or (tran_key[0] != u'#')) and (current_line.begin() >= 1):
    #         # current_line_text = view.substr(current_line)
    #         # match = re.match(pattern, current_line_text)
    #         # if (match is not None):
    #         #     spacer = match.group(1)
    #         #     tran_key = match.group(2)
    #         #     tran_value = match.group(3)
    #         #     # Only include the last container block since they can be nested
    #         #     if (trim_containers and (tran_key == ':Container')):
    #         #         if not found_container:
    #         #             translator_tree.append((tran_key, tran_value))
    #         #             found_container = True
    #         #     else:
    #         #         translator_tree.append((tran_key, tran_value))
    #         #     pattern = r'^(' + spacer[2:] + ')([A-Za-z0-9:#]+)\s*(.*)'
    #         # current_line = view.line(current_line.begin() - 1)
    #         # # logger.debug('current_line = %s', current_line)
    #         # # logger.debug('current_line_text = %s', current_line_text)
    #         if current_line.begin() <= 0:
    #             proceed = False
    #         if current_line.empty():
    #             current_line = view.line(current_line.begin() - 1)
    #             continue
    #         current_line_text = view.substr(current_line)
    #         match = re.match(pattern, current_line_text)
    #         if (match is not None):
    #             spacer, tran_key, tran_value = match.groups()
    #             if tran_key[0] == u'#':
    #                 proceed = False
    #             # Only include the last container block since they can be nested
    #             if (trim_containers and (tran_key == ':Container')):
    #                 if not found_container:
    #                     translator_tree.append((tran_key, tran_value))
    #                     found_container = True
    #             else:
    #                 translator_tree.append((tran_key, tran_value))
    #             pattern = r'^(' + spacer[2:] + ')([A-Za-z0-9:#]+)\s*(.*)'
    #         current_line = view.line(current_line.begin() - 1)
        
    #     translator_tree.reverse()
    #     return translator_tree

    def find_alias(self, view, alias):
        line = view.find(r"^[ \t]+:Alias\s+%s" % alias, 1)

        if (line is None) or (line.empty()):
            line = view.find(r"^ *Alias +" + alias, 0)
            if (line is not None):
                line = view.line(line.begin()-1)
                substring = view.substr(line)
                match = re.match(r'^ *:EntryPoint +(.+) *?', substring)
                while (match is None) and (line.begin() > 1):
                    line = view.line(line.begin()-1)
                    substring = view.substr(line)
                    match = re.match(r'^ *:EntryPoint +(.+) *?', substring)
                line = None
                if (match is not None):
                    sub_name = match.group(1)
                    line = view.find(r":Code\s+%s$" % sub_name, 0)

        return line

    def find_subroutine(self, view, subroutine):
        file_ = self.filename
        region = view.find(r"^\s*:Code\s+" + subroutine + "$", 0)
        logger.debug('Region in current file: %s', region)

        if ((region is None) or region.empty()):
            file_ = None
            code_matcher = re.compile(r"^\s*:Code\s+" + subroutine)
            for f in self.get_include_files(view):
                file_contents = read_file(f, False)
                match = None
                for line, text in enumerate(file_contents):
                    match = code_matcher.match(text)
                    if (match is not None):
                        break
                if (match is not None):
                    file_ = f
                    region = (line+1, match.start(0))
                    break
        
        yield file_
        yield region

    def find_screen_component(self, view, component_type, component_name):
        file_ = self.filename
        if (component_type == 'PtctButtons'):
            component_type = 'BodyButtons'
        pattern = r'^ *:%s +%s' % (component_type, component_name)
        region = view.find(pattern, 1)

        if ((region is None) or region.empty()):
            file_ = None
            component_matcher = re.compile(pattern)
            for f in self.get_include_files(view):
                file_contents = read_file(f, False)
                match = None
                for line, text in enumerate(file_contents):
                    match = component_matcher.match(text)
                    if (match is not None):
                        break
                if (match is not None):
                    file_ = f
                    region = (line+1, match.start(0))
                    break
        
        yield file_
        yield region

    def find_local(self, view, local):
        file_ = self.filename
        pattern = r'^ *:Name +%s' % local
        region = view.find(pattern, 1)

        if ((region is None) or region.empty()):
            file_ = None
            local_matcher = re.compile(pattern)
            for f in self.get_include_files(view):
                file_contents = read_file(f, False)
                match = None
                for line, text in enumerate(file_contents):
                    match = local_matcher.match(text)
                    if (match is not None):
                        break
                if (match is not None):
                    file_ = f
                    region = (line+1, match.start(0))
                    break
        
        yield file_
        yield region

    def get_codeblock(self, view, sel = None):
        if sel == None:
            sel = view.sel()[0]
        return CodeBlock(view, sel.begin())

    def is_translatable(self):
        return (self.ring_object is not None)

    def translate(self):
        """Translates the Focus file"""

        if not self.is_translatable():
            return False

        full_path = None
        default_path = os.path.join('PgmObject', 'Foc', 
                                    'FocZ.Textpad.Translate.P.mps')
        partial_path = None
        
        logger.debug('self.filename: %s', self.filename)
        partial_path = default_path
        settings = sublime.load_settings("m-at.sublime-settings")
        custom_cmd = settings.get("custom_translate_command")
        if (custom_cmd is not None):
            custom_path = os.path.join('PgmObject', custom_cmd)
            custom_file_path = self.ring_object.get_file_path(custom_path)
            if ((custom_file_path is not None) and os.path.isfile(custom_file_path)):
                partial_path = custom_path
                logger.info('Using %s for Translate command', partial_path)
        
        return self.ring_object.run_file(partial_path = partial_path, 
            full_path = full_path, parameters = self.filename)

    def format(self):
        """Formats the Focus file"""

        partial_path = os.path.join('PgmObject', 'Foc', 
                                    'FocZ.Textpad.Format.P.mps')
        return self.ring_object.run_file(partial_path = partial_path, 
                                         parameters = self.filename)

    def is_runnable(self):
        """Returns true if the file is a screen or process file and can be run"""
        l = self.filename.lower()
        return ((self.ring_object is not None) and 
                (('.p.' in l) or ('.s.' in l)))

    def run(self):
        """Runs the Focus file if possible"""
        if self.is_runnable():
            return self.ring_object.run_file_nice(full_path = self.filename)

    def is_includable(self):
        l = self.filename.lower()
        logger.debug('File includable: %s', (l.endswith('.i.focus') or l.endswith('.d.focus')))
        return (l.endswith('.i.focus') or l.endswith('.d.focus'))
        
class CodeBlock(object):
    """Represents a single subroutine in a Focus file."""

    def __init__(self, view, point):
        super(CodeBlock, self).__init__()
        self.view = view
        if (Focus.score_selector(view, point, 'subroutine') == 0):
            raise InvalidCodeblockError(view, point)
        self.codeblock_region = self.get_codeblock_region(point)
        # logger.debug('self.codeblock_region = %s', self.codeblock_region)
        self.header_region, self.documentation_region, self.code_region = self.split_codeblock_region()
        # logger.debug('self.header_region = %s', self.header_region)
        # logger.debug('self.documentation_region = %s', self.documentation_region)
        # logger.debug('self.code_region = %s', self.code_region)
        self.codeblock_name = self.view.substr(self.header_region)
        name_match = re.match(r':Code\s+(.+)', self.codeblock_name)
        if name_match is not None:
            self.codeblock_name = name_match.group(1)
        # logger.debug('self.codeblock_name = %s', self.codeblock_name)
        # logger.debug('Finished creating CodeBlock')

    def get_codeblock_region(self, point):
        """Gets the region containing the function surrounding the current point"""
        if Focus.score_selector(self.view, point, 'subroutine') <= 0:
            return None

        line = self.view.line(point)
        point = line.end()
        if Focus.score_selector(self.view, point, 'subroutine') <= 0:
            point = line.begin() - 1

        while Focus.score_selector(self.view, point, 'subroutine') > 0:
            region = self.view.extract_scope(point)
            point = region.end()

        return region 
        
    def split_codeblock_region(self):
        """Splits the codeblock region into header region, documentation region and code region"""
        start = self.codeblock_region.begin()
        header_region = self.view.line(start)
        yield header_region

        doc_start = header_region.end() + 1
        if Focus.score_selector(self.view, doc_start, 'comment') > 0:
            doc_region = self.view.extract_scope(doc_start)
            doc_region = sublime.Region(doc_region.begin(), doc_region.end()-1)
        else:
            doc_region = sublime.Region(doc_start, doc_start)
        yield doc_region
        yield sublime.Region(doc_region.end()+1, self.codeblock_region.end())


    def get_arguments_from_function(self, return_flat_list = False):
        """Gathers the arguments to a function."""

        codeblock_args = list()

        first_line = self.view.substr(self.view.line(self.code_region.begin()))
        match = re.match(r"^(\[.*?\])*\^([A-Z]|\{[A-Z,{}]*\})", first_line)

        if match:
            if (match.group(2)[0] == '{'):
                codeblock_args = CodeBlock.split_args(match.group(2))
                if return_flat_list:
                    codeblock_args = CodeBlock.flatten_args(codeblock_args)
            elif return_flat_list:
                codeblock_args.append(match.group(2))
            else:
                codeblock_args = match.group(2)

        return codeblock_args

    def split_args(arg_string):
        match_dictionary = dict()
        key_counter = 0
        proceed = True

        while ( '{' in arg_string ) and proceed:
            proceed = False
            matches = re.findall( r'\{[A-Z,\d$]*\}', arg_string )
            for m in matches:
                proceed = True
                arg_list = list()
                split_args = m[1:-1].split(',')

                for index, arg in enumerate( split_args ):
                    if ( arg == '' ):
                        arg = str( index )
                    elif ( arg[0] == '$' ):
                        arg = match_dictionary[arg]
                    arg_list.append( arg )

                key_counter += 1
                key = '${0}'.format( key_counter )
                match_dictionary[key] = arg_list
                arg_string = arg_string.replace( m, key )

        return match_dictionary[key]

    def flatten_args(arg_list):
        flat_list = list()

        for a in arg_list:
            if isinstance( a, list ):
                for p in CodeBlockDocumentation.flatten_args( a ):
                    flat_list.append( p )
            elif ( isinstance( a, str ) and a.isalpha() ):
                flat_list.append( a )

        return flat_list

    def get_variables_from_function(self):
        """Get the variables used in the function."""

        codeblock_vars = dict()
        codeblock_args = set()

        first_line = self.view.substr( self.view.line( self.code_region.begin() ) )
        match = re.search( r"\^([A-Z,{}]*)", first_line )
        if match:
            args = match.group(1)
            codeblock_args = set( re.findall( r'\b[A-Z]\b', args ) )

        for r in Focus.find_by_selector(self.view, 'fs_local'):
            if self.code_region.contains( r ):
                var = self.view.substr( r )
                if var in codeblock_vars.keys():
                    codeblock_vars[var].add_region( r )
                else: 
                    is_arg = False
                    if ( var in codeblock_args ):
                        is_arg = True
                    cbv = CodeBlockVar( var, is_arg, self.view, [r] )
                    codeblock_vars[cbv.var] = cbv

        return codeblock_vars

    def get_sets_from_function(self):
        """Get the sets used in the function"""

        codeblock_sets = dict()

        for r in self.view.find_all( r'@[A-Za-z]\d+' ):
            if self.code_region.contains( r ):
                listset = self.view.substr( r )
                set_number = listset[2:]
                upper_or_lower = CodeBlockSet.determine_upper( listset )
                listset = CodeBlockSet.format_set( set_number, upper_or_lower )

                if listset in codeblock_sets.keys():
                    codeblock_sets[listset].add_region( r )
                else: 
                    cbs = CodeBlockSet( set_number, upper_or_lower, self.view, [r] )
                    codeblock_sets[cbs.set] = cbs

        return codeblock_sets

    def update_documentation( self, update_only = False, use_snippets = False):
        documentation = CodeBlockDocumentation( self )
        return documentation.update( update_only, use_snippets )

class CodeBlockAttribute(object):
    """Represents a piece of data used in a CodeBlock. 
       Meant to be a superclass for CodeBlockVar and CodeBlockSet."""

    def __init__(self, value, view, regions = list(), documentation = None):
        super(CodeBlockAttribute, self).__init__()
        self.value = value
        self.view = view
        self.regions = regions
        self.documentation = documentation

    def add_region(self, region):
        self.regions.append( region )

    def __str__(self):
        return self.value

class CodeBlockVar(CodeBlockAttribute):
    """Represents a variable within a CodeBlock."""

    def __init__(self, var, is_arg, view, regions, documentation = None):
        super(CodeBlockVar, self).__init__( var, view, regions, documentation )
        self.is_arg = is_arg

    @property
    def var(self):
        return self.value

    def __str__(self):
        return self.var
    
class CodeBlockSet(CodeBlockAttribute):
    """Represents an upper or lower listset within a codeblock."""

    UPPER = "UPPER"
    LOWER = "LOWER"

    def __init__(self, set_number, upper_or_lower, view, regions, documentation = None):
        super(CodeBlockSet, self).__init__( (upper_or_lower, set_number), view, regions, documentation )
        self.upper_or_lower = upper_or_lower
        self.set_number = set_number
        self.is_lower = False
        self.is_upper = False
        if ( upper_or_lower == CodeBlockSet.UPPER ):
            self.is_upper = True
        elif ( upper_or_lower == CodeBlockSet.LOWER ):
            self.is_lower = True

    @property
    def set(self):
        return CodeBlockSet.format_set( self.set_number, self.upper_or_lower )

    def __str__(self):
        return self.set

    def determine_upper(string):
        match = re.match( r'@[A-Z]', string )
        if match:
            return CodeBlockSet.UPPER
        else:
            return CodeBlockSet.LOWER

    def format_set(set_number, upper_or_lower):
        prefix = 'U'
        if ( upper_or_lower == CodeBlockSet.LOWER ):
            prefix = 'L'
        return '{0}({1})'.format( prefix, set_number )
    
class CodeBlockDocumentation(object):
    """Represents the documentation for a CodeBlock."""

    all_doc_sections = ['Purpose', 'Arguments', 'Preconditions', 
                        'Local Variables', 'Data Structures', 'Side Effects', 
                        'Returns', 'Additional Notes', 'Unit Test', 
                        'Deprecated']

    required_doc_sections = ('Purpose', 'Arguments', 'Local Variables', 'Returns')

    omit_sections = ['Unit Test', 'Deprecated']

    def __init__(self, codeblock):
        # super(CodeBlockDocumentation, self).__init__()
        self.codeblock = codeblock
        self.doc_regions = dict()
        for region in self.split_doc_region():
            # logger.debug('region = %s', region)
            # logger.debug('region = %s', self.view.substr(region))
            if ( not region.empty() ):
                dr = self.get_region( region )
                self.doc_regions[dr.section] = dr
        self._snippet_counter = 0
        self.omit_sections = CodeBlockDocumentation.omit_sections
        settings = sublime.load_settings('m-at.sublime-settings')
        requested_sections = settings.get('documentation_sections')
        if (requested_sections is not None):
            self.omit_sections = list(set(CodeBlockDocumentation.all_doc_sections) - 
                                 set(requested_sections))

    @property
    def region(self):
        return self.codeblock.documentation_region

    @property
    def snippet_counter(self):
        self._snippet_counter += 1
        return self._snippet_counter

    @property
    def view(self):
        return self.codeblock.view
    
    def split_doc_region(self):
        reg_ex = r"//\s*:Doc\s+.+"
        f = self.view.find( reg_ex, self.region.begin() )
        # logger.debug(self.region)
        if ( f and self.region.contains( f ) ):
            start = f.begin()
            f = self.view.find( reg_ex, f.end() )
            # logger.debug('f = %s', f)
            while (f and self.region.contains( f ) ):
                # logger.debug('f = %s', f)
                yield sublime.Region(start, f.begin() - 1)
                start = f.begin()
                f = self.view.find( reg_ex, f.end() )
            yield sublime.Region( start, self.region.end() )
        else:
            yield self.region

    def get_region(self, region = None, section = None):
        r = None
        if region:
            reg_ex = r"\s*//\s*:Doc\s*([a-zA-Z ]+?)\s*$"
            header_region = self.view.find( reg_ex, region.begin() )
            header = self.view.substr( header_region )
            match = re.match( reg_ex, header )

            if match:
                section = match.group(1)
        elif not section:
            section = 'Deprecated'

        if ( section == 'Arguments' ):
            r = CodeBlockDocumentation.ArgumentsRegion( self, region, section )
        elif ( section == 'Local Variables' ):
            r = CodeBlockDocumentation.LocalVarsRegion( self, region, section )
        elif ( section == 'Data Structures' ):
            r = CodeBlockDocumentation.DataStrucRegion( self, region, section )
        # elif ( section == 'Unit Test' ):
        #     r = CodeBlockDocumentation.UnitTestRegion( self, region, section )
        else:
            r = CodeBlockDocumentation.Region( self, region, section )

        return r
    
    def update(self, update_only = False, use_snippets = False):
        """Generates an updated documentation section for the function"""

        updated_sections = list()
        sections_to_return = self.doc_regions.keys()

        if (not update_only):
            sections_to_return = CodeBlockDocumentation.all_doc_sections

        for section in CodeBlockDocumentation.all_doc_sections:
            if (section in self.doc_regions.keys()):
                self.doc_regions[section].update( use_snippets )
                updated_sections.append( self.doc_regions[section].updated_content )
            elif ((section not in self.omit_sections) and (not update_only)):
                temp_section = self.get_region( None, section )
                temp_section.update(use_snippets)
                updated_sections.append(temp_section.updated_content)

        return '\n'.join(updated_sections)

    class Region(object):
        """Represents a single documentation section"""

        header_match_object = re.compile(r'\s*//\s*:Doc\s*([a-zA-Z ]+?)\s*$')
        none_match_object = re.compile(r'//\s*None\s*$', re.MULTILINE)
        body_prefix = '//     '

        def __init__(self, documentation, region = None, section = None):
            self.documentation = documentation
            settings = sublime.load_settings('m-at.sublime-settings')
            self.separators = dict()
            self.separators['alpha'] = settings.get('default_variable_separator', ' - ')
            self.separators['numeric'] = settings.get('default_numeric_separator', '.  ')
            # logger.debug('self.separators = %s', self.separators)
            self.separator_width = max(len(self.separators['alpha']), 
                                       len(self.separators['numeric']))

            if (region != None):
                self.region = region
                self.current_content = self.view.substr( self.region )
                self.header_region, self.body_region, self.current_header, self.section, self.current_body = self.split_region()
                
                if (self.section == None):
                    if (section != None):
                        self.section = section
                    else:
                        raise DocRegionException('Doc Region Type could not be determined from Region, and no Type specified.')
            elif (section != None):
                self.section = section
                self.region = None
                self.current_content = None
                self.header_region = None
                self.body_region = None
                self.current_header = None
                self.current_body = None
            else:
                raise DocRegionException('A Doc Region must have a specified Region or Type to be instantiated.')

        @property
        def codeblock(self):
            return self.documentation.codeblock
        
        @property
        def view(self):
            return self.documentation.view
        
        def split_region(self):
            """Breaks the Doc_region up into header and content regions"""

            body_region = self.region
            header_region = self.view.find( r"\s*//\s*:Doc\s*[a-zA-Z ]+", self.region.begin() )
            if ( header_region != None ) and body_region.contains(header_region):
                body_region = sublime.Region( header_region.end() + 1, self.region.end() )
                header_content = self.view.substr(header_region)
                type_match = CodeBlockDocumentation.Region.header_match_object.search( header_content )

                yield header_region                 # Header Region
                yield body_region                   # Body Region
                yield header_content                # Header Content
                if (type_match != None):
                    yield type_match.group(1)       # section
                else:
                    yield None
                yield self.view.substr(body_region) # Body Content
            else:
                yield None                          # Header Region
                yield body_region                   # Body Region
                yield '//**Deprecated**'            # Header Content
                yield 'Deprecated'                  # section
                yield self.view.substr(body_region) # Body Content

        def update(self, use_snippets):
            self.updated_header = '//:Doc {0}'.format(self.section)
            # logger.debug('current body: %s', self.current_body)

            if ( ( self.current_body == None ) or ( self.current_body == '' ) ):
                self.update_none_section( use_snippets )
            else:
                none_match = self.none_match_object.match( self.current_body )
                if none_match:
                    self.update_none_section( use_snippets )
                else:
                    self.updated_body = self.current_body
                    self.updated_content = self.updated_header + '\n' + self.updated_body

        def update_none_section(self, use_snippets):
            if use_snippets:
                a = b = 0
                if ( self.section not in CodeBlockDocumentation.required_doc_sections ):
                    b = self.documentation.snippet_counter
                a = self.documentation.snippet_counter
                self.updated_body = '{0}${{{1}:None}}'.format( CodeBlockDocumentation.Region.body_prefix, a )
                self.updated_content = self.updated_header + '\n' + self.updated_body
                if ( self.section not in CodeBlockDocumentation.required_doc_sections ):
                    self.updated_content = '${{{0}:{1}}}'.format( b, self.updated_content )
            else:
                self.updated_body = '{0}None}}'.format( CodeBlockDocumentation.Region.body_prefix )
                self.updated_content = self.updated_header + '\n' + self.updated_body

        def normalize_separators(self, l):
            for var, sep, content in l.values():
                if '.' in sep:
                    sep = '{{0:<{0}}}'.format( self.separator_width ).format(sep.strip())
                else:
                    sep = '{{0:^{0}}}'.format( self.separator_width ).format(sep.strip())
                if (var.isnumeric()):
                    self.separators['numeric'] = sep
                else:
                    self.separators['alpha'] = sep
                l[var] = (var, sep, content)

            return l

        def get_prefix_postfix(self, index, length):
            prefix = postfix = ''
            if ( index == 0 ):
                prefix = '{'
            else:
                prefix = '|'
            if ( index + 1 == length ):
                postfix = '}'

            yield prefix
            yield postfix

        def get_separator(self, var):
            sep = self.separators['alpha']
            if (var.isnumeric()):
                sep = self.separators['numeric']

            return sep

        class DocRegionException( Exception ):
            """Exception that is raised if you try to create an inappropriate Doc Region"""

            def __init__(self, description):
                Exception.__init__( self )
                self.description = description

            def __str__(self):
                return repr(self)

    class ArgumentsRegion(Region):
        """CodeBlock Documentation Region for Arguments. Arguments require special parsing and updating."""

        body_prefix = '//     '

        def __init__(self, documentation, region = None, section = None):
            super(CodeBlockDocumentation.ArgumentsRegion, self).__init__( documentation, region, section )
            self.documented_args = dict()
            self.parse_doc()

        def parse_doc(self):
            if (self.current_body != None):
                # get initial indentation
                indent = CodeBlockDocumentation.Region.body_prefix
                indent_match = re.search(r"(//\s*)[|\{]?([A-Z]|\d{1,2})\s*[-=:.]\s*", self.current_body)
                if indent_match:
                    indent = indent_match.group(1)

                reg_ex = indent + r" ?[|\{]?([A-Z]|\d{1,2})(\s*[-=:.]\s*)([\s\S]*?)\n(?=" + indent + r" ?[|\{]?([A-Z]|\d{1,2})\s*[-=:.]|END)"

                # Extract the variable documentation
                documented_arg_info = re.findall( reg_ex, self.current_body + '\nEND' )
                for arg, sep, content, unused in documented_arg_info:
                    self.documented_args[arg] = (arg, sep, content)
                    if (len(sep) > self.separator_width):
                        self.separator_width = len(sep)

                self.documented_args = self.normalize_separators( self.documented_args )

        def update(self, use_snippets):
            # Build each line of the new section
            updated_arg_text = list()
            arguments_in_use = self.codeblock.get_arguments_from_function()
            documented_args = dict(self.documented_args)

            if isinstance( arguments_in_use, str ):
                try:
                    var, sep, content = documented_args[arguments_in_use]
                    del documented_args[var]
                except KeyError:
                    var = arguments_in_use
                    if (var.isnumeric()):
                        sep = self.separators['numeric']
                    else:
                        sep = self.separators['alpha']

                    if use_snippets:
                        content = '${0}'.format(self.documentation.snippet_counter)

                updated_arg_text.append( '{0}{1}{2}{3}'.format(CodeBlockDocumentation.Region.body_prefix, 
                    var, sep, content) )
            else:
                updated_arg_text = self.format_list( arguments_in_use, documented_args, use_snippets )

            # Add the arguments that are no longer used
            for arg, sep, content in documented_args.values():
                updated_arg_text.append(CodeBlockDocumentation.Region.body_prefix + arg + sep + '**Unused** ' + content)
                
            # Store the updated doc.
            self.updated_header = '//:Doc {0}'.format(self.section)
            if (len(updated_arg_text) == 0):
                super(CodeBlockDocumentation.ArgumentsRegion, self).update( use_snippets )
            else:
                self.updated_body = '\n'.join( updated_arg_text )
                self.updated_content = self.updated_header + '\n' + self.updated_body

        def format_list(self, l, documented_args, use_snippets, indent = body_prefix):
            updated_arg_text = list()
            length = len( l )
            print(documented_args)

            for index, var in enumerate( l ):
                sep = content = ''

                prefix, postfix = self.get_prefix_postfix( index, length )

                if isinstance( var, list ):
                    try:
                        var, sep, content = documented_args[str(index)]
                        if ( ( index + 1 == length ) and ( content[-1] == '}' ) ) or ( content[-1] == '|' ):
                            content = content[:-1]
                        del documented_args[str(index)]

                    except KeyError:
                        sep = self.separators['numeric']
                        first_line = '{0}{1}{2}'.format( index, sep, prefix )
                        temp_indent = indent + ' ' * len( first_line )
                        sub_list = self.format_list( var, documented_args, use_snippets, temp_indent )
                        print(sub_list)
                        var = str( index )
                        
                        sub_list[0] = sub_list[0][len( temp_indent ):]

                        content = '\n'.join( sub_list )
                    
                else:
                    try:
                        var, sep, content = documented_args[var]
                        if ( ( index + 1 == length ) and ( content[-1] == '}' ) ) or ( content[-1] == '|' ):
                            content = content[:-1]
                        del documented_args[var]

                    except KeyError:
                        sep = self.get_separator( var )

                        if use_snippets:
                            content = '${0}'.format( self.documentation.snippet_counter )

                updated_line = '{0}{1}{2}{3}{4}{5}'.format(indent, prefix, var, sep, content, postfix)
                updated_arg_text.append( updated_line )

            return updated_arg_text
            
    class LocalVarsRegion(Region):
        """CodeBlock Documentation Region for Local Variables. Local Variables require special parsing and updating."""

        def __init__(self, documentation, region = None, section = None):
            super(CodeBlockDocumentation.LocalVarsRegion, self).__init__( documentation, region, section )
            self.documented_vars = dict()
            self.parse_doc()

        def parse_doc(self):
            if (self.current_body != None):
                # Extract the variable documentation
                documented_var_info = re.findall(r"//\s*([A-Z])(\s*[-=:]\s*)([\s\S]*?)\n(?=//\s*[A-Z]\s*[-=:]|END)", self.current_body + '\nEND')
                for var, sep, content in documented_var_info:
                    self.documented_vars[var] = (var, sep, content)
                    if (len(sep) > self.separator_width):
                        self.separator_width = len(sep)
                
            # normalize separators
            self.documented_vars = self.normalize_separators( self.documented_vars )

        def update(self, use_snippets):
            documented_vars = dict( self.documented_vars )
            variables_in_use = self.codeblock.get_variables_from_function().keys()
            arguments_in_use = self.codeblock.get_arguments_from_function( return_flat_list = True )
            updated_var_text = list()
            separator = self.separators['alpha']

            # Merge the documented vars with the function vars
            for var in variables_in_use:
                if ( var not in documented_vars.keys() ):
                    documented_vars[var] = ( var, separator, '' )

            # Build each line of the new section
            for var, sep, content in sorted( documented_vars.values() ):
                if ( ( var in arguments_in_use ) and ( content.lower() != 'see arguments' ) ):
                    if ( use_snippets and ( content != '' ) ):
                        content = '${{{0}:{1}}}'.format( self.documentation.snippet_counter, ': ' + content )
                    content = 'See arguments{0}'.format( content )

                if ( use_snippets and ( content == '' ) ):
                    content = '${0}'.format( self.documentation.snippet_counter )
                elif ( var not in variables_in_use ):
                    content = '**Unused** {0}'.format( content )
                    if use_snippets:
                        content = '${{{0}:{1}}}'.format( self.documentation.snippet_counter, content )
                updated_var_text.append( '{0}{1}{2}{3}'.format( CodeBlockDocumentation.Region.body_prefix, var, sep, content ) )

            # Store the regenerated documentation
            self.updated_header = '//:Doc {0}'.format(self.section)
            if ( len( updated_var_text ) == 0 ):
                super(CodeBlockDocumentation.LocalVarsRegion, self).update(use_snippets)
            else:
                self.updated_body = '\n'.join( updated_var_text )
                self.updated_content = self.updated_header + '\n' + self.updated_body
            
    class DataStrucRegion(Region):
        """CodeBlock Documentation Region for Data Structures. Data Structures require special parsing and updating."""
        
        def __init__(self, documentation, region = None, section = None):
            super(CodeBlockDocumentation.DataStrucRegion, self).__init__( documentation, region, section )
            self.documented_sets = dict()
            self.parse_doc()

        def parse_doc(self):
            if (self.current_body != None):
                # Extract the set documentation
                documented_set_info = re.findall(r"//\s*((L|U)\(\d+\))(\s*[-=:]\s*)([\s\S]*?)\n(?=//\s*(L|U)\(\d+\)\s*[-=:]|END)", self.current_body + '\nEND')
                for set, type, sep, content, unused in documented_set_info:
                    self.documented_sets[set] = (set, sep, content)
                    if (len(sep) > self.separator_width):
                        self.separator_width = len(sep)
                
            # normalize separators
            self.documented_sets = self.normalize_separators(self.documented_sets)

        def update(self, use_snippets):
            documented_sets = dict(self.documented_sets)
            sets_in_use = self.codeblock.get_sets_from_function().keys()
            updated_set_text = list()
            separator = self.separators['alpha']

            # Merge the documented sets with the function sets
            for listset in sets_in_use:
                if (listset not in documented_sets.keys()):
                    type = listset[0]
                    number = int(listset[2:-1])
                    documented_sets[listset] = (listset, separator, '')

            for listset, sep, content in documented_sets.values():
                type = listset[0]
                number = int(listset[2:-1])
                documented_sets[listset] = (type, number, listset, separator, content)

            # Build each line of the new section
            for unused, unused, listset, sep, content in sorted(documented_sets.values()):
                if use_snippets and ( content == '' ):
                    content = '${0}'.format( self.documentation.snippet_counter )
                elif ( listset not in sets_in_use ):
                    content = '**Unused** ' +  content
                    if use_snippets:
                        content = '${{{0}:{1}}}'.format( self.documentation.snippet_counter, content )

                updated_set_text.append( '{0}{1}{2}{3}'.format( CodeBlockDocumentation.Region.body_prefix, listset, sep, content ) )

            self.updated_header = '//:Doc ' + self.section
            if ( len( updated_set_text ) == 0 ):
                super(CodeBlockDocumentation.DataStrucRegion, self).update( use_snippets )
            else:
                self.updated_body = '\n'.join( updated_set_text )
                self.updated_content = self.updated_header + '\n' + self.updated_body
            
    class UnitTestRegion(Region):
        """CodeBlock Documentation Region for Data Structures. Data Structures require special parsing and updating."""
        
        def __init__(self, documentation, region = None, section = None):
            super(CodeBlockDocumentation.UnitTestRegion, self).__init__( documentation, region, section )
            self.unit_tests = []
            self.parse_doc()

        def parse_doc(self):
            if (self.current_body != None):
                # Extract the set documentation
                documented_set_info = re.findall(r"//\s*((L|U)\(\d+\))(\s*[-=:]\s*)([\s\S]*?)\n(?=//\s*(L|U)\(\d+\)\s*[-=:]|END)", self.current_body + '\nEND')
                for set, type, sep, content, unused in documented_set_info:
                    self.documented_sets[set] = (set, sep, content)
                    if (len(sep) > self.separator_width):
                        self.separator_width = len(sep)
                
            # normalize separators
            self.documented_sets = self.normalize_separators( self.documented_sets )

        def update(self, use_snippets):
            documented_sets = dict( self.documented_sets )
            sets_in_use = self.codeblock.get_sets_from_function().keys()
            updated_set_text = list()
            separator = self.separators['alpha']

            # Merge the documented sets with the function sets
            for listset in sets_in_use:
                if ( listset not in documented_sets.keys() ):
                    documented_sets[listset] = ( listset, separator, '' )

            # Build each line of the new section
            for listset, sep, content in sorted( documented_sets.values() ):
                if use_snippets and ( content == '' ):
                    content = '${0}'.format( self.documentation.snippet_counter )
                elif ( listset not in sets_in_use ):
                    content = '**Unused** ' +  content
                    if use_snippets:
                        content = '${{{0}:{1}}}'.format( self.documentation.snippet_counter, content )

                updated_set_text.append( 
                    '{0}{1}{2}{3}'.format( 
                        CodeBlockDocumentation.Region.body_prefix, listset, 
                        sep, content 
                    ) 
                )

            self.updated_header = '//:Doc ' + self.section
            if ( len( updated_set_text ) == 0 ):
                super(CodeBlockDocumentation.UnitTestRegion, self).update( use_snippets )
            else:
                self.updated_body = '\n'.join( updated_set_text )
                self.updated_content = self.updated_header + '\n' + self.updated_body

        class UnitTest(object):
            """Object to represent an M-AT Unit Test."""

            def __init__(self, name, setup, results):
                super(UnitTest, self).__init__()
                self.name = name
                self.setup = setup
                self.results = results

                
def extract_fs_function(view, sel):
    """Extracts the text and region of the FS function nearest to sel.

    Keyword arguments:
    view - The view to extract from
    sel - a single Region
    
    """
    scope_name = view.scope_name(sel.begin()).strip()
    if (Focus.score_selector(view, sel.begin(), 'fs_function') == 0):
        return None
        
    selection = sel
    substring = view.substr(selection)
    # Find the location of the closest @ in or left of the selection
    try:
        at_loc = substring.index('@')
    except ValueError:
        temp_start = selection.begin()
        while (view.substr(temp_start) != '@'):
            temp_start -= 1
        selection = sublime.Region(temp_start, selection.end())
    else:
        selection = sublime.Region(selection.begin() + at_loc, selection.end())
    
    end = view.find_by_class(selection.begin(), True, sublime.CLASS_WORD_END, 
                             "/\\()\"'-:,;<>~!#$%^@&*|+=[]{}`~?.")
    selection = sublime.Region(selection.begin(), end)
    substring = view.substr(selection)
    logger.debug('selection = %s', selection)
    logger.debug('substring = %s', substring)

    return (substring, selection)

def extract_focus_function(view, sel):
    """Extracts the text and region of the Focus function nearest to sel.

    Keyword arguments:
    view - The view to extract from
    sel - a single Region
    
    """
    if isinstance(sel, int):
        if Focus.score_selector(view, sel, 'focus_function') <= 0:
            return None
            
        selection = sublime.Region(sel, sel)
    else:
        if Focus.score_selector(view, sel.begin(), 'focus_function') <= 0:
            return None
            
        selection = sel
    substring = view.substr(selection)
    # Find the location of the closest @ in or left of the selection
    try:
        at_loc = substring.index('@')
    except ValueError:
        start = selection.begin()
        if (selection.empty() and (view.substr(start) == '@')):
            logger.debug('left of @')
            start = start + 1
            selection = sublime.Region(start, start)
    else:
        start = selection.begin() + at_loc + 1
        selection = sublime.Region(start, max(selection.end(), start))
        logger.debug(selection)
        logger.debug(view.substr(selection))

    selection_1 = view.expand_by_class(selection, sublime.CLASS_PUNCTUATION_START, '@')
    selection_2 = view.expand_by_class(selection, sublime.CLASS_PUNCTUATION_END, ')')
    selection = selection_1.intersection(selection_2)
    substring = view.substr(selection)
    
    logger.debug(selection)
    logger.debug(substring)

    return (substring, selection)

def split_focus_function(string, region):
    """Splits a focus function string and region into it's name and arguments

    Keyword arguments:
    string - A string representing the entire focus function
    region - A region representing the entire focus function

    """
    match = re.match(r'\@([A-Za-z0-9]+)\((.*)\)', string)
    if match is not None:
        name = match.group(1)
        name_span = match.span(1)
        arguments = match.group(2)
        arg_span = match.span(2)

        start = region.begin()
        name_reg = sublime.Region(start + name_span[0], start + name_span[1])
        arg_reg = sublime.Region(start + arg_span[0], start + arg_span[1])

        logger.debug(((name, name_reg), (arguments, arg_reg)))

        return ((name, name_reg), (arguments, arg_reg))
    else:
        return None

def extract_focus_function_name(view, sel):
    """Extracts the text and region of the name of the Focus function nearest to sel.

    Keyword arguments:
    view - The view to extract from
    sel - a single Region
    
    """
    match = extract_focus_function(view, sel)

    if match is not None:
        match = split_focus_function(match[0], match[1])

        if match is not None:
            string = '@' + match[0][0]
            region = match[0][1]
            region = sublime.Region(region.begin()-1, region.end())
            return (string, region)

    return None

def extract_alias(view, sel):
    """Extracts the text and region of the alias nearest to sel.

    Keyword arguments:
    view - The view to extract from
    sel - a single Region
    
    """
    if Focus.score_selector(view, sel.begin(), 'called_alias') <= 0:
        return None
        
    selection = sel
    substring = view.substr(selection)
    logger.debug(selection)
    logger.debug(substring)
    # Find the location of the closest @ in or left of the selection
    try:
        at_loc = substring.index('@')
    except ValueError:
        start = selection.begin()
        if (selection.empty() and (view.substr(start) == '@')):
            logger.debug('left of @')
            start = start + 3
            selection = sublime.Region(start, start)
    else:
        start = selection.begin() + at_loc + 3
        selection = sublime.Region(start, max(selection.end(), start))

    selection_1 = view.expand_by_class(selection, sublime.CLASS_WORD_END, '@')
    selection_2 = view.expand_by_class(selection, sublime.CLASS_WORD_START, ')')
    selection = selection_1.intersection(selection_2)
    substring = view.substr(selection)
    
    logger.debug(selection)
    logger.debug(substring)

    return (substring, selection)

    