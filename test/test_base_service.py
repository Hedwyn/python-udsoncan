"""
Test suite for some base_service utilities

@date: 25.09.2024
@author: Baptiste Pestourie
"""

from __future__ import annotations
from dataclasses import dataclass
import pytest
from udsoncan.base_service import (
    ServiceData,
    uds_field,
)


@dataclass
class SimpleServiceData(ServiceData):
    """
    A ServiceData child class without any subfunction specifier
    """

    an_int: int = uds_field(42, "d")
    a_float: float = uds_field(3.14, "f")


def test_service_data_sanity() -> None:
    """
    Sanity checks for the ServiceData class
    """
    assert ServiceData.get_parameter_names() == ()
    assert SimpleServiceData.get_parameter_names() == ("an_int", "a_float")
    assert SimpleServiceData.get_parameter_scaling_factors() == (1, 1)
    assert SimpleServiceData.get_parameter_resolutions() == (1, 1)


def test_service_data_get_parameters() -> None:
    """
    Verifies that parameter names are properly extracted for
    ServiceData classes without subfunction specific parameters
    """
    data = SimpleServiceData()
    assert tuple(data.get_parameter_values()) == (42, 3.14)
    iterator = iter(data.get_parameter_items())
    assert next(iterator) == ("an_int", 42)
    assert next(iterator) == ("a_float", 3.14)


def test_service_data_get_payload_fmt() -> None:
    """
    Checks that the payload format is properly computed
    from the declared uds_field objects
    """
    SimpleServiceData._iter_payload_fmt() == (">df",)


def test_service_data_pack_no_raise() -> None:
    """
    Checks that packing does not raise any error
    """
    data = SimpleServiceData()
    data.pack()


# Note: using power of two for floats to avoid dealing with rounding errors here
@pytest.mark.parametrize(
    "int_value,float_value",
    [
        (0, 0.0),
        (42, 1 / 8),
        (-17, 1 / 8),
    ],
)
def test_service_data_pack_inverts_unpack(int_value: int, float_value: float) -> None:
    """
    Checks that running pack->unpack returns the original data
    """
    base_data = SimpleServiceData(an_int=int_value, a_float=float_value)
    assert base_data.unpack(base_data.pack()) == base_data


@dataclass
class AdvancedServiceData(ServiceData):
    """
    Uses parameter that are sub-function dependant
    """

    an_int: int = uds_field(42, "d")
    a_float: float = uds_field(3.14, "f", subfunctions=1)


@dataclass
class ScaledServiceData(ServiceData):
    """
    Uses parameter that have a resolution
    """

    an_int: int = uds_field(42, "d")
    a_float: float = uds_field(3.14, "f", subfunctions=1, resolution=0.1)


@pytest.mark.parametrize("data_cls", [ScaledServiceData, AdvancedServiceData])
def test_get_subfunction_parameters(
    data_cls: type[ScaledServiceData] | type[AdvancedServiceData],
) -> None:
    """
    Checks that parameters that are only relevant to a particular subfunction
    are properly extracted, and that Internal parameters are ruled out.
    """
    assert data_cls.get_parameter_names() == ("an_int",)
    assert data_cls.get_parameter_names(1) == ("an_int", "a_float")


@pytest.mark.parametrize("data_cls", [ScaledServiceData, AdvancedServiceData])
@pytest.mark.parametrize("subfunction,expects", [(0, ">d"), (1, ">df")])
def test_payload_fmt_with_subfunctions(
    data_cls: type[ScaledServiceData] | type[AdvancedServiceData],
    subfunction: int,
    expects: str,
) -> None:
    """
    For ServiceData with subfunction-specific fields,
    verifies that the payload format is properly computed for each subfunction
    """
    assert data_cls.get_payload_fmt(subfunction) == expects
    assert data_cls._iter_payload_fmt(subfunction) == (expects,)


@pytest.mark.parametrize(
    "int_value,float_value",
    [
        (0, 0.0),
        (42, 1 / 8),
        (-17, 1 / 8),
    ],
)
@pytest.mark.parametrize("subfunction", [0, 1])
def test_service_data_pack_inverts_unpack_advanced(
    int_value: int, float_value: int, subfunction: int
) -> None:
    """
    Check that pack/unpack function work properly for service data
    having customized parameters for each subfunction
    """
    base_data = AdvancedServiceData(
        subfunction=subfunction, an_int=int_value, a_float=float_value
    )
    unpacked_data = base_data.unpack(base_data.pack(), subfunction=subfunction)
    assert unpacked_data.an_int == base_data.an_int
    if subfunction == 1:
        assert unpacked_data.a_float == float_value


@pytest.mark.parametrize(
    "int_value,float_value",
    [
        (0, 0.0),
        (42, 1 / 8),
        (-17, 1 / 8),
    ],
)
def test_service_data_scaling(
    int_value: int,
    float_value: int,
) -> None:
    """
    Checks that resolution/scaling factors are properly extracted for each subfunction
    """
    assert ScaledServiceData.get_parameter_resolutions(0) == (1,)
    assert ScaledServiceData.get_parameter_resolutions(1) == (1, 0.1)
    base_data = ScaledServiceData(subfunction=1, an_int=int_value, a_float=float_value)
    assert tuple(base_data.get_parameter_values(1, scale=True)) == (
        int_value,
        float_value * 10,
    )


@pytest.mark.parametrize(
    "int_value,float_value",
    [
        (0, 0.0),
        (42, 1 / 8),
        (-17, 1 / 8),
    ],
)
def test_service_data_resolution_packing(
    int_value: int,
    float_value: int,
) -> None:
    """
    Checks that resolution are properly applied when packing ServiceData objects
    """
    base_data = ScaledServiceData(subfunction=1, an_int=int_value, a_float=float_value)
    # Note: we simply load the values into the non-scaled version of the same object
    # and verify that the original value has been scaled
    unpacked = AdvancedServiceData.unpack(base_data.pack(), subfunction=1)
    assert unpacked.an_int == base_data.an_int
    assert unpacked.a_float == base_data.a_float * 10


@pytest.mark.parametrize(
    "int_value,float_value",
    [
        (0, 0.0),
        (42, 1 / 8),
        (-17, 1 / 8),
    ],
)
def test_service_data_resolution_unpacking(
    int_value: int,
    float_value: int,
) -> None:
    """
    Checks that resolution are properly applied when packing ServiceData objects
    """
    base_data = AdvancedServiceData(
        subfunction=1, an_int=int_value, a_float=float_value
    )
    # Note: we simply load the values into the non-scaled version of the same object
    # and verify that the original value has been scaled
    unpacked = ScaledServiceData.unpack(base_data.pack(), subfunction=1)
    assert unpacked.an_int == base_data.an_int
    assert unpacked.a_float == base_data.a_float / 10


@dataclass
class SimpleVariadicServiceData(ServiceData):
    """
    A service data class that has a single variadic field
    """

    an_int: int = uds_field(42, "d")
    some_bytes: bytes = uds_field(b"", "h{}s")
    a_float: float = uds_field(3.14, "f")


def test_service_data_variadic_payload_fmt() -> None:
    assert SimpleVariadicServiceData._iter_payload_fmt() == (">dh", ">{}sf")


def test_service_data_variadic_sanity() -> None:
    assert SimpleVariadicServiceData.has_variadic_fields() is True
    assert SimpleVariadicServiceData.get_variadic_fields_indexes() == (1,)


def test_service_data_variadic_length() -> None:
    test_data = b"\x01\x02\x03\x04\x05\x06"
    data = SimpleVariadicServiceData()
    # length field requires 2 bytes
    assert len(data.pack()) == len(SimpleServiceData().pack()) + 2
    data.some_bytes = test_data
    assert len(data.pack()) == len(SimpleServiceData().pack()) + 6 + 2
    # binary data starts after 8 bytes as first element is an int64, length is two bytes
    packed = data.pack()
    assert packed[8:10] == b"\x00\x06"
    assert packed[10:16] == test_data


def test_service_data_pack_inverts_unpack_variadic() -> None:
    test_data = b"\x01\x02\x03\x04\x05\x06"
    data = SimpleVariadicServiceData(some_bytes=test_data)
    unpacked = SimpleVariadicServiceData.unpack(data.pack())

    assert data.some_bytes == unpacked.some_bytes
