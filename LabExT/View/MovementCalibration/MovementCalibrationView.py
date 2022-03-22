#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from tkinter import BooleanVar, Checkbutton, Frame, Label, OptionMenu, StringVar, Button, messagebox, NORMAL, DISABLED, LEFT, RIGHT, TOP, X, W
from itertools import product
from bidict import bidict
from typing import Type

from LabExT.View.Controls.CustomTable import CustomTable
from LabExT.View.Movement.CoordinatePairingsWindow import CoordinatePairingsWindow
from LabExT.Movement.Transformations import Axis, Direction
from LabExT.Utils import catch_and_prompt_error, try_to_lift_window
from LabExT.View.Controls.CustomFrame import CustomFrame
from LabExT.View.Controls.Wizard import Wizard


class MovementCalibrationView(Wizard):
    """
    Implements a Wizard for calibrate the stages in 3 steps.

    1. Fix cooridnate system to allow relative movement in chip cooridnates
    2. Fix one single point to allow approx absolute movement in chip cooridnates
    3. Fully calibrate stages by defining a global rotation
    """

    STAGE_AXIS_OPTIONS = bidict({o: " ".join(map(str, o))
                                for o in product(Direction, Axis)})

    def __init__(self, parent, experiment_manager, mover, controller, stage_calibration_controllers) -> None:
        super().__init__(
            parent,
            width=1000,
            height=700,
            on_cancel=lambda: catch_and_prompt_error(lambda: self.controller.reset_all() if self._confirm_cancel() else None),
            on_finish=lambda: catch_and_prompt_error(lambda: self.controller.perform_sanity_check()),
            cancel_button_label="Cancel and Close",
            finish_button_label="Finish and Save"
        )
        self.title("Stage Calibration Wizard")

        self.controller = controller
        self.stage_calibration_controllers = stage_calibration_controllers

        self.experiment_manager = experiment_manager
        self.mover = mover

        # -- 1. STEP: FIX COORDINATE SYSTEM --
        self.fix_coordinate_system_step = self.add_step(
            self._fix_coordinate_system_step_builder,
            title="Fix Coordinate System",
            on_reload=self._check_axis_calibration)
        # Step tkinter variables and buttons
        self._axis_wiggle_buttons = {}       

        self._axis_calibration_vars = {}
        for controller in self.stage_calibration_controllers:
            for chip_axis in Axis:
                axis_var = StringVar(self.parent, self.STAGE_AXIS_OPTIONS[(Direction.POSITIVE, chip_axis)])
                axis_var.trace(W, lambda *_, controller=controller, chip_axis=chip_axis, axis_var=axis_var: controller.update_axes_rotation(chip_axis, *self.STAGE_AXIS_OPTIONS.inverse[axis_var.get()]))

                self._axis_calibration_vars.setdefault(controller.calibration, {})[chip_axis] = axis_var      

        # -- 2. STEP: CALIBRATE STAGES --
        self.calibrate_stages_step = self.add_step(
            self._calibrate_stages_step_builder,
            title="Calibrate Stages",
            on_reload=self._check_stage_calibration)
        # Step tkinter variables and state
        self._use_input_stage_var = BooleanVar(self.parent, True)
        self._use_output_stage_var = BooleanVar(self.parent, True)
        self._full_calibration_new_pairing_button = None

        # Global state
        self._coordinate_pairing_window = None

        # Connect steps
        self.fix_coordinate_system_step.next_step = self.calibrate_stages_step
        self.calibrate_stages_step.previous_step = self.fix_coordinate_system_step

        # Start Wizard by setting the current step
        self.current_step = self.fix_coordinate_system_step

    def _fix_coordinate_system_step_builder(self, frame: Type[CustomFrame]):
        """
        Step builder to fix the coordinate system.
        """
        frame.title = "Fix Coordinate System"

        step_description = Label(
            frame,
            text="In order for each stage to move relative to the chip coordinates, the direction of each axis of each stage must be defined. \n Postive Y-Axis: North of chip, Positive X-Axis: East of chip, Positive Z-Axis: Lift stage")
        step_description.pack(side=TOP, fill=X)

        for calibration_controller in self.stage_calibration_controllers:
            stage_calibration_frame = CustomFrame(frame)
            stage_calibration_frame.title = str(calibration_controller.calibration)
            stage_calibration_frame.pack(side=TOP, fill=X, pady=2)

            for chip_axis in Axis:
                chip_axis_frame = Frame(stage_calibration_frame)
                chip_axis_frame.pack(side=TOP, fill=X)

                Label(
                    chip_axis_frame,
                    text="Positive {}-Chip-axis points to ".format(chip_axis.name)
                ).pack(side=LEFT)

                OptionMenu(
                    chip_axis_frame,
                    self._axis_calibration_vars[calibration_controller.calibration][chip_axis],
                    *self.STAGE_AXIS_OPTIONS.values(),
                ).pack(side=LEFT)

                Label(chip_axis_frame, text="of Stage").pack(side=LEFT)
                
                wiggle_button = Button(
                    chip_axis_frame,
                    text="Wiggle {}-Axis".format(
                        chip_axis.name),
                    command=lambda axis=chip_axis, calibration_controller=calibration_controller: catch_and_prompt_error(
                        lambda: calibration_controller.wiggle_axis(axis) if self._confirm_wiggle(axis) else None,
                        parent=self),
                    state=NORMAL if calibration_controller.is_axes_rotation_valid else DISABLED)
                wiggle_button.pack(side=RIGHT)

                self._axis_wiggle_buttons.setdefault(calibration_controller.calibration, {})[chip_axis] = wiggle_button

    def _calibrate_stages_step_builder(self, frame):
        """
        Step builder to calibrate stages.
        """
        frame.title = "Calibrate Stage to enable absolute movement"

        step_description = Label(
            frame,
            text="To move the stages absolutely in chip coordinates, define at least 3 stage-chip-coordinate pairings to calculate the rotation. \n" +
            "Note: After one coordinate pairing TODO. Therefore this is only an approximation.")
        step_description.pack(side=TOP, fill=X)

        # Render table with all defined pairings
        pairings_frame = CustomFrame(frame)
        pairings_frame.title = "Defined Pairings"
        pairings_frame.pack(side=TOP, fill=X)

        pairings_table_frame = Frame(pairings_frame)
        pairings_table_frame.pack(side=TOP, fill=X, expand=False)

        CustomTable(
            parent=pairings_table_frame,
            selectmode='none',
            columns=('ID', 'Stage', 'Stage Cooridnate', 'Device', 'Chip Coordinate'),
            rows=[(idx,) + p for idx, p in enumerate(self.controller.all_pairings)])

        # Render frame to show current calibration state
        calibration_summary_frame = CustomFrame(frame)
        calibration_summary_frame.pack(side=TOP, fill=X)

        for calibration in self.mover.calibrations.values():
            stage_calibration_frame = CustomFrame(calibration_summary_frame)
            stage_calibration_frame.title = str(calibration)
            stage_calibration_frame.pack(side=TOP, fill=X, pady=2)

            # SINGLE POINT STATE
            Label(
                stage_calibration_frame,
                text="Single Point Fixation:"
            ).grid(row=0, column=0, padx=2, pady=2, sticky=W)
            Label(
                stage_calibration_frame,
                text=calibration.single_point_transformation,
                foreground='#4BB543' if calibration.single_point_transformation.is_valid else "#FF3333",
            ).grid(row=0, column=1,  padx=2, pady=2, sticky=W)

            # GLOBAL STATE
            Label(
                stage_calibration_frame,
                text="Global Transformation:"
            ).grid(row=1, column=0,  padx=2, pady=2, sticky=W)
            Label(
                stage_calibration_frame,
                text=calibration.full_transformation,
                foreground='#4BB543' if calibration.full_transformation.is_valid else "#FF3333",
            ).grid(row=1, column=1, padx=2, pady=2, sticky=W)


        # FRAME FOR NEW PAIRING
        new_pairing_frame = CustomFrame(frame)
        new_pairing_frame.title = "Create New Pairing"
        new_pairing_frame.pack(side=TOP, fill=X, pady=5)

        Checkbutton(
            new_pairing_frame,
            text="Use Input-Stage for Pairing",
            variable=self._use_input_stage_var
        ).pack(side=LEFT)
        Checkbutton(
            new_pairing_frame,
            text="Use Output-Stage for Pairing",
            variable=self._use_output_stage_var
        ).pack(side=LEFT)

        self._full_calibration_new_pairing_button = Button(
            new_pairing_frame,
            text="New Pairing...",
            command=lambda: self._new_coordinate_pairing_window(
                in_calibration=self.mover.input_calibration if self._use_input_stage_var.get() else None,
                out_calibration=self.mover.output_calibration if self._use_output_stage_var.get() else None,
                on_finish=lambda pairings: catch_and_prompt_error(lambda: self.controller.save_pairings(pairings), parent=self)))
        self._full_calibration_new_pairing_button.pack(side=RIGHT)

        rmsd_hint = Label(
            frame,
            text="RMSD: Root mean square distance between the set of chip coordinates and the set of stage coordinates after alignment."
        )
        rmsd_hint.pack(side=TOP, fill=X)

    #
    #   Reload callbacks
    #   
    #   The following methods are called when a wizard step is reloaded.
    #   The methods are used to indicate errors in the current configuration.

    def _check_axis_calibration(self):
        """
        Callback, when coordinate system fixation step gets reloaded.

        Checks, if the current assignment is valid.
        """
        if all(c.is_axes_rotation_valid for c in self.stage_calibration_controllers):
            self.current_step.next_step_enabled = True
            self.set_error("")
        else:
            self.current_step.next_step_enabled = False
            self.set_error("Please do not assign a stage axis twice.")

    def _check_stage_calibration(self):
        """
        Callback, when stage calibration step gets reloaded.

        Checks, if the calibration is valid.
        """
        if not all(c.is_single_transformation_valid for c in self.stage_calibration_controllers):
            self.current_step.finish_step_enabled = False
            self.set_error("Please fix for each stage a single point.")
            return

        if not all(c.is_full_transformation_valid for c in self.stage_calibration_controllers):
            self.current_step.finish_step_enabled = False
            self.set_error("Please define for each stage at least three points to calibrate the stages globally.")
            return

        self.current_step.finish_step_enabled = True
        self.set_error("")


    #
    #   Helper
    #

    def _new_coordinate_pairing_window(
            self,
            in_calibration=None,
            out_calibration=None,
            on_finish=None):
        """
        Opens a new window to pair a chip cooridnate with a stage cooridnate.
        """

        if self._check_for_exisiting_coordinate_window():
            return

        try:
            self._coordinate_pairing_window = CoordinatePairingsWindow(
                self.experiment_manager,
                parent=self,
                mover=self.mover,
                in_calibration=in_calibration,
                out_calibration=out_calibration,
                on_finish=on_finish)
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

    #
    #   User Feedback Functions
    #

    def _confirm_wiggle(self, axis) -> bool:
        """
        Confirms with user if wiggeling is allowed.
        """
        message = 'By proceeding this button will move the stage along the {} direction. \n\n'.format(axis) \
                  + 'Please make sure it has enough travel range(+-5mm) to avoid collision. \n\n' \
                  + 'For correct operation the stage should: \n' \
                  + 'First: Move in positive {}-Chip-Axis direction \n'.format(axis) \
                  + 'Second: Move in negative {}-Chip-Axis direction \n\n'.format(axis) \
                  + 'If not, please check your assignments.\n Do you want to proceed with wiggling?'

        return messagebox.askokcancel("Warning", message, parent=self)

    def _confirm_cancel(self) -> bool:
        """
        Confirms with user to cancel the wizard.
        """
        return messagebox.askokcancel(
            "Quit Wizard?",
            "Do you really want to cancel the calibration? All changes will be reset.",
            parent=self)