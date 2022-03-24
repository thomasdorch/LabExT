#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from tkinter import  messagebox
from LabExT.Utils import try_to_lift_window

from LabExT.View.Controls.Wizard import Wizard
from LabExT.View.Movement.CoordinatePairingsWindow import CoordinatePairingsWindow

from LabExT.View.Movement.MovementViews import AxesCalibrationStep, StageCalibrationStep, StageConfigurationStep, StageDriversStep, StageConnectionStep

class MovementWizard(Wizard):
    def __init__(self, master, experiment_manager, controller, mover):
        super().__init__(
            master,
            width=1100,
            height=800,
            sidebar_width=300,
            next_button_label="Next Step",
            previous_button_label="Previous Step",
            cancel_button_label="Cancel",
            finish_button_label="Finish Setup",
            enable_sidebar=True
        )
        self.master = master
        self.experiment_manager = experiment_manager
        self.controller = controller
        self.mover = mover

        self.title("Configure Mover Wizard")

        self.load_driver_step = StageDriversStep(
            self,
            stage_classes=self.mover.stage_classes,
            on_load_driver=self.controller.load_driver,
            on_reload_classes=self.controller.reload_stage_classes)
        self.load_driver_step.config(title="Driver Settings")

        self.connect_stages_step = StageConnectionStep(
            self,
            mover=self.mover,
            on_save_assignment=self.controller.save_stage_assignment)
        self.connect_stages_step.config(title="Stage Connection")

        self.configure_stages_step = StageConfigurationStep(
            self,
            mover=self.mover,
            on_save_configuration=self.controller.save_configuration)
        self.configure_stages_step.config(title="Stage Configuration")

        self.fix_coordinate_system_step = AxesCalibrationStep(
            self,
            mover=self.mover,
            on_update_axes_rotation=self.controller.update_axes_rotation,
            on_axis_wiggle=self.controller.axis_wiggle)
        self.fix_coordinate_system_step.config(title="Fix Coordinate System")

        self.calibrate_stages_step = StageCalibrationStep(
            self,
            mover=self.mover,
            on_new_pairing=self.new_coordinate_pairing_window)
        self.calibrate_stages_step.config(title="Calibrate Stages")

        self.load_driver_step.next_step = self.connect_stages_step
        self.connect_stages_step.previous_step = self.load_driver_step
        self.connect_stages_step.next_step = self.configure_stages_step
        self.configure_stages_step.previous_step = self.connect_stages_step
        self.configure_stages_step.next_step = self.fix_coordinate_system_step
        self.fix_coordinate_system_step.previous_step = self.configure_stages_step
        self.fix_coordinate_system_step.next_step = self.calibrate_stages_step
        self.calibrate_stages_step.previous_step = self.fix_coordinate_system_step

        self.current_step = self.load_driver_step

        # States
        self._coordinate_pairing_window = None

    def on_finish(self) -> bool:
        if self.controller.perform_sanity_check():
            return True

        return messagebox.askokcancel(
            title="Quit?",
            message="Are you sure you want to leave the Wizard? The mover is currently NOT in the fully calibrated state. Do you want to continue?",
            parent=self)

    def on_cancel(self) -> bool:
        if messagebox.askokcancel(
            title="Quit?",
            message="Are you sure you want to leave the Wizard? The mover will be completely reset and all progress will be lost. Do you want to continue?",
            parent=self):
            self.controller.restore_all()
            return True
        
        return False

    def new_coordinate_pairing_window(self, with_input_stage = True, with_output_stage = True):
        if self._check_for_exisiting_coordinate_window():
            return
        
        try:
            self._coordinate_pairing_window = CoordinatePairingsWindow(
                self,
                self.experiment_manager,
                self.mover,
                in_calibration=self.mover.input_calibration if with_input_stage else None,
                out_calibration=self.mover.output_calibration if with_output_stage else None,
                on_finish=self.controller.save_pairings)
        except Exception as e:
            messagebox.showerror(
                "Error",
                "Could not initiate a new coordinate pairing: {}".format(e),
                parent=self)

    def _check_for_exisiting_coordinate_window(self) -> bool:
        """
        Ensures that only one window exists to create a new coordinate pair.

        Returns True if there is a exsiting window.
        """
        if self._coordinate_pairing_window is None or not try_to_lift_window(
                self._coordinate_pairing_window):
            return False

        if not messagebox.askyesno(
            "New Coordinate-Pairing",
            "You have an incomplete creation of a coordinate pair. Click Yes if you want to continue it or No if you want to create the new one.",
                parent=self._coordinate_pairing_window):
            self._coordinate_pairing_window._cancel()
            self._coordinate_pairing_window = None
            return False

        return True