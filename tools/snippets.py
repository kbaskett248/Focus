from collections import OrderedDict
import re

import sublime


def insert_compound_snippet(view, edit, user_selection, region_snippets):
    region_snippets = update_tab_stops(region_snippets)
    super_snippet = build_super_snippet(view,
                                        user_selection,
                                        region_snippets)
    insert_and_correct_snippet(view, edit, user_selection, super_snippet)


def make_string_replacements(rep_string, replacements):
    for span, rep in replacements.items():
        rep_string = rep_string[:span[0]] + rep + rep_string[span[1]:]
    return rep_string


def update_tab_stops(region_snippets):
    """
    Replaces the tab stops in multiple snippets so they can be combined into
    a super snippet.
    """
    region_snippets.sort()
    updated_region_snippets = []
    tab_stop_matcher = re.compile(r"\$((\d+)|{(\d+):([^}]*)})")

    tab_stop_counter = 1

    for region, snippet in region_snippets:
        # Maps the span to a tuple of (tab stop, text if any)
        tab_stop_originals = dict()
        # List of indexes in the snippet
        indexes = []

        for tsm in tab_stop_matcher.finditer(snippet):
            span = tsm.span()
            if (tsm.group(2) is not None):
                original = (tsm.group(2), None)
            else:
                original = (tsm.group(3), tsm.group(4))
            tab_stop_originals[span] = original
            indexes.append(original[0])

        # Update tab stops
        # Maps an original tab stop to an updated one
        tab_stop_indexes = OrderedDict()
        for k in sorted(indexes):
            tab_stop_indexes[k] = str(tab_stop_counter)
            tab_stop_counter += 1

        # Replace tab stops in snippets
        current_replacements = dict()
        for span, original in tab_stop_originals.items():
            stop = tab_stop_indexes[original[0]]
            text = original[1]
            replacement_text = '$' + stop
            if text is not None:
                replacement_text = '${%s:%s}' % (stop, text)
            current_replacements[span] = replacement_text

        current_replacements = OrderedDict(
            sorted(current_replacements.items(),
                   key=lambda t: t[0],
                   reverse=True))

        current_snippet = make_string_replacements(snippet,
                                                   current_replacements)

        updated_region_snippets.append((region, current_snippet))

    return updated_region_snippets


def build_super_snippet(view, user_selection, region_snippets):
    """
    Builds a super snippet containing all the user's selections replaced with
    the given snippets and the text in between.
    """
    initial_selection_begin = user_selection[0].begin()
    selections = list(user_selection)
    selections.sort()

    # An OrderedDict mapping a region in the overall selection to the inserted
    # snippet
    replacements = OrderedDict()
    for region, snippet in sorted(region_snippets, reverse=True):
        replacements[(region.begin() - initial_selection_begin,
                      region.end() - initial_selection_begin)] = snippet

    big_region = selections[0].cover(selections[-1])
    big_region_content = view.substr(big_region)

    return make_string_replacements(big_region_content, replacements)


def insert_and_correct_snippet(view, edit, user_selection, snippet):
    """
    Inserts the snippet, then corrects the indentation so that it mirrors the
    original contents.
    """
    selections = list(user_selection)
    selections.sort()
    big_region = selections[0].cover(selections[-1])

    user_selection.clear()
    user_selection.add(big_region)

    view.run_command('insert_snippet', {'contents': snippet})

    snippet_lines = len(snippet.split('\n'))

    line = view.line(big_region.begin())
    first_line_content = view.substr(line)
    first_line_indent_match = re.match(r'\s+', first_line_content)
    if (first_line_indent_match is not None):
        first_line_indent = first_line_indent_match.group()
        first_line_indent_length = len(first_line_indent)
        for i in range(snippet_lines - 1):
            line = view.line(line.end() + 1)
            repl_reg = sublime.Region(line.begin(), line.begin() +
                                      first_line_indent_length)
            view.replace(edit, repl_reg, "")
            line = view.line(line.begin())
