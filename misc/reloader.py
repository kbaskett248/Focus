# Borrowed from Will Bond, https://github.com/wbond

from imp import reload
import logging
import sys

import sublime_plugin

logger = logging.getLogger(__name__)
logger.setLevel('INFO')


# Python allows reloading modules on the fly, which allows us to do live
# upgrades. The only caveat to this is that you have to reload in the
# dependency order.
#
# Thus is module A depends on B and we don't reload B before A, when A is
# reloaded it will still have a reference to the old B. Thus we hard-code the
# dependency order of the various Package Control modules so they get reloaded
# properly.
#
# There are solutions for doing this all programatically, but this is much
# easier to understand.

reload_mods = []
for mod in sys.modules:
    if ((mod.lower().startswith('mtfocuscommon')) and
            (sys.modules[mod] is not None)):
        reload_mods.append(mod)

mod_prefix = 'MTFocusCommon.'

mods_load_order = [
    'tools.general',
    'tools.focus',
    'tools.load_translator_completions',
    'tools.settings',
    'tools.snippets',
    'tools.sublime',
    'tools',

    'classes',
    'classes.compatibility',
    'classes.metaclasses',
    'classes.code_blocks',
    'classes.rings',
    'classes.ring_files',
    'classes.views',

    'Lib.bs4'
]

plugins_load_order = [
    'MTFocusCommon.OnQueryContextCommands',
    'MTFocusFileTools.MTFileCommands',
    'MTFocusFileTools.MTFileDocLink',
    'MTFocusFileTools.MTIncludeFileCompletions',
    'MTFocusFileTools.MTRingCompletions',
    'MTFocusFileTools.MTViewCommands',
    'MTFocusFileTools.MTViewCompletions',
    'MTFocusRingTools.Commands'
]

if reload_mods:
    logger.info('reloading modules from MTFocusCommon')
for suffix in mods_load_order:
    mod = mod_prefix + suffix
    logger.debug("checking %s", mod)
    if mod in reload_mods:
        logger.info("reloading %s", mod)
        reload(sys.modules[mod])


# We just want to reload the plugins if it isn't the first load, so we're
# saving the state of the API when this file is loaded.
Reload_Plugins = sublime_plugin.api_ready


def _plugin_loaded():
    if Reload_Plugins:
        logger.info('reloading packages that reference MTFocusCommon')
        for plugin in plugins_load_order:
            if plugin in sys.modules:
                sublime_plugin.reload_plugin(plugin)
