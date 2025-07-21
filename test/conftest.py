import shutil
from pathlib import Path

import pytest

from test.fixtures.architecture import *
from test.fixtures.integration import *
from test.fixtures.operation_tree import *
from test.fixtures.port import *
from test.fixtures.resources import *
from test.fixtures.schedule import *
from test.fixtures.signal import signal, signals  # noqa: F401
from test.fixtures.signal_flow_graph import *


@pytest.fixture
def datadir(tmpdir, request):
    filepath = Path(request.module.__file__)

    test_dir = filepath.parent / filepath.stem

    if test_dir.is_dir():
        shutil.copytree(test_dir, Path(tmpdir), dirs_exist_ok=True)

    return tmpdir
