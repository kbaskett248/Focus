import abc
import functools
import re
import logging

from ..tools.general import string_match, string_search
from ..tools.sublime import (
    extract_focus_function,
    extract_fs_function,
    extract_rt_tool,
    extract_operator,
    extract_alias,
    extract_include_file,
    extract_external_pageset,
    extract_keyword,
    extract_keyword_value,
    extract_attribute,
    extract_attribute_value,
    KEYWORD_ATTRIBUTE_MATCHER,
    strip_alias
)


logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')


@functools.lru_cache(maxsize=64)
def get_object_search_reg_exes(type_, name):
    def format_reg_ex(k, v):
        if not isinstance(k, str):
            k = '|'.join(k)
        return r"^[ \t]*:({keyword})[ \t]+({value})[ \t]*$".format(
            keyword=k, value=v)

    parts = name.split('.')
    reg_exes = []
    reg_exes.append(format_reg_ex('Object', parts[0]))
    length = len(parts)

    if length == 1:
        pass
    elif (type_ == 'IndexKey') and (length == 3):
        reg_exes.append(format_reg_ex('Index', parts[1]))
        reg_exes.append(format_reg_ex('IndexKey', parts[2]))
    elif type_ == 'Element':
        reg_exes.append(format_reg_ex(('Key', 'Field'), parts[1]))
    else:
        reg_exes.append(format_reg_ex(type_, parts[1]))

    return reg_exes


Object_Load_Reg_Exes = {}
ALL_OBJECT_KEYWORDS = ('Object', 'LongLock', 'Mutex', 'File', 'Record', 'Key',
                       'Field', 'Index', 'IndexKey')


def get_object_load_reg_ex(type_):
    def format_reg_ex(*args):
        keys = '|'.join(args)
        return (r"^[ \t]*:(?P<keyword>{keyword})[ \t]+"
                r"(?P<entity>.+?)[ \t]*$").format(keyword=keys)

    try:
        return Object_Load_Reg_Exes[type_]
    except KeyError:
        pass

    if type_ == 'All':
        keys = ALL_OBJECT_KEYWORDS
    else:
        keys = ['Object']

        if type_ == 'IndexKey':
            keys.append('Index')

        if type_ == 'Element':
            keys.append('Key')
            keys.append('Field')
        else:
            keys.append(type_)

    reg_ex = re.compile(format_reg_ex(*keys), re.MULTILINE)
    Object_Load_Reg_Exes[type_] = reg_ex
    return reg_ex


class FSCompatibility(metaclass=abc.ABCMeta):
    """
    Contains common functions that can be used between both MTFSView and
    MTFSFile classes.

    """

    @abc.abstractmethod
    def get_contents(self):
        """
        Returns the contents of the entire file or view.
        """
        pass

    @abc.abstractmethod
    def get_line(self, point):
        """
        Returns a tuple of the span of the line or lines at the specified point
        and the contents of those lines.

        Keyword arguments:
        point - Either an int representing a point in the file or a tuple
            representing a selection in the file.
        """
        pass

    @abc.abstractmethod
    def get_lines_iterator(self, skip_blanks=False):
        """
        Creates an iterator that returns the lines of a file or view.
        """
        pass

    @abc.abstractmethod
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
        pass

    def find_member(self, name):
        reg_ex = r"^ *:(Code|List) +({name})".format(name=name)
        return string_search(self.get_contents(),
                             reg_ex,
                             match_group=2,
                             flags=re.MULTILINE)[0]

    MEMBER_REGION_REGEX = re.compile(r"(#[A-Za-z]+|:[A-Za-z]+) *(.+)?$")

    def get_member_region(self, point):
        if isinstance(point, tuple):
            point = point[0]
        line_span = self.get_line(point)[0]
        line_span = (line_span[1] + 1, line_span[1] + 1)

        start_point = None
        for line in self.get_lines_from_iterator(point, reverse=True):
            line_span = (line_span[0] - len(line) - 1, line_span[0] - 1)
            match = string_match(line, self.MEMBER_REGION_REGEX,
                                 base_point=line_span[0])
            if match[0] and (match[1] in MAGIC_KEYWORDS):
                start_point = line_span[0]
                break
        if not start_point or (start_point > point):
            return None

        end_point = None
        line_stack = []
        for line in self.get_lines_from_iterator(line_span[1] + 1):
            line_span = (line_span[1] + 1, line_span[1] + len(line) + 1)
            if line == '':
                continue

            match = string_match(line, self.MEMBER_REGION_REGEX,
                                 base_point=line_span[0])
            if match[0]:
                prev_line = line_stack.pop()
                end_point = prev_line[0][1]
                break
            line_stack.append((line_span, line))
        else:
            end_point = line_span[1]

        if end_point >= point:
            return (start_point, end_point)
        else:
            return None

    def _extract_entity(self, extract_func, point):
        if isinstance(point, tuple):
            if point[0] == point[1]:
                point = point[0]
        span, line_string = self.get_line(point)
        if span is None:
            return (None, None)

        return extract_func(line_string, point, base_point=span[0])

    def extract_fs_function(self, point):
        return self._extract_entity(extract_fs_function, point)

    def extract_rt_tool(self, point):
        return self._extract_entity(extract_rt_tool, point)

    def extract_operator(self, point):
        return self._extract_entity(extract_operator, point)

    def get_entities(self, reg_ex, match_group='entity', translator=None,
                     flags=0, for_completions=False):
        """
        Finds all of the instances of the given reg_ex and returns the text
        of them in a set.

        """
        entities = set()
        if translator:
            contents = '\n'.join(
                [a[1] for a in self.get_translator_sections(translator)])
        else:
            contents = self.get_contents()

        if isinstance(reg_ex, str):
            match_iter = re.finditer(reg_ex, contents, flags)
        elif hasattr(reg_ex, 'finditer'):
            match_iter = reg_ex.finditer(contents)
        else:
            return entities

        for m in match_iter:
            e = m.group(match_group)
            if e:
                if for_completions:
                    e = (e,)
                entities.add(e)

        return entities

    DEFINED_SUBROUTINE_LOADER = re.compile(
        r"^[ \t]*:Code[ \t]+(?P<entity>.+?)[ \t]*$", re.MULTILINE)

    def get_defined_subroutines(self, for_completions=False):
        return self.get_entities(self.DEFINED_SUBROUTINE_LOADER,
                                 for_completions=for_completions)

    DEFINED_LIST_LOADER = re.compile(
        r"^[ \t]*:List[ \t]+(?P<entity>.+?)[ \t]*$", re.MULTILINE)

    def get_defined_lists(self, for_completions=False):
        return self.get_entities(self.DEFINED_LIST_LOADER,
                                 for_completions=for_completions)

    def get_multi_entities(self, reg_ex, match_group='entity', translator=None,
                           flags=0, for_completions=False):
        """
        Finds all of the instances of the given reg_ex and returns the text
        of them in a set.

        """
        entities = dict()
        if translator:
            contents = '\n'.join(
                [a[1] for a in self.get_translator_sections(translator)])
        else:
            contents = self.get_contents()

        if isinstance(reg_ex, str):
            match_iter = re.finditer(reg_ex, contents, flags)
        elif hasattr(reg_ex, 'finditer'):
            match_iter = reg_ex.finditer(contents)
        else:
            return entities

        for m in match_iter:
            t = m.group('type')
            e = m.group(match_group)
            if e and t:
                if for_completions:
                    e = (e,)
                try:
                    entities[t].add(e)
                except KeyError:
                    entities[t] = set()
                    entities[t].add(e)

        return entities


MAGIC_KEYWORDS = (':Code', ':List', ':EntryPoint', ':Icon')


class FocusCompatibility(FSCompatibility):
    """
    Contains common functions that can be used between both MTFocusView and
    MTFocusFile classes.

    """

    def extract_focus_function(self, point):
        return self._extract_entity(extract_focus_function, point)

    def extract_alias(self, point):
        return self._extract_entity(extract_alias, point)

    def extract_include_file(self, point):
        return self._extract_entity(extract_include_file, point)

    def extract_external_pageset(self, point):
        return self._extract_entity(extract_external_pageset, point)

    def extract_keyword(self, point):
        return self._extract_entity(extract_keyword, point)

    def extract_keyword_value(self, point):
        return self._extract_entity(extract_keyword_value, point)

    def extract_attribute(self, point):
        return self._extract_entity(extract_attribute, point)

    def extract_attribute_value(self, point):
        return self._extract_entity(extract_attribute_value, point)

    def get_translator_sections_iter(self, translator):
        if translator.startswith('#'):
            translator = translator[1:]

        contents = self.get_contents() + "\n#END"

        regex = (r"^((//[ -=+*_]+\n)?#" +
                 translator +
                 r"\n.+?)(//[ -=+*_]+\n)?^#[A-Za-z]+$")

        for m in re.finditer(regex, contents, re.MULTILINE | re.DOTALL):
            yield (m.span(1), m.group(1))

    def get_translator_sections(self, translator):
        return list(self.get_translator_sections_iter(translator))

    def get_keyword_and_value(self, point):
        if isinstance(point, tuple):
            if point[0] == point[1]:
                point = point[0]
        span, line_string = self.get_line(point)
        if span is None:
            return ((None, None), (None, None))

        return string_match(line_string, KEYWORD_ATTRIBUTE_MATCHER,
                            base_point=span[0], match_group=(1, 2))

    def find_alias_definition(self, name):
        name = strip_alias(name)
        if name is None:
            return None

        reg_ex = (r"^([ \t]*:|:EntryPoint[ \t]+(?P<subroutine>\S+)\s+)"
                  r"Alias[ \t]+(?P<alias>{name})").format(name=name)

        match = re.search(reg_ex, self.get_contents(), re.MULTILINE)
        if match is None:
            return None

        subroutine = match.group("subroutine")
        if (subroutine is None) or (subroutine == ''):
            return match.span('alias')
        else:
            return self.find_member(subroutine)

    def find_local_definition(self, name):
        if name is None:
            return None

        reg_ex = r"^[ \t]*:Name[ \t]+(?P<local>{name})".format(name=name)

        for t_span, t_string in self.get_translator_sections('Locals'):
            span = string_search(t_string,
                                 reg_ex,
                                 match_group='local',
                                 base_point=t_span[0],
                                 flags=re.MULTILINE)[0]
            if span is not None:
                return span

        return None

    def find_screen_component(self, component_type, name):
        if (name is None) or (component_type is None):
            return None

        if component_type[0] == ':':
            component_type = component_type[1:]

        reg_ex = r"^[ \t]*:{component_type}[ \t]+({name})".format(
            component_type=component_type, name=name)

        for t_span, t_string in self.get_translator_sections(
                'ScreenComponent'):
            span = string_search(t_string,
                                 reg_ex,
                                 match_group=1,
                                 base_point=t_span[0],
                                 flags=re.MULTILINE)[0]
            if span is not None:
                return span

        return None

    def find_container_region(self, name):
        if name is None:
            return None

        reg_ex = r"^[ \t]*:Region[ \t]+({name})".format(name=name)

        for t_span, t_string in self.get_translator_sections('ScreenPage'):
            span = string_search(t_string,
                                 reg_ex,
                                 match_group=1,
                                 base_point=t_span[0],
                                 flags=re.MULTILINE)[0]
            if span is not None:
                return span

        return None

    def find_object(self, type_, name):
        """
        Return the span where the given object entity definition is found in
        the view or file.

        Keyword Arguments:
        type_ - The type of entity you are looking for; e.g., Object, Record,
            Field, IndexKey, etc.
        name - The object entity; e.g., Object.Field

        """
        if (type_ is None) or (name is None):
            return None

        reg_exes = get_object_search_reg_exes(type_, name)
        if not reg_exes:
            return None

        for t_span, t_str in self.get_translator_sections_iter('DataDef'):
            for reg_ex in reg_exes:
                # Try to find the given reg_ex in the text remaining in the
                # translator.
                span = string_search(t_str,
                                     reg_ex,
                                     match_group=2,
                                     base_point=t_span[0],
                                     flags=re.MULTILINE)[0]

                # If it isn't found, the definition isn't in this translator
                # section, so fall out.
                if span is None:
                    break
                # Otherwise, we found this, so modify the string and the span
                # and continue searching on the modified string for the next
                # reg_ex
                else:
                    t_str = t_str[(span[1] - t_span[0]):]
                    t_span = (span[1], t_span[1])
            else:
                # If we made it all the way through the reg_ex loop without
                # encountering a break, we found the final reg_ex, so return
                # the span. Otherwise, search the next translator section.
                return span

        return None

    DEFINED_ALIAS_LOADER = re.compile(
        r"^([ \t]*:|:EntryPoint[ \t]+\S+\s+)Alias[ \t]+(?P<entity>\S+)",
        re.MULTILINE)

    def get_defined_aliases(self, for_completions=False):
        return self.get_entities(self.DEFINED_ALIAS_LOADER,
                                 for_completions=for_completions)

    USED_LOCAL_LOADER = re.compile(
        r"(//.+|@(Get|Put)Local\((?P<entity>\S+?)\))")
    DEFINED_LOCAL_LOADER = re.compile(
        r"^[ \t]*:Name[ \t]+(?P<entity>.+?)[ \t]*$", re.MULTILINE)

    def get_used_locals(self, for_completions=False):
        return self.get_entities(self.USED_LOCAL_LOADER,
                                 for_completions=for_completions)

    def get_defined_locals(self, for_completions=False):
        return self.get_entities(self.DEFINED_SUBROUTINE_LOADER,
                                 translator='Local',
                                 for_completions=for_completions)

    def get_defined_objects(self, type_='All', for_completions=False):
        object_dict = {}

        def add_to_dict(keyword, value):
            try:
                object_dict[keyword].add(value)
            except KeyError:
                object_dict[keyword] = set()
                object_dict[keyword].add(value)

            if keyword in ('Key', 'Field'):
                add_to_dict('Element', value)

        compiled_reg_ex = get_object_load_reg_ex(type_)
        object_ = ''
        index = ''

        for t_span, t_string in self.get_translator_sections('DataDef'):
            for m in compiled_reg_ex.finditer(t_string):
                keyword = m.group('keyword')
                value = m.group('entity')

                if keyword == 'Object':
                    object_ = value
                elif keyword == 'IndexKey':
                    value = index + '.' + value
                else:
                    value = object_ + '.' + value
                    if keyword == 'Index':
                        index = value

                if for_completions:
                    value = (value,)

                add_to_dict(keyword, value)

        return object_dict

    DEFINED_SCREEN_COMPONENT_LOADER = re.compile(
        r"^[ \t]*:(?P<type>ElementSet|Index|Display)[ \t]+" +
        r"(?P<entity>.+?)[ \t]*$", re.MULTILINE)

    def get_defined_screen_components(self, for_completions=False):
        return self.get_multi_entities(
            self.DEFINED_SCREEN_COMPONENT_LOADER,
            translator='ScreenComponent', for_completions=for_completions)

    DEFINED_BODY_BUTTON_LOADER = re.compile(
        r"^[ \t]*:BodyButtons[ \t]+" +
        r"(?P<entity>.+?)[ \t]*$", re.MULTILINE)

    def get_defined_body_buttons(self, for_completions=False):
        return self.get_entities(self.DEFINED_BODY_BUTTON_LOADER,
                                 translator='BodyButtons',
                                 for_completions=for_completions)

    def build_translator_tree(self, point, trim_containers=False):
        """Builds a list of (Translator option, Value)"""
        translator_tree = list()
        found_container = False
        iterator = self.get_lines_from_iterator(point, reverse=True)
        line = next(iterator)

        pattern = r'^(\s*)((:|#)[A-Za-z0-9]*|[A-Za-z0-9]+)(\s*)(.*)$'
        match = re.match(pattern, line)

        if match is None:
            translator_tree.append(('', ''))
            pattern = r"^(\s*)((:|#)[A-Za-z0-9]*)(\s*)(.*)$"

        for line in iterator:
            if match is not None:
                # Only include the last container block since they can be
                # nested
                if (trim_containers and (match.group(2) == ':Container')):
                    if not found_container:
                        translator_tree.append(
                            (match.group(2), match.group(5)))
                        found_container = True
                else:
                    if ((match.group(4) == '') and (match.group(5) != '')):
                        translator_tree.append(
                            ('', match.group(2) + match.group(5)))
                    else:
                        translator_tree.append(
                            (match.group(2), match.group(5)))
                        if match.group(2) in MAGIC_KEYWORDS:
                            translator_tree.append(('#Magic', ''))
                            break

                # If we found the translator, stop. Otherwise, update the
                # pattern
                if match.group(3) == '#':
                    break
                else:
                    pattern = r"^(\s{0,%s})((:|#)[A-Za-z0-9]*)(\s*)(.*)$" % (
                        len(match.group(1)) - 2)

            match = re.match(pattern, line)

        translator_tree.reverse()
        logger.debug('translator_tree = %s', translator_tree)
        return translator_tree
