import re

import sublime

from ..tools.sublime import (
    split_member_region
)
from ..tools.settings import (
    get_documentation_sections,
    get_default_separators,
    get_documentation_indent
)


class CodeBlock(object):
    """Represents a single subroutine in a Focus file."""

    ARG_MATCHER = re.compile(r"^(\[.*?\])*\^([A-Z]|\{[A-Z,{}]*\})")
    ARG_SPLITTER = re.compile(r"\{[A-Z,\d$]*\}")

    def __init__(self, ring_view, point):
        super(CodeBlock, self).__init__()
        self.ring_view = ring_view
        if self.ring_view is None:
            raise InvalidCodeBlockError(self.view, point)
        self.point = point
        if self.view.score_selector(point, 'meta.subroutine.fs') <= 0:
            raise InvalidCodeBlockError(self.view, point)

        reg = self.ring_view.get_member_region(self.point)
        if not reg:
            raise InvalidCodeBlockError(self.view, point)

        self.codeblock_region = sublime.Region(reg[0], reg[1])

    @property
    def view(self):
        return self.ring_view.view

    @property
    def header_region(self):
        try:
            return self._header_region
        except AttributeError:
            self.split_codeblock_region()
            return self._header_region

    @header_region.setter
    def header_region(self, value):
        self._header_region = value

    @property
    def documentation_region(self):
        try:
            return self._documentation_region
        except AttributeError:
            self.split_codeblock_region()
            return self._documentation_region

    @documentation_region.setter
    def documentation_region(self, value):
        self._documentation_region = value

    @property
    def code_region(self):
        try:
            return self._code_region
        except AttributeError:
            self.split_codeblock_region()
            return self._code_region

    @code_region.setter
    def code_region(self, value):
        self._code_region = value

    @property
    def codeblock_name(self):
        try:
            return self._codeblock_name
        except AttributeError:
            self._codeblock_name = self.view.substr(self.header_region)
            name_match = re.match(r':Code\s+(.+)', self._codeblock_name)
            if name_match is not None:
                self._codeblock_name = name_match.group(1)
            return self._codeblock_name

    @codeblock_name.setter
    def codeblock_name(self, value):
        self._codeblock_name = value

    @property
    def doc(self):
        try:
            return self._doc
        except AttributeError:
            self._doc = CodeBlockDoc(self)
            return self._doc

    def split_codeblock_region(self):
        """
        Splits the codeblock region into header region, documentation region
        and code region.
        """
        (self.header_region,
         self.documentation_region,
         self.var_declaration_region,
         self.code_region) = split_member_region(self.view,
                                                 self.codeblock_region)

    def get_arguments_from_function(self, return_flat_list=False):
        """Gathers the arguments to a function."""

        codeblock_args = list()

        first_line = self.view.substr(self.view.line(self.code_region.begin()))
        match = CodeBlock.ARG_MATCHER.match(first_line)

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

        while ('{' in arg_string) and proceed:
            proceed = False
            matches = re.findall(r'\{[A-Z,\d$]*\}', arg_string)
            for m in matches:
                proceed = True
                arg_list = list()
                split_args = m[1:-1].split(',')

                for index, arg in enumerate(split_args):
                    if arg == '':
                        arg = str(index)
                    elif arg[0] == '$':
                        arg = match_dictionary[arg]
                    arg_list.append(arg)

                key_counter += 1
                key = '${0}'.format(key_counter)
                match_dictionary[key] = arg_list
                arg_string = arg_string.replace(m, key)

        return match_dictionary[key]

    def flatten_args(arg_list):
        """Return a flat list of arguments from a possibly nested list."""
        flat_list = list()

        for a in arg_list:
            if isinstance(a, list):
                for p in CodeBlock.flatten_args(a):
                    flat_list.append(p)
            elif isinstance(a, str) and a.isalpha():
                flat_list.append(a)

        return flat_list

    def get_variables_from_function(self):
        """Get the variables used in the function."""

        codeblock_vars = dict()
        codeblock_args = set()

        first_line = self.view.substr(
            self.view.line(self.code_region.begin()))
        match = re.search(r"\^([A-Z,{}]*)", first_line)
        if match:
            args = match.group(1)
            codeblock_args = set(re.findall(r'\b[A-Z]\b', args))

        for r in self.view.find_by_selector('meta.variable.other'):
            if self.code_region.contains(r):
                var = self.view.substr(r)
                if var in codeblock_vars.keys():
                    codeblock_vars[var].add_region(r)
                else:
                    is_arg = False
                    if var in codeblock_args:
                        is_arg = True
                    cbv = CodeBlockVar(var, is_arg, self.view, [r])
                    codeblock_vars[cbv.var] = cbv

        return codeblock_vars

    def get_sets_from_function(self):
        """Get the sets used in the function"""

        codeblock_sets = dict()

        for r in self.view.find_all(r'@[A-Za-z]\d+'):
            if self.code_region.contains(r):
                listset = self.view.substr(r)
                set_number = listset[2:]
                upper_or_lower = CodeBlockSet.determine_upper(listset)
                listset = CodeBlockSet.format_set(set_number, upper_or_lower)

                if listset in codeblock_sets.keys():
                    codeblock_sets[listset].add_region(r)
                else:
                    cbs = CodeBlockSet(set_number,
                                       upper_or_lower,
                                       self.view,
                                       [r])
                    codeblock_sets[cbs.set] = cbs

        return codeblock_sets


class CodeBlockAttribute(object):
    """Represents a piece of data used in a CodeBlock.
       Meant to be a superclass for CodeBlockVar and CodeBlockSet."""

    def __init__(self, value, view, regions=[], documentation=None):
        super(CodeBlockAttribute, self).__init__()
        self.value = value
        self.view = view
        self.regions = regions
        self.documentation = documentation

    def add_region(self, region):
        self.regions.append(region)

    def __str__(self):
        return self.value


class CodeBlockVar(CodeBlockAttribute):
    """Represents a variable within a CodeBlock."""

    def __init__(self, var, is_arg, view, regions, documentation=None):
        super(CodeBlockVar, self).__init__(var, view, regions, documentation)
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

    def __init__(self, set_number, upper_or_lower, view, regions,
                 documentation=None):
        super(CodeBlockSet, self).__init__((upper_or_lower, set_number), view,
                                           regions, documentation)
        self.upper_or_lower = upper_or_lower
        self.set_number = set_number
        self.is_lower = False
        self.is_upper = False
        if upper_or_lower == CodeBlockSet.UPPER:
            self.is_upper = True
        elif upper_or_lower == CodeBlockSet.LOWER:
            self.is_lower = True

    @property
    def set(self):
        return CodeBlockSet.format_set(self.set_number, self.upper_or_lower)

    def __str__(self):
        return self.set

    def determine_upper(string):
        match = re.match(r'@[A-Z]', string)
        if match:
            return CodeBlockSet.UPPER
        else:
            return CodeBlockSet.LOWER

    def format_set(set_number, upper_or_lower):
        prefix = 'U'
        if upper_or_lower == CodeBlockSet.LOWER:
            prefix = 'L'
        return '{0}({1})'.format(prefix, set_number)


class CodeBlockDoc(object):
    """Represents the documentation for a CodeBlock."""

    all_doc_sections = ['Purpose', 'Arguments', 'Preconditions',
                        'Local Variables', 'Data Structures', 'Side Effects',
                        'Returns', 'Additional Notes', 'Unit Test',
                        'Deprecated']

    required_doc_sections = ('Purpose', 'Arguments', 'Local Variables',
                             'Returns')

    omit_sections = ['Unit Test', 'Deprecated']

    def __init__(self, codeblock):
        super(CodeBlockDoc, self).__init__()
        self.codeblock = codeblock

        self.doc_regions = dict()
        for region in self.split_doc_region():
            self.add_region(region)

        self._snippet_counter = 0
        self.omit_sections = CodeBlockDoc.omit_sections

        requested_sections = get_documentation_sections()
        if (requested_sections is not None):
            self.omit_sections = list(
                set(CodeBlockDoc.all_doc_sections) -
                set(requested_sections))

    def __str__(self):
        return self.view.substr(self.region)

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
        f = self.view.find(reg_ex, self.region.begin())
        if f and self.region.contains(f):
            start = f.begin()
            f = self.view.find(reg_ex, f.end())

            while f and self.region.contains(f):
                yield sublime.Region(start, f.begin() - 1)
                start = f.begin()
                f = self.view.find(reg_ex, f.end())
            yield sublime.Region(start, self.region.end())
        else:
            yield self.region

    def add_region(self, region):
        if not region.empty():
            dr = self.get_region(region)
            self.doc_regions[dr.section] = dr
            attribute = dr.section.lower().replace(' ', '_')
            setattr(self, attribute, dr)

    def get_region(self, region=None, section=None):
        r = None
        if region:
            reg_ex = r"\s*//\s*:Doc\s*([a-zA-Z ]+?)\s*$"
            header_region = self.view.find(reg_ex, region.begin())
            header = self.view.substr(header_region)
            match = re.match(reg_ex, header)

            if match:
                section = match.group(1)

        elif not section:
            section = 'Deprecated'

        if section == 'Arguments':
            r = CodeBlockDoc.ArgumentsRegion(self, region, section)
        elif section == 'Local Variables':
            r = CodeBlockDoc.LocalVarsRegion(self, region, section)
        elif section == 'Data Structures':
            r = CodeBlockDoc.DataStrucRegion(self, region, section)
        elif section == 'Unit Test':
            r = CodeBlockDoc.UnitTestRegion(self, region, section)
        else:
            r = CodeBlockDoc.Region(self, region, section)

        return r

    def update(self, update_only=False, use_snippets=False):
        """Generates an updated documentation section for the function"""

        updated_sections = list()

        for section in CodeBlockDoc.all_doc_sections:
            if (section in self.doc_regions.keys()):
                updated_sections.append(
                    self.doc_regions[section].update(use_snippets))
            elif ((section not in self.omit_sections) and (not update_only)):
                temp_section = self.get_region(None, section)
                updated_sections.append(temp_section.update(use_snippets))

        return '\n'.join(updated_sections)

    class Region(object):
        """Represents a single documentation section"""

        header_match_object = re.compile(r'\s*//\s*:Doc\s*([a-zA-Z ]+?)\s*$')
        none_match_object = re.compile(r'//\s*None\s*$', re.MULTILINE)

        def __init__(self, documentation, region=None, section=None):
            self.documentation = documentation

            self.separators = get_default_separators()
            self.separator_width = max(len(self.separators['alpha']),
                                       len(self.separators['numeric']))
            self.body_prefix = '//' + get_documentation_indent()

            if region is not None:
                self.region = region
                self.current_content = self.view.substr(self.region)
                (self.header_region, self.body_region, self.current_header,
                    self.section, self.current_body) = self.split_region()

                if self.section is None:
                    if section is not None:
                        self.section = section
                    else:
                        raise DocRegionException(
                            'Doc Region Type could not be determined from ' +
                            'Region, and no Type specified.')
            elif section is not None:
                self.section = section
                self.region = None
                self.current_content = ''
                self.header_region = None
                self.body_region = None
                self.current_header = None
                self.current_body = None
            else:
                raise DocRegionException(
                    'A Doc Region must have a specified Region or Type to ' +
                    'be instantiated.')

        def __str__(self):
            return self.current_content

        @property
        def codeblock(self):
            return self.documentation.codeblock

        @property
        def view(self):
            return self.documentation.view

        @property
        def required(self):
            try:
                return self._required
            except AttributeError:
                self._required = (self.section in
                                  CodeBlockDoc.required_doc_sections)

        def split_region(self):
            """Breaks the Doc_region up into header and content regions"""

            body_region = self.region
            header_region = self.view.find(r"\s*//\s*:Doc\s*[a-zA-Z ]+",
                                           self.region.begin())
            if ((header_region is not None) and
                    body_region.contains(header_region)):
                body_region = sublime.Region(header_region.end() + 1,
                                             self.region.end())
                header_content = self.view.substr(header_region)
                type_match = CodeBlockDoc.Region.header_match_object.search(
                    header_content)

                yield header_region                  # Header Region
                yield body_region                    # Body Region
                yield header_content                 # Header Content
                if type_match is not None:
                    yield type_match.group(1)        # section
                else:
                    yield None
                yield self.view.substr(body_region)  # Body Content
            else:
                yield None                           # Header Region
                yield body_region                    # Body Region
                yield '//**Deprecated**'             # Header Content
                yield 'Deprecated'                   # section
                yield self.view.substr(body_region)  # Body Content

        def update(self, use_snippets):
            if (self.current_body is None) or (self.current_body is ''):
                updated_content = self.update_none_section(use_snippets)
            else:
                none_match = self.none_match_object.match(self.current_body)
                if none_match:
                    updated_content = self.update_none_section(use_snippets)
                else:
                    updated_content = '//:Doc {0}\n{1}'.format(
                        self.section, self.current_body)

            return updated_content

        def update_none_section(self, use_snippets):
            if use_snippets:
                if not self.required:
                    b = self.documentation.snippet_counter
                a = self.documentation.snippet_counter

                updated_content = '//:Doc {0}\n{1}${{{2}:None}}'.format(
                    self.section, self.body_prefix, a)

                if not self.required:
                    updated_content = '${{{0}:{1}}}'.format(b,
                                                            updated_content)
            else:
                updated_content = '//:Doc {0}\n{1}None'.format(
                    self.section, self.body_prefix)

            return updated_content

        def normalize_separators(self, l):
            for var, sep, content in l.values():
                if '.' in sep:
                    sep = '{{0:<{0}}}'.format(
                        self.separator_width).format(sep.strip())
                else:
                    sep = '{{0:^{0}}}'.format(
                        self.separator_width).format(sep.strip())
                if var.isnumeric():
                    self.separators['numeric'] = sep
                else:
                    self.separators['alpha'] = sep
                l[var] = (var, sep, content)

            return l

        def get_prefix_postfix(self, index, length):
            prefix = postfix = ''
            if index == 0:
                prefix = '{'
            else:
                prefix = '|'
            if index + 1 == length:
                postfix = '}'

            yield prefix
            yield postfix

        def get_separator(self, var):
            sep = self.separators['alpha']
            if (var.isnumeric()):
                sep = self.separators['numeric']

            return sep

    class ArgumentsRegion(Region):
        """
        CodeBlock Documentation Region for Arguments. Arguments require
        special parsing and updating.
        """

        def __init__(self, documentation, region=None, section=None):
            super(CodeBlockDoc.ArgumentsRegion, self).__init__(documentation,
                                                               region,
                                                               section)
            self.documented_args = dict()
            self.parse_doc()

        def parse_doc(self):
            if self.current_body is not None:
                # get initial indentation
                indent = self.body_prefix
                indent_match = re.search(
                    r"(//\s*)[|\{]?([A-Z]|\d{1,2})\s*[-=:.]\s*",
                    self.current_body)
                if indent_match:
                    indent = indent_match.group(1)

                reg_ex = (
                    indent +
                    r" ?[|\{]?([A-Z]|\d{1,2})(\s*[-=:.]\s*)([\s\S]*?)[|\}]?\n(?=" +
                    indent +
                    r" ?[|\{]?([A-Z]|\d{1,2})\s*[-=:.]|END)")

                # Extract the variable documentation
                documented_arg_info = re.findall(reg_ex,
                                                 self.current_body + '\nEND')
                for arg, sep, content, unused in documented_arg_info:
                    self.documented_args[arg] = (arg, sep, content)
                    if (len(sep) > self.separator_width):
                        self.separator_width = len(sep)

                self.documented_args = self.normalize_separators(
                    self.documented_args)

        def update(self, use_snippets):
            # Build each line of the new section
            updated_arg_text = list()
            arguments_in_use = self.codeblock.get_arguments_from_function()
            documented_args = dict(self.documented_args)

            if isinstance(arguments_in_use, str):
                try:
                    var, sep, content = documented_args[arguments_in_use]
                    del documented_args[var]
                except KeyError:
                    var = arguments_in_use
                    if var.isnumeric():
                        sep = self.separators['numeric']
                    else:
                        sep = self.separators['alpha']

                    if use_snippets:
                        content = '${0}'.format(
                            self.documentation.snippet_counter)

                updated_arg_text.append('{0}{1}{2}{3}'.format(
                    self.body_prefix, var, sep, content))
            else:
                updated_arg_text = self.format_list(arguments_in_use,
                                                    documented_args,
                                                    use_snippets)

            # Add the arguments that are no longer used
            for arg, sep, content in documented_args.values():
                updated_arg_text.append(
                    self.body_prefix + arg + sep +
                    '**Unused** ' + content)

            # Return the updated doc.
            if len(updated_arg_text) == 0:
                updated_content = super(
                    CodeBlockDoc.ArgumentsRegion, self).update(use_snippets)
            else:
                updated_content = '//:Doc {0}\n{1}'.format(
                    self.section, '\n'.join(updated_arg_text))

            return updated_content

        def format_list(self, l, documented_args, use_snippets,
                        indent=None):
            indent = indent if indent is not None else self.body_prefix
            updated_arg_text = list()
            length = len(l)
            # print(documented_args)

            for index, var in enumerate(l):
                sep = content = ''

                prefix, postfix = self.get_prefix_postfix(index, length)

                if isinstance(var, list):
                    try:
                        var, sep, content = documented_args[str(index)]
                        if ((index + 1 == length) and
                                (content[-1] == '}')) or (content[-1] == '|'):
                            content = content[:-1]
                        del documented_args[str(index)]

                    except KeyError:
                        sep = self.separators['numeric']
                        first_line = '{0}{1}{2}'.format(index, sep, prefix)
                        temp_indent = indent + ' ' * len(first_line)
                        sub_list = self.format_list(var,
                                                    documented_args,
                                                    use_snippets,
                                                    temp_indent)
                        print(sub_list)
                        var = str(index)

                        sub_list[0] = sub_list[0][len(temp_indent):]

                        content = '\n'.join(sub_list)

                else:
                    try:
                        var, sep, content = documented_args[var]
                        if ((index + 1 == length) and
                                (content[-1] == '}')) or (content[-1] == '|'):
                            content = content[:-1]
                        del documented_args[var]

                    except KeyError:
                        sep = self.get_separator(var)

                        if use_snippets:
                            content = '${0}'.format(
                                self.documentation.snippet_counter)

                updated_line = indent + prefix + var + sep + content + postfix
                updated_arg_text.append(updated_line)

            return updated_arg_text

    class LocalVarsRegion(Region):
        """
        CodeBlock Documentation Region for Local Variables. Local Variables
        require special parsing and updating.
        """

        LocalVarParser = re.compile(
            r"//\s*([A-Z])(\s*[-=:]\s*)([\s\S]*?)\n(?=//\s*[A-Z]\s*[-=:]|END)")

        def __init__(self, documentation, region=None, section=None):
            super(CodeBlockDoc.LocalVarsRegion, self).__init__(documentation,
                                                               region,
                                                               section)
            self.documented_vars = dict()
            self.parse_doc()

        def parse_doc(self):
            if self.current_body is not None:
                # Extract the variable documentation
                documented_var_info = self.LocalVarParser.findall(
                    self.current_body + '\nEND')
                for var, sep, content in documented_var_info:
                    self.documented_vars[var] = (var, sep, content)
                    if (len(sep) > self.separator_width):
                        self.separator_width = len(sep)

            # normalize separators
            self.documented_vars = self.normalize_separators(
                self.documented_vars)

        def update(self, use_snippets):
            documented_vars = dict(self.documented_vars)
            variables_in_use = self.codeblock.get_variables_from_function().keys()
            arguments_in_use = self.codeblock.get_arguments_from_function(
                return_flat_list=True)
            updated_var_text = list()
            separator = self.separators['alpha']

            # Merge the documented vars with the function vars
            for var in variables_in_use:
                if var not in documented_vars.keys():
                    documented_vars[var] = (var, separator, '')

            # Build each line of the new section
            for var, sep, content in sorted(documented_vars.values()):
                if ((var in arguments_in_use) and
                        (content.lower() != 'see arguments')):
                    if use_snippets and (content != ''):
                        content = '${{{0}:{1}}}'.format(
                            self.documentation.snippet_counter, ': ' + content)
                    content = 'See arguments' + content

                if use_snippets and (content == ''):
                    content = '${0}'.format(self.documentation.snippet_counter)
                elif var not in variables_in_use:
                    content = '**Unused** ' + content
                    if use_snippets:
                        content = '${{{0}:{1}}}'.format(
                            self.documentation.snippet_counter, content)
                updated_var_text.append(
                    self.body_prefix + var + sep + content)

            # Store the regenerated documentation
            self.updated_header = '//:Doc {0}'.format(self.section)
            if len(updated_var_text) == 0:
                updated_content = super(
                    CodeBlockDoc.LocalVarsRegion, self).update(use_snippets)
            else:
                updated_content = '//:Doc {0}\n{1}'.format(
                    self.section, '\n'.join(updated_var_text))

            return updated_content

    class DataStrucRegion(Region):
        """
        CodeBlock Documentation Region for Data Structures. Data Structures
        require special parsing and updating.
        """

        DataStrucParser = re.compile(
            r"//\s*((L|U)\(\d+\))(\s*[-=:]\s*)([\s\S]*?)\n" +
            r"(?=//\s*(L|U)\(\d+\)\s*[-=:]|END)")

        def __init__(self, documentation, region=None, section=None):
            super(CodeBlockDoc.DataStrucRegion, self).__init__(documentation,
                                                               region,
                                                               section)
            self.documented_sets = dict()
            self.parse_doc()

        def parse_doc(self):
            if self.current_body is not None:
                # Extract the set documentation
                documented_set_info = self.DataStrucParser.findall(
                    self.current_body + '\nEND')
                for set, type, sep, content, unused in documented_set_info:
                    self.documented_sets[set] = (set, sep, content)
                    if len(sep) > self.separator_width:
                        self.separator_width = len(sep)

            # normalize separators
            self.documented_sets = self.normalize_separators(
                self.documented_sets)

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
                documented_sets[listset] = (type, number, listset,
                                            separator, content)

            # Build each line of the new section
            for unused, unused, listset, sep, content in sorted(
                    documented_sets.values()):
                if use_snippets and (content == ''):
                    content = '${0}'.format(self.documentation.snippet_counter)
                elif listset not in sets_in_use:
                    content = '**Unused** ' + content
                    if use_snippets:
                        content = '${{{0}:{1}}}'.format(
                            self.documentation.snippet_counter, content)

                updated_set_text.append(
                    self.body_prefix + listset + sep + content)

            self.updated_header = '//:Doc ' + self.section
            if len(updated_set_text) == 0:
                updated_content = super(
                    CodeBlockDoc.DataStrucRegion, self).update(use_snippets)
            else:
                updated_content = '//:Doc {0}\n{1}'.format(
                    self.section, '\n'.join(updated_set_text))

            return updated_content

    class UnitTestRegion(Region):
        """
        CodeBlock Documentation Region for Unit Tests. Unit Tests
        require special parsing.
        """

        UnitTestParser = re.compile(
            r"(// *:Test *([\s\S]*?))\n(?=// *:Test *|END)")

        def __init__(self, documentation, region=None, section=None):
            super(CodeBlockDoc.UnitTestRegion, self).__init__(documentation,
                                                              region,
                                                              section)
            self.unit_tests = []
            self.parse_doc()

        def parse_doc(self):
            if (self.current_body is not None):
                # Extract the set documentation
                unit_tests = self.UnitTestParser.findall(
                    self.current_body + '\nEND')
                for test, unused in unit_tests:
                    self.unit_tests.append(test)


class InvalidCodeBlockError(Exception):
    """Raised when trying to create a codeblock when not in a codeblock."""

    def __init__(self, view, point):
        super(InvalidCodeBlockError, self).__init__()
        self.view = view
        self.filename = self.view.file_name()
        if self.filename is None:
            self.filename = self.view.name()
        self.point = point
        self.row, self.col = self.view.rowcol(self.point)
        self.row += 1
        self.col += 1
        self.line = self.view.line(point)
        self.line_text = self.view.substr(self.line)
        self.description = ('Point %s is not within a valid codeblock.\n' +
                            'File: %s\n' +
                            '%s, %s: %s') % (self.point,
                                             self.filename,
                                             self.row,
                                             self.col,
                                             self.line_text)

    def __str__(self):
        return self.description


class DocRegionException(Exception):
    """
    Exception that is raised if you try to create an inappropriate Doc Region
    """

    def __init__(self, description):
        Exception.__init__(self)
        self.description = description

    def __str__(self):
        return repr(self)
