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

from .tools.load_translator_completions import _load_translator_completions


class VersionNumber(object):
    def __init__(self, ver_string):
        super(VersionNumber, self).__init__()
        self.ver_string = ver_string
        self.prerelease = ''
        if '-' in self.ver_string:
            i = self.ver_string.find('-')
            self.prerelease = self.ver_string[i:]
            ver_string = self.ver_string[:i]
        self.parts = [int(s) for s in ver_string.split('.')]
        self.parts.append(self.prerelease)
        self.major_version = self.parts[0]
        self.minor_version = self.parts[1]
        self.bug_fix = self.parts[2]

    def __str__(self):
        return self.ver_string

    def __lt__(self, other):
        if isinstance(other, VersionNumber):
            return self.parts < other.parts
        else:
            return str(self) < str(other)


def plugin_loaded():
    _load_translator_completions()

    from package_control import events
    ver = events.install('Focus')
    if not ver:
        ver = events.post_upgrade('Focus')
        if not ver:
            return

    ver = VersionNumber(ver)
    if ver.major_version >= 2 and ver.minor_version == 0:
        sublime.run_command('migrate_focus_settings')
