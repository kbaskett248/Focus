import itertools
import logging
import os
import re
import sys
import time

import sublime
import sublime_plugin

from .tools.settings import (
    get_universe_roots,
    get_universes_to_load,
    get_ring_utilities
)
from .tools.classes import (
    get_ring_file,
    get_ring,
    list_rings,
    get_ring_by_id,
    is_local_ring
)
from .classes.command_templates import RingCommand

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

CompareInInstalled = False


def _check_for_compare_in():
    global CompareInInstalled
    CompareInInstalled = 'CompareIn' in sys.modules.keys()


def _load_installed_rings():
    dirs_to_check = set()
    directories = get_universe_roots()
    universes = get_universes_to_load()
    paths = [os.path.join(*j) for j in
             itertools.product(directories, universes)]

    logger.debug('Possible Universe Paths: %s', paths)
    for path in paths:
        if os.path.isdir(path):
            for folder in os.listdir(path):
                if folder.lower().endswith('.ring'):
                    dir_ = os.path.join(path, folder)
                    if os.path.isdir(dir_):
                        dirs_to_check.add(dir_)

    logger.debug('Existing Universe Paths: %s', dirs_to_check)
    logger.debug("Loading rings:")
    for dir_ in dirs_to_check:
        ring = get_ring(dir_)
        print(ring.ring_info())


def plugin_loaded():
    """Loads completion loaders as well as the installed rings."""

    _check_for_compare_in()
    _load_installed_rings()


class RingUpdateCommand(RingCommand):
    """Runs the SVN Ring Update command for a chosen ring."""

    InstalledRingFilters = {'local_only': True}

    def ring_run_command(self, ring, **kwargs):
        if ring.update():
            sublime.status_message(
                'Launching Update for %s' % ring.name)


class OpenMagicKingdomCommand(RingCommand):
    """
    Opens Magic Kingdom for a ring from the currently installed rings.
    """

    def ring_run_command(self, ring, **kwargs):
        if ring.open_kingdom():
            sublime.status_message(
                'Launching Magic Kingdom in %s' % ring.name)


class LaunchFocusUtilityCommand(RingCommand):
    """Command to open a utility in a selected ring."""

    def run(self, utility=None, **kwargs):
        """
        Shows quicklist to choose a ring for running the specified utility or
        one to be chosen later.

        Keyword arguments:
        utility - The name of a utility in the command list to run. If not
                  specified, you can choose one after choosing the ring.

        """
        self.load_commands()

        if utility is None:
            self.ring_run_command = self.choose_utility
            super(LaunchFocusUtilityCommand, self).run(**kwargs)
        elif utility in self.commands.keys():
            self.ring_run_command = self.launch_utility
            super(LaunchFocusUtilityCommand, self).run(utility=utility,
                                                       **kwargs)
        else:
            logger.error('No command defined: %s', utility)
            sublime.error_message(
                "'%s' is not defined as an M-AT utility.\nYou may need to "
                "define it in 'User\\Focus Package.sublime-settings.'" %
                utility)

    def load_commands(self):
        """Loads additional commands defined in the settings file."""
        self.commands = get_ring_utilities()
        logger.info(self.commands)

    def launch_utility(self, ring, utility=None, **kwargs):
        """Launches the defined utility for the selected ring."""
        if (ring is None) or (utility is None):
            return

        try:
            partial_path = self.commands[utility]
            if partial_path is None:
                raise KeyError()
        except KeyError:
            return

        if 'FocSource.Process.S' in partial_path:
            partial_path = ring.ManageSourceCmd

        partial_path = os.path.join('PgmSource', partial_path)
        logger.info('Launching %s in %s; partial path = %s', utility,
                    ring.id, partial_path)
        full_path = ring.get_file_path(partial_path)
        logger.debug('full_path = %s', full_path)
        if full_path is None:
            logger.warning('%s does not exist in %s', partial_path, ring.id)
            sublime.status_message(
                'Cannot launch %s in %s' % (utility, ring.id))
            return

        sublime.run_command('app_run_ring_file', {'file_name': full_path})
        # if ring.run_file_nice(partial_path=partial_path):
        #     sublime.status_message(
        #         'Launching {0} in {1}'.format(utility, ring.name))
        #     logger.debug('Successful')
        # elif (utility == 'Edit Object'):
        #     partial_path = os.path.join('PgmObject', 'Foc',
        #                                 'FocObj.Ee.S.mps')
        #     if ring.run_file_nice(partial_path=partial_path):
        #         sublime.status_message(
        #             'Launching {0} in {1}'.format(utility, ring.ring))
        #         logger.debug('Successful')


    def choose_utility(self, ring, **kwargs):
        """Displays a quick list for choosing a utility."""
        if (ring is not None):
            choices = [x for x in self.commands.keys()]
            choices.sort()
            sublime.set_timeout(
                lambda: sublime.active_window().show_quick_panel(
                    choices,
                    lambda sel: self.utility_chooser_handler(
                        ring, choices, sel, **kwargs)),
                0)

    def utility_chooser_handler(self, ring, choices, sel, **kwargs):
        """Handler for launching the chosen utility."""
        if sel != -1:
            utility = choices[sel]
            self.launch_utility(ring, utility, **kwargs)


class LocalUpdateSidebarCommand(sublime_plugin.TextCommand):
    """Updates the ring for the current file"""

    def __init__(self, view):
        super(LocalUpdateSidebarCommand, self).__init__(view)

    def run(self, edit, paths=None):
        d = self.get_dir(paths)
        ring = get_ring(d)
        if ((ring is not None) and is_local_ring(ring)):
            ring.update()

    def is_visible(self, paths=None):
        v, e = self.determine_visibility(paths)
        return v

    def is_enabled(self, paths=None):
        v, e = self.determine_visibility(paths)
        return e

    def determine_visibility(self, paths):
        visible = False
        enabled = False
        d = self.get_dir(paths)
        ring = get_ring(d)
        logger.debug(ring)

        if (ring is not None):
            visible = True
            if is_local_ring(ring):
                enabled = True

        yield visible
        yield enabled

    def get_dir(self, paths):
        if paths:
            d = paths[0] + os.sep
        else:
            d = self.view.file_name()

        return d


class OpenInOtherRingCommand(RingCommand):
    """Opens the utility defined in the argument."""

    def run(self, file=None, ring=None, compare=False, edit=False):
        self.compare = compare
        self.edit = edit
        self.current_file = sublime.active_window().active_view().file_name()
        self.current_ring = get_ring(self.current_file)

        self.target_file = file
        if (ring is not None):
            logger.debug('Attempting to use supplied ring: %s', ring)
            self.target_ring = get_ring_by_id(ring)
            if self.target_ring is None:
                logger.error('Could not get ring for %s', ring)
                sublime.error_message(
                    'The specified ring (%s) could not be used' % ring)
                return
            else:
                logger.info('Using ring: %s', self.ring.ring_path)

        self.get_file_and_ring()

    def get_file_and_ring(self):
        proceed = True
        if (self.target_ring is None):
            self.get_ring()
            print(self.target_ring)
            proceed = False
        elif (self.target_file is None):
            self.get_file()
            proceed = False
        elif isinstance(self.target_file, str):
            if (self.target_file.lower() == 'current'):
                self.get_file()
                proceed = False
            elif not os.path.isfile(self.target_file):
                print(self.target_file)
                logger.error('Invalid ring: %s', self.target_ring)
                sublime.error_message(
                    'The specified ring (%s) could not be used' %
                    self.target_ring)
                proceed = False

        if proceed:
            self.open_file()

    def get_ring(self):
        logger.info('Choosing ring')
        rings_to_remove = []
        if ((self.current_ring is not None) and
                (self.target_file == 'current')):
            if self.edit:
                # remove current ring if the current file is the cache version
                if (is_local_ring(self.current_ring) or
                        (self.current_ring.cache_path in self.current_file)):
                    rings_to_remove.append(self.current_ring)
            else:
                # remove current ring if there is no other version of the
                # current file.
                partial_path = self.current_ring.partial_path(
                    self.current_file)
                logger.debug('partial_path: %s', partial_path)
                file_existence = self.current_ring.check_file_existence(
                    partial_path)
                if (len(file_existence) <= 1):
                    rings_to_remove.append(self.current_ring)

        self.choose_installed_ring(self.ring_selected,
                                   rings_to_remove=rings_to_remove
                                   )
        return

    def ring_selected(self, ring):
        self.target_ring = ring
        self.get_file_and_ring()

    def get_file(self):
        proceed = True

        if (self.target_file is None):
            logger.error('Selecting file - not implemented')
            proceed = False
        elif (self.target_file == 'current'):
            logger.info('Using current file: %s', self.current_file)
            if (self.current_ring is not None):
                partial_path = self.current_ring.partial_path(
                    self.current_file)
                file_existence = self.target_ring.check_file_existence(
                    partial_path, multiple_matches=True)

                if file_existence:
                    if self.edit:
                        if is_local_ring(self.target_ring):
                            self.target_file = file_existence[0][1]
                        else:
                            self.target_file = os.path.join(
                                self.target_ring.pgm_cache_path, partial_path)
                            if (not os.path.isfile(self.target_file)):
                                self.target_ring.copy_source_to_cache(
                                    self.target_file)
                    else:
                        if len(file_existence) == 1:
                            logger.debug('Replace ring path in %s',
                                         self.current_file)
                            self.target_file = file_existence[0][1]
                        else:
                            logger.info(
                                'Choosing a file from the following: %s',
                                file_existence)
                            self.path_choices = [c for c in file_existence if
                                                 (c[1] != self.current_file)]
                            if (len(self.path_choices) == 1):
                                self.target_file = self.path_choices[0][1]
                            else:
                                path_choices = [c[0] for c in
                                                self.path_choices]
                                sublime.set_timeout(
                                    lambda: sublime.active_window().show_quick_panel(
                                        path_choices,
                                        self.path_choice_handler),
                                    10)
                                proceed = False
                else:
                    logger.info('%s does not exist in %s',
                                partial_path,
                                self.target_ring)
                    sublime.error_message('%s does not exist in %s' %
                                          (partial_path, self.target_ring))
                    proceed = False
        elif not os.path.exists(self.target_file):
            logger.error('%s does not exist', self.target_file)
            sublime.error_message('%s does not exist' % self.target_file)
            proceed = False

        if proceed:
            self.get_file_and_ring()

    def path_choice_handler(self, num):
        if (num != -1):
            self.target_file = self.path_choices[num][1]
            self.get_file_and_ring()

    def open_file(self):
        if self.compare:
            logger.info('Comparing %s and %s',
                        self.current_file,
                        self.target_file)
            # compare_program = self.get_compare_program()
            # cmd = '{0} "{1}" "{2}"'.format(compare_program,
            #                                self.current_file,
            #                                self.target_file)
            left_read_only = right_read_only = False
            if not is_local_ring(self.current_ring):
                if (self.current_ring.server_path in self.current_file):
                    left_read_only = True
                    # cmd += ' /leftreadonly'
            if not is_local_ring(self.target_ring):
                if (self.target_ring.server_path in self.target_file):
                    # cmd += ' /rightreadonly'
                    right_read_only = True
            sublime.run_command('compare_in',
                                {'left_file': self.current_file,
                                 'right_file': self.target_file,
                                 'left_read_only': left_read_only,
                                 'right_read_only': right_read_only})
            # logger.info(cmd)
            # try:
            #     subprocess.Popen(cmd)
            # except Exception:
            #     logger.error('Problem opening comparison tool')
            #     sublime.error_message(
            #         'There was an error running your merge command.\n%s' % cmd)
        else:
            logger.info('Opening file: %s', self.target_file)
            sublime.active_window().open_file(self.target_file)

    def is_visible(self, compare=False):
        result = False
        if compare and (not CompareInInstalled):
            pass
        elif super(OpenInOtherRingCommand, self).is_visible():
            v = sublime.active_window().active_view()
            f = get_ring_file(v.file_name())
            if f is not None:
                result = True
        return result

    def is_enabled(self):
        return self.is_visible()


class LookupAliasCommand(RingCommand):
    """Allows you to jump to the definition of an alias."""

    def run(self):
        self.switch_back_view = sublime.active_window().active_view()
        self.choose_installed_ring(self.choose_alias)

    def choose_alias(self, ring):
        """
        Displays a list of all Global aliases to open.

        Keyword arguments:
        ring - a ring object

        """
        if (ring is not None):
            if ring.alias_lookup is None:
                ring.load_aliases()
            aliases = [['@@' + a, b[1]] for a, b in ring.alias_lookup.items()]
            aliases.sort()
            sublime.set_timeout(
                lambda: sublime.active_window().show_quick_panel(
                    aliases,
                    lambda sel: self.open_alias(ring, aliases, sel),
                    0,
                    0,
                    lambda sel: self.open_alias(ring, aliases, sel, True)),
                0)

    def open_alias(self, ring, aliases, selection, transient=False):
        """
        Opens the selected alias in the selected ring.

        Keyword arguments:
        ring - a ring object
        aliases - A list of [Alias, File name]
        selection - The number of the item selected

        """
        if (selection != -1):
            selected_alias = aliases[selection][0][2:]
            alias_entry = ring.alias_lookup[selected_alias]
            logger.debug(alias_entry)
            file_ = ring.get_file_path(os.path.join('PgmSource',
                                                    alias_entry[0],
                                                    alias_entry[1] + '.focus'))
            flags = 0
            if transient:
                flags = sublime.TRANSIENT
            else:
                self.switch_back_view = None
            view = sublime.active_window().open_file(file_, flags)
            sublime.set_timeout_async(
                lambda: self.show_alias(view, selected_alias), 0)
        else:
            logger.debug(self.switch_back_view)
            self.switch_back_view.window().focus_view(self.switch_back_view)
            self.switch_back_view = None

    def show_alias(self, view, selected_alias):
        """
        Jumps to the location in the view where the alias is defined.

        Keyword arguments:
        view - The view representing the file
        selected_alias - The text of the alias chosen

        """
        while view.is_loading():
            time.sleep(0.005)

        region = view.find(r"^\s*:?Alias\s+%s\s*?$" % selected_alias, 0)
        if (region is not None):
            region_string = view.substr(region)
            if (':Alias' in region_string):
                select_string = selected_alias
            else:
                ep_pattern = re.compile(r"^:EntryPoint +(.+?) *$")
                prev_line_reg, prev_line_text = self.get_previous_line(
                    view, region)
                match = ep_pattern.match(prev_line_text)
                while (match is None) and (prev_line_reg.begin() > 0):
                    prev_line_reg, prev_line_text = self.get_previous_line(
                        view, prev_line_reg)
                    match = ep_pattern.match(prev_line_text)
                if (match is not None):
                    sub_name = match.group(1)
                    region = view.find(r"^\s*:Code\s+%s$" % sub_name, 0)
                    select_string = sub_name
        if (region is not None):
            v = view.text_to_layout(region.begin())
            view.set_viewport_position(v, False)
            select_region = view.find(select_string, region.begin())
            if (select_region is not None):
                s = view.sel()
                s.clear()
                s.add(select_region)

    def get_previous_line(self, view, region):
        """
        Returns the region of the line before the given region and the text of
        that line.

        Keyword arguments:
        view - A view object
        region - A region

        """
        line_reg = view.line(region)
        prev_line_reg = view.line(line_reg.begin() - 1)
        yield prev_line_reg
        yield view.substr(prev_line_reg)


class BrowseSourceCommand(RingCommand):
    """
    Command to view the source files in a ring as you would in Manage Source
    Code.

    This command allows you to drill down to the source file by choosing the
    Application, object, and source file.

    """

    def run(self):
        self.switch_back_view = sublime.active_window().active_view()
        self.choose_installed_ring(
            self.choose_application,
            ring_filter_callback=BrowseSourceCommand.ring_is_browsable)

    def choose_application(self, ring):
        """
        Displays a list of all of Applications in the selected ring to choose
        from.

        Keyword arguments:
        ring - a ring object

        """
        if (ring is None):
            return

        logger.debug('ring.pgmsource_path = %s', ring.pgmsource_path)
        if ((ring.pgmsource_path is None) or
                (not os.path.isdir(ring.pgmsource_path))):
            return

        applications = os.listdir(ring.pgmsource_path)
        # logger.debug('applications = %s', applications)
        paths = [os.path.join(ring.pgmsource_path, f) for f in applications]
        # logger.debug('paths = %s', paths)

        sublime.set_timeout(
            lambda: sublime.active_window().show_quick_panel(
                applications,
                lambda sel: self.choose_object(ring, paths, sel)),
            0)

    def choose_object(self, ring, paths=[], sel=None, app=None):
        """
        Displays a list of the objects in the selected application to choose
        from.

        Keyword arguments:
        ring - An Ring object
        paths - A list of paths to each application folder
        sel - The index of the selected application
        app - An override path to an application folder

        """
        if app is None:
            if sel == -1:
                self.switch_back_view = None
                return

            app = paths[sel]

        object_dict = {}
        for f in os.listdir(app):
            k = f.split('.')[0]
            v = os.path.join(app, f)
            try:
                object_dict[k].append(v)
            except KeyError:
                object_dict[k] = [v]
        objects = ['..']
        objects.extend(object_dict.keys())
        objects.sort()
        # logger.debug('objects = %s', objects)

        sublime.set_timeout(
            lambda: sublime.active_window().show_quick_panel(
                objects,
                lambda sel: self.choose_file(ring, objects, object_dict, sel)),
            0)

    def choose_file(self, ring, objects, object_dict, sel):
        """Displays a list of the files for the selected object to choose from.

        Keyword arguments:
        ring - An Ring object
        objects - A list of objects in the selected application
        object_dict - A dictionary keyed by object where each item is a list
                      of files for that object
        sel - The index of the selected object

        """
        if sel == -1:
            self.switch_back_view = None
            return

        object = objects[sel]

        if object == '..':
            sublime.set_timeout(self.choose_application(ring), 0)
            return

        files = object_dict[object]
        disp_files = ['..']
        disp_files.extend([os.path.basename(f) for f in files])

        sublime.set_timeout(
            lambda: sublime.active_window().show_quick_panel(
                disp_files,
                lambda sel: self.open_file(ring,
                                           disp_files,
                                           files,
                                           sel,
                                           False),
                0,
                0,
                lambda sel: self.open_file(ring,
                                           disp_files,
                                           files,
                                           sel,
                                           True)),
            0)

    def open_file(self, ring, disp_files, files, sel, transient):
        """Opens the selected file."""
        if sel <= 0:
            # logger.debug(self.switch_back_view)
            self.switch_back_view.window().focus_view(self.switch_back_view)
            if sel == -1:
                self.switch_back_view = None
            elif sel == 0:
                sublime.set_timeout(
                    self.choose_object(ring,
                                       app=os.path.dirname(files[1])),
                    0)
            return
        else:
            file_ = files[sel - 1]
            if transient:
                flags = sublime.TRANSIENT
            else:
                flags = 0
                self.switch_back_view = None
            sublime.active_window().open_file(file_, flags)

    def is_visible(self):
        result = False
        if super(BrowseSourceCommand, self).is_visible():
            for r in list_rings():
                if BrowseSourceCommand.ring_is_browsable(r):
                    result = True
                    break
        return result

    @classmethod
    def ring_is_browsable(cls, ring):
        if ring is None:
            return False
        elif ring.pgmsource_path is None:
            return False
        else:
            return os.path.isdir(ring.pgmsource_path)
