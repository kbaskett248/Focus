import json
import re

import sublime

from .general import extract_entity, string_match, read_file


def scope_from_view(view):
    """Returns the primary source scope for a view."""
    try:
        scope = view.scope_name(view.sel()[0].begin())
    except IndexError:
        scope = view.scope_name(0)

    return scope.split(' ')[0]


def load_settings(file_name):
    s = ''
    for line in read_file(file_name):
        if line.strip().startswith('//'):
            continue
        s += (line + '\n')

    return json.loads(s)


def split_member_region(view, codeblock_region):
    """
    Splits the codeblock region into header region, documentation region
    and code region.
    """
    start = codeblock_region.begin()
    if view.score_selector(start, 'meta.subroutine.fs, meta.list.fs') <= 0:
        yield None
        yield None
        yield None
        yield None
    else:
        header_region = view.line(start)
        yield header_region

        doc_start = header_region.end() + 1
        if view.score_selector(doc_start, 'comment') > 0:
            doc_region = view.extract_scope(doc_start)
            doc_region = sublime.Region(doc_region.begin(), doc_region.end()-1)
        else:
            doc_region = sublime.Region(doc_start, doc_start)
        yield doc_region

        if doc_region.empty():
            var_declaration_start = doc_region.end()
        else:
            var_declaration_start = doc_region.end()+1
        if view.score_selector(var_declaration_start,
                'meta.variable.other.local.named.declaration') > 0:
            var_declaration = view.line(var_declaration_start)
        else:
            var_declaration = sublime.Region(var_declaration_start,
                                             var_declaration_start)
        yield var_declaration

        yield sublime.Region(var_declaration.end()+1, codeblock_region.end())


FOCUS_FUNCTION_MATCHER = re.compile(r"(?<!\@)\@[A-Za-z]{3,}[A-Za-z0-9]*"
                                    r"\(([^)]+|\([^)]*\))*\)")

FOCUS_FUNCTION_SPLITTER = re.compile(r"(\@[A-Za-z0-9]+)\((.*)\)")

FS_FUNCTION_MATCHER = re.compile(r"(?<!\@)\@([A-Z][A-Za-z]|[A-Za-z]\d+)")

RT_TOOL_MATCHER = re.compile(r"(?<!\@)\@([a-wz][A-Za-z])")

OPERATOR_MATCHER = re.compile(r"@?\~?[\!\#\$\%\&\*\+\-\.\/\:\<\=\>\?\|\\]")

ALIAS_MATCHER = re.compile(r"\@\@[^(]+\(([^)]+|\([^)]*\))*\)")

SUBROUTINE_MATCHER = re.compile(r":Code.+\n[\w\W\n]+?;(?=\n(\n|:L|:C|:E|#))")

INCLUDE_FILE_MATCHER = re.compile(r"[ \t]*File[ \t]+([\w._-]+)")

EXTERNAL_PAGESET_MATCHER = re.compile(r"[ \t]*Source[ \t]+([\w._-]+)")

KEYWORD_MATCHER = re.compile(
    r"^[ \t]*(:[A-Z][A-Za-z0-9]+)[ \t]([ \t]*(.+\S))?")

ATTRIBUTE_MATCHER = re.compile(
    r"^[ \t]*([A-Z][A-Za-z0-9]+)[ \t]([ \t]*(.+\S))?")

KEYWORD_ATTRIBUTE_MATCHER = re.compile(
    r"^[ \t]*(:?[A-Z][A-Za-z0-9]+)[ \t]([ \t]*(.+\S))?")

FOCUS_FILE_MATCHER = re.compile(
    r"([A-Z][a-z]{1,2}[A-Z0-9][A-Za-z0-9.]+?\.[A-Z])(\.focus)?\b")


def extract_focus_function(string, point, base_point=0):
    """
    Extracts the text and region of the Focus function in string containing
    point.

    Keyword arguments:
    string - A string containing a focus function
    point - An int representing a location in the string or a tuple
            representing a selection. The point may be relative to an
            optional base point.
    base_point - If specified, this is subtracted from point before checking
                 and added to the resulting location before it is returned.

    """
    return extract_entity(FOCUS_FUNCTION_MATCHER, string, point, base_point)


def split_focus_function(string, base_point=0):
    """Splits a focus function string and region into it's name and arguments

    Keyword arguments:

    """
    name_span, name = string_match(string, FOCUS_FUNCTION_SPLITTER, 1,
                                   base_point)
    arg_span, args = string_match(string, FOCUS_FUNCTION_SPLITTER, 2,
                                  base_point)

    return ((name_span, name), (arg_span, args))


def extract_fs_function(string, point, base_point=0):
    """
    Extracts the text and region of the FS function in string containing
    point.

    Keyword arguments:
    string - A string containing a FS function
    point - An int representing a location in the string or a tuple
            representing a selection. The point may be relative to an
            optional base point.
    base_point - If specified, this is subtracted from point before checking
                 and added to the resulting location before it is returned.

    """
    return extract_entity(FS_FUNCTION_MATCHER, string, point, base_point)

def extract_rt_tool(string, point, base_point=0):
    """
    Extracts the text and region of the RT Tool call in string containing
    point.

    Keyword arguments:
    string - A string containing an RT Tool call
    point - An int representing a location in the string or a tuple
            representing a selection. The point may be relative to an
            optional base point.
    base_point - If specified, this is subtracted from point before checking
                 and added to the resulting location before it is returned.

    """
    return extract_entity(RT_TOOL_MATCHER, string, point, base_point)


def extract_operator(string, point, base_point=0):
    """
    Extracts the text and region of the FS function in string containing
    point.

    Keyword arguments:
    string - A string containing an FS operator
    point - An int representing a location in the string or a tuple
            representing a selection. The point may be relative to an
            optional base point.
    base_point - If specified, this is subtracted from point before checking
                 and added to the resulting location before it is returned.

    """
    return extract_entity(OPERATOR_MATCHER, string, point, base_point)


def extract_alias(string, point, base_point=0):
    """
    Extracts the text and region of the Alias in string containing point.

    Keyword arguments:
    string - A string containing an Alias
    point - An int representing a location in the string or a tuple
            representing a selection. The point may be relative to an
            optional base point.
    base_point - If specified, this is subtracted from point before checking
                 and added to the resulting location before it is returned.

    """
    return extract_entity(ALIAS_MATCHER, string, point, base_point)


def extract_subroutine(string, point, base_point=0):
    """
    Extracts the text and region of the Subroutine in string containing point.

    Keyword arguments:
    string - A string containing an Alias
    point - An int representing a location in the string or a tuple
            representing a selection. The point may be relative to an
            optional base point.
    base_point - If specified, this is subtracted from point before checking
                 and added to the resulting location before it is returned.

    """
    string += ":END"
    return extract_entity(ALIAS_MATCHER, string, point, base_point)


def extract_include_file(string, point, base_point=0):
    """
    Extracts the text and region of the Include File in string containing
    point.

    Keyword arguments:
    string - A string containing an Include File
    point - An int representing a location in the string or a tuple
            representing a selection. The point may be relative to an
            optional base point.
    base_point - If specified, this is subtracted from point before checking
                 and added to the resulting location before it is returned.

    """
    return extract_entity(INCLUDE_FILE_MATCHER, string, point, base_point,
                          match_group=1)


def extract_external_pageset(string, point, base_point=0):
    """
    Extracts the text and region of the External Pageset in string containing
    point.

    Keyword arguments:
    string - A string containing an External Pageset
    point - An int representing a location in the string or a tuple
            representing a selection. The point may be relative to an
            optional base point.
    base_point - If specified, this is subtracted from point before checking
                 and added to the resulting location before it is returned.

    """
    return extract_entity(EXTERNAL_PAGESET_MATCHER, string, point, base_point,
                          match_group=1)


def extract_keyword(string, point, base_point=0):
    """
    Extracts the text and region of the keyword in string containing
    point.

    Keyword arguments:
    string - A string containing an keyword
    point - An int representing a location in the string or a tuple
            representing a selection. The point may be relative to an
            optional base point.
    base_point - If specified, this is subtracted from point before checking
                 and added to the resulting location before it is returned.

    """
    return extract_entity(KEYWORD_MATCHER, string, point, base_point,
                          match_group=1)


def extract_keyword_value(string, point, base_point=0):
    """
    Extracts the text and region of the keyword value in string containing
    point.

    Keyword arguments:
    string - A string containing an keyword value
    point - An int representing a location in the string or a tuple
            representing a selection. The point may be relative to an
            optional base point.
    base_point - If specified, this is subtracted from point before checking
                 and added to the resulting location before it is returned.

    """
    return extract_entity(KEYWORD_MATCHER, string, point, base_point,
                          match_group=3)


def extract_attribute(string, point, base_point=0):
    """
    Extracts the text and region of the attribute in string containing
    point.

    Keyword arguments:
    string - A string containing an attribute
    point - An int representing a location in the string or a tuple
            representing a selection. The point may be relative to an
            optional base point.
    base_point - If specified, this is subtracted from point before checking
                 and added to the resulting location before it is returned.

    """
    return extract_entity(ATTRIBUTE_MATCHER, string, point, base_point,
                          match_group=1)


def extract_attribute_value(string, point, base_point=0):
    """
    Extracts the text and region of the attribute value in string containing
    point.

    Keyword arguments:
    string - A string containing an attribute value
    point - An int representing a location in the string or a tuple
            representing a selection. The point may be relative to an
            optional base point.
    base_point - If specified, this is subtracted from point before checking
                 and added to the resulting location before it is returned.

    """
    return extract_entity(ATTRIBUTE_MATCHER, string, point, base_point,
                          match_group=3)


def extract_focus_file(string, point, base_point=0):
    """
    Extracts the text and region of the focus file in string containing point.

    Keyword arguments:
    string - A string containing a Focus file name.
    point - An int representing a location in the string or a tuple
            representing a selection. The point may be relative to an
            optional base point.
    base_point - If specified, this is subtracted from point before checking
                 and added to the resulting location before it is returned.

    """
    return extract_entity(FOCUS_FILE_MATCHER, string, point, base_point,
                          match_group=1)


ALIAS_NAME_MATCHER = re.compile(r"(\@\@)?([^(]+)\(")


def strip_alias(alias):
    name = ALIAS_NAME_MATCHER.match(alias)
    if name is None:
        return None
    else:
        return name.group(2)


def display_in_output_panel(window, panel_id, file_name=None, text=''):
    output_panel = window.create_output_panel(panel_id)
    if file_name is not None:
        text = '\n'.join(read_file(file_name, False))

    output_panel.run_command('append', {'characters': text, 'force': True})
    window.run_command('show_panel', {'panel': 'output.' + panel_id})

    return output_panel


def display_in_new_view(window, file_name=None, text=''):
    view = window.new_file()
    if file_name is not None:
        text = '\n'.join(read_file(file_name, False))

    view.set_scratch(True)
    view.run_command('append', {'characters': text, 'force': True})

    return view
