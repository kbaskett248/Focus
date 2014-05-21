import imp
import os
import re
import subprocess
import sys
import time

import sublime
import sublime_plugin

from .src.Ring import Ring, ring_matcher
from .src.tools import debug, get_env
from .src.Managers.RingManager import RingManager
from .src.Managers.RingFileManager import RingFileManager
from .src.Exceptions import InvalidRingError

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

RING_MANAGER = RingManager.getInstance()
FILE_MANAGER = RingFileManager.getInstance()

def plugin_loaded():
    """Loads completion loaders as well as the installed rings."""

    RING_MANAGER.load_installed_local_rings()
    RING_MANAGER.load_installed_server_rings()

class RingCommand(sublime_plugin.ApplicationCommand):
    """Parent class for commands that operate on loaded rings."""

    def choose_installed_ring(self, function, local_only = False, 
                              rings_to_remove = None):
        """Allows the user to select a ring and runs a specified command on it.

        Keyword arguments:
        function - the method to run with the ring as it's argument
        local_only - True to display only local rings
        rings_to_remove - list of rings to remove from the quick list

        """
        if (function is not None):
            rings = RING_MANAGER.list_rings(local_only)
            rings.sort(key = lambda r: r.name)

            if (len(rings) == 1):
                function(rings[0])

            elif (len(rings) > 1):
                if (rings_to_remove is not None):
                    for r in rings_to_remove:
                        if r in rings:
                            rings.remove(r)

                logger.debug('Rings: %s', rings)

                view = sublime.active_window().active_view()
                ring_file = FILE_MANAGER.get_ring_file(view)
                # Move the ring for the current file to the top of the list
                if (ring_file is not None):
                    current_ring = ring_file.ring_object
                    if current_ring in rings:
                        rings.remove(current_ring)
                        rings.insert(0, current_ring)

                sublime.active_window().show_quick_panel([r.name for r in rings], 
                    lambda num: self._ring_chooser_handler(function, rings, num))

    def _ring_chooser_handler(self, function, rings, num):
        """Runs the function passed into choose_installed_ring for the selected ring."""
        if ((num != -1) and (function is not None)):
            function(rings[num])

    def is_visible(self):
        return (RING_MANAGER.num_rings > 0)

    def is_enabled(self):
        return self.is_visible()

class RingUpdateCommand(RingCommand):
    """Runs the SVN Ring Update command for a chosen ring."""
    
    def run(self):
        self.choose_installed_ring(self.run_update_command, local_only = True)

    def run_update_command(self, ring):
        if (ring is not None):
            if ring.update():
                sublime.status_message(
                    'Launching Update for %s' % ring.name)

class OpenMagicKingdomCommand(RingCommand):
    """Opens Magic Kingdom for a ring from the currently installed rings."""

    def run(self):
        self.choose_installed_ring(self.launch_kingdom)

    def launch_kingdom(self, ring):
        if (ring is not None):
            if ring.open_kingdom():
                sublime.status_message( 
                    'Launching Magic Kingdom in %s' % ring.name)

class LaunchMatUtilityCommand(RingCommand):
    """Command to open a utility in a selected ring."""

    options = {'Object Viewer': os.path.join('Foc', 'FocXobjUtil.Main.S.mps'),
               'Edit Object': os.path.join('Foc', 'FocObj.Mgmt.S.mps'),
               'Home Care Desktop': os.path.join('Hha', 'HhaBrowser.Refresh.P.mps'),
               'Error Viewer': os.path.join('Hha', 'HhaZt.DevUtilities.ErrorView.S.mps'),
               'Fixer Single Run Utility': os.path.join('Hha', 'HhaZtMaintUtilities.Interface.SingleRun.S.mps')
               }
    
    def run(self, utility = None):
        """Shows quicklist to choose a ring for running the specified utility or one to be chosen later.

        Keyword arguments:
        utility - The name of a utility in the command list to run. If not 
                  specified, you can choose one after choosing the ring.

        """
        self.load_commands()

        if (utility in self.commands.keys()):
            self.utility = utility
            self.partial_path = self.commands[utility]
            self.partial_path = os.path.join('PgmObject', self.partial_path)
            self.choose_installed_ring(self.launch_utility)
        elif (utility == None):
            self.choose_installed_ring(self.choose_utility)
        else:
            logger.error('No command defined: %s', utility)
            sublime.error_message("""'%s' is not defined as an M-AT utility.\nYou may need to define it in 'User\\m-at.sublime-settings.'""" % utility)

    def load_commands(self):
        """Loads additional commands defined in the settings file."""
        self.commands = dict(LaunchMatUtilityCommand.options)

        settings = sublime.load_settings("m-at.sublime-settings")
        additional_commands = settings.get("ring_utilities", dict())

        logger.debug(additional_commands)

        if additional_commands:
            for k, v in additional_commands.items():
                self.commands[k] = v

        logger.info(self.commands)

    def launch_utility(self, ring):
        """Launches the defined utility for the selected ring."""
        if (ring is not None) and (self.partial_path is not None):
            if (("26" in ring.name) and ("FocSource.Process.Ptct.S" in self.partial_path)):
                self.partial_path = self.partial_path.replace(
                    "FocSource.Process.Ptct.S", "FocSource.Process.S")
            logger.info('Launching %s in %s; partial path = %s', self.utility, ring.ring, self.partial_path)
            if ring.run_file_nice(partial_path = self.partial_path):
                sublime.status_message(
                    'Launching {0} in {1}'.format(self.utility, ring.ring)
                )
                logger.debug('Successful')
            elif (self.utility == 'Edit Object'):
                self.partial_path = os.path.join('PgmObject', 'Foc', 'FocObj.Ee.S.mps')
                if ring.run_file_nice(partial_path = self.partial_path):
                    sublime.status_message(
                        'Launching {0} in {1}'.format(self.utility, ring.ring)
                    )
                    logger.debug('Successful')
        del self.utility, self.partial_path

    def choose_utility(self, ring):
        """Displays a quick list for choosing a utility."""
        if (ring is not None):
            self.ring = ring
            self.choices = [x for x in self.commands.keys()]
            self.choices.sort()
            sublime.set_timeout(
                lambda: sublime.active_window().show_quick_panel(self.choices, 
                                                                 self.utility_chooser_handler), 
                10)

    def utility_chooser_handler(self, u):
        """Handler for launching the chosen utility."""
        if (u != -1):
            self.utility = self.choices[u]
            self.partial_path = os.path.join('PgmObject', 
                                             self.commands[self.utility]
                                             )
            self.launch_utility(self.ring)
            del self.ring

class BuildObjectListsCommand(RingCommand):
    """Builds the Object Lists for a ring based on the currently installed rings."""
    
    def run(self):
        self.choose_installed_ring(self.update_object_lists)

    def update_object_lists(self, ring):
        if (ring is not None):
            if (ring.build_object_lists() is not None):
                sublime.status_message(
                    'Building Object Lists for {0}'.format(ring.ring)
                    )

class MatUpdateSidebarCommand(sublime_plugin.TextCommand):
    """Updates the ring for the current file"""

    def __init__(self, view):
        super(MatUpdateSidebarCommand, self).__init__(view)

    def run(self, edit, paths=None):
        d = self.get_dir(paths)
        ring = RING_MANAGER.get_ring_by_path(d)
        if ((ring is not None) and ring.local_ring):
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
        ring = RING_MANAGER.get_ring_by_path(d)
        logger.debug(ring)

        if (ring is not None):
            visible = True
            if ring.local_ring:
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
    
    def run(self, file = None, ring = None, compare = False, edit = False):
        self.compare = compare
        self.edit = edit
        self.current_file = sublime.active_window().active_view().file_name()
        try:
            self.current_ring = RING_MANAGER.get_ring_by_path(self.current_file)
        except InvalidRingError:
            self.current_ring = None

        self.target_file = file
        if (ring is not None):
            try:
                logger.debug('Attempting to use supplied ring: %s', ring)
                self.target_ring = RING_MANAGER.get_ring_by_name(ring)
                logger.info('Using ring: %s', self.ring.ring_path)
            except InvalidRingError:
                logger.error('Could not get ring for %s', ring)
                sublime.error_message('The specified ring (%s) could not be used' % ring)
                return
        else:
            self.target_ring = None

        self.get_file_and_ring()

    def get_file_and_ring(self):
        proceed = True
        if (self.target_ring is None):
            self.get_ring()
            proceed = False
        elif (self.target_file is None):
            self.get_file()
            proceed = False
        elif isinstance(self.target_file, str):
            if (self.target_file.lower() == 'current'):
                self.get_file()
                proceed = False
            elif not os.path.isfile(self.target_file):
                logger.error('Invalid ring: %s', self.target_ring)
                sublime.error_message('The specified ring (%s) could not be used' % ring)
                proceed = False

        if proceed:
            self.open_file()

    def get_ring(self):
        logger.info('Choosing ring')
        rings_to_remove = []
        if ((self.current_ring is not None) and (self.target_file == 'current')):
            if self.edit:
                # remove current ring if the current file is the cache version
                if (self.current_ring.local_ring or 
                    (self.current_ring.cache_path in self.current_file)):
                    rings_to_remove.append(self.current_ring)
            else:
                # remove current ring if there is no other version of the current file.
                partial_path = self.current_ring.partial_path(self.current_file)
                logger.debug('partial_path: %s', partial_path)
                file_existence = self.current_ring.check_file_existence(partial_path)
                if (len(file_existence) <= 1):
                    rings_to_remove.append(self.current_ring)
            
        self.choose_installed_ring(self.ring_selected, 
                                   rings_to_remove = rings_to_remove
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
                partial_path = self.current_ring.partial_path(self.current_file)
                file_existence = self.target_ring.check_file_existence(partial_path)
                
                if file_existence:
                    if self.edit:
                        if self.target_ring.local_ring:
                            self.target_file = file_existence[0][1]
                        else:
                            self.target_file = os.path.join(
                                self.target_ring.cache_path, partial_path)
                            if (not os.path.isfile(self.target_file)):
                                self.target_ring.copy_source_to_cache(self.target_file)
                    else:
                        if len(file_existence) == 1:
                            logger.debug('Replace ring path in %s', 
                                         self.current_file)
                            self.target_file = file_existence[0][1]
                        else:
                            logger.info('Choosing a file from the following: %s', 
                                        file_existence)
                            self.path_choices = [c for c in file_existence if (c[1] != self.current_file)]
                            if (len(self.path_choices) == 1):
                                self.target_file = self.path_choices[0][1]
                            else:
                                path_choices = [c[0] for c in self.path_choices]
                                sublime.set_timeout(
                                    lambda: sublime.active_window().show_quick_panel(path_choices, 
                                                                                     self.path_choice_handler), 
                                    10)
                                proceed = False
                else:
                    logger.info('%s does not exist in %s', partial_path, self.target_ring)
                    sublime.error_message('%s does not exist in %s' % (partial_path, self.target_ring))
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
            logger.info('Comparing %s and %s', self.current_file, self.target_file)
            compare_program = self.get_compare_program()
            cmd = '{0} "{1}" "{2}"'.format(compare_program, 
                                           self.current_file,
                                           self.target_file)
            if (not self.current_ring.local_ring):
                if (self.current_ring.server_path in self.current_file):
                    cmd += ' /leftreadonly'
            if (not self.target_ring.local_ring):
                if (self.target_ring.server_path in self.target_file):
                    cmd += ' /rightreadonly'
            logger.info(cmd)
            try:
                subprocess.Popen(cmd)
            except Exception as e:
                logger.error('Problem opening comparison tool')
                sublime.error_message(
                    'There was an error running your merge command.\n%s' % cmd)
        else:
            logger.info('Opening file: %s', self.target_file)
            sublime.active_window().open_file(self.target_file)

    def get_compare_program(self):
        settings = sublime.load_settings("m-at.sublime-settings")
        compare_program = settings.get("compare_program")
        if ((compare_program is None) or (not os.path.isfile(compare_program))):
            compare_program = os.path.join(get_env("ProgramFiles"), 
                                           'Beyond Compare 2', 
                                           'BC2.exe')
            if not os.path.isfile(compare_program):
                compare_program = os.path.join(get_env("ProgramFiles(x86)"), 
                                           'Beyond Compare 2', 
                                           'BC2.exe')

        if (not os.path.isfile(compare_program)):
            compare_program = None
        logger.debug('Comparison tool: %s', compare_program)

        return compare_program

    def launch_sublimerge(self):
        from Sublimerge import SublimergeDiffThread
        th = SublimergeDiffThread(self.window, self.base, self.compareTo)
        th.start()

    def is_visible(self):
        result = False
        if super(OpenInOtherRingCommand, self).is_visible():
            v = sublime.active_window().active_view()
            f = FILE_MANAGER.get_ring_file(v)
            if (f is not None):
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
        """Displays a list of all Global aliases to open.

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

    def open_alias(self, ring, aliases, selection, transient = False):
        """Opens the selected alias in the selected ring.

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
                                                    alias_entry[1] + '.focus')
                                                    )
            flags = 0
            if transient:
                flags = sublime.TRANSIENT
            else:
                self.switch_back_view = None
            view = sublime.active_window().open_file(file_, flags)
            sublime.set_timeout_async(lambda: self.show_alias(view, selected_alias), 0)
        else:
            logger.debug(self.switch_back_view)
            self.switch_back_view.window().focus_view(self.switch_back_view)
            self.switch_back_view = None
            
    def show_alias(self, view, selected_alias):
        """Jumps to the location in the view where the alias is defined.

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
                prev_line_reg, prev_line_text = self.get_previous_line(view, region)
                match = ep_pattern.match(prev_line_text)
                while (match is None) and (prev_line_reg.begin() > 0):
                    prev_line_reg, prev_line_text = self.get_previous_line(view, prev_line_reg)
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
        """Returns the region of the line before the given region and the text of that line.

        Keyword arguments:
        view - A view object
        region - A region

        """
        line_reg = view.line(region)
        prev_line_reg = view.line(line_reg.begin() - 1)
        yield prev_line_reg
        yield view.substr(prev_line_reg)


class BrowseSourceCommand(RingCommand):
    """Command to view the source files in a ring as you would in Manage Source Code.

    This command allows you to drill down to the source file by choosing the 
    Application, object, and source file.

    """
    
    def run(self):
        self.switch_back_view = sublime.active_window().active_view()
        self.choose_installed_ring(self.choose_application)

    def choose_application(self, ring):
        """Displays a list of all of Applications in the selected ring to choose from.

        Keyword arguments:
        ring - a ring object

        """
        if (ring is None):
            return
        path = os.path.join(ring.pgm_path(), 'PgmSource')
        if not os.path.isdir(path):
            return

        applications = os.listdir(path)
        logger.debug('applications = %s', applications)
        paths = [os.path.join(path, f) for f in applications]
        logger.debug('paths = %s', paths)

        sublime.set_timeout(
            lambda: sublime.active_window().show_quick_panel(
                applications, 
                lambda sel: self.choose_object(ring, paths, sel)), 
            0)

    def choose_object(self, ring, paths = [], sel = None, app = None):
        """Displays a list of the objects in the selected application to choose from.

        Keyword arguments:


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
        logger.debug('objects = %s', objects)

        sublime.set_timeout(
            lambda: sublime.active_window().show_quick_panel(
                objects, 
                lambda sel: self.choose_file(ring, objects, object_dict, sel)), 
            0)

    def choose_file(self, ring, objects, object_dict, sel):
        """Displays a list of the files for the selected object to choose from.

        Keyword arguments:


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
                lambda sel: self.open_file(ring, disp_files, files, sel, False),
                0,
                0,
                lambda sel: self.open_file(ring, disp_files, files, sel, True)), 
            0)
        
    def open_file(self, ring, disp_files, files, sel, transient):
        """Opens the selected file."""
        if sel <= 0:
            logger.debug(self.switch_back_view)
            self.switch_back_view.window().focus_view(self.switch_back_view)
            if sel == -1:
                self.switch_back_view = None
            elif sel == 0:
                sublime.set_timeout(self.choose_object(ring, app = os.path.dirname(files[1])), 0)
            return
        else:
            file_ = files[sel - 1]
            if transient:
                flags = sublime.TRANSIENT
            else:
                flags = 0
                self.switch_back_view = None
            sublime.active_window().open_file(file_, flags)

        