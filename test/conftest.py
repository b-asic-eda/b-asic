from test.fixtures.operation_tree import *
from test.fixtures.port import *
from test.fixtures.schedule import *
from test.fixtures.signal import signal, signals
from test.fixtures.signal_flow_graph import *

from distutils import dir_util
import os

import pytest


@pytest.fixture
def datadir(tmpdir, request):
    print(tmpdir, request)
    filename = request.module.__file__
    print(filename)
    test_dir, ext = os.path.splitext(filename)
    print(test_dir, ext)

    if os.path.isdir(test_dir):
        dir_util.copy_tree(test_dir, str(tmpdir))

    return tmpdir
