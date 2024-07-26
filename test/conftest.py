import os
from distutils import dir_util
from test.fixtures.operation_tree import *
from test.fixtures.port import *
from test.fixtures.resources import *
from test.fixtures.schedule import *
from test.fixtures.signal import signal, signals  # noqa: F401
from test.fixtures.signal_flow_graph import *

import pytest


@pytest.fixture
def datadir(tmpdir, request):
    filename = request.module.__file__
    test_dir, ext = os.path.splitext(filename)

    if os.path.isdir(test_dir):
        dir_util.copy_tree(test_dir, str(tmpdir))

    return tmpdir
