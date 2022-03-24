#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

import importlib
import sys
from typing import List, Type
from LabExT.Movement.Calibration import Calibration, State

from LabExT.Movement.Stage import Stage, StageError
from LabExT.Movement.Transformations import Axis, CoordinatePairing, Direction
from LabExT.View.Movement.MovementWizard import MovementWizard
from LabExT.Movement.MoverNew import MoverError, MoverNew


class MovementController:
    def __init__(self, experiment_manager, mover, parent=None) -> None:
        self.experiment_manager = experiment_manager
        self.mover: Type[MoverNew] = mover
        self.view = MovementWizard(
            parent, self.experiment_manager, self, self.mover) if parent else None

        self._performing_wiggle = False

    def load_driver(self, stage_class: Type[Stage]):
        """
        Invokes the load_driver function of some Stage class.

        If successful, it reloads the Stage module and the wizard.
        """
        if not stage_class.meta.driver_specifiable:
            return

        if stage_class.load_driver(parent=self.view):
            importlib.reload(sys.modules.get(stage_class.__module__))
            self.mover.reload_stage_classes()
            self.mover.reload_stages()
            self.view.__reload__()

    def reload_stage_classes(self):
        """
        Callback, when user wants to reload stage classes.
        """
        self.mover.reload_stage_classes()
        self.view.__reload__()

    def save_stage_assignment(self, assignments) -> bool:
        self.mover.reset()

        for stage, assignment in assignments.items():
            try:
                calibration = self.mover.add_stage_calibration(
                    stage, *assignment)
                calibration.connect_to_stage()
            except (ValueError, MoverError, StageError) as e:
                self.mover.reset()
                raise e

        return True

    def save_configuration(self, speed_xy, speed_z, acceleration_xy, z_lift) -> bool:
        if not self.mover.has_connected_stages:
            raise RuntimeError("You need connected stages to configure the mover!")

        self.mover.speed_xy = speed_xy
        self.mover.speed_z = speed_z
        self.mover.acceleration_xy = acceleration_xy
        self.mover.z_lift = z_lift

        return True

    
    def update_axes_rotation(self, calibration: Type[Calibration], chip_axis, direction, stage_axis) -> bool:
        self.restore_single_point_fixation(calibration)
        calibration.update_axes_rotation(chip_axis, direction, stage_axis)

        self.view.__reload__()
        return True

    def restore_axes_rotation(self, calibration: Type[Calibration]):
        calibration.axes_rotation.reset()

    def axis_wiggle(self, calibration: Type[Calibration], axis):
        if self._performing_wiggle:
            raise AssertionError("Stage cannot wiggle because another stage is being wiggled.")

        try:
            self._performing_wiggle = True
            calibration.wiggle_axis(axis)
        finally:
            self._performing_wiggle = False


    def save_pairings(self, pairings: List[CoordinatePairing]):
        """
        Delegates the list of pairings to the responsible calibrations.
        """
        for pairing in pairings:
            single_point_trafo = pairing.calibration.single_point_transformation

            if not single_point_trafo.is_valid:
                pairing.calibration.update_single_point_transformation(pairing)

            pairing.calibration.update_full_transformation(pairing)    

        self.view.__reload__()

    def restore_single_point_fixation(self, calibration: Type[Calibration]):
        calibration.single_point_transformation.reset()

    def restore_full_calibration(self, calibration: Type[Calibration]):
        calibration.full_transformation.reset()

    def perform_sanity_check(self) -> bool:
        """
        Checks if mover is in fully calibrated state and all stages pass sanity check.
        """
        # Force to reload all states
        self.mover.reload_calibration_states()

        if self.experiment_manager:
            self.experiment_manager.main_window.refresh_context_menu()

        return self.mover.state == State.FULLY_CALIBRATED and all(c.state == State.FULLY_CALIBRATED for c in self.mover.calibrations.values())

    def restore_all(self):
        self.mover.reset()

        if self.experiment_manager:
            self.experiment_manager.main_window.refresh_context_menu()
        