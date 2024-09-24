from udsoncan.request import Request
from udsoncan.response import Response
from udsoncan.exceptions import *
from udsoncan.base_service import BaseService, BaseResponseData
from udsoncan.response_code import ResponseCode


class ReadDataByPeriodicIdentifier(BaseService):
    _sid = 0x2A

    supported_negative_response = [
        ResponseCode.IncorrectMessageLengthOrInvalidFormat,
        ResponseCode.ConditionsNotCorrect,
        ResponseCode.RequestOutOfRange,
        ResponseCode.SecurityAccessDenied,
    ]

    class ResponseData(BaseResponseData):
        def __init__(self):
            super().__init__(ReadDataByPeriodicIdentifier)

    class InterpretedResponse(Response):
        service_data: "ReadDataByPeriodicIdentifier.ResponseData"

    @classmethod
    def make_request(cls) -> Request:
        raise NotImplementedError("Service is not implemented")

    @classmethod
    def interpret_response(cls, response: Response) -> InterpretedResponse:
        raise NotImplementedError("Service is not implemented")
