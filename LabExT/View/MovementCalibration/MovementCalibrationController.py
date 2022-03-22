#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from functools import reduce
from operator import add
from typing import Type
from LabExT.Movement.Transformations import Axis, Direction
from LabExT.Utils import run_with_wait_window
from LabExT.View.MovementCalibration.MovementCalibrationView import MovementCalibrationView
from LabExT.Movement.Calibration import State


class MovementCalibrationController:
    """
    Controller to calibrate all connected stages of the mover.
    """

    def __init__(self, experiment_manager, mover, parent=None) -> None:
        if not mover.has_connected_stages:
            raise AssertionError(
                "Cannot calibrate mover without any connected stage. ")

        self.experiment_manager = experiment_manager
        self.mover = mover

        self.stage_calibration_controllers = [StageCalibrationController(self, c) for c in self.mover.calibrations.values()]

        self.view = MovementCalibrationView(
            parent, experiment_manager, self.mover, self, self.stage_calibration_controllers) if parent else None

        self.coordinate_pairings = {}


    @property
    def all_pairings(self):
        """
        Returns a list of all pairings of all calibrations.
        """
        return reduce(add, [c.coordinate_pairings for c in self.stage_calibration_controllers], [])

    def save_pairings(self, pairings):
        """
        Delegates the list of pairings to the responsible calibrations.
        """
        for pairing in pairings:
            single_point_trafo = pairing.calibration.single_point_transformation

            if not single_point_trafo.is_valid:
                pairing.calibration.update_single_point_transformation(pairing)

            pairing.calibration.update_full_transformation(pairing)    

        self.view.__reload__()


    def perform_sanity_check(self) -> bool:
        """
        Checks if mover is in fully calibrated state and all stages pass sanity check.
        """
        # Force to reload all states
        self.mover.reload_calibration_states()

        if self.mover.state == State.FULLY_CALIBRATED and all(c.state == State.FULLY_CALIBRATED for c in self.mover.calibrations.values()):
            # Refresh Context Menu
            if self.experiment_manager:
                self.experiment_manager.main_window.refresh_context_menu()

            return True
        
        return False

    
    def reset_all(self) -> bool:
        """
        Checks if user wants to quit the wizard.
        Resets all progress.
        """
        if self.mover.reset_calibrations():
            if self.experiment_manager:
                self.experiment_manager.main_window.refresh_context_menu()
            return True
        
        return False


class StageCalibrationController:
    def __init__(self, movement_calibration_controller, calibration) -> None:
        self.movement_calibration_controller = movement_calibration_controller
        self.calibration = calibration

        self._performing_wiggle = False

    @property
    def coordinate_pairings(self):
        """
        Returns a list of CooridnatePairings defined by full and single calibration.
        """
        pairings = self.calibration.full_transformation.pairings
        single_point = self.calibration.single_point_transformation.pairing
        if single_point and single_point not in pairings:
            return [single_point] + pairings

        return pairings


    def update_axes_rotation(self, chip_axis, direction, stage_axis):
        chip_axis = chip_axis if type(chip_axis) == Axis else Axis[chip_axis.upper()]
        stage_axis = stage_axis if type(stage_axis) == Axis else Axis[stage_axis.upper()]
        direction = direction if type(direction) == Direction else Direction[direction.upper()]
        
        self.calibration.update_axes_rotation(chip_axis, direction, stage_axis)

        self.movement_calibration_controller.view.__reload__()

    def wiggle_axis(self, axis: Type[Axis]):
        if self._performing_wiggle:
            raise AssertionError("Stage cannot wiggle because another stage is being wiggled.")

        try:
            self._performing_wiggle = True
            run_with_wait_window(
                self.movement_calibration_controller.view, description="Wiggling {} of {}".format(
                    axis, self.calibration), function=lambda: self.calibration.wiggle_axis(axis))
        finally:
            self._performing_wiggle = False      

    @property
    def is_axes_rotation_valid(self) -> bool:
        return self.calibration.axes_rotation.is_valid

    @property
    def is_single_transformation_valid(self) -> bool:
        return self.calibration.single_point_transformation.is_valid

    @property
    def is_full_transformation_valid(self) -> bool:
        return self.calibration.full_transformation.is_valid