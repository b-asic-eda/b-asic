import pytest

from b_asic import Addition, Constant, Signal, Butterfly


@pytest.fixture
def operation():
    return Constant(2)

@pytest.fixture
def operation_tree():
    """Valid addition operation connected with 2 constants.
    2---+
        |
        v
       add = 2 + 3 = 5
        ^
        |
    3---+
    """
    return Addition(Constant(2), Constant(3))

@pytest.fixture
def large_operation_tree():
    """Valid addition operation connected with a large operation tree with 2 other additions and 4 constants.
    2---+
        |
        v
       add---+
        ^    |
        |    |
    3---+    v
            add = (2 + 3) + (4 + 5) = 14
    4---+    ^
        |    |
        v    |
       add---+
        ^
        |
    5---+
    """
    return Addition(Addition(Constant(2), Constant(3)), Addition(Constant(4), Constant(5)))

@pytest.fixture
def large_operation_tree_names():
    """Valid addition operation connected with a large operation tree with 2 other additions and 4 constants.
    With names.
    2---+
        |
        v
       add---+
        ^    |
        |    |
    3---+    v
            add = (2 + 3) + (4 + 5) = 14
    4---+    ^
        |    |
        v    |
       add---+
        ^
        |
    5---+
    """
    return Addition(Addition(Constant(2, name="constant2"), Constant(3, name="constant3")), Addition(Constant(4, name="constant4"), Constant(5, name="constant5")))

@pytest.fixture
def butterfly_operation_tree():
    """Valid butterfly operations connected to eachother with 3 butterfly operations and 2 constants as inputs and 2 outputs.
    2 ---+       +--- (2 + 4) ---+       +--- (6 + (-2)) ---+       +--- (4 + 8) ---> out1 = 12
         |       |               |       |                  |       |
         v       ^               v       ^                  v       ^
         butterfly               butterfly                  butterfly
         ^       v               ^       v                  ^       v
         |       |               |       |                  |       |               
    4 ---+       +--- (2 - 4) ---+       +--- (6 - (-2)) ---+       +--- (4 - 8) ---> out2 = -4
    """
    return Butterfly(*(Butterfly(*(Butterfly(Constant(2), Constant(4), name="bfly3").outputs), name="bfly2").outputs), name="bfly1")

@pytest.fixture
def operation_graph_with_cycle():
    """Invalid addition operation connected with an operation graph containing a cycle.
     +-+
     | |
     v |
    add+---+
     ^     |
     |     v
     7    add = (? + 7) + 6 = ?
           ^
           |
           6
    """
    add1 = Addition(None, Constant(7))
    add1.input(0).connect(add1)
    return Addition(add1, Constant(6))
