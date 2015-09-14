import copy
import json
import logging
import os
import webbrowser

import sublime
import sublime_plugin

from .tools.sublime import load_settings


logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')


class OpenWebPageCommand(sublime_plugin.WindowCommand):

    def run(self, url=''):
        if url:
            webbrowser.open(url)

    def is_visible(self, url=''):
        return bool(url)


class MigrateFocusSettingsCommand(sublime_plugin.ApplicationCommand):
    """Migrates existing settings from focus.sublime-settings to the new
       settings location in Focus Package.sublime-settings.

    """

    def run(self):
        try:
            existing_settings = self.get_existing_settings()
        except ValueError as e:
            sublime.error_message(
                'The existing settings file (m-at.sublime-settings) cannot be '
                'parsed. Please remove any comments (lines beginning '
                'with "//") and extra commas. Then re-run Focus Tools: Migrate'
                ' Settings to Focus Package Settings.\n\n' + str(e))
            return

        if existing_settings is None:
            sublime.message_dialog(
                'No focus.sublime-settings file was found. No settings to '
                'migrate.')
            return
        if not self.confirm_run():
            return

        logger.debug('existing_settings: %s', existing_settings)

        self.new_settings_path = os.path.join(
            sublime.packages_path(), 'User', 'Focus Package.sublime-settings')
        new_settings = self.get_new_settings()
        temp_settings = {}

        for existing_key, existing_value in existing_settings.items():
            # new_key will be None if it is a setting that doesn't need to be
            # migrated.
            new_key = self.map_key(existing_key)
            if new_key is None:
                continue
            try:
                new_settings[new_key]
            except KeyError:
                pass
            else:
                continue

            new_value = self.map_value(existing_key, existing_value,
                                       new_key, temp_settings)
            temp_settings[new_key] = new_value

        if not self.add_server_access(temp_settings):
            return

        logger.debug('temp_settings: %s', json.dumps(temp_settings, indent=4))

        for k, v in temp_settings.items():
            new_settings[k] = v
        self.dump_new_settings(new_settings)
        sublime.active_window().open_file(self.new_settings_path)

    def confirm_run(self):
        """Displays a confirmation message to migrate settings."""
        return sublime.ok_cancel_dialog(
            'This will attempt to migrate User settings from '
            'focus.sublime-settings to Focus Package.sublime-settings.')

    def get_existing_settings(self):
        old_settings_path = os.path.join(
            sublime.packages_path(), 'User', 'm-at.sublime-settings')

        if not os.path.isfile(old_settings_path):
            return None
        old_settings = load_settings(old_settings_path)

        return old_settings

    def get_new_settings(self):
        if os.path.isfile(self.new_settings_path):
            new_settings = load_settings(self.new_settings_path)
        else:
            new_settings = {}

        return new_settings

    def dump_new_settings(self, new_settings):
        with open(self.new_settings_path, 'w') as f:
            json.dump(new_settings, f, indent=4)

    def map_key(self, existing_key):
        return self.KEY_MAPPINGS.get(existing_key)

    def map_value(self, existing_key, existing_value, new_key, temp_settings):
        if new_key == 'documentation_separator':
            v = temp_settings.get(new_key, dict())
            m = {'default_numeric_separator': 'numeric_separator',
                 'default_variable_separator': 'variable_separator'}
            v[m[existing_key]] = existing_value
            return v

        elif new_key == 'documentation_sections':
            return existing_value

        elif new_key == 'translate_command':
            return existing_value

        elif new_key == 'ring_utilities':
            return {k: v.replace('.mps', '.focus') for k, v in
                    existing_value.items()}

        elif new_key == 'show_doc_method':
            v = copy.deepcopy(self.SHOW_DOC_METHOD)
            if not existing_value:
                v['focus_function'] = 'source'
                v['fs_function'] = 'source'
            return v

    def add_server_access(self, temp_settings):
        add = sublime.yes_no_cancel_dialog(
            'Would you like to initialize the settings file with Home Care '
            'server access?')
        if add == sublime.DIALOG_YES:
            temp_settings['server_access'] = [
                "\\\\BORIS\\F",
                "\\\\MOOSE\\F",
                "\\\\HHFILSRV1\\F",
                "\\\\HHQA27-FS1\\F"
            ]
        elif add == sublime.DIALOG_CANCEL:
            return False

        return True

    KEY_MAPPINGS = {
        'default_numeric_separator': 'documentation_separator',
        'default_variable_separator': 'documentation_separator',
        'documentation_sections': 'documentation_sections',
        'custom_translate_command': 'translate_command',
        'ring_utilities': 'ring_utilities',
        'show_doc_in_panel': 'show_doc_method'
        }

    SHOW_DOC_METHOD = {
        "focus_function": "popup",
        "fs_function": "popup",
        "subroutine": "source",
        "translator": "source",
        "alias": "source",
        "include_file": "source",
        "local": "source",
        "object": "source",
        "screen_component": "source",
        "rt_tool": "source"
    },
