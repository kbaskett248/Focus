import json
import logging
import logging.handlers
import os
import sys

import sublime

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)
    logger.info('Using standard logging system')
else:
    logger.handlers = []

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.WARNING)
    stream_handler.setFormatter(logging.Formatter(sublimelogging.getBasicFormat()))
    logger.addHandler(stream_handler)

    file_handler_path = os.path.join(sublimelogging.getLogsPath(), 'Focus.log')
    print('Focus file_handler_path: %s' % file_handler_path)
    timed_file_handler = logging.handlers.TimedRotatingFileHandler(
        file_handler_path, when = 'midnight', backupCount = 3)
    timed_file_handler.setLevel(logging.DEBUG)
    timed_file_handler.setFormatter(logging.Formatter(sublimelogging.getDetailFormat()))
    logger.addHandler(timed_file_handler)
    logger.info('Using AAASublimeLogging system')
finally:
    logger.propagate = False
    logger.setLevel(logging.DEBUG)

from .src import FocusLanguage

def _addLibToPath():
    """Adds Lib to the system path so sublimelogging is available to all packages."""
    path_to_lib = os.path.join(os.path.dirname(__file__), 'src', 'Lib')
    if not path_to_lib in sys.path:
        sys.path.append(path_to_lib)
        print("Added %s to sys.path." % path_to_lib)

_addLibToPath()

TranslatorCompletions = dict()
ScopeMappings = dict()

def plugin_loaded():
    """Adds SettingFilters to the handlers. 

    There is no access to the settings until the plugin is loaded.

    """
    stream_handler.addFilter(
        sublimelogging.SettingsEnabledFilter('m-at.sublime-settings', 
                                             'log_to_console')
        )
    stream_handler.addFilter(
        sublimelogging.SettingsLevelFilter(stream_handler, 
                                           'm-at.sublime-settings', 
                                           'console_log_level')
        )
    timed_file_handler.addFilter(
        sublimelogging.SettingsEnabledFilter('m-at.sublime-settings', 
                                             'log_to_file')
        )
    timed_file_handler.addFilter(
        sublimelogging.SettingsLevelFilter(timed_file_handler, 
                                           'm-at.sublime-settings', 
                                           'file_log_level')
        )

    FocusLanguage.plugin_loaded()
    load_translator_completions()
    load_scope_mappings()

def load_translator_completions():
    global TranslatorCompletions
    try:
        tran_comp = sublime.load_resource(
        'Packages/User/Translator Completions.json')
    except IOError:
        tran_comp = sublime.load_resource(
            'Packages/Focus/Language/Translator Completions.json')
    TranslatorCompletions = json.loads(tran_comp, object_hook = object_hook)

def object_hook(object_dict):
    # logger.debug('object_dict = %s', object_dict)
    keys = object_dict.keys()
    if ((len(object_dict) == 0) or ('children' in keys) or 
        ('completions' in keys) or ('completion_types' in keys)):
        return TranslatorObject(**object_dict)
    else:
        return object_dict
    

class TranslatorObject(object):
    """docstring for TranslatorObject"""

    def __init__(self, children = {}, completions = [], completion_types = [], required = False):
        super(TranslatorObject, self).__init__()
        self.children = children
        self.completions = completions
        self.completion_types = completion_types
        self.required = required

    # def __str__(self):
    #     string = 'Completions: %s\nCompletion Types: %s\nSubitems:\n' % (self.completions, self.completion_types, self.children)
    #     for c in self.children:
    #         substring = c.__str__()
    #         new_substring = ''
    #         for s in substring.split('\n'):
    #             new_substring += '\t%s\n' % s
    #         string += new_substring + '\n'
    #     return string

def load_scope_mappings():
    global ScopeMappings
    try:
        scope_mappings = sublime.load_resource(
        'Packages/User/focus.scope-mapping')
    except IOError:
        scope_mappings = sublime.load_resource(
            'Packages/Focus/Language/focus.scope-mapping')
    ScopeMappings = json.loads(scope_mappings)

def scope_map(key, default = 'NONE'):
    try:
        return ScopeMappings[key]
    except KeyError:
        return default

def score_selector(view, point, key, default = 'NONE'):
    return view.score_selector(point, scope_map(key, default))

def find_by_selector(view, key, default = 'NONE'):
    return view.find_by_selector(scope_map(key, default))


