#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""


from itertools import permutations, product
from random import randrange, sample, choice
import unittest
from unittest.mock import Mock
import pytest
from os.path import join

from LabExT import rmsd
from LabExT.Wafer.Chip import Chip
from parameterized import parameterized

import numpy as np


from LabExT.Movement.Transformations import ChipCoordinate, Coordinate, CoordinatePairing, KabschRotation, StageCoordinate, AxesRotation, Axis, Direction, SinglePointTransformation

def kabsch_model(
        stage_coords,
        chip_coords):

    # translate coordinates to origin
    stage_offset = rmsd.centroid(stage_coords)
    stage_coords = stage_coords - stage_offset
    chip_offset = rmsd.centroid(chip_coords)
    chip_coords = chip_coords - chip_offset

    # calculate rotation matrix using kabsch algorithm
    matrix = rmsd.kabsch(chip_coords, stage_coords)

    return matrix, chip_offset, stage_offset


class CoordinateTest(unittest.TestCase):
    @parameterized.expand([
        ([1,2,3,4], 1,2,3),
        ([1,2,3], 1,2,3),
        ([1,2], 1,2,0),
        ([1], 1,0,0),
        ([], 0,0,0),
   ])
    def test_from_list(self, list, x, y, z):
        cooridnate = Coordinate.from_list(list)
        self.assertEqual(cooridnate.x, x)
        self.assertEqual(cooridnate.y, y)
        self.assertEqual(cooridnate.z, z)

    @parameterized.expand([
        (np.array([1,2,3,4]), 1,2,3),
        (np.array([1,2,3]), 1,2,3),
        (np.array([1,2]), 1,2,0),
        (np.array([1]), 1,0,0),
        (np.array([]), 0,0,0),
   ])
    def test_from_array(self, array, x, y, z):
        cooridnate = Coordinate.from_array(array)
        self.assertEqual(cooridnate.x, x)
        self.assertEqual(cooridnate.y, y)
        self.assertEqual(cooridnate.z, z)

    def test_to_list(self):
        self.assertEqual(Coordinate(1,2,3).to_list(), [1,2,3])

    def test_to_list(self):
        self.assertTrue(np.array_equal(
            Coordinate(1,2,3).to_array(), np.array([1,2,3])
        ))

    @parameterized.expand([
        ([1,2,3,4], [5,6,7,8], [6,8,10]),
        ([1,2,3], [4,5,6], [5,7,9]),
        ([1,2], [3,4], [4,6,0]),
        ([1], [2], [3,0,0]),
        ([], [], [0,0,0]),
    ])
    def test_addition_with_valid_types(self, addend1, addend2, expected_sum):
        sum = Coordinate.from_list(addend1) + Coordinate.from_list(addend2)
        self.assertEqual(type(sum), Coordinate)
        self.assertEqual(sum.to_list(), expected_sum)

        sum = StageCoordinate.from_list(addend1) + StageCoordinate.from_list(addend2)
        self.assertEqual(type(sum), StageCoordinate)
        self.assertEqual(sum.to_list(), expected_sum)

        sum = ChipCoordinate.from_list(addend1) + ChipCoordinate.from_list(addend2)
        self.assertEqual(type(sum), ChipCoordinate)
        self.assertEqual(sum.to_list(), expected_sum)


    def test_addition_with_invalid_types(self):
        with self.assertRaises(ValueError):
            StageCoordinate(1,2,3) + ChipCoordinate(4,5,6)

        with self.assertRaises(ValueError):
            StageCoordinate(1,2,3) + Coordinate(4,5,6)

        with self.assertRaises(ValueError):
            ChipCoordinate(1,2,3) + Coordinate(4,5,6)

        with self.assertRaises(ValueError):
            Coordinate(1,2,3) + [4,5,6]

        with self.assertRaises(ValueError):
            Coordinate(1,2,3) + np.array([4,5,6])

    @parameterized.expand([
        ([1,2,3,4], [5,6,7,8], [-4,-4,-4]),
        ([1,2,3], [4,5,6], [-3,-3,-3]),
        ([1,2], [3,4], [-2,-2,0]),
        ([1], [2], [-1,0,0]),
        ([], [], [0,0,0]),
    ])
    def test_substraction_with_valid_types(self, minute, subtrahend, expected_difference):
        difference = Coordinate.from_list(minute) - Coordinate.from_list(subtrahend)
        self.assertEqual(type(difference), Coordinate)
        self.assertEqual(difference.to_list(), expected_difference)

        difference = StageCoordinate.from_list(minute) - StageCoordinate.from_list(subtrahend)
        self.assertEqual(type(difference), StageCoordinate)
        self.assertEqual(difference.to_list(), expected_difference)

        difference = ChipCoordinate.from_list(minute) - ChipCoordinate.from_list(subtrahend)
        self.assertEqual(type(difference), ChipCoordinate)
        self.assertEqual(difference.to_list(), expected_difference)


    def test_substraction_with_invalid_types(self):
        with self.assertRaises(ValueError):
            StageCoordinate(1,2,3) - ChipCoordinate(4,5,6)

        with self.assertRaises(ValueError):
            StageCoordinate(1,2,3) - Coordinate(4,5,6)

        with self.assertRaises(ValueError):
            ChipCoordinate(1,2,3) - Coordinate(4,5,6)

        with self.assertRaises(ValueError):
            Coordinate(1,2,3) - [4,5,6]

        with self.assertRaises(ValueError):
            Coordinate(1,2,3) - np.array([4,5,6])

class AxesRotationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.rotation = AxesRotation()
        return super().setUp()

    def test_default_case(self):
        self.assertTrue((self.rotation._matrix == np.identity(3)).all())
        self.assertTrue(self.rotation.is_valid)

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):
            self.rotation.update("X", Direction.POSITIVE, Axis.X)

        with self.assertRaises(ValueError):
            self.rotation.update(Axis.X, Direction.POSITIVE, "X")

        with self.assertRaises(ValueError):
            self.rotation.update(Axis.X,  "positive", Axis.X)

    def test_double_x_axis_assignment(self):
        self.rotation.update(Axis.X, Direction.POSITIVE, Axis.Y)
        self.assertFalse(self.rotation.is_valid)
        self.assertEqual(self.rotation.get_mapped_stage_axis(Axis.X), (Direction.POSITIVE, Axis.Y))

        self.rotation.update(Axis.Y, Direction.POSITIVE, Axis.X)
        self.assertTrue(self.rotation.is_valid)
        self.assertEqual(self.rotation.get_mapped_stage_axis(Axis.Y), (Direction.POSITIVE, Axis.X))

    def test_double_y_axis_assignment(self):
        self.rotation.update(Axis.Y, Direction.POSITIVE, Axis.X)
        self.assertFalse(self.rotation.is_valid)
        self.assertEqual(self.rotation.get_mapped_stage_axis(Axis.Y), (Direction.POSITIVE, Axis.X))

        self.rotation.update(Axis.X, Direction.POSITIVE, Axis.Y)
        self.assertTrue(self.rotation.is_valid)
        self.assertEqual(self.rotation.get_mapped_stage_axis(Axis.X), (Direction.POSITIVE, Axis.Y))

    def test_double_z_axis_assignment(self):
        self.rotation.update(Axis.Z, Direction.POSITIVE, Axis.Y)
        self.assertFalse(self.rotation.is_valid)
        self.assertEqual(self.rotation.get_mapped_stage_axis(Axis.Z), (Direction.POSITIVE, Axis.Y))

        self.rotation.update(Axis.Y, Direction.POSITIVE, Axis.Z)
        self.assertTrue(self.rotation.is_valid)
        self.assertEqual(self.rotation.get_mapped_stage_axis(Axis.Y), (Direction.POSITIVE, Axis.Z))

    def test_switch_x_and_y_axis(self):
        self.rotation.update(Axis.X, Direction.NEGATIVE, Axis.Y)
        self.assertTrue(np.array_equal(self.rotation._matrix, np.array([
            np.array((0, 0, 0)), np.array((-1, 1, 0)), np.array((0, 0, 1)),
        ])))
        self.assertFalse(self.rotation.is_valid)

        self.rotation.update(Axis.Y, Direction.POSITIVE, Axis.X)
        self.assertTrue(np.array_equal(self.rotation._matrix, np.array([
            np.array((0, 1, 0)), np.array((-1, 0, 0)), np.array((0, 0, 1)),
        ])))
        self.assertTrue(self.rotation.is_valid)

        chip_cooridnate = ChipCoordinate(1,2,3)
        self.assertEqual(self.rotation.rotate_chip_to_stage(chip_cooridnate).to_list(), [2,-1,3])

        stage_coordinate = StageCoordinate(1,2,3)
        self.assertEqual(self.rotation.rotate_stage_to_chip(stage_coordinate).to_list(), [-2,1,3])

    def test_switch_x_and_z_axis(self):
        self.rotation.update(Axis.X,  Direction.POSITIVE, Axis.Z)
        self.assertTrue(np.array_equal(self.rotation._matrix, np.array([
            np.array((0, 0, 0)), np.array((0, 1, 0)), np.array((1, 0, 1)),
        ])))
        self.assertFalse(self.rotation.is_valid)

        self.rotation.update(Axis.Z, Direction.NEGATIVE, Axis.X)
        self.assertTrue(np.array_equal(self.rotation._matrix, np.array([
            np.array((0, 0, -1)), np.array((0, 1, 0)), np.array((1, 0, 0)),
        ])))
        self.assertTrue(self.rotation.is_valid)

        chip_cooridnate = ChipCoordinate(1,2,3)
        self.assertEqual(self.rotation.rotate_chip_to_stage(chip_cooridnate).to_list(), [-3,2,1])

        stage_coordinate = StageCoordinate(1,2,3)
        self.assertEqual(self.rotation.rotate_stage_to_chip(stage_coordinate).to_list(), [3,2,-1])

    def test_switch_y_and_z_axis(self):
        self.rotation.update(Axis.Z, Direction.NEGATIVE, Axis.Y)
        self.assertTrue(np.array_equal(self.rotation._matrix, np.array([
            np.array((1, 0, 0)), np.array((0, 1, -1)), np.array((0, 0, 0)),
        ])))
        self.assertFalse(self.rotation.is_valid)

        self.rotation.update(Axis.Y, Direction.POSITIVE, Axis.Z)
        self.assertTrue(np.array_equal(self.rotation._matrix, np.array([
            np.array((1, 0, 0)), np.array((0, 0, -1)), np.array((0, 1, 0)),
        ])))
        self.assertTrue(self.rotation.is_valid)

        chip_cooridnate = ChipCoordinate(1,2,3)
        self.assertEqual(self.rotation.rotate_chip_to_stage(chip_cooridnate).to_list(), [1,-3,2])

        stage_coordinate = StageCoordinate(1,2,3)
        self.assertEqual(self.rotation.rotate_stage_to_chip(stage_coordinate).to_list(), [1,3,-2])


    def test_all_permutations(self):
        input_chip_coordinate = ChipCoordinate(*[1,2,3])
        expected_stage_coordinates = list(permutations([1,2,3]))

        for i, (chip_x_axis, chip_y_axis, chip_z_axis) in enumerate(permutations(Axis)):
            for (x_axis_direction, y_axis_direction, z_axis_direction) in product(Direction, repeat=3): 
                expected_stage_coordinate = np.array([x_axis_direction.value, y_axis_direction.value, z_axis_direction.value]) * np.array(expected_stage_coordinates[i])

                self.rotation.update(chip_x_axis, x_axis_direction, Axis.X)
                self.rotation.update(chip_y_axis, y_axis_direction, Axis.Y)
                self.rotation.update(chip_z_axis, z_axis_direction, Axis.Z)

                self.assertTrue(self.rotation.is_valid)

                stage_coordinate = self.rotation.rotate_chip_to_stage(input_chip_coordinate)
                chip_coordinate = self.rotation.rotate_stage_to_chip(StageCoordinate(*expected_stage_coordinate))

                self.assertEqual(type(stage_coordinate), StageCoordinate)
                self.assertEqual(type(chip_coordinate), ChipCoordinate)

                self.assertTrue(np.array_equal(
                    stage_coordinate.to_array(), expected_stage_coordinate
                ), "{} not equal to {}".format(stage_coordinate, expected_stage_coordinate))

                self.assertTrue(np.array_equal(
                    input_chip_coordinate.to_array(), chip_coordinate.to_array()
                ), "{} not equal to {}".format(stage_coordinate, expected_stage_coordinate))

                self.assertEqual(
                    input_chip_coordinate.to_list(),
                    self.rotation.rotate_stage_to_chip(self.rotation.rotate_chip_to_stage(input_chip_coordinate)).to_list())

                self.assertTrue(np.array_equal(
                    expected_stage_coordinate,
                    self.rotation.rotate_chip_to_stage(self.rotation.rotate_stage_to_chip(StageCoordinate(*expected_stage_coordinate))).to_array()))


class SinglePointTransformationTest(unittest.TestCase):

    def setUp(self) -> None:
        self.rotation = AxesRotation()
        self.transformation = SinglePointTransformation(self.rotation)

    @parameterized.expand([
        (-1000, 1000),
        (-10000, 10000),
        (-100000, 100000)
    ])
    def test_foo(self,  upper, lower):
        for (chip_x_axis, chip_y_axis, chip_z_axis) in permutations(Axis):
            for (x_axis_direction, y_axis_direction, z_axis_direction) in product(Direction, repeat=3): 
            
                self.rotation.update(chip_x_axis, x_axis_direction, Axis.X)
                self.rotation.update(chip_y_axis, y_axis_direction, Axis.Y)
                self.rotation.update(chip_z_axis, z_axis_direction, Axis.Z)

                chip_coordinate = ChipCoordinate(*sample(range(upper, lower), 2), z=0)
                stage_coordinate = StageCoordinate(*sample(range(upper, lower), 3))

                self.transformation.update(CoordinatePairing(
                    object(),
                    stage_coordinate,
                    object(),
                    chip_coordinate
                ))

                self.assertEqual(self.transformation.chip_to_stage(chip_coordinate).to_list(), stage_coordinate.to_list())
                self.assertEqual(self.transformation.stage_to_chip(stage_coordinate).to_list(), chip_coordinate.to_list())



class KabschRotationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.kabsch = KabschRotation()
        self.chip = Chip(join(pytest.fixture_folder, "QuarkJaejaChip.csv"))


    @parameterized.expand([
        (-1000, 1000, [3, 4, 5, 10, 100, 1000]),
        (-10000, 10000, [3, 4, 5, 10, 100, 1000]),
        (-100000, 100000, [3, 4, 5, 10, 100, 1000])
    ])
    def test_with_golden_model(self, upper, lower, points):
        
        stage_coords = np.empty((0, 3), float)
        chip_coords = np.empty((0, 3), float)

        for num_points in points:
            stage_coordinate = StageCoordinate(*sample(range(upper, lower), 3))
            device = choice(list(self.chip._devices.values()))
            self.kabsch.update(
                CoordinatePairing(
                    Mock(),
                    stage_coordinate,
                    device,
                    device.input_coordinate))

            stage_coords = np.append(
                stage_coords,
                [stage_coordinate.to_array()],
                axis=0)

            chip_coords = np.append(
                chip_coords,
                [device.input_coordinate.to_array()],
                axis=0)

        self.assertTrue(self.kabsch.is_valid)


        matrix, chip_offset, stage_offset = kabsch_model(stage_coords, chip_coords)

        self.assertTrue(
            np.allclose(
                matrix,
                self.kabsch._rotation.as_matrix()))
        self.assertTrue(np.allclose(chip_offset, self.kabsch._chip_offset.to_array()))
        self.assertTrue(np.allclose(stage_offset, self.kabsch._stage_offset.to_array()))


        chip_input = ChipCoordinate(*sample(range(upper, lower), 3))
        stage_input = StageCoordinate(*sample(range(upper, lower), 3))

        self.assertTrue(np.allclose(
            np.dot(chip_input.to_array() - chip_offset, matrix) + stage_offset,
            self.kabsch.chip_to_stage(chip_input).to_array()
        ))

        self.assertTrue(np.allclose(
            np.dot(stage_input.to_array() - stage_offset, np.linalg.inv(matrix)) + chip_offset,
            self.kabsch.stage_to_chip(stage_input).to_array()
        ))

        self.assertTrue(np.allclose(
            chip_input.to_array(),
            self.kabsch.stage_to_chip(self.kabsch.chip_to_stage(chip_input)).to_array()
        ))

        self.assertTrue(np.allclose(
            stage_input.to_array(),
            self.kabsch.chip_to_stage(self.kabsch.stage_to_chip(stage_input)).to_array()
        ))
