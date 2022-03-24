#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from tkinter import Label, Toplevel, Frame, Button, FLAT, TOP, RIGHT, LEFT, X, Y, BOTH, NORMAL, DISABLED, messagebox
from typing import Type

from LabExT.View.Controls.CustomFrame import CustomFrame

class WizardStep(ABC):
    def __init__(self, wizard) -> None:
        self.wizard: Wizard = wizard

        self.next_step: WizardStep = None
        self.previous_step: WizardStep = None 

        self.enable_next_step: bool = True
        self.enable_previous_step: bool = True
        self.enable_finish: bool = True

        self.config()

    def config(self, title=None, next_is_finish = False):
        self.title = title
        self.next_is_finish = next_is_finish

        self.wizard._register_step_in_sidebar(self)

    @abstractmethod
    def render(self, master=None):
        pass

    def on_reload(self) -> None:
        pass

    def on_enter(self) -> None:
        pass
 
    def on_next(self) -> bool:
        return True

    def on_previous(self) -> bool:
        return True

    @property
    def _next_step_available(self) -> bool:
        return self.enable_next_step and self.next_step is not None

    @property
    def _previous_step_available(self) -> bool:
        return self.enable_previous_step and self.previous_step is not None


class Wizard(Toplevel, ABC):
    """
    Implementation of a Wizard Widget.
    """
    ERROR_COLOR = "#FF3333"
    ACTIVE_LABEL_COLOR = "#000000"
    INACTIVE_LABEL_COLOR = "#808080"

    def __init__(
        self,
        master,
        width=640,
        height=480,
        sidebar_width=200,
        enable_sidebar = True,
        next_button_label = None,
        previous_button_label = None,
        cancel_button_label = None,
        finish_button_label = None) -> None:
        Toplevel.__init__(
            self,
            master,
            borderwidth=0,
            highlightthickness=0,
            takefocus=0,
            relief=FLAT)

        self.master = master

        self._current_step: Type[WizardStep] = None
        self._sidebar_labels = {}

        # Build Sidebar
        if enable_sidebar:
            self._sidebar_frame = CustomFrame(self, width=sidebar_width)
            self._sidebar_frame.pack(side=LEFT, fill=BOTH, anchor='nw')
        else:
            self._sidebar_frame = None

        # Build content frame
        self._content_frame = Frame(self, borderwidth=0, relief=FLAT)
        self._content_frame.pack(side=RIGHT, fill=BOTH, expand=True)

        self._step_frame = Frame(
            self._content_frame,
            borderwidth=0,
            relief=FLAT)
        self._step_frame.pack(side=TOP, fill=BOTH, expand=True)
    
        self._error_frame = Frame(
            self._content_frame, borderwidth=0, relief=FLAT)
        self._error_frame.pack(side=TOP, fill=X, padx=10, expand=0)
        self._error_label = Label(
            self._error_frame,
            text=None,
            foreground=self.ERROR_COLOR,
            anchor="w")
        self._error_label.pack(side=LEFT, fill=X)

        self._buttons_frame = Frame(
            self._content_frame,
            borderwidth=0,
            highlightthickness=0,
            takefocus=0)
        self._buttons_frame.pack(side=TOP, fill=X, expand=0)

        if cancel_button_label:
            self._cancel_button = Button(
                self._buttons_frame,
                text=cancel_button_label,
                width=10,
                command=lambda: self.destroy() if self.on_cancel() else None)
            self._cancel_button.pack(
                side=RIGHT, fill=Y, expand=0, padx=(
                    5, 10), pady=10)
        else:
            self._cancel_button

        if finish_button_label:
            self._finish_button = Button(
                self._buttons_frame,
                text=finish_button_label,
                width=10,
                command=lambda: self.destroy() if self.on_finish() else None)
            self._finish_button.pack(
                side=RIGHT, fill=Y, expand=0, padx=(
                20, 5), pady=10)
        else: 
            self._finish_button = None

        if next_button_label:
            self._next_button = Button(
                self._buttons_frame,
                text=next_button_label,
                width=10,
                command=self._on_next)
            self._next_button.pack(side=RIGHT, fill=Y, expand=0, padx=5, pady=10)
        else:
            self._next_button = None

        if previous_button_label:
            self._previous_button = Button(
                self._buttons_frame,
                text=previous_button_label,
                width=10,
                command=self._on_previous)
            self._previous_button.pack(
                side=RIGHT, fill=Y, expand=0, padx=5, pady=10)
        else: 
            self._previous_button = None

        self.wm_geometry("{width:d}x{height:d}".format(
            width=width + sidebar_width if enable_sidebar else width,
            height=height))
        self.protocol('WM_DELETE_WINDOW', lambda: self.destroy() if self.on_cancel() else None)
        
    def __reload__(self):
        """
        Updates the Wizard contents.
        """
        try: 
            self.current_step.on_reload()
        except Exception as e:
            messagebox.showerror(
                title="Error",
                message="Reloading current step failed: {}".format(e),
                parent=self)
            return

        # Update Button States
        if self._previous_button:
            self._previous_button.config(
                state=NORMAL if self.current_step._previous_step_available else DISABLED)
        if self._next_button:
            self._next_button.config(
                state=NORMAL if self.current_step._next_step_available else DISABLED)
        if self._finish_button:
            self._finish_button.config(
                state=NORMAL if self.current_step.enable_finish else DISABLED)

        # Remove all widgets in main frame
        for child in self._step_frame.winfo_children():
            child.forget()

        # Create step frame and build it by calling step builder
        frame = CustomFrame(self._step_frame)
        self.current_step.render(frame)
        frame.pack(side=LEFT, fill=BOTH, padx=10, pady=(10, 2), expand=1)

        self.update_idletasks()

    @property
    def current_step(self) -> Type[WizardStep]:
        return self._current_step

    @current_step.setter
    def current_step(self, step: Type[WizardStep]) -> None:
        """
        Sets the current step, updates the sidebar and resets error.

        Reloads Wizard afterwards.
        """
        self._set_sidebar_color(color=self.INACTIVE_LABEL_COLOR)
        self.set_error("")

        self._current_step = step
        
        self._set_sidebar_color(color=self.ACTIVE_LABEL_COLOR)
        
        self.__reload__()

    def set_error(self, message):
        if not self._error_label:
            return

        self._error_label.config(text=message)

    def on_cancel(self) -> bool:
        return True

    def on_finish(self) -> bool:
        return True
        
    def _on_previous(self):
        if not self.current_step:
            return

        if self.current_step._previous_step_available:
            try: 
                if not self.current_step.on_previous():
                    return
            except Exception as e:
                messagebox.showerror(
                    title="Error",
                    message="Proceeding to previous step failed: {}".format(e),
                    parent=self)
                return

            self.current_step.previous_step.on_enter()
            self.current_step = self.current_step.previous_step

    def _on_next(self):
        if not self.current_step:
            return

        if self.current_step._next_step_available:
            try: 
                if not self.current_step.on_next():
                    return
            except Exception as e:
                messagebox.showerror(
                    title="Error",
                    message="Proceeding to next step failed: {}".format(e),
                    parent=self)
                return

            self.current_step.next_step.on_enter()
            self.current_step = self.current_step.next_step

    def _register_step_in_sidebar(self, step: Type[WizardStep]):
        if step.title is None or self._sidebar_frame is None:
            return

        sidebar_label = Label(
            self._sidebar_frame,
            anchor="w",
            text=step.title,
            foreground=self.INACTIVE_LABEL_COLOR)
        sidebar_label.pack(side=TOP, fill=X, padx=10, pady=5)    
        self._sidebar_labels[step] = sidebar_label

    def _set_sidebar_color(self, color):
        sidebar_label = self._sidebar_labels.get(self.current_step)
        if not sidebar_label:
            return

        sidebar_label.config(foreground=color)
