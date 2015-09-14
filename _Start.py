import os

import sublime

try:
    import NewSublimeProject
except ImportError:
    pass
else:
    NewSublimeProject.register_template_folder_to_install(
        'Packages/Focus/New Sublime Project Templates',
        'Focus Package.sublime-settings',
        'install_new_sublime_project_templates')

from .tools.general import add_to_path
from .tools.load_translator_completions import _load_translator_completions

# Add beautiful soup 4 to the path so it works correctly
_BS4_LIB = os.path.join(os.path.dirname(__file__), 'Lib')
add_to_path(_BS4_LIB)


def plugin_loaded():
    _load_translator_completions()

    from package_control import events
    ver = events.install('Focus')

    if ver == '2.0.0':
        sublime.run_command('migrate_focus_settings')
