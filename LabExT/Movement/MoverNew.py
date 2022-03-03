#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from LabExT.Movement.Transformations import make_3d_coordinate
from bidict import bidict, ValueDuplicationError, KeyDuplicationError, OnDup, RAISE
from typing import Type, List
from functools import wraps

from LabExT.Movement.Stage import Stage
from LabExT.Movement.Calibration import Calibration, DevicePort, DevicePort, Orientation, State


def assert_connected_stages(func):
    """
    Use this decorator to assert that the mover has at least one connected stage,
    when calling methods, which require connected stages.
    """

    @wraps(func)
    def wrapper(mover, *args, **kwargs):
        if not mover.has_connected_stages:
            raise MoverError(
                "Function {} needs at least one connected stage. Please use the connection functions beforehand".format(
                    func.__name__))

        return func(mover, *args, **kwargs)
    return wrapper


class MoverError(RuntimeError):
    pass


class MoverNew:
    """
    Entrypoint for all movement in LabExT.
    """

    # For range constants: See SmarAct Control Guide for more details.
    # Both ranges are inclusive, e.g speed in [SPEED_LOWER_BOUND,
    # SPEED_UPPER_BOUND]
    SPEED_LOWER_BOUND = 0
    SPEED_UPPER_BOUND = 1e5

    ACCELERATION_LOWER_BOUND = 0
    ACCELERATION_UPPER_BOUND = 1e7

    # Reasonable default values
    DEFAULT_SPEED_XY = 200.0
    DEFAULT_SPEED_Z = 20.0
    DEFAULT_ACCELERATION_XY = 0.0

    DEFAULT_Z_LIFT = 20.0

    def __init__(self, experiment_manager):
        """Constructor.

        Parameters
        ----------
        experiment_manager : ExperimentManager
            Current instance of ExperimentManager.
        """
        self.experiment_manager = experiment_manager

        self._stage_classes: List[Stage] = []
        self._available_stages: List[Type[Stage]] = []

        # Mover state
        self._calibrations = bidict()
        self._port_by_orientation = bidict()
        self._speed_xy = None
        self._speed_z = None
        self._acceleration_xy = None
        self._z_lift = self.DEFAULT_SPEED_Z
        self._stages_lifted = False

        self.reload_stages()
        self.reload_stage_classes()

    def reset(self):
        """
        Resets Mover state.
        """
        self._calibrations = bidict()
        self._port_by_orientation = bidict()
        self._speed_xy = None
        self._speed_z = None
        self._acceleration_xy = None
        self._z_lift = self.DEFAULT_SPEED_Z

    def reset_calibrations(self):
        """
        Resets state for each calibration
        """
        for calibration in self.calibrations.values():
            calibration.reset()

    #
    #   Reload properties
    #

    def reload_stages(self) -> None:
        """
        Loads all available stages.
        """
        self._available_stages = Stage.find_available_stages()

    def reload_stage_classes(self) -> None:
        """
        Loads all Stage classes.
        """
        self._stage_classes = Stage.find_stage_classes()

    #
    #   Properties
    #

    @property
    def state(self) -> State:
        """
        Fetches states of all calibrations and returns the common one.
        Raises MoverError if not all calibrations are in the same state.
        """
        if not self.has_connected_stages:
            return State.UNINITIALIZED

        states = set(c.state for c in self.calibrations.values())
        if len(states) != 1:
            raise MoverError("Not all Stages are in the same state!")
        return states.pop()

    @property
    def stage_classes(self) -> List[Stage]:
        """
        Returns a list of all Stage classes.
        Read-only.
        """
        return self._stage_classes

    @property
    def available_stages(self) -> List[Type[Stage]]:
        """
        Returns a list of stages available to the computer (all possible connection types)
        For example: For SmarAct Stages, this function returns all USB-connected stages.
        Read-only.
        """
        return self._available_stages

    @property
    def calibrations(self):
        """
        Returns a mapping: Calibration -> (orientation, device_port) instance
        Read-only. Use add_stage_calibration to register a new stage.
        """

        return self._calibrations

    @property
    def active_stages(self) -> List[Type[Stage]]:
        """
        Returns a list of all active stages. A stage is called active if it has been assigned
        to an orientation and device port
        """
        return [c.stage for c in self._calibrations.values()]

    @property
    def connected_stages(self) -> List[Type[Stage]]:
        """
        Returns a list of all connected stages.
        """
        return [s for s in self.active_stages if s.connected]

    @property
    def has_connected_stages(self) -> bool:
        """
        Returns True if any of the connected stage is connected (opened a connection to the stage).
        """
        return len(self.connected_stages) > 0

    @property
    def left_calibration(self): return self._get_calibration(
        orientation=Orientation.LEFT)

    @property
    def right_calibration(self): return self._get_calibration(
        orientation=Orientation.RIGHT)

    @property
    def top_calibration(self): return self._get_calibration(
        orientation=Orientation.TOP)

    @property
    def bottom_calibration(self): return self._get_calibration(
        orientation=Orientation.BOTTOM)

    @property
    def input_calibration(self): return self._get_calibration(
        port=DevicePort.INPUT)

    @property
    def output_calibration(self): return self._get_calibration(
        port=DevicePort.OUTPUT)

    #
    #   Add new stage
    #

    def add_stage_calibration(
            self,
            stage: Type[Stage],
            orientation: Orientation,
            port: DevicePort) -> Type[Calibration]:
        """
        Creates a new Calibration instance for a stage.
        Adds this instance to the list of connected stages.

        Raises ValueError, if orientation or device port is invalid.
        Raises MoverError, if Stage has been used before.

        Returns new calibration instance.
        """
        if not isinstance(port, DevicePort):
            raise ValueError("{} is an invalid port".format(port))

        if not isinstance(orientation, Orientation):
            raise ValueError(
                "{} is an invalid orientation".format(orientation))

        try:
            self._port_by_orientation.put(
                orientation, port, OnDup(key=RAISE))
        except ValueDuplicationError:
            raise MoverError(
                "A stage has already been assigned for the {} port.".format(port))
        except KeyDuplicationError:
            raise MoverError(
                "A stage has already been assigned for {}.".format(orientation))

        calibration = Calibration(self, stage, orientation, port)

        if stage in self.active_stages:
            del self._port_by_orientation[orientation]
            raise MoverError(
                "Stage {} has already an assignment.".format(stage))

        self._calibrations.put(
            (orientation, port), calibration, OnDup(
                key=RAISE))
        return calibration

    #
    #   Stage Settings Methods
    #

    @property
    @assert_connected_stages
    def speed_xy(self) -> float:
        """
        Returns the XY speed of all connected stages.
        If a stage has a different speed than stored in the Mover object (self._speed_xy), it will be changed to the stored one.
        """
        if any(s.get_speed_xy() != self._speed_xy for s in self.connected_stages):
            self.speed_xy = self._speed_xy

        return self._speed_xy

    @speed_xy.setter
    @assert_connected_stages
    def speed_xy(self, umps: float):
        """
        Sets the XY speed for all connected stages to umps.
        Throws MoverError if a change of a stage fails. Stores the speed internally in the Mover object.
        """
        if umps < self.SPEED_LOWER_BOUND or umps > self.SPEED_UPPER_BOUND:
            raise ValueError("Speed for xy is out of valid range.")

        try:
            for stage in self.connected_stages:
                stage.set_speed_xy(umps)
        except RuntimeError as exec:
            raise MoverError("Setting xy speed failed: {}".format(exec))

        self._speed_xy = umps

    @property
    @assert_connected_stages
    def speed_z(self) -> float:
        """
        Returns the Z speed of all connected stages.
        If a stage has a different speed than stored in the Mover object (self._speed_z), it will be changed to the stored one.
        """
        if any(s.get_speed_z() != self._speed_z for s in self.connected_stages):
            self.speed_z = self._speed_z

        return self._speed_z

    @speed_z.setter
    @assert_connected_stages
    def speed_z(self, umps: float):
        """
        Sets the Z speed for all connected stages to umps.
        Throws MoverError if a change of a stage fails. Stores the speed internally in the Mover object.
        """
        if umps < self.SPEED_LOWER_BOUND or umps > self.SPEED_UPPER_BOUND:
            raise ValueError("Speed for z is out of valid range.")

        try:
            for stage in self.connected_stages:
                stage.set_speed_z(umps)
        except RuntimeError as exec:
            raise MoverError("Setting z speed failed: {}".format(exec))

        self._speed_z = umps

    @property
    @assert_connected_stages
    def acceleration_xy(self) -> float:
        """
        Returns the XY acceleration of all connected stages.
        If a stage has a different acceleration than stored in the Mover object (self._acceleration_xy), it will be changed to the stored one.
        """
        if any(s.get_acceleration_xy() !=
               self._acceleration_xy for s in self.connected_stages):
            self.acceleration_xy = self._acceleration_xy

        return self._acceleration_xy

    @acceleration_xy.setter
    @assert_connected_stages
    def acceleration_xy(self, umps2: float):
        """
        Sets the XY acceleration for all connected stages to umps.
        Throws MoverError if a change of a stage fails. Stores the acceleration internally in the Mover object.
        """
        if umps2 < self.ACCELERATION_LOWER_BOUND or umps2 > self.ACCELERATION_UPPER_BOUND:
            raise ValueError("Acceleration for xy is out of valid range.")

        try:
            for stage in self.connected_stages:
                stage.set_acceleration_xy(umps2)
        except RuntimeError as exec:
            raise MoverError("Acceleration xy speed failed: {}".format(exec))

        self._acceleration_xy = umps2

    @property
    def z_lift(self):
        """
        Returns the set value of how much the stage moves up
        :return: how much the stage moves up [um]
        """
        return self._z_lift

    @z_lift.setter
    def z_lift(self, height):
        """
        Sets the value of how much the stage moves up
        :param height: how much the stage moves up [um]
        """
        height = float(height)
        assert height >= 0.0, "Lift distance must be non-negative."
        self._z_lift = height

    #
    #   LEGACY SUPPORT!!
    #

    @assert_connected_stages
    def get_absolute_stage_coords(self):
        """Read stage positions in all two resp. four dimensions in um.

           return format for 2 stages is [lx, ly, rx, ry]
           return format for 1 stage is [lx, ly]

        Returns
        ----------
        list of double
            current absolute stage coordinates of all configured dimensions

        Raises
        ------
        RuntimeError
            If stages could not be initialised.
        """
        coords = []
        for stage in self.active_stages:
            coords += stage.get_current_position()

        return coords

    @assert_connected_stages
    def move_absolute_direct(self, *args):
        if self.left_calibration:
            self.left_calibration.stage.move_absolute([args[0], args[1], 0])
        if self.right_calibration:
            self.right_calibration.stage.move_absolute([args[2], args[3], 0])

    #
    #   Movement Methods
    #

    @assert_connected_stages
    def move_absolute(self, left=[], right=[], lift_z_dir=False, min_fiber_distance=1.1 * 125.0):
        if lift_z_dir:
            self.lift_stages()

        x0l = self.left_calibration.position[0]
        x0r = self.right_calibration.position[0]
        x1l = left[0]
        x1r = right[0]

        assert min_fiber_distance > 0.0, "Fiber distance must be greater than 0, otherwise half-planes of fibers overlap."
        assert x0l < x0r - min_fiber_distance, "For this collision avoidance algorithm to work, the left stage must " \
                                            "ALWAYS be left of the right stage. Starting points not far enough apart..."
        assert x1l < x1r - min_fiber_distance, "For this collision avoidance algorithm to work, the left stage must " \
                                            "ALWAYS be left of the right stage. Target points not far enough apart..."

        delta_l = x1l - x0l  # delta movement of x coordinate of left stage
        delta_r = x1r - x0r  # delta movement of x coordinate of right stage
        # case handling, depending on the half-plane's relative move
        # noinspection PyChainedComparisons
        if delta_l < 0 and delta_r < 0:
            # obv. left moves first
            #  1. move left stage from start to target
            #  2. move right stage from start to target
            self.left_calibration.move_absolute(left)
            self.right_calibration.move_absolute(right)
        elif delta_l < 0 and delta_r >= 0:
            # doesnt matter which one moves first as both move avay from each other
            #  1. move left stage from start to target
            #  2. move right stage from start to target
            self.left_calibration.move_absolute(left)
            self.right_calibration.move_absolute(right)
        elif delta_l >= 0 and delta_r < 0:
            # this can lead to collisions, but since end coordinates are also far enough apart, we are good to go
            #  1. move right stage from start to target
            #  2. move left stage from start to target
            self.right_calibration.move_absolute(right)
            self.left_calibration.move_absolute(left)
        elif delta_l >= 0 and delta_r >= 0:
            # obv. right moves first
            #  1. move right stage from start to target
            #  2. move left stage from start to target
            self.right_calibration.move_absolute(right)
            self.left_calibration.move_absolute(left)
        else:
            raise AssertionError('Coder did not do proper case distinction for positive-ness of two variables!')

        if lift_z_dir:
            self.lower_stages()

    @assert_connected_stages
    def move_relative(self, left=[], right=[], lift_z_dir=False):
        self.move_absolute(
            left=make_3d_coordinate(self.left_calibration.position) + make_3d_coordinate(left),
            right=make_3d_coordinate(self.left_calibration.position) + make_3d_coordinate(right),
            lift_z_dir=lift_z_dir
        )


    @assert_connected_stages
    def lift_stages(self):
        if self._stages_lifted:
            return

        for calibration in self.calibrations.values():
            calibration.move_relative([0,0,self.z_lift])

        self._stages_lifted = True

    @assert_connected_stages
    def lower_stages(self):
        if not self._stages_lifted:
            return

        for calibration in self.calibrations.values():
            calibration.move_relative([0,0,-self.z_lift])

        self._stages_lifted = False

    @assert_connected_stages
    def move_to_device(self, device):
        """Moves to a specific device on the chip.

        Parameters
        ----------
        device : Device
            Device to move to.

        Raises
        ------
        RuntimeError
            If no 2D transformation has been done beforehand.
        """
        self.move_absolute(left=device._in_position, right=device._out_position)


    #
    #   Helpers
    #

    def _get_calibration(self, port=None, orientation=None, default=None):
        """
        Get safely calibration by port and orientation.
        """
        orientation = orientation or self._port_by_orientation.inverse.get(
            port)
        port = port or self._port_by_orientation.get(orientation)
        return self.calibrations.get((orientation, port), default)
