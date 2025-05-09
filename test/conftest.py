import os
import shutil

import pytest

from test.fixtures.integration import *
from test.fixtures.operation_tree import *
from test.fixtures.port import *
from test.fixtures.resources import *
from test.fixtures.schedule import *
from test.fixtures.signal import signal, signals  # noqa: F401
from test.fixtures.signal_flow_graph import *


@pytest.fixture
def datadir(tmpdir, request):
    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)

    if os.path.isdir(test_dir):
        shutil.copytree(test_dir, str(tmpdir), dirs_exist_ok=True)

    return tmpdir
