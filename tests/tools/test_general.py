from copy import deepcopy
import os
import pytest
import random

from ...tools import general


rand_string = " Asperiores recusandae labore aut ut odio. "


test_data = []
test_data.append(
    {'string': ':Code FunctionName\n',
     'reg_ex': r":(Code|List) +(\S.*)",
     'match_group': 2,
     'span': (6, 18),
     'value': 'FunctionName'}
)


def pytest_generate_tests(metafunc):
    func_name = metafunc.function.__name__
    if ((func_name == 'test_string_match') or
            (func_name == 'test_string_search')):
        test_cases = []
        for data in deepcopy(test_data):
            string = data.pop('string')
            reg_ex = data.pop('reg_ex')
            span = data.pop('span')
            value = data.pop('value')

            kwargs = data

            test_cases.append((string, reg_ex, kwargs.copy(), span, value))

            alt_string = string + rand_string
            test_cases.append((alt_string, reg_ex, kwargs.copy(), span, value))

            alt_string = rand_string + string + rand_string
            if func_name == 'test_string_match':
                test_cases.append(
                    (alt_string, reg_ex, kwargs.copy(), None, None))
            elif func_name == 'test_string_search':
                l = len(rand_string)
                span = (span[0] + l, span[1] + l)
                test_cases.append(
                    (alt_string, reg_ex, kwargs.copy(), span, value))

        for string, reg_ex, kwargs, span, value in test_cases.copy():
            kwargs = kwargs.copy()
            kwargs['base_point'] = 10
            if span:
                span = (span[0] + 10, span[1] + 10)
            test_cases.append((string, reg_ex, kwargs, span, value))

        metafunc.parametrize('string, reg_ex, kwargs, span, value', test_cases)

    elif (func_name == 'test_extract_entity'):
        test_cases = []
        for data in deepcopy(test_data):
            string = data.pop('string')
            reg_ex = data.pop('reg_ex')
            span = data.pop('span')
            value = data.pop('value')
            point = random.randint(*span)

            kwargs = data

            test_cases.append(
                (string, reg_ex, point, kwargs.copy(), span, value))

            alt_string = string + rand_string
            test_cases.append(
                (alt_string, reg_ex, point, kwargs.copy(), span, value))

            alt_string = rand_string + string + rand_string
            l = len(rand_string)
            span = (span[0] + l, span[1] + l)
            point += l
            test_cases.append(
                (alt_string, reg_ex, point, kwargs.copy(), span, value))

        for string, reg_ex, point, kwargs, span, value in test_cases.copy():
            kwargs = kwargs.copy()
            kwargs['base_point'] = 10
            if span:
                span = (span[0] + 10, span[1] + 10)
                point += 10
            test_cases.append((string, reg_ex, point, kwargs, span, value))

        metafunc.parametrize('string, reg_ex, point, kwargs, span, value',
                             test_cases)


def test_string_match(string, reg_ex, kwargs, span, value):
    assert general.string_match(string, reg_ex, **kwargs) == (span, value)


def test_string_search(string, reg_ex, kwargs, span, value):
    assert general.string_search(string, reg_ex, **kwargs) == (span, value)


def test_extract_entity(string, reg_ex, point, kwargs, span, value):
    assert general.extract_entity(
        reg_ex, string, point, **kwargs) == (span, value)


@pytest.mark.parametrize('path', [
        "C:\Program Files (x86)\PTCT-AP\SoloFocus\PTCTDEV.Universe\DEV25.Ring\PgmSource\HHA\HhaAdvisory.EditAdvisory.I.focus",
        "C:\ProgramData\MEDITECH\PTCTDEV.Universe\DEV25.Ring.Local\!AllUsers\Sys\PgmCache\Ring\PgmObject\Hha\HhaBatch.Tools.C.mcs"
    ])
def test_merge_paths(path):
    parts = path.split(os.sep)
    i = (random.randint(0, len(parts) - 1), random.randint(0, len(parts) - 1))
    p1 = os.sep.join(parts[:max(i)])
    p2 = os.sep.join(parts[min(i):])
    print(p1, p2)
    assert general.merge_paths(p1, p2) == path


def test_create_folder_success(tmpdir):
    path = str(tmpdir.dirpath('Temporary', 'Folder'))
    general.create_folder(path)
    assert os.path.exists(path)
    assert os.path.isdir(path)
    general.create_folder(path)
    assert os.path.exists(path)
    assert os.path.isdir(path)


def test_create_folder_failure(tmpdir):
    path = str(tmpdir.join(':?$'))

    with pytest.raises(OSError):
        general.create_folder(path)
