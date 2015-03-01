import os

try:
    import NewSublimeProject
except ImportError:
    pass
else:
    NewSublimeProject.register_template_folder_to_install(
        'Packages/MTFocus/New Sublime Project Templates',
        'MT-Focus.sublime-settings',
        'install_new_sublime_project_templates')

from .tools import add_to_path
from .tools.load_translator_completions import _load_translator_completions

# Add beautiful soup 4 to the path so it works correctly
_BS4_LIB = os.path.join(os.path.dirname(__file__), 'Lib')
add_to_path(_BS4_LIB)


def plugin_loaded():
    _load_translator_completions()
