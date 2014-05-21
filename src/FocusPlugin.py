import inspect
import imp
import importlib
import os
import sys
import zipfile

try:
    import sublimelogging
    logger = sublimelogging.getLogger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

class FocusPlugin(object):
    """Parent Class for any object that is dynamically loaded and returned."""

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls)

    def api_call(func):
        def api_func(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.exception('Exception occurred in FocusPlugin')
        return api_func

    @classmethod
    def import_plugins(cls, modules_to_skip = []):
        """Imports and returns all plugins that are descended from this class."""

        # Build a dictionary of each extending class pointed to its module
        classes = dict()
        for name, module in cls._get_module_list():
            if module in sys.modules.keys():
                logger.info('Module %s already loaded', module)
                mod = sys.modules[module]
            else:
                logger.info('Importing %s', module)
                mod = importlib.import_module(module)
            for name, _cls in inspect.getmembers(mod, cls.isextendingclass):
                classes[_cls.__name__] = mod

        logger.debug('classes = %s', classes)

        # Build a list of modules that need reloading
        # Build a list of classes based on those that are already in memory
        modules_to_reload = [(cls.__name__, classes[cls.__name__])]
        classes_to_check = cls.__subclasses__()
        plugin_names = []
        while classes_to_check:
            c = classes_to_check.pop()
            modules_to_reload.append((c.__name__, classes[c.__name__]))
            if c.__subclasses__():
                classes_to_check.extend(c.__subclasses__())
            else:
                plugin_names.append(c.__name__)

        # Reload all plugins in order, from parent to subclass
        already_reloaded = set()
        for c, m in modules_to_reload:
            if m not in already_reloaded:
                m = imp.reload(m)
                already_reloaded.add(m)
            else:
                m = sys.modules[m.__name__]
            classes[c] = m

        logger.debug('classes = %s', classes)
        logger.info('plugin_names = %s', plugin_names)

        # Build a set of plugin classes from the reloaded modules if they are 
        # in the list of plugin names.
        plugins = set()
        for c, m in classes.items():
            if c in plugin_names:
                for name, _cls in inspect.getmembers(m, cls.isextendingclass):
                    if name in plugin_names:
                        plugins.add(_cls)
                
        logger.info('plugins: %s', plugins)
        return plugins

    @classmethod
    def issubclass(cls, object_):
        if inspect.isclass(object_):
            if cls.__name__ in [c.__name__ for c in object_.__mro__]:
                if not object_.__subclasses__():
                    return True
        return False

    @classmethod
    def isextendingclass(cls, object_):
        if inspect.isclass(object_):
            if cls.__name__ in [c.__name__ for c in object_.__mro__]:
                return True
        return False

    @classmethod
    def _get_module_list(cls):
        """Returns a list of (name, module) for plugins descended from this class."""
        module_list = []
        path, plugin_name = os.path.split(inspect.getfile(cls))
        if os.path.isdir(path):
            index = path.find('Focus')
            partial_path = path[index:]
            logger.debug('Importing %s plugins from %s', plugin_name, path)
            logger.debug('partial_path: %s', partial_path)
            module_prefix = partial_path.replace('\\','.')
            logger.debug('module_prefix: %s', module_prefix)
            module_list = [(d[:-3], '%s.%s' % (module_prefix, d[:-3])) 
                    for d in os.listdir(path) 
                    if (d.lower().endswith('.py'))]
        elif ('.sublime-package' in path):
            with zipfile.ZipFile(path) as zip_file:
                namelist = zip_file.namelist()
            partial_path = '/'.join(plugin_name.split('.')[1:-1])
            plugin_name = '%s.py' % plugin_name.split('.')[-1]
            plugin_path = '%s/%s' % (partial_path, plugin_name)
            logger.debug('Importing %s plugins from %s', plugin_name, path)
            logger.debug('partial_path: %s', partial_path)
            module_list = [(os.path.basename(d)[:-3], 'Focus.%s' % d.replace('/','.')[:-3]) 
                           for d in namelist if (d.lower().endswith('.py') and 
                                                 (partial_path.lower() in d.lower()))]
        logger.debug('module_list: %s', module_list)
        return module_list