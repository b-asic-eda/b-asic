"""
B-ASIC test suite for the core operations.
"""

from b_asic.core_operations import Constant, Addition, Subtraction, Multiplication, Division, SquareRoot, ComplexConjugate, Max, Min, Absolute, ConstantMultiplication, ConstantAddition, ConstantSubtraction, ConstantDivision

# Constant tests.
def test_constant():
    constant_operation = Constant(3)
    assert constant_operation.evaluate() == 3

def test_constant_negative():
    constant_operation = Constant(-3)
    assert constant_operation.evaluate() == -3

def test_constant_complex():
    constant_operation = Constant(3+4j)
    assert constant_operation.evaluate() == 3+4j

# Addition tests.
def test_addition():
    test_operation = Addition()
    constant_operation = Constant(3)
    constant_operation_2 = Constant(5)
    assert test_operation.evaluate(constant_operation.evaluate(), constant_operation_2.evaluate()) == 8

def test_addition_negative():
    test_operation = Addition()
    constant_operation = Constant(-3)
    constant_operation_2 = Constant(-5)
    assert test_operation.evaluate(constant_operation.evaluate(), constant_operation_2.evaluate()) == -8

def test_addition_complex():
    test_operation = Addition()
    constant_operation = Constant((3+5j))
    constant_operation_2 = Constant((4+6j))
    assert test_operation.evaluate(constant_operation.evaluate(), constant_operation_2.evaluate()) == (7+11j)

# Subtraction tests.
def test_subtraction():
    test_operation = Subtraction()
    constant_operation = Constant(5)
    constant_operation_2 = Constant(3)
    assert test_operation.evaluate(constant_operation.evaluate(), constant_operation_2.evaluate()) == 2

def test_subtraction_negative():
    test_operation = Subtraction()
    constant_operation = Constant(-5)
    constant_operation_2 = Constant(-3)
    assert test_operation.evaluate(constant_operation.evaluate(), constant_operation_2.evaluate()) == -2

def test_subtraction_complex():
    test_operation = Subtraction()
    constant_operation = Constant((3+5j))
    constant_operation_2 = Constant((4+6j))
    assert test_operation.evaluate(constant_operation.evaluate(), constant_operation_2.evaluate()) == (-1-1j)

# Multiplication tests.
def test_multiplication():
    test_operation = Multiplication()
    constant_operation = Constant(5)
    constant_operation_2 = Constant(3)
    assert test_operation.evaluate(constant_operation.evaluate(), constant_operation_2.evaluate()) == 15

def test_multiplication_negative():
    test_operation = Multiplication()
    constant_operation = Constant(-5)
    constant_operation_2 = Constant(-3)
    assert test_operation.evaluate(constant_operation.evaluate(), constant_operation_2.evaluate()) == 15

def test_multiplication_complex():
    test_operation = Multiplication()
    constant_operation = Constant((3+5j))
    constant_operation_2 = Constant((4+6j))
    assert test_operation.evaluate(constant_operation.evaluate(), constant_operation_2.evaluate()) == (-18+38j)

# Division tests.
def test_division():
    test_operation = Division()
    constant_operation = Constant(30)
    constant_operation_2 = Constant(5)
    assert test_operation.evaluate(constant_operation.evaluate(), constant_operation_2.evaluate()) == 6

def test_division_negative():
    test_operation = Division()
    constant_operation = Constant(-30)
    constant_operation_2 = Constant(-5)
    assert test_operation.evaluate(constant_operation.evaluate(), constant_operation_2.evaluate()) == 6

def test_division_complex():
    test_operation = Division()
    constant_operation = Constant((60+40j))
    constant_operation_2 = Constant((10+20j))
    assert test_operation.evaluate(constant_operation.evaluate(), constant_operation_2.evaluate()) == (2.8-1.6j)

# SquareRoot tests.
def test_squareroot():
    test_operation = SquareRoot()
    constant_operation = Constant(36)
    assert test_operation.evaluate(constant_operation.evaluate()) == 6

def test_squareroot_negative():
    test_operation = SquareRoot()
    constant_operation = Constant(-36)
    assert test_operation.evaluate(constant_operation.evaluate()) == 6j

def test_squareroot_complex():
    test_operation = SquareRoot()
    constant_operation = Constant((48+64j))
    assert test_operation.evaluate(constant_operation.evaluate()) == (8+4j)

# ComplexConjugate tests.
def test_complexconjugate():
    test_operation = ComplexConjugate()
    constant_operation = Constant(3+4j)
    assert test_operation.evaluate(constant_operation.evaluate()) == (3-4j)

def test_test_complexconjugate_negative():
    test_operation = ComplexConjugate()
    constant_operation = Constant(-3-4j)
    assert test_operation.evaluate(constant_operation.evaluate()) == (-3+4j)

# Max tests.
def test_max():
    test_operation = Max()
    constant_operation = Constant(30)
    constant_operation_2 = Constant(5)
    assert test_operation.evaluate(constant_operation.evaluate(), constant_operation_2.evaluate()) == 30

def test_max_negative():
    test_operation = Max()
    constant_operation = Constant(-30)
    constant_operation_2 = Constant(-5)
    assert test_operation.evaluate(constant_operation.evaluate(), constant_operation_2.evaluate()) == -5

# Min tests.
def test_min():
    test_operation = Min()
    constant_operation = Constant(30)
    constant_operation_2 = Constant(5)
    assert test_operation.evaluate(constant_operation.evaluate(), constant_operation_2.evaluate()) == 5

def test_min_negative():
    test_operation = Min()
    constant_operation = Constant(-30)
    constant_operation_2 = Constant(-5)
    assert test_operation.evaluate(constant_operation.evaluate(), constant_operation_2.evaluate()) == -30

# Absolute tests.
def test_absolute():
    test_operation = Absolute()
    constant_operation = Constant(30)
    assert test_operation.evaluate(constant_operation.evaluate()) == 30

def test_absolute_negative():
    test_operation = Absolute()
    constant_operation = Constant(-5)
    assert test_operation.evaluate(constant_operation.evaluate()) == 5

def test_absolute_complex():
    test_operation = Absolute()
    constant_operation = Constant((3+4j))
    assert test_operation.evaluate(constant_operation.evaluate()) == 5.0

# ConstantMultiplication tests.
def test_constantmultiplication():
    test_operation = ConstantMultiplication(5)
    constant_operation = Constant(20)
    assert test_operation.evaluate(constant_operation.evaluate()) == 100

def test_constantmultiplication_negative():
    test_operation = ConstantMultiplication(5)
    constant_operation = Constant(-5)
    assert test_operation.evaluate(constant_operation.evaluate()) == -25

def test_constantmultiplication_complex():
    test_operation = ConstantMultiplication(3+2j)
    constant_operation = Constant((3+4j))
    assert test_operation.evaluate(constant_operation.evaluate()) == (1+18j)

# ConstantAddition tests.
def test_constantaddition():
    test_operation = ConstantAddition(5)
    constant_operation = Constant(20)
    assert test_operation.evaluate(constant_operation.evaluate()) == 25

def test_constantaddition_negative():
    test_operation = ConstantAddition(4)
    constant_operation = Constant(-5)
    assert test_operation.evaluate(constant_operation.evaluate()) == -1

def test_constantaddition_complex():
    test_operation = ConstantAddition(3+2j)
    constant_operation = Constant((3+4j))
    assert test_operation.evaluate(constant_operation.evaluate()) == (6+6j)

# ConstantSubtraction tests.
def test_constantsubtraction():
    test_operation = ConstantSubtraction(5)
    constant_operation = Constant(20)
    assert test_operation.evaluate(constant_operation.evaluate()) == 15

def test_constantsubtraction_negative():
    test_operation = ConstantSubtraction(4)
    constant_operation = Constant(-5)
    assert test_operation.evaluate(constant_operation.evaluate()) == -9

def test_constantsubtraction_complex():
    test_operation = ConstantSubtraction(4+6j)
    constant_operation = Constant((3+4j))
    assert test_operation.evaluate(constant_operation.evaluate()) == (-1-2j)

# ConstantDivision tests.
def test_constantdivision():
    test_operation = ConstantDivision(5)
    constant_operation = Constant(20)
    assert test_operation.evaluate(constant_operation.evaluate()) == 4

def test_constantdivision_negative():
    test_operation = ConstantDivision(4)
    constant_operation = Constant(-20)
    assert test_operation.evaluate(constant_operation.evaluate()) == -5

def test_constantdivision_complex():
    test_operation = ConstantDivision(2+2j)
    constant_operation = Constant((10+10j))
    assert test_operation.evaluate(constant_operation.evaluate()) == (5+0j)
