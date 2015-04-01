import Focus.classes.rings
import Focus.classes.ring_files
import Focus.classes.views


def get_ring(path):
    return Focus.classes.rings.Ring.get_ring(path)


def get_backup_ring():
    return Focus.classes.rings.Ring.get_backup_ring()


def is_local_ring(ring):
    return isinstance(ring, Focus.classes.rings.LocalRing)


def is_homecare_ring(ring):
    return isinstance(ring, Focus.classes.rings.HomeCareRing)


def list_rings(**kwargs):
    return Focus.classes.rings.Ring.list_rings(**kwargs)


def get_ring_by_id(ring):
    return Focus.classes.rings.Ring.get_ring_by_id(ring)


def get_ring_file(file_name):
    return Focus.classes.ring_files.RingFile.get_ring_file(file_name)


def is_focus_file(ring_file):
    return isinstance(ring_file, Focus.classes.ring_files.FocusFile)


def get_view(view):
    return Focus.classes.views.RingView.get_view(view)


def is_focus_view(ring_view):
    return isinstance(ring_view, Focus.classes.views.FocusView)


def is_fs_view(ring_view):
    return isinstance(ring_view, Focus.classes.views.FSView)
