#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from operator import add
from functools import reduce
from itertools import product
from tkinter import BooleanVar, messagebox, ttk, Frame, Label, Button, OptionMenu, StringVar, DoubleVar, Entry, Checkbutton, W, TOP, RIGHT, LEFT, X, VERTICAL, NORMAL, DISABLED
from typing import List, Callable, Type
from LabExT.Movement.MoverNew import MoverNew
from bidict import bidict

from LabExT.Utils import catch_and_prompt_error

from LabExT.View.Controls.Wizard import Wizard, WizardStep
from LabExT.View.Controls.CustomFrame import CustomFrame
from LabExT.View.Controls.CustomTable import CustomTable

from LabExT.Movement.Transformations import Axis, Direction
from LabExT.Movement.Stage import Stage
from LabExT.Movement.Calibration import Calibration, DevicePort, Orientation

class StageDriversStep(WizardStep):

    def __init__(self, wizard, stage_classes, on_load_driver, on_reload_classes) -> None:
        super().__init__(wizard)
        self.stage_classes: List[Stage] = stage_classes
        self.on_load_driver: Callable = on_load_driver
        self.on_reload_classes: Callable = on_reload_classes

    def render(self, parent):
        step_description = Label(
            parent,
            text="Below you can see all Stage classes available in LabExT.\nSo that all stages can be found correctly, make sure that the drivers for each class are loaded."
        )
        step_description.pack(side=TOP, fill=X)

        ttk.Separator(
            parent, orient=VERTICAL
        ).pack(side=TOP, fill=X, pady=10)

        if not self.stage_classes:
            Label(parent, text="No stage classes found!").pack(side=TOP, fill=X)

        for stage_class in self.stage_classes:
            stage_driver_frame = Frame(parent)
            stage_driver_frame.pack(side=TOP, fill=X, pady=2)

            stage_driver_label = Label(
                stage_driver_frame,
                text="[{}] {}".format(
                    stage_class.__name__,
                    stage_class.meta.description))
            stage_driver_label.pack(side=LEFT, fill=X)

            stage_driver_load = Button(
                stage_driver_frame,
                text="Load Driver",
                state=NORMAL if stage_class.meta.driver_specifiable else DISABLED,
                command=lambda stage_class=stage_class: self.on_load_driver(stage_class))
            stage_driver_load.pack(side=RIGHT)

            stage_driver_status = Label(
                stage_driver_frame,
                text="Loaded" if stage_class.driver_loaded else "Not Loaded",
                foreground='#4BB543' if stage_class.driver_loaded else "#FF3333",
            )
            stage_driver_status.pack(side=RIGHT, padx=10)

        ttk.Separator(
            parent, orient=VERTICAL
        ).pack(side=TOP, fill=X, pady=10)

        reload_stage_classes_button = Button(
            parent,
            text="Reload Stage classes",
            command=self.on_reload_classes
        )
        reload_stage_classes_button.pack(side=TOP, anchor="e")


class StageConnectionStep(WizardStep):

    ASSIGNMENT_MENU_PLACEHOLDER = "-- unused --"

    def __init__(self, wizard, mover, on_save_assignment) -> None:
        super().__init__(wizard)

        self.mover: Type[MoverNew] = mover
        self.available_stages: List[Type[Stage]] = []
        self.on_save_assignment: Callable = on_save_assignment

        self.current_assignment = {}
        self.initial_assignment = {}

        self._stage_port_var = {}
        self._stage_orientation_var = {}


    def on_enter(self) -> None:
        self.available_stages = self.mover.available_stages
        self.initial_assignment = {c.stage: (o,p) for (o, p), c in self.mover.calibrations.items()}
        self.current_assignment = self.initial_assignment.copy()

        for stage in self.available_stages:
            orientation, port = self.initial_assignment.get(stage, (self.ASSIGNMENT_MENU_PLACEHOLDER, DevicePort.INPUT))

            port_var = StringVar(self.wizard, port)
            port_var.trace(
                W, lambda *_, stage=stage: self._on_stage_assignment(stage))

            orientation_var = StringVar(self.wizard, orientation)
            orientation_var.trace(
                W, lambda *_, stage=stage: self._on_stage_assignment(stage))

            self._stage_orientation_var[stage] = orientation_var
            self._stage_port_var[stage] = port_var
        

    def render(self, parent):
        """
        Builds stage to assign stages.
        """
        step_description = Label(
            parent,
            text="Below you can see all the stages found by LabExT.\nIf stages are missing, go back one step and check if all drivers are loaded."
        )
        step_description.pack(side=TOP, fill=X)

        available_stages_frame = CustomFrame(parent)
        available_stages_frame.title = "Available Stages"
        available_stages_frame.pack(side=TOP, fill=X)

        CustomTable(
            parent=available_stages_frame,
            selectmode='none',
            columns=(
                'ID', 'Description', 'Stage Class', 'Address', 'Connected'
            ),
            rows=[
                (idx,
                 s.__class__.meta.description,
                 s.__class__.__name__,
                 s.address_string,
                 s.connected)
                for idx, s in enumerate(self.available_stages)])

        stage_assignment_frame = CustomFrame(parent)
        stage_assignment_frame.title = "Connect and assign stages"
        stage_assignment_frame.pack(side=TOP, fill=X)

        for available_stage in self.available_stages:
            available_stage_frame = Frame(stage_assignment_frame)
            available_stage_frame.pack(side=TOP, fill=X, pady=2)

            Label(
                available_stage_frame, text=str(available_stage), anchor="w"
            ).pack(side=LEFT, fill=X, padx=(0, 10))

            # Set up menu for port selection
            stage_port_menu = OptionMenu(
                available_stage_frame,
                self._stage_port_var[available_stage],
                *(list(DevicePort))
            )
            stage_port_menu.pack(side=RIGHT, padx=5)
            stage_port_menu.config(state=DISABLED if self._stage_orientation_var[available_stage].get(
            ) == self.ASSIGNMENT_MENU_PLACEHOLDER else NORMAL)

            Label(
                available_stage_frame, text="Device Port:"
            ).pack(side=RIGHT, fill=X, padx=5)

            # Set up menu for orientation selection
            OptionMenu(
                available_stage_frame,
                self._stage_orientation_var[available_stage],
                *([self.ASSIGNMENT_MENU_PLACEHOLDER] + list(Orientation))
            ).pack(side=RIGHT, padx=5)

            Label(
                available_stage_frame, text="Stage Orientation:"
            ).pack(side=RIGHT, fill=X, padx=5)

    def on_next(self) -> bool:
        if not self.mover.has_connected_stages:
            return self.on_save_assignment(self.current_assignment)

        if self.current_assignment != self.initial_assignment:
            if messagebox.askokcancel(
                title="Proceed?",
                message="You have changed the stage assignment. If you continue, all calibrations will be reset. Are you sure you want to continue?",
                parent=self.wizard):
                return self.on_save_assignment(self.current_assignment)
        else:
            return True

    def on_reload(self) -> None:
        if not self.current_assignment:
            self.enable_next_step = False
            self.enable_finish = False
            self.wizard.set_error("Please assign at least one to proceed.")
            return

        if any(map(lambda l: len(l) != len(set(l)), zip(*self.current_assignment.values()))):
            self.enable_next_step = False
            self.enable_finish = False
            self.wizard.set_error("Please do not assign a orientation or device port twice.")
            return

        self.enable_next_step = True
        self.enable_finish = False
        self.wizard.set_error("")

    def _on_stage_assignment(self, stage):
        """
        Callback, when user changes a stage assignment.
        Updates internal wizard state and reloads contents.
        """
        port = self._stage_port_var.get(stage, StringVar()).get()
        orientation = self._stage_orientation_var.get(stage, StringVar).get()

        if orientation == self.ASSIGNMENT_MENU_PLACEHOLDER:
            self.current_assignment.pop(stage, None)
            self.wizard.__reload__()
            return

        self.current_assignment[stage] = (
            Orientation[orientation.upper()], DevicePort[port.upper()])
        self.wizard.__reload__()

class StageConfigurationStep(WizardStep):

    def __init__(self, wizard, mover, on_save_configuration) -> None:
        super().__init__(wizard)

        self.mover: Type[MoverNew] = mover
        self.on_save_configuration: Callable = on_save_configuration

        self.xy_speed_var = DoubleVar(
            self.wizard,
            self.mover.speed_xy if self.mover._speed_xy else self.mover.DEFAULT_SPEED_XY)
        self.z_speed_var = DoubleVar(
            self.wizard,
            self.mover.speed_z if self.mover._speed_z else self.mover.DEFAULT_SPEED_Z)
        self.xy_acceleration_var = DoubleVar(
            self.wizard,
            self.mover.acceleration_xy if self.mover._acceleration_xy else self.mover.DEFAULT_ACCELERATION_XY)
        self.z_lift_var = DoubleVar(
            self.wizard,
            self.mover.z_lift if self.mover._z_lift else self.mover.DEFAULT_Z_LIFT)

    def on_enter(self) -> None:
        if not self.mover.has_connected_stages:
            raise AssertionError("You need connected stages to proceed!")

    def render(self, parent):
        """
        Builds step to configure stages.
        """
        parent.title = "Configure Assigned Stages"

        step_description = Label(
            parent,
            text="Configure the selected stages.\nThese settings are applied globally to all selected stages."
        )
        step_description.pack(side=TOP, fill=X)

        stage_properties_frame = CustomFrame(parent)
        stage_properties_frame.title = "Speed and Acceleration Settings"
        stage_properties_frame.pack(side=TOP, fill=X)

        Label(
            stage_properties_frame,
            anchor="w",
            text="Speed Hint: A value of 0 (default) deactivates the speed control feature. The stage will move as fast as possible!"
        ).pack(side=TOP, fill=X)
        Label(
            stage_properties_frame,
            anchor="w",
            text="Acceleration Hint: A value of 0 (default) deactivates the acceleration control feature."
        ).pack(side=TOP, fill=X)

        ttk.Separator(
            stage_properties_frame,
            orient=VERTICAL
        ).pack(side=TOP, fill=X, pady=10)

        self._build_entry_with_label(
            stage_properties_frame,
            self.xy_speed_var,
            label="Movement speed xy direction (valid range: {}...{:.0e}um/s):".format(
                self.mover.SPEED_LOWER_BOUND,
                self.mover.SPEED_UPPER_BOUND),
            unit="[um/s]")

        self._build_entry_with_label(
            stage_properties_frame,
            self.z_speed_var,
            label="Movement speed z direction (valid range: {}...{:.0e}um/s):".format(
                self.mover.SPEED_LOWER_BOUND,
                self.mover.SPEED_UPPER_BOUND),
            unit="[um/s]")

        self._build_entry_with_label(
            stage_properties_frame,
            self.xy_acceleration_var,
            label="Movement acceleration xy direction (valid range: {}...{:.0e}um/s^2):".format(
                self.mover.ACCELERATION_LOWER_BOUND,
                self.mover.ACCELERATION_LOWER_BOUND),
            unit="[um/s^2]")

        stage_lift_frame = CustomFrame(parent)
        stage_lift_frame.title = "Z-Lift"
        stage_lift_frame.pack(side=TOP, fill=X)

        self._build_entry_with_label(
            stage_lift_frame,
            self.z_lift_var,
            label="Z channel up-movement during xy movement:",
            unit="[um]")

    def on_next(self) -> bool:
        speed_xy = self._get_safe_value(
            self.xy_speed_var, float, self.mover.DEFAULT_SPEED_XY)
        speed_z = self._get_safe_value(
            self.z_speed_var, float, self.mover.DEFAULT_SPEED_Z)
        acceleration_xy = self._get_safe_value(
            self.xy_acceleration_var, float, self.mover.DEFAULT_ACCELERATION_XY)
        z_lift = self._get_safe_value(
            self.z_lift_var, float, self.mover.DEFAULT_SPEED_Z)

        if self._warn_user_about_zero_speed(
                speed_xy) and self._warn_user_about_zero_speed(speed_z):
            return self.on_save_configuration(speed_xy, speed_z, acceleration_xy, z_lift)
        else:
            return False

    def _build_entry_with_label(
            self,
            parent,
            var: Type[DoubleVar],
            label: str = None,
            unit: str = None) -> None:
        """
        Builds an tkinter entry with label and unit.
        """
        entry_frame = Frame(parent)
        entry_frame.pack(side=TOP, fill=X, pady=2)

        Label(entry_frame, text=label).pack(side=LEFT)
        Label(entry_frame, text=unit).pack(side=RIGHT)
        entry = Entry(entry_frame, textvariable=var)
        entry.pack(side=RIGHT, padx=10)

    def _warn_user_about_zero_speed(self, speed) -> bool:
        """
        Warns user when settings speed to zero.

        Returns True if speed is not zero or user wants to set speed to zero.
        """
        if speed == 0.0:
            return messagebox.askokcancel(
                message="Setting speed to 0 will turn the speed control OFF! \n"
                "The stage will now move as fast as possible. Set a different speed if "
                "this is not intended. Do you want still to proceed?",
                parent=self.wizard)

        return True

    def _get_safe_value(
            self,
            var: Type[DoubleVar],
            to_type: type,
            default=None):
        """
        Returns the value of a tkinter entry and cast it to a specified type.

        If casting or retrieving fails, it returns a default value.
        """
        try:
            return to_type(var.get())
        except (ValueError, TypeError):
            return default

class AxesCalibrationStep(WizardStep):

    STAGE_AXIS_OPTIONS = bidict({o: " ".join(map(str, o))
                                for o in product(Direction, Axis)})

    def __init__(self, wizard, mover, on_update_axes_rotation, on_axis_wiggle) -> None:
        super().__init__(wizard)

        self.mover = mover
        self.calibrations_list: List[Type[Calibration]] = []
        self.on_update_axes_rotation: Callable = on_update_axes_rotation
        self.on_axis_wiggle: Callable = on_axis_wiggle

        self._axis_wiggle_buttons = {}       
        self._axis_calibration_vars = {}

    def on_enter(self) -> None:
        self.calibrations_list: List[Type[Calibration]] = self.mover.calibrations.values()

        if not self.calibrations_list:
            raise AssertionError("You need at least one assigned stage for calibration.")

        for calibration in self.calibrations_list:
            for chip_axis in Axis:
                axis_var = StringVar(
                    self.wizard,
                    self.STAGE_AXIS_OPTIONS[calibration.axes_rotation.get_mapped_stage_axis(chip_axis)])
                axis_var.trace(W, lambda *_, calibration=calibration, chip_axis=chip_axis, axis_var=axis_var: self._on_axes_calibration(calibration, chip_axis, axis_var))

                self._axis_calibration_vars.setdefault(calibration, {})[chip_axis] = axis_var

    def render(self, frame):
        """
        Step builder to fix the coordinate system.
        """
        frame.title = "Fix Coordinate System"

        step_description = Label(
            frame,
            text="In order for each stage to move relative to the chip coordinates, the direction of each axis of each stage must be defined. \n Postive Y-Axis: North of chip, Positive X-Axis: East of chip, Positive Z-Axis: Lift stage")
        step_description.pack(side=TOP, fill=X)

        for calibration in self.calibrations_list:
            stage_calibration_frame = CustomFrame(frame)
            stage_calibration_frame.title = str(calibration)
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
                    self._axis_calibration_vars[calibration][chip_axis],
                    *self.STAGE_AXIS_OPTIONS.values(),
                ).pack(side=LEFT)

                Label(chip_axis_frame, text="of Stage").pack(side=LEFT)
                
                wiggle_button = Button(
                    chip_axis_frame,
                    text="Wiggle {}-Axis".format(
                        chip_axis.name),
                    command=lambda axis=chip_axis, calibration=calibration: catch_and_prompt_error(
                        lambda: self.on_axis_wiggle(calibration, axis) if self._confirm_wiggle(axis) else None,
                        parent=self.wizard),
                    state=NORMAL if calibration.axes_rotation.is_valid else DISABLED)
                wiggle_button.pack(side=RIGHT)

                self._axis_wiggle_buttons.setdefault(calibration, {})[chip_axis] = wiggle_button

    def on_reload(self) -> None:
        """
        Callback, when coordinate system fixation step gets reloaded.

        Checks, if the current assignment is valid.
        """
        if all(c.axes_rotation.is_valid for c in self.calibrations_list):
            self.enable_next_step = True
            self.enable_finish = True
            self.wizard.set_error("")
        else:
            self.enable_next_step = False
            self.enable_finish = False
            self.wizard.set_error("Please do not assign a stage axis twice.")

    def on_next(self) -> bool:
        if not all(c.axes_rotation.is_valid for c in self.calibrations_list):
            raise ValueError("Not all axes rotations are valid! Can not proceed safely.")
        
        return True

    def _on_axes_calibration(self, calibration, chip_axis, axis_var):
        if calibration.single_point_transformation.pairing:
            if not messagebox.askokcancel(
                title="Proceed?",
                message="A single point has already been fixed with a previous axis rotation. If you continue, this fixation will be reset. Do you want to continue?",
                parent=self.wizard):
                return

        direction, stage_axis = self.STAGE_AXIS_OPTIONS.inverse[axis_var.get()]
        self.on_update_axes_rotation(calibration, chip_axis, direction, stage_axis)

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

        return messagebox.askokcancel("Warning", message, parent=self.wizard)


class StageCalibrationStep(WizardStep):
    def __init__(self, wizard, mover, on_new_pairing) -> None:
        super().__init__(wizard)

        self.mover: Type[MoverNew] = mover
        self.calibrations_list: List[Type[Calibration]] = []
        self.on_new_pairing: Callable = on_new_pairing
        self.pairings = set()

        self._use_input_stage_var = BooleanVar(self.wizard, True)
        self._use_output_stage_var = BooleanVar(self.wizard, True)
        self._full_calibration_new_pairing_button = None

    def on_enter(self) -> None:
        self.calibrations_list = self.mover.calibrations.values()
        

    def on_reload(self) -> None:
        self.pairings = set(reduce(add, [
            c.full_transformation.pairings for c in self.calibrations_list
        ], []))

        if not all(c.single_point_transformation.is_valid for c in self.calibrations_list):
            self.enable_next_step = False
            self.enable_finish = False
            self.wizard.set_error("Please fix for each stage a single point.")
            return

        if not all(c.full_transformation.is_valid for c in self.calibrations_list):
            self.enable_next_step = False
            self.enable_finish = True
            self.wizard.set_error("Please define for each stage at least three points to calibrate the stages globally.")
            return

        self.enable_next_step = True
        self.enable_finish = True
        self.wizard.set_error("")

    def render(self, frame):
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
            rows=[(idx,) + p for idx, p in enumerate(self.pairings)])

        # Render frame to show current calibration state
        calibration_summary_frame = CustomFrame(frame)
        calibration_summary_frame.pack(side=TOP, fill=X)

        for calibration in self.calibrations_list:
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
            command=self.on_new_pairing)
        self._full_calibration_new_pairing_button.pack(side=RIGHT)

        rmsd_hint = Label(
            frame,
            text="RMSD: Root mean square distance between the set of chip coordinates and the set of stage coordinates after alignment."
        )
        rmsd_hint.pack(side=TOP, fill=X)