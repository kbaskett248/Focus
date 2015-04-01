import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

import sublime_plugin

from .tools.classes import get_ring_file
from .tools.settings import get_translate_on_save


class MTRingFileEventListener(sublime_plugin.EventListener):

    def get_file_for_view(self, view):
        return get_ring_file(view.file_name())

    def on_post_save_async(self, view):
        s = get_translate_on_save()

        if isinstance(s, dict):
            ext = os.path.splitext(view.file_name())[1][1:]
            try:
                s = s[ext]
            except KeyError:
                s = False

        if s:
            ring_file = self.get_file_for_view(view)
            if ((ring_file is not None) and
                    ring_file.is_translatable()):
                view.run_command('translate_ring_file',
                                 {"encoding": "ascii",
                                  "exec_cmd": "enhanced_exec",
                                  "startup_info": False})
