#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabExT  Copyright (C) 2022  ETH Zurich and Polariton Technologies AG
This program is free software and comes with ABSOLUTELY NO WARRANTY; for details see LICENSE file.
"""

from abc import ABC, abstractmethod, abstractproperty
from enum import Enum
from typing import NamedTuple, Type
import numpy as np
from scipy.spatial.transform import Rotation

class Coordinate:
    @classmethod
    def from_list(cls, list: list):
        return cls(*list[:3])

    @classmethod
    def from_array(cls, array: np.ndarray):
        return cls(*array.tolist()[:3])

    def __init__(self, x=0, y=0, z=0) -> None:
        self.x = x
        self.y = y
        self.z = z

    def __str__(self) -> str:
        """
        Prints Coordinate rounded to 2 digits
        """
        return "[{:.2f}, {:.2f}, {:.2f}]".format(self.x, self.y, self.z)

    def __add__(self, other):
        if not isinstance(other, type(self)):
            raise ValueError("Invalid types: {} and {} cannot be added.".format(type(self), type(other)))

        return type(self).from_array(self.to_array() + other.to_array())

    def __sub__(self, other):
        if not isinstance(other, type(self)):
            raise ValueError("Invalid types: {} and {} cannot be subtracted.".format(type(self), type(other)))

        return type(self).from_array(self.to_array() - other.to_array())

    def to_list(self) -> list:
        return [self.x, self.y, self.z]

    def to_array(self) -> np.ndarray:
        return np.array(self.to_list())


class StageCoordinate(Coordinate):
    pass


class ChipCoordinate(Coordinate):
    pass


class CoordinatePairing(NamedTuple):
    calibration: object
    stage_coordinate: Type[StageCoordinate]
    device: object
    chip_coordinate: Type[ChipCoordinate]

class Transformation(ABC):
    """
    Abstract interface for transformations.
    """

    @abstractmethod
    def __init__(self) -> None:
        pass

    @abstractproperty
    def is_valid(self):
        """
        Returns True if the transformation is valid.
        """
        pass

    @abstractmethod
    def chip_to_stage(self, chip_coordinate: Type[ChipCoordinate]) -> Type[StageCoordinate]:
        """
        Transforms a coordinate in chip space to stage space.
        """
        pass

    @abstractmethod
    def stage_to_chip(self, stage_coordinate: Type[StageCoordinate]) -> Type[ChipCoordinate]:
        """
        Transforms a coordinate in stage space to chip space.
        """
        pass


    @abstractmethod
    def reset(self) -> None:
        """
        Resets transformation.
        """
        pass


class Axis(Enum):
    """Enumerate different channels. Each channel represents one axis."""
    X = 0
    Y = 1
    Z = 2

    def __str__(self) -> str:
        return "{}-Axis".format(self.name)


class Direction(Enum):
    """
    Enumerate different axis directions.
    """
    POSITIVE = 1
    NEGATIVE = -1

    def __str__(self) -> str:
        return self.name.capitalize()


class AxesRotation:
    """
    Assigns a stage axis (X,Y,Z) to the positive chip axes (X,Y,Z) with associated direction.
    If the assignment is well defined, a rotation matrix is calculated, which rotates the given chip coordinate perpendicular to the stage coordinate.
    The rotation matrix (3x3) is therefore a signed permutation matrix of the coordinate axes of the chip.

    Each row of the matrix represents a chip axis. Each column of the matrix represents a stage axis.
    """

    def __init__(self) -> None:
        self._n = len(Axis)
        self._matrix = np.identity(len(Axis))  # 3x3 identity matrix

    def reset(self):
        self._n = len(Axis)
        self._matrix = np.identity(len(Axis))  # 3x3 identity matrix

    def update(self, chip_axis: Axis, direction: Direction, stage_axis: Axis):
        """
        Updates the axes rotation matrix.
        Replaces the column vector of given chip with signed (direction) i-th unit vector (i is stage)
        """
        if not (isinstance(chip_axis, Axis) and isinstance(stage_axis, Axis)):
            raise ValueError("Unknown axes given for calibration.")

        if not isinstance(direction, Direction):
            raise ValueError("Unknown direction given for calibration.")

        # Replacing column of chip with signed (direction) i-th unit vector (i
        # is stage)
        self._matrix[:, chip_axis.value] = np.eye(
            1, 3, stage_axis.value) * direction.value

    @property
    def is_valid(self):
        """
        Checks if given matrix is a permutation matrix.

        A matrix is a permutation matrix if the sum of each row and column is exactly 1.
        """
        abs_matrix = np.absolute(self._matrix)
        return (
            abs_matrix.sum(
                axis=0) == 1).all() and (
            abs_matrix.sum(
                axis=1) == 1).all()


    def rotate_chip_to_stage(self, chip_coordinate: Type[ChipCoordinate]) -> Type[StageCoordinate]:
        """
        Rotates the chip coordinate (x,y,z) according to the axes calibration.

        Raises CalibrationError error if matrix is not valid.
        """
        if not self.is_valid:
            raise ValueError(
                "The current axis assignment does not define a valid 90 degree rotation. ")
        
        return StageCoordinate.from_array(
            self._matrix.dot(chip_coordinate.to_array()))

    def rotate_stage_to_chip(self, stage_coordinate: Type[StageCoordinate]) -> Type[ChipCoordinate]:
        """
        Rotates the stage coordinate (x,y,z) according to the axes calibration.

        Raises CalibrationError error if matrix is not valid.
        """
        if not self.is_valid:
            raise ValueError(
                "The current axis assignment does not define a valid 90 degree rotation. ")

        return ChipCoordinate.from_array(
            np.linalg.inv(self._matrix).dot(stage_coordinate.to_array()))



class SinglePointTransformation(Transformation):
    """
    Performs a translation based on a fixed single point.
    """
    def __init__(self, axes_rotation: Type[AxesRotation]) -> None:
        self.pairing = None

        self._chip_coordinate: Type[ChipCoordinate] = None
        self._stage_coordinate: Type[StageCoordinate] = None
        self._stage_offset: Type[StageCoordinate] = None

        self._axes_rotation = axes_rotation

    def __str__(self) -> str:
        if self._stage_offset is None:
            return "No single point fixed"

        return "Stage-Coordinate {} fixed with Chip-Coordinate {}".format(
            self._stage_coordinate, self._chip_coordinate)

    def reset(self):
        self.pairing = None
        self._chip_coordinate: Type[ChipCoordinate] = None
        self._stage_coordinate: Type[StageCoordinate] = None
        self._stage_offset: Type[StageCoordinate] = None

    @property
    def is_valid(self):
        """
        Returns True if single point transformation is defined.
        """
        return self._stage_offset is not None and self._axes_rotation.is_valid

    def update(self, pairing: Type[CoordinatePairing]) -> None:
        """
        Updates the offset based on a coordinate pairing.
        """
        if pairing.chip_coordinate is None or pairing.stage_coordinate is None:
            raise ValueError("Incomplete Pairing")

        self.pairing = pairing

        self._chip_coordinate = pairing.chip_coordinate
        self._stage_coordinate = pairing.stage_coordinate

        self._stage_offset = self._axes_rotation.rotate_chip_to_stage(self._chip_coordinate) - self._stage_coordinate

    def chip_to_stage(self, chip_coordinate: Type[ChipCoordinate]) -> Type[StageCoordinate]:
        """
        Translates chip coordinate to stage coordinate
        """
        if not self.is_valid:
            raise RuntimeError("Cannot translate with invalid fixation. ")

        return self._axes_rotation.rotate_chip_to_stage(chip_coordinate) + self._stage_offset

    def stage_to_chip(self, stage_coordinate: Type[StageCoordinate]) -> Type[ChipCoordinate]:
        """
        Translates stage coordinate to chip coordinate
        """
        if not self.is_valid:
            raise RuntimeError("Cannot translate with invalid fixation. ")

        return self._axes_rotation.rotate_stage_to_chip(stage_coordinate - self._stage_offset)


class KabschRotation(Transformation):
    """
    Estimate a rotation to optimally align two sets of vectors.

    Find a rotation to align a set of stage coordinates with a set of chip coordinates.
    For more information see Kabsch Algorithm.

    We require 3 points for a 3D transformation.
    More points are possible and may increase the accuracy.
    """

    MIN_POINTS = 3

    def __init__(self) -> None:
        self.pairings = []

        self._chip_coordinates = np.empty((0, 3), float)
        self._stage_coordinates = np.empty((0, 3), float)

        self._rotation = None
        self._rmsd = None

        self._chip_offset = None
        self._stage_offset = None

    def __str__(self) -> str:
        if not self.is_valid:
            return "No valid rotation defined ({}/{} Points set)".format(
                len(self.pairings), self.MIN_POINTS)

        return "Rotation defined with {} Points (RMSD: {})".format(len(self.pairings), self.rmsd)

    def reset(self):
        self.pairings = []

        self._chip_coordinates = np.empty((0, 3), float)
        self._stage_coordinates = np.empty((0, 3), float)

        self._rotation = None
        self._rmsd = None

        self._chip_offset = None
        self._stage_offset = None

    @property
    def is_valid(self) -> bool:
        """
        Returns True if Kabsch transformation is defined.
        """
        return len(self.pairings) >= self.MIN_POINTS

    @property
    def rmsd(self):
        """
        Returns RMSD of rotation
        """
        return self._rmsd if self.is_valid else "-"

    def update(self, pairing: Type[CoordinatePairing]) -> None:
        """
        Updates the transformation by adding a new pairing.
        """
        if not isinstance(pairing, CoordinatePairing) or not all(pairing):
            raise ValueError(
                "Use a complete CoordinatePairing object to update the rotation. ")

        if any(p.device == pairing.device for p in self.pairings):
            raise ValueError(
                "A pairing with this device has already been saved.")

        self.pairings.append(pairing)

        self._chip_coordinates = np.append(
            self._chip_coordinates,
            [pairing.chip_coordinate.to_list()],
            axis=0)
        self._stage_coordinates = np.append(
            self._stage_coordinates,
            [pairing.stage_coordinate.to_list()],
            axis=0)

        # Calculate mean for each set
        self._chip_offset = ChipCoordinate.from_array(self._chip_coordinates.mean(axis=0))
        self._stage_offset = StageCoordinate.from_array(self._stage_coordinates.mean(axis=0))

        # Create Rotation with centered vectors
        self._rotation, self._rmsd = Rotation.align_vectors(
            (self._chip_coordinates - self._chip_offset.to_array()),
            (self._stage_coordinates - self._stage_offset.to_array()))

    def chip_to_stage(self, chip_coordinate: Type[ChipCoordinate]) -> Type[StageCoordinate]:
        """
        Transforms a position in chip coordinates to stage coordinates
        """
        if not self.is_valid:
            raise RuntimeError("Cannot rotation with invalid transformation. ")

        centered_chip_coordinate = chip_coordinate - self._chip_offset

        return StageCoordinate.from_array(
            self._rotation.apply(centered_chip_coordinate.to_array(),
            inverse=True)) + self._stage_offset

    def stage_to_chip(self, stage_coordinate: Type[StageCoordinate]) -> Type[ChipCoordinate]:
        """
        Transforms a position in stage coordinates to chip coordinates
        """
        if not self.is_valid:
            raise RuntimeError("Cannot rotation with invalid transformation. ")

        centered_stage_coordinate = stage_coordinate - self._stage_offset

        return ChipCoordinate.from_array(
            self._rotation.apply(centered_stage_coordinate.to_array())) + self._chip_offset  
