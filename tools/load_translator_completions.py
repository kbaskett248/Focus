# Used to load the Translator Completion tree from the json file.

import json

import sublime


_TRANSLATOR_COMPLETIONS = dict()
_FILE_NAME = 'Translator Completions.json'
_DEFAULT_PATH = 'Packages/Focus/misc/' + _FILE_NAME
_USER_PATH = 'Packages/User' + _FILE_NAME


def _load_translator_completions():
    global _TRANSLATOR_COMPLETIONS
    try:
        tran_comp = sublime.load_resource(_USER_PATH)
    except IOError:
        tran_comp = sublime.load_resource(_DEFAULT_PATH)

    def object_hook(object_dict):
        class TranslatorObject(object):
            """
            Object representing a Translator.
            """

            def __init__(self, children={}, completions=[],
                         completion_types=[], required=False,
                         restrict_to_file=False):
                super(TranslatorObject, self).__init__()
                self.children = children
                self.completions = completions
                self.completion_types = completion_types
                self.required = required
                self.restrict_to_file = restrict_to_file

        keys = object_dict.keys()
        if ((len(object_dict) == 0) or ('children' in keys) or
                ('completions' in keys) or ('completion_types' in keys)):
            return TranslatorObject(**object_dict)
        else:
            return object_dict

    _TRANSLATOR_COMPLETIONS = json.loads(tran_comp, object_hook=object_hook)


def get_translator_completions():
    return _TRANSLATOR_COMPLETIONS
