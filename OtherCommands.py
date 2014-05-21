import os
import re
import webbrowser

import sublime
import sublime_plugin

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class OpenFilPageCommand(sublime_plugin.WindowCommand):
    """Opens the test plan, tech design, design or public test plan for a FIL.
       If fil_number is "project", the current window's project is checked. If
       it contains FIL, the number contained in the project title is used as
       the fil number."""

    Pages = {'Design': 'FIL_${fil_number}', 
             'Public Test Plan': 'FIL_${fil_number}_PublicTestPlan', 
             'Technical Design': 'FIL_${fil_number}_TechnicalDesign', 
             'Test Plan': 'FIL_${fil_number}_TestPlan'}

    WikiUrl = 'http://ptdoc.ptct.com/mwiki/index.php/'
    
    def run(self, fil_number = None, page = None):
        if (fil_number is None):
            self.window.show_input_panel('FIL Number', '', 
                lambda x: self.open_page(x, page), 
                None, None)
        elif (fil_number.lower() == 'project'):
            fil_number = self.parse_fil_number_from_project()
            if (fil_number is not None):
                self.open_page(fil_number, page)
        else:
            self.open_page(fil_number, page)

    def open_page(self, fil_number, page):
        if (page in self.Pages.keys()):
            url_part = self.Pages[page]
            url_part = url_part.replace('${fil_number}', fil_number)
            url = self.WikiUrl + url_part
            webbrowser.open(url)

    def parse_fil_number_from_project(self):
        result = None
        project_file = self.window.project_file_name()
        if (project_file is not None):
            project_file = os.path.basename(project_file).lower()
            match = re.match(r'fil\s*(\d{4,6})', project_file)
            if (match is not None):
                result = match.group(1)
        return result

    def is_enabled(self, fil_number = None, page = None):
        result = True
        if (page not in self.Pages.keys()):
            result = False
        elif ((fil_number is not None) and
              (fil_number.lower() == 'project') and 
              (self.parse_fil_number_from_project() is None)):
            result = False
        return result

class InsertInViewCommand(sublime_plugin.TextCommand):
    """A command to write a message to an open buffer."""

    def run(self, edit, string = ''):
        self.view.insert(edit, self.view.size(), string)

# class DebugListFilesCommand(sublime_plugin.ApplicationCommand):
#     """Debugging function to list the files managed by the file manager."""
    
#     def run(self):
#         print( Manager )
#         print( 'Focus Files:' )
#         for x in Manager.list_files():
#             print( '    ' + x.filename )
        
# class DebugListExcludedFilesCommand(sublime_plugin.ApplicationCommand):
#     """Debugging function to list the files that have been determined to not be Focus Files"""

#     def run(self):
#         print( Manager )
#         print( "Excluded Files:" )
#         for x in Manager.exclude_set:
#             print( '    ' + x )
