import platform
import pytest

from ...tools import focus


test_data = [
    ("C:\Program Files (x86)\PTCT-AP\SoloFocus\PTCTDEV.Universe\DEV25.Ring\PgmSource\HHA\HhaAdvisory.EditAdvisory.I.focus",
     'PTCTDEV', 'DEV25', True,
     'C:\Program Files (x86)\PTCT-AP\SoloFocus\PTCTDEV.Universe\DEV25.Ring',
     'C:\ProgramData\MEDITECH\PTCTDEV.Universe\DEV25.Ring.Local'),
    ("C:\Program Files (x86)\PTCT-AP\SoloFocus\PTCTDEV.Universe\DEV25.Ring\System\RTTools\\b-File.fs",
     'PTCTDEV', 'DEV25', True,
     'C:\Program Files (x86)\PTCT-AP\SoloFocus\PTCTDEV.Universe\DEV25.Ring',
     'C:\ProgramData\MEDITECH\PTCTDEV.Universe\DEV25.Ring.Local'),
    ("C:\Program Files (x86)\MEDITECH\PTCTQA.Universe\QA26.Ring\PgmObject\Hha\HhaInterface.ReadMessageFromPort.P.mps",
     'PTCTQA', 'QA26', False,
     'C:\Program Files (x86)\MEDITECH\PTCTQA.Universe\QA26.Ring',
     'C:\ProgramData\MEDITECH\PTCTQA.Universe\QA26.Ring'),
    ("C:\ProgramData\MEDITECH\PTCTDEV.Universe\S2.7.Ring\!AllUsers\Sys\PgmCache\Ring\PgmObject\Hha\HhaBrowser.Common.ImportExport.C!!00000000000000.mcs",
     'PTCTDEV', 'S2.7', False,
     'C:\Program Files (x86)\MEDITECH\PTCTDEV.Universe\S2.7.Ring',
     'C:\ProgramData\MEDITECH\PTCTDEV.Universe\S2.7.Ring'),
    ("C:\ProgramData\MEDITECH\PTCTDEV.Universe\DEV25.Ring.Local\!AllUsers\Sys\PgmCache\Ring\PgmObject\Hha\HhaBatch.Tools.C.mcs",
     'PTCTDEV', 'DEV25', True,
     'C:\Program Files (x86)\PTCT-AP\SoloFocus\PTCTDEV.Universe\DEV25.Ring',
     'C:\ProgramData\MEDITECH\PTCTDEV.Universe\DEV25.Ring.Local'),
    ('C:\Magic\Test.txt', None, None, False, '', '')
]


@pytest.mark.parametrize('file_path, universe, ring, is_local',
                         [(f, u, r, l) for f, u, r, l, rp, cp in test_data])
def test_parse_ring_path(file_path, universe, ring, is_local):
    assert focus.parse_ring_path(file_path) == (universe, ring, is_local)


windows_version = int(platform.win32_ver()[1].split('.', 1)[0])


@pytest.mark.parametrize(
    'result', [
        pytest.mark.skipif(
            windows_version > 5,
            reason='New windows version')(
                'C:\Documents and Settings\\all users\\Application Data\\Meditech'),
        pytest.mark.skipif(
            windows_version <= 5,
            reason='Old windows version')('C:\ProgramData\MEDITECH')
    ])
def test_get_cache_root(result):
    assert focus.get_cache_root().lower() == result.lower()


@pytest.mark.parametrize('args, expected', [
                         ('A', 'A'),
                         (['A'], (chr(1) + 'A' + chr(2)))
                         ])
def test_convert_to_focus_lists(args, expected):
    assert focus.convert_to_focus_lists(args) == expected


@pytest.mark.parametrize('universe, ring, is_local, ring_path, cache_path',
                         [(u, r, l, rp.lower(), cp.lower())
                          for f, u, r, l, rp, cp in test_data if (u and r)])
def test_get_ring_locations(universe, ring, is_local, ring_path, cache_path):
    rp, cp = focus.get_ring_locations(universe, ring, is_local)
    assert (rp.lower(), cp.lower()) == (ring_path, cache_path)


@pytest.mark.parametrize('universe', [None, '', 'PTCTDEV'])
@pytest.mark.parametrize('ring', [None, '', 'DEV25'])
@pytest.mark.parametrize('is_local', [None, False])
def test_error_get_ring_locations(universe, ring, is_local):
    if (not universe) or (not ring):
        with pytest.raises(NotADirectoryError):
            focus.get_ring_locations(universe, ring, is_local)
    else:
        rp, cp = focus.get_ring_locations(universe, ring, is_local)
        assert (rp.lower(), cp.lower()) == (
            'C:\Program Files (x86)\MEDITECH\PTCTDEV.Universe\DEV25.Ring'.lower(),
            'C:\ProgramData\MEDITECH\PTCTDEV.Universe\DEV25.Ring'.lower())
