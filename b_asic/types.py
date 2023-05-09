from typing import NewType, Union

# https://stackoverflow.com/questions/69334475/how-to-hint-at-number-types-i-e-subclasses-of-number-not-numbers-themselv
Num = Union[int, float, complex]

NumRuntime = (complex, float, int)


Name = str
# # We want to be able to initialize Name with String literals, but still have the
# # benefit of static type checking that we don't pass non-names to name locations.
# # However, until python 3.11 a string literal type was not available. In those
# # versions, we'll fall back on just aliasing `str` => Name.
# if sys.version_info >= (3, 11):
#     from typing import LiteralString
#     Name: TypeAlias = NewType("Name", str) | LiteralString
# else:
#     Name = str

TypeName = NewType("TypeName", str)
GraphID = NewType("GraphID", str)
GraphIDNumber = NewType("GraphIDNumber", int)
