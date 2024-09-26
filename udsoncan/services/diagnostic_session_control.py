from __future__ import annotations
import struct
from udsoncan.request import Request
from udsoncan.response import Response
from udsoncan import latest_standard
from udsoncan.standards import StandardVersion
from udsoncan.exceptions import *
from udsoncan.base_service import BaseService, BaseSubfunction, ServiceData, uds_field
from udsoncan.response_code import ResponseCode
import udsoncan.tools as tools

from dataclasses import dataclass
from typing import Optional, cast, overload, Literal


@dataclass
class ResponseDataPost2006(ServiceData):
    """
    Parameters
    ----------
    p2_server_max: Optional[float]
        Default P2 max timing supported by the server for the activated diagnostic session. Applicable for 2013 version and above. Value in seconds.

    p2_star_server_max: Optional[float]
        Default P2* (NRC 0x78) max timing supported by the server for the activated diagnostic session. Applicable for 2013 version and above. Value in seconds
    """

    p2_server_max: float = uds_field(100.0, "H", resolution=.001)
    p2_star_server_max: float = uds_field(100.0, "H", resolution=.01)


@dataclass
class ResponseDataPre2006(ServiceData):
    """
    Parameters
    ----------
    session_param_records: bytes
        Manufacturer dependant.
    """

    # TODO: fix base class to allow variable length
    session_param_records: bytes = uds_field(b"", "2s")


class DiagnosticSessionControl(BaseService):
    _sid = 0x10

    supported_negative_response = [
        ResponseCode.SubFunctionNotSupported,
        ResponseCode.IncorrectMessageLengthOrInvalidFormat,
        ResponseCode.ConditionsNotCorrect,
    ]

    payload_fmt = ">HH"

    class Session(BaseSubfunction):
        """
        DiagnosticSessionControl defined subfunctions
        """

        __pretty_name__ = "session"

        defaultSession = 1
        programmingSession = 2
        extendedDiagnosticSession = 3
        safetySystemDiagnosticSession = 4

    @classmethod
    def get_request_cls(
        cls, standard_version: StandardVersion = StandardVersion.latest()
    ) -> type[ServiceData]:
        """
        Main dispatcher for service classes.
        Service classes should override appropriately.
        Provides the appropriate dataclass to use for the request for the requested standard version.
        If standard version is irrelevant it may be simply ignored.

        Returns
        -------
        type[ServiceData]
            The class to use for the request payload
        """
        raise NotImplementedError

    @classmethod
    def get_response_cls(
        cls, standard_version: StandardVersion = StandardVersion.latest()
    ) -> type[ServiceData]:
        """
        Main dispatcher for service classes.
        Service classes should override appropriately.
        Provides the appropriate dataclass to use for the response for the requested standard version.
        If standard version is irrelevant it may be simply ignored.

        Returns
        -------
        type[ServiceData]
            The class to use for the response payload
        """
        if standard_version == StandardVersion.UDS_2006:
            return ResponseDataPre2006
        return ResponseDataPost2006

    @classmethod
    def make_request(cls, session: int) -> Request:
        """
        Generates a request for DiagnosticSessionControl service

        :param session: Service subfunction. Allowed values are from 0 to 0x7F
        :type session: int

        :raises ValueError: If parameters are out of range, missing or wrong type
        """

        tools.validate_int(session, min=0, max=0x7F, name="Session number")
        return Request(service=cls, subfunction=session)

    @overload
    @classmethod
    def interpret_response(
        cls, response: Response, standard_version: Literal[StandardVersion.UDS_2006]
    ) -> ResponseDataPre2006: ...

    @overload
    @classmethod
    def interpret_response(
        cls,
        response: Response,
        standard_version: Literal[
            StandardVersion.UDS_2013, StandardVersion.UDS_2020, StandardVersion.UDS_2020
        ],
    ) -> ResponseDataPost2006: ...

    @classmethod
    def interpret_response(
        cls,
        response: Response,
        standard_version: StandardVersion = StandardVersion.latest(),
    ):
        """
        Populates the response ``service_data`` property with an instance of :class:`DiagnosticSessionControl.ResponseData<udsoncan.services.DiagnosticSessionControl.ResponseData>`

        :param response: The received response to interpret
        :type response: :ref:`Response<Response>`

        :param standard_version: The version of the ISO-14229 (the year). eg. 2006, 2013, 2020
        :type standard_version: int

        :raises InvalidResponseException: If length of ``response.data`` is too short
        """
        return cls._interpret_response(response, standard_version)
