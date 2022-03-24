#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from contextlib import contextmanager
from functools import wraps
import time
import numpy as np
from typing import Dict, Type
from enum import Enum, auto

from LabExT.Movement.Transformations import AxesRotation, Axis, ChipCoordinate, Coordinate, CoordinatePairing, KabschRotation, SinglePointTransformation, StageCoordinate, Transformation
from LabExT.Movement.Stage import Stage, StageError


class CalibrationError(RuntimeError):
    pass


class Orientation(Enum):
    """
    Enumerate different state orientations.
    """
    LEFT = auto()
    RIGHT = auto()
    TOP = auto()
    BOTTOM = auto()

    def __str__(self) -> str:
        return self.name.capitalize()


class DevicePort(Enum):
    """Enumerate different device ports."""
    INPUT = auto()
    OUTPUT = auto()

    def __str__(self) -> str:
        return self.name.capitalize()


class State(Enum):
    """
    Enumerate different calibration states.
    """
    NOT_CONFIGURED = 0
    CONNECTED = 1
    COORDINATE_SYSTEM_FIXED = 2
    SINGLE_POINT_FIXED = 3
    FULLY_CALIBRATED = 4

    def __lt__(self, other):
        """
        Defines a total ordering.
        """
        if self.__class__ is other.__class__:
            return self.value < other.value
        return NotImplemented

    def __str__(self) -> str:
        return self.name.replace('_', ' ').capitalize()

def assert_min_state_by_coordinate_system(constraints: Dict[Type[Coordinate], State]):
    """
    Use this decorator to assert that the calibration has at least a certain state for a given cooridnate system.
    """
    def assert_state(func):
        @wraps(func)
        def wrapper(calibration, *args, **kwargs):
            if calibration.current_coordinate_system is None:
                raise CalibrationError(
                    "Function {} needs a cooridnate system to operate in. Please use the context to set the system.".format(
                        func.__name__))

            asserted_state =  constraints.get(calibration.current_coordinate_system)
            if not asserted_state:
                raise ValueError("Unsupported coordinate system: {}".format(calibration.current_coordinate_system))

            if calibration.state < asserted_state:
                raise CalibrationError(
                    "Function {} needs at least a calibration state of {} to operate in coordinate system {}".format(
                        func.__name__, asserted_state, calibration.current_coordinate_system))

            return func(calibration, *args, **kwargs)
        return wrapper
    return assert_state

class Calibration:
    """
    Represents a calibration of one stage.
    """

    def __init__(self, mover, stage, orientation, device_port) -> None:
        self.mover = mover
        self.stage: Type[Stage] = stage

        self._state = State.CONNECTED if stage.connected else State.NOT_CONFIGURED
        self._orientation = orientation
        self._device_port = device_port

        self._axes_rotation: Type[AxesRotation] = AxesRotation()
        self._single_point_transformation: Type[Transformation] = SinglePointTransformation(self._axes_rotation)
        self._full_transformation: Type[Transformation] = KabschRotation()

        self.current_coordinate_system: Type[Coordinate] = None

    #
    #   Representation
    #

    def __str__(self) -> str:
        return "{} Stage ({})".format(str(self.orientation), str(self.stage))

    @property
    def short_str(self) -> str:
        return "{} Stage ({})".format(
            str(self.orientation), str(self._device_port))

    #
    #   Context to set current coordinate system
    #

    @contextmanager
    def in_coordinate_system(self, coordinate_system: Type[Coordinate]):
        self.current_coordinate_system = coordinate_system
        try:
            yield
        finally:
            self.current_coordinate_system = None

    #
    #   
    #


    def connect_to_stage(self):
        """
        Opens a connections to the stage.
        """
        self.stage.connect()
        self.determine_state()

    def disconnect_from_stage(self):
        """
        Closes connections to the stage.
        """
        self.stage.disconnect()
        self.determine_state()


    @property
    def axes_rotation(self):
        return self._axes_rotation

    def update_axes_rotation(self, chip_axis, direction, stage_axis):
        self._axes_rotation.update(chip_axis, direction, stage_axis)
        self.determine_state(skip_connection=True)

    @property
    def single_point_transformation(self):
        return self._single_point_transformation

    def update_single_point_transformation(self, pairing: Type[CoordinatePairing]):
        self._single_point_transformation.update(pairing)
        self.determine_state(skip_connection=True)

    @property
    def full_transformation(self):
        return self._full_transformation

    def update_full_transformation(self, pairing: Type[CoordinatePairing]):
        self._full_transformation.update(pairing)
        self.determine_state(skip_connection=True)

    #
    #   Properties
    #

    @property
    def state(self) -> State:
        """
        Returns the current calibration state.
        """
        return self._state

    @property
    def orientation(self) -> Orientation:
        """
        Returns the orientation of the stage: Left, Right, Top or Bottom
        """
        return self._orientation

    @property
    def is_input_stage(self):
        """
        Returns True if the stage will move to the input of a device.
        """
        return self._device_port == DevicePort.INPUT

    @property
    def is_output_stage(self):
        """
        Returns True if the stage will move to the output of a device.
        """
        return self._device_port == DevicePort.OUTPUT

    #
    #   Calibration Setup Methods
    #

    def reset(self) -> bool:
        """
        Resets calibration by removing
        axes rotation, single point fixation and full calibration.
        """
        self.axes_rotation.reset()
        self.single_point_transformation.reset()
        self.full_transformation.reset()
        self._state = State.CONNECTED if self.stage.connected else State.NOT_CONFIGURED

        return True

    def determine_state(self, skip_connection = False):
        """
        Determines the status of the calibration independently of the status variables of the instance.
        1. Checks whether the stage responds. If yes, status is at least CONNECTED.      
        2. Checks if axis rotation is valid. If Yes, status is at least COORDINATE SYSTEM FIXED.
        3. Checks if single point fixation is valid. If Yes, status is at least SINGLE POINT FIXED.
        4. Checks if full calibration is valid. If Yes, status is FULLY CALIBRATED.
        """
        # Reset state
        self._state = State.NOT_CONFIGURED

        # 1. Check if stage responds
        if not skip_connection:
            try:
                if self.stage is None or self.stage.get_status() is None:
                    return
                self._state = State.CONNECTED
            except StageError:
                return
        else:
            self._state = State.CONNECTED

        assert self._state == State.CONNECTED

        # 2. Check if axis rotation is valid
        if self.axes_rotation is None or not self.axes_rotation.is_valid:
            return
        self._state = State.COORDINATE_SYSTEM_FIXED

        assert self._state == State.COORDINATE_SYSTEM_FIXED

        # 3. Check if single point fixation is valid
        if self.single_point_transformation is None or not self.single_point_transformation.is_valid:
            return
        self._state = State.SINGLE_POINT_FIXED

        assert self._state == State.SINGLE_POINT_FIXED

        # 4. Check if Full Calibration is valid
        if self.full_transformation is None or not self.full_transformation.is_valid:
            return

        self._state = State.FULLY_CALIBRATED

    #
    #   Position Methods
    #

    @property
    @assert_min_state_by_coordinate_system({
        StageCoordinate: State.CONNECTED,
        ChipCoordinate: State.SINGLE_POINT_FIXED
    })
    def position(self) -> Type[Coordinate]:
        """
        Returns the current positions of the stage in the specified system.
        """
        # Return position in stage coordinate.
        if self.current_coordinate_system == StageCoordinate:
            return StageCoordinate.from_list(self.stage.position)

        # Return position in chip coordinate.
        if self.current_coordinate_system == ChipCoordinate:
            if self.state == State.FULLY_CALIBRATED:
                return self.full_transformation.stage_to_chip(
                    StageCoordinate.from_list(self.stage.position))
            elif self.state == State.SINGLE_POINT_FIXED:
                return self.single_point_transformation.stage_to_chip(
                    StageCoordinate.from_list(self.stage.position))

    #
    #   Movement methods
    #

    @assert_min_state_by_coordinate_system({
        StageCoordinate: State.CONNECTED,
        ChipCoordinate: State.COORDINATE_SYSTEM_FIXED
    })
    def move_relative(self, relative_difference: Type[Coordinate]):
        """
        Moves the stage relative to the specified coordinate system.
        """
        # Move stage relative in stage coordinates
        if self.current_coordinate_system == StageCoordinate:
            assert type(relative_difference) in (Coordinate, StageCoordinate), "Use pass a stage coordinate to move the stage relative in stage coordinates."
            stage_relative_difference = relative_difference
        # Move stage relative in chip cooridnates
        elif self.current_coordinate_system == ChipCoordinate:
            assert type(relative_difference) in (Coordinate, ChipCoordinate), "Use pass a chip coordinate to move the stage relative in chip coordinates."
            stage_relative_difference = self.axes_rotation.rotate_chip_to_stage(relative_difference)

        self.stage.move_relative(
            x=stage_relative_difference.x,
            y=stage_relative_difference.y,
            z=stage_relative_difference.z 
        )

    @assert_min_state_by_coordinate_system({
        StageCoordinate: State.CONNECTED,
        ChipCoordinate: State.SINGLE_POINT_FIXED
    })
    def move_absolute(self, coordinate: Type[Coordinate]):
        """
        Moves the stage absolute in the specified cooridnate system.
        """
        # Move stage absolute in stage cooridnates
        if self.current_coordinate_system == StageCoordinate:
            assert type(coordinate) in (Coordinate, StageCoordinate), "Use pass a stage coordinate to move the stage absolute in stage coordinates."
            stage_coordinate = coordinate
        elif self.current_coordinate_system == ChipCoordinate:
            assert type(coordinate) in (Coordinate, ChipCoordinate), "Use pass a chip coordinate to move the stage absolute in chip coordinates."
            if self.state == State.FULLY_CALIBRATED:
                stage_coordinate = self.full_transformation.chip_to_stage(coordinate)
            elif self.state == State.SINGLE_POINT_FIXED:
                stage_coordinate == self.single_point_transformation.chip_to_stage(coordinate)

        self.stage.move_absolute(
            x=stage_coordinate.x,
            y=stage_coordinate.y,
            z=stage_coordinate.z
        )

    def wiggle_axis(
        self,
        wiggle_axis: Axis,
        wiggle_distance=1e3,
        wiggle_speed=1e3):
        """
        Wiggles the requested axis positioner in order to enable the user to test the correct direction and axis mapping.
        """

        current_speed_xy = self.stage.get_speed_xy()
        current_speed_z = self.stage.get_speed_z()

        self.stage.set_speed_xy(wiggle_speed)
        self.stage.set_speed_z(wiggle_speed)

        wiggle_difference = np.array([wiggle_distance if wiggle_axis == axis else 0 for axis in Axis])
        with self.in_coordinate_system(ChipCoordinate):
            self.move_relative(ChipCoordinate.from_array(wiggle_difference))
            time.sleep(2)
            self.move_relative(ChipCoordinate.from_array(-wiggle_difference))

        self.stage.set_speed_xy(current_speed_xy)
        self.stage.set_speed_z(current_speed_z)
