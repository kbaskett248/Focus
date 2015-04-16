import webbrowser

import sublime_plugin

import logging
logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')


class OpenWebPageCommand(sublime_plugin.WindowCommand):

    def run(self, url=''):
        if url:
            webbrowser.open(url)

    def is_visible(self, url=''):
        return bool(url)
