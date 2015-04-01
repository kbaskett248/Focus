import logging
import os

import sublime

from .general import get_env


logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')


SETTINGS_FILE = 'Focus Package.sublime-settings'


SETTINGS_INFO = (
    ('get_show_doc_setting', 'show_doc_in_panel', False),
    ('get_focus_wiki_setting', 'focus_wiki', 'http://stxwiki/wiki10/'),
    ('get_fs_wiki_setting', 'fs_wiki', 'http://stxwiki/magicfs6/'),
    ('get_set_highlighter_setting', 'highlight_sets_across_file', False),
    ('get_translator_doc_url_overrides_setting',
     'translator_doc_url_overrides', {}),
    ('get_documentation_sections', 'documentation_sections',
     ["Purpose", "Arguments", "Preconditions", "Local Variables",
      "Data Structures", "Side Effects", "Returns", "Additional Notes"]),
    ('get_fs_function_doc_url_overrides_setting',
     'fs_function_doc_url_overrides', {}),
    ('get_focus_function_doc_url_overrides_setting',
     'focus_function_doc_url_overrides', {}),
    ('get_default_ring', 'default_ring', None),
    ('get_server_access', 'server_access', []),
    ('get_universes_to_load', 'universes_to_load', []),
    ('get_translate_command', 'translate_command',
     'Foc\\FocZ.Textpad.Translate.P.mps'),
    ('get_tool_file_names', 'tool_file_names', []),
    ('get_translate_on_save', 'translate_on_save', False),
    ('get_sort_local_rings', 'sort_local_rings_to_top', False),
    ('get_ring_utilities', 'ring_utilities', {}),
    ('get_disable_translator_indent', 'disable_translator_indent_for', False)
)


def add_basic_settings_function(name, setting_name, default):
    def basic_settings_function():
        settings = sublime.load_settings(SETTINGS_FILE)
        return settings.get(setting_name, default)

    basic_settings_function.__name__ = name
    globals()[name] = basic_settings_function


for info in SETTINGS_INFO:
    add_basic_settings_function(*info)
del info


# DocLink Settings
# def get_show_doc_setting():
#     settings = sublime.load_settings(SETTINGS_FILE)
#     return settings.get('show_doc_in_panel', False)


# def get_focus_wiki_setting():
#     settings = sublime.load_settings(SETTINGS_FILE)
#     return settings.get('focus_wiki', "http://stxwiki/wiki10/")


# def get_fs_wiki_setting():
#     settings = sublime.load_settings(SETTINGS_FILE)
#     return settings.get('fs_wiki', "http://stxwiki/magicfs6/")


# def get_set_highlighter_setting():
#     settings = sublime.load_settings(SETTINGS_FILE)
#     return settings.get('highlight_sets_across_file', False)


# def get_translator_doc_url_overrides_setting():
#     settings = sublime.load_settings(SETTINGS_FILE)
#     return settings.get('translator_doc_url_overrides', {})


def get_focus_function_argument_type(function):
    settings = sublime.load_settings(
        'Focus-Function Argument Types.sublime-settings')
    return settings.get(function, None)


# def get_fs_function_doc_url_overrides_setting():
#     settings = sublime.load_settings(SETTINGS_FILE)
#     return settings.get('fs_function_doc_url_overrides', {})


# def get_focus_function_doc_url_overrides_setting():
#     settings = sublime.load_settings(SETTINGS_FILE)
#     return settings.get('focus_function_doc_url_overrides', {})


# Completions
def get_completion_trigger_enabled_setting(trigger):
    settings = sublime.load_settings(SETTINGS_FILE)
    s = settings.get('enable_smart_completion_triggers', True)
    if isinstance(s, dict):
        try:
            return s[trigger]
        except KeyError:
            return True
    elif isinstance(s, bool):
        return s
    else:
        return bool(s)


def get_completion_source_enabled_setting(completion_type, source):
    settings = sublime.load_settings(SETTINGS_FILE)
    s = settings.get('enable_smart_completion_sources', True)

    def convert_setting(setting, *args):
        if isinstance(setting, dict):
            try:
                return convert_setting(setting[args[0]], *args[1:])
            except KeyError:
                return True
        elif isinstance(setting, bool):
            return setting
        else:
            return bool(setting)

    return convert_setting(s, completion_type, source)


# Rings
# def get_default_ring():
#     settings = sublime.load_settings(SETTINGS_FILE)
#     return settings.get('default_ring', None)


# def get_server_access():
#     settings = sublime.load_settings(SETTINGS_FILE)
#     return settings.get('server_access', [])


def get_universe_roots():
    results = []
    pgm_files = get_env('ProgramFiles(x86)')
    settings = sublime.load_settings(SETTINGS_FILE)
    for p in settings.get('universe_roots', []):
        try:
            path = p.format(program_files=pgm_files)
        except AttributeError:
            continue
        else:
            if os.path.exists(path):
                results.append(path)
    return results


# def get_universes_to_load():
#     settings = sublime.load_settings(SETTINGS_FILE)
#     return settings.get('universes_to_load', [])


# def get_translate_command():
#     settings = sublime.load_settings(SETTINGS_FILE)
#     return settings.get('translate_command',
#                         'Foc\\FocZ.Textpad.Translate.P.mps')


def get_translate_include_settings():
    settings = sublime.load_settings(SETTINGS_FILE)
    translate_include_files = settings.get('translate_including_files', True)
    if translate_include_files:
        return (True, settings.get('translate_max_file_count', 20))
    else:
        return (False, 1)


def get_default_separators():
    settings = sublime.load_settings(SETTINGS_FILE)
    sep_dict = {'alpha': ' - ',
                'numeric': '.  '}
    separators = settings.get('documentation_separator', sep_dict)
    if isinstance(separators, str):
        sep_dict = {k: separators for k in sep_dict.keys()}
    elif isinstance(separators, list):
        try:
            sep_dict['alpha'] = separators[0]
            sep_dict['numeric'] = separators[1]
        except IndexError:
            pass
    elif isinstance(separators, dict):
        try:
            sep_dict['alpha'] = separators[
                'variable_separator']
        except KeyError:
            pass

        try:
            sep_dict['numeric'] = separators[
                'numeric_separator']
        except KeyError:
            pass

    return sep_dict
