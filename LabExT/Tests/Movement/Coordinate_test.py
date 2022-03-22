import unittest
from LabExT.Movement.Transformations import ChipCoordinate, Coordinate, StageCoordinate

class FooTest(unittest.TestCase):

    def setUp(self) -> None:
        self.a = StageCoordinate.from_list([1,2,3])
        self.b = ChipCoordinate.from_list([1,2,3])

        self.c = StageCoordinate.from_list([4,5,6])

    def test_foo(self):
        breakpoint()