#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY;
for details see LICENSE file.
"""

import unittest
from unittest.mock import Mock
from parameterized import parameterized

from LabExT.Tests.Utils import with_stage_discovery_patch

from LabExT.Movement.config import Orientation, DevicePort, State
from LabExT.Movement.MoverNew import MoverNew
from LabExT.Movement.Stages.DummyStage import DummyStage
from LabExT.Movement.Calibration import Calibration, assert_minimum_state_for_coordinate_system, CalibrationError


class AssertMinimumStateForCoordinateSystemTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calibration = Mock(spec=Calibration)
        self.func = Mock()
        self.func.__name__ = "Dummy Function"

        self.low_state = 0
        self.high_state = 1

        return super().setUp()

    def test_raises_error_if_coordinate_system_is_not_fixed(self):
        self.calibration.coordinate_system = None

        with self.assertRaises(CalibrationError):
            assert_minimum_state_for_coordinate_system()(self.func)(self.calibration)
        
        self.func.assert_not_called()
