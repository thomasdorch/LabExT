#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from random import choice, sample
import pytest
import unittest
from unittest.mock import Mock, call, patch
from parameterized import parameterized
import numpy as np
from os.path import join

from LabExT.Wafer.Chip import Chip
from LabExT.Tests.Utils import with_stage_discovery_patch
from LabExT.Movement.Transformations import ChipCoordinate, CoordinatePairing, Direction, KabschRotation, StageCoordinate
from LabExT.Movement.MoverNew import MoverNew
from LabExT.Movement.Stage import Stage, StageError
from LabExT.Movement.Stages.DummyStage import DummyStage
from LabExT.Movement.Calibration import AxesRotation, Axis, Calibration, CalibrationError, DevicePort, Orientation, State, assert_min_state_by_coordinate_system    

class AssertMinStateByCoordinateSystem(unittest.TestCase):
    @with_stage_discovery_patch
    def setUp(self, available_stages_mock, stage_classes_mock) -> None:
        stage_classes_mock.return_value = []
        available_stages_mock.return_value = []
        
        self.mover = MoverNew(None)
        self.stage = DummyStage('usb:123456789')

        self.calibration = self.mover.add_stage_calibration(self.stage, Orientation.LEFT, DevicePort.INPUT)
    
        self.function = Mock()
        self.function.__name__ = "Dummy Function"

    def test_raises_error_if_coordinate_system_is_not_fixed(self):
        self.calibration.current_coordinate_system = None

        with self.assertRaises(CalibrationError):
            assert_min_state_by_coordinate_system({})(self.function)(self.calibration)
        
        self.function.assert_not_called()

    def test_raises_error_if_coordinate_system_is_unknown(self):
        with self.calibration.in_coordinate_system(ChipCoordinate):
            with self.assertRaises(ValueError):
                assert_min_state_by_coordinate_system({ "my_system": None })(self.function)(self.calibration)
        
            
            self.function.assert_not_called()

    @parameterized.expand([
        (State.NOT_CONFIGURED, State.CONNECTED),
        (State.NOT_CONFIGURED, State.COORDINATE_SYSTEM_FIXED),
        (State.NOT_CONFIGURED, State.SINGLE_POINT_FIXED),
        (State.NOT_CONFIGURED, State.FULLY_CALIBRATED),
        (State.CONNECTED, State.COORDINATE_SYSTEM_FIXED),
        (State.CONNECTED, State.SINGLE_POINT_FIXED),
        (State.CONNECTED, State.FULLY_CALIBRATED),
        (State.COORDINATE_SYSTEM_FIXED, State.SINGLE_POINT_FIXED),
        (State.COORDINATE_SYSTEM_FIXED, State.FULLY_CALIBRATED),
        (State.SINGLE_POINT_FIXED, State.FULLY_CALIBRATED),
    ])
    def test_raises_error_if_required_state_is_higher_than_given(self, given_state, required_state):
        self.calibration._state = given_state

        with self.calibration.in_coordinate_system(ChipCoordinate):
            with self.assertRaises(CalibrationError):
                assert_min_state_by_coordinate_system({ChipCoordinate: required_state })(self.function)(self.calibration)
        
            
            self.function.assert_not_called()

    @parameterized.expand([
        (State.NOT_CONFIGURED, State.NOT_CONFIGURED),
        (State.CONNECTED, State.NOT_CONFIGURED),
        (State.CONNECTED, State.CONNECTED),
        (State.COORDINATE_SYSTEM_FIXED, State.NOT_CONFIGURED),
        (State.COORDINATE_SYSTEM_FIXED, State.CONNECTED),
        (State.COORDINATE_SYSTEM_FIXED, State.COORDINATE_SYSTEM_FIXED),
        (State.SINGLE_POINT_FIXED, State.NOT_CONFIGURED),
        (State.SINGLE_POINT_FIXED, State.CONNECTED),
        (State.SINGLE_POINT_FIXED, State.COORDINATE_SYSTEM_FIXED),
        (State.SINGLE_POINT_FIXED, State.SINGLE_POINT_FIXED),
        (State.FULLY_CALIBRATED, State.NOT_CONFIGURED),
        (State.FULLY_CALIBRATED, State.CONNECTED),
        (State.FULLY_CALIBRATED, State.COORDINATE_SYSTEM_FIXED),
        (State.FULLY_CALIBRATED, State.SINGLE_POINT_FIXED),
        (State.FULLY_CALIBRATED, State.FULLY_CALIBRATED),
    ])
    def test_execute_function_if_required_state_is_lower_than_given(self, given_state, required_state):
        self.calibration._state = given_state

        with self.calibration.in_coordinate_system(ChipCoordinate):
            assert_min_state_by_coordinate_system({ChipCoordinate: required_state })(self.function)(self.calibration)

            self.function.assert_called_once()

class CalibrationTest(unittest.TestCase):
    @with_stage_discovery_patch
    def setUp(self, available_stages_mock, stage_classes_mock) -> None:
        stage_classes_mock.return_value = []
        available_stages_mock.return_value = []
        
        self.chip = Chip(join(pytest.fixture_folder, "QuarkJaejaChip.csv"))
        self.experiment_manager = Mock()
        self.experiment_manager.chip = self.chip

        self.mover = MoverNew(self.experiment_manager)
        self.stage = DummyStage('usb:123456789')

        self.calibration = self.mover.add_stage_calibration(self.stage, Orientation.LEFT, DevicePort.INPUT)
    

    def setup_random_full_transformation(self):
        for _ in range(3):
            stage_coordinate = StageCoordinate(*sample(range(-10000, 10000), 3))
            device = choice(list(self.chip._devices.values()))
            self.calibration.update_full_transformation(
                CoordinatePairing(
                    self.calibration,
                    stage_coordinate,
                    device,
                    device.input_coordinate))

    @parameterized.expand([
        (None,), (ChipCoordinate,), (StageCoordinate,)
    ])
    def test_set_current_coordinate_system(self, system):
        self.calibration.current_coordinate_system = system
        self.assertEqual(self.calibration.current_coordinate_system, system)

    @parameterized.expand([
        ("None",), ("chip",), ("stage",), (1,), (object,), (StageCoordinate(),), (ChipCoordinate(),)
    ])
    def test_set_current_coordinate_system_invalid(self, system):
        with self.assertRaises(ValueError):
            self.calibration.current_coordinate_system = system

    @parameterized.expand([
        (ChipCoordinate,), (StageCoordinate,)
    ])
    def test_in_coordinate_system_sets_system(self, system):
        self.assertIsNone(self.calibration.current_coordinate_system)

        with self.calibration.in_coordinate_system(system):
            self.assertEqual(self.calibration.current_coordinate_system, system)

        self.assertIsNone(self.calibration.current_coordinate_system)

    def test_in_coordinate_system_sets_system_does_not_accept_none(self):
        with self.assertRaises(ValueError):
            with self.calibration.in_coordinate_system(None):
                pass


    def test_position_in_stage_coordinates_unconnected(self):
        with self.calibration.in_coordinate_system(StageCoordinate):
            with self.assertRaises(CalibrationError):
                self.calibration.position

    def test_position_in_stage_coordinates_connected(self):
        self.calibration.connect_to_stage()
        stage_position = self.stage.position

        with self.calibration.in_coordinate_system(StageCoordinate):
            stage_coordinate = self.calibration.position
            self.assertEqual(type(stage_coordinate), StageCoordinate)
            self.assertEqual(stage_coordinate.to_list(), stage_position)

    def test_position_in_chip_coordinates_without_single_point_fixation(self):
        self.calibration.connect_to_stage()

        with self.calibration.in_coordinate_system(ChipCoordinate):
            with self.assertRaises(CalibrationError):
                self.calibration.position

    def test_position_in_chip_coordinates_without_full_calibration(self):
        self.calibration.connect_to_stage()
        stage_posiiton = self.stage.position

        self.calibration.update_single_point_transformation(CoordinatePairing(
            self.calibration,
            StageCoordinate(1,2,3),
            object(),
            ChipCoordinate(4,5,6)
        ))

        with self.calibration.in_coordinate_system(ChipCoordinate):
            chip_cooridnate = self.calibration.position
            self.assertEqual(type(chip_cooridnate), ChipCoordinate)
            self.assertEqual(
                chip_cooridnate.to_list(),
                self.calibration.single_point_transformation.stage_to_chip(
                    StageCoordinate(*stage_posiiton)
            ).to_list())

    def test_position_in_chip_coordinates_with_full_calibration(self):
        self.calibration.connect_to_stage()
        stage_posiiton = self.stage.position

        self.calibration.update_single_point_transformation(CoordinatePairing(
            self.calibration,
            StageCoordinate(1,2,3),
            object(),
            ChipCoordinate(4,5,6)
        ))

        self.setup_random_full_transformation()

        with self.calibration.in_coordinate_system(ChipCoordinate):
            chip_cooridnate = self.calibration.position
            self.assertEqual(type(chip_cooridnate), ChipCoordinate)
            self.assertEqual(
                chip_cooridnate.to_list(),
                self.calibration.full_transformation.stage_to_chip(
                    StageCoordinate(*stage_posiiton)
            ).to_list())

    @patch.object(DummyStage, "move_relative")
    def test_move_relative_in_stage_coordinates(self, move_relative_patch):
        with self.assertRaises(CalibrationError):
            self.calibration.move_relative(StageCoordinate(1,2,3))

        self.calibration.connect_to_stage()

        with self.calibration.in_coordinate_system(StageCoordinate):
            self.calibration.move_relative(StageCoordinate(1,2,3))

        move_relative_patch.assert_called_once_with(x=1, y=2, z=3)

    @parameterized.expand([
        (Axis.X, Axis.Y, Axis.Z),
        (Axis.X, Axis.Z, Axis.Y),
        (Axis.Y, Axis.X, Axis.Z),
        (Axis.Y, Axis.Z, Axis.X),
        (Axis.Z, Axis.X, Axis.Y),
        (Axis.Z, Axis.Y, Axis.X)
    ])
    def test_move_relative_in_chip_coordinates(self, x_axis, y_axis, z_axis):
        self.calibration.connect_to_stage()

        self.calibration.update_axes_rotation(Axis.X, Direction.POSITIVE, x_axis)
        self.calibration.update_axes_rotation(Axis.Y, Direction.POSITIVE, y_axis)
        self.calibration.update_axes_rotation(Axis.Z, Direction.POSITIVE, z_axis)

        with patch.object(DummyStage, "move_relative") as move_relative_patch:
            relative_chip_diff = ChipCoordinate(1,2,3)

            with self.calibration.in_coordinate_system(ChipCoordinate):
                self.calibration.move_relative(relative_chip_diff)

            expected_difference = self.calibration.axes_rotation.rotate_chip_to_stage(relative_chip_diff)

            move_relative_patch.assert_called_once_with(
                x=expected_difference.x,
                y=expected_difference.y,
                z=expected_difference.z)

    @patch.object(DummyStage, "move_absolute")
    def test_move_absolute_in_stage_coordinates(self, move_absolute_patch):
        with self.assertRaises(CalibrationError):
            self.calibration.move_absolute(StageCoordinate(1,2,3))

        self.calibration.connect_to_stage()

        with self.calibration.in_coordinate_system(StageCoordinate):
            self.calibration.move_absolute(StageCoordinate(1,2,3))

        move_absolute_patch.assert_called_once_with(x=1, y=2, z=3)

    @patch.object(DummyStage, "move_absolute")
    def test_move_absolute_in_chip_coordinates_with_single_point_transformation(self, move_absolute_patch):
        self.calibration.connect_to_stage()

        with self.calibration.in_coordinate_system(ChipCoordinate):
            with self.assertRaises(CalibrationError):
                self.calibration.move_absolute(ChipCoordinate(1,2,3))

        self.calibration.update_single_point_transformation(CoordinatePairing(
            self.calibration,
            StageCoordinate(1,2,3),
            object(),
            ChipCoordinate(4,5,6)
        ))

        chip_coordinate = ChipCoordinate(1,2,3)
        with self.calibration.in_coordinate_system(ChipCoordinate):
            self.calibration.move_absolute(ChipCoordinate(1,2,3))

        expected_coordinate = self.calibration.single_point_transformation.chip_to_stage(chip_coordinate)

        move_absolute_patch.assert_called_once_with(
            x=expected_coordinate.x,
            y=expected_coordinate.y,
            z=expected_coordinate.z)

    @patch.object(DummyStage, "move_absolute")
    def test_move_absolute_in_chip_coordinates_with_full_transformation(self, move_absolute_patch):
        self.calibration.connect_to_stage()

        self.calibration.update_single_point_transformation(CoordinatePairing(
            self.calibration,
            StageCoordinate(1,2,3),
            object(),
            ChipCoordinate(4,5,6)
        ))

        self.setup_random_full_transformation()

        chip_coordinate = ChipCoordinate(1,2,3)
        with self.calibration.in_coordinate_system(ChipCoordinate):
            self.calibration.move_absolute(ChipCoordinate(1,2,3))

        expected_coordinate = self.calibration.full_transformation.chip_to_stage(chip_coordinate)

        move_absolute_patch.assert_called_once_with(
            x=expected_coordinate.x,
            y=expected_coordinate.y,
            z=expected_coordinate.z)

    def test_wiggle_axis_raises_error_if_axes_rotation_is_invalid(self):
        self.calibration.update_axes_rotation(
            chip_axis=Axis.X,
            stage_axis=Axis.Y,
            direction=Direction.POSITIVE)

        with self.assertRaises(CalibrationError):
            self.calibration.wiggle_axis(Axis.X)

    @patch.object(DummyStage, "move_relative")
    def test_wiggle_axis_with_rotation(self, move_relative_mock):
        self.calibration.connect_to_stage()

        self.calibration.update_axes_rotation(
            chip_axis=Axis.X,
            stage_axis=Axis.Y,
            direction=Direction.NEGATIVE)
        self.calibration.update_axes_rotation(
            chip_axis=Axis.Y,
            stage_axis=Axis.Z,
            direction=Direction.POSITIVE)
        self.calibration.update_axes_rotation(
            chip_axis=Axis.Z,
            stage_axis=Axis.X,
            direction=Direction.NEGATIVE)

        self.assertTrue(self.calibration.axes_rotation.is_valid)
        wiggle_distance = 2000
        expected_movement_calls = [
            call(x=0, y=-2000.0, z=0), call(x=0, y=2000.0, z=0),
            call(x=0, y=0, z=2000.0), call(x=0, y=0, z=-2000.0),
            call(x=-2000.0, y=0, z=0), call(x=2000.0, y=0, z=0),
        ]

        self.calibration.wiggle_axis(Axis.X, wiggle_distance)
        self.calibration.wiggle_axis(Axis.Y, wiggle_distance)
        self.calibration.wiggle_axis(Axis.Z, wiggle_distance)

        move_relative_mock.assert_has_calls(expected_movement_calls)

    @patch.object(DummyStage, "move_relative")
    @patch.object(DummyStage, "set_speed_xy")
    @patch.object(DummyStage, "set_speed_z")
    def test_wiggle_axis_sets_and_resets_speed(
            self,
            set_speed_z_mock,
            set_speed_xy_mock,
            move_relative_mock):
        current_speed_xy = self.stage._speed_xy
        current_speed_z = self.stage._speed_z

        self.calibration.connect_to_stage()

        self.calibration.wiggle_axis(Axis.X, wiggle_speed=5000)

        move_relative_mock.assert_has_calls(
            [call(x=1000.0, y=0, z=0), call(x=-1000.0, y=0, z=0)])
        set_speed_z_mock.assert_has_calls([call(5000), call(current_speed_z)])
        set_speed_xy_mock.assert_has_calls(
            [call(5000), call(current_speed_xy)])

