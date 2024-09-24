from udsoncan.request import Request
from udsoncan.response import Response
from udsoncan.exceptions import *
from udsoncan.base_service import BaseService, BaseResponseData
from udsoncan.response_code import ResponseCode


class ResponseOnEvent(BaseService):
    _sid = 0x86

    supported_negative_response = [
        ResponseCode.SubFunctionNotSupported,
        ResponseCode.IncorrectMessageLengthOrInvalidFormat,
        ResponseCode.ConditionsNotCorrect,
        ResponseCode.RequestOutOfRange,
    ]

    class ResponseData(BaseResponseData):
        def __init__(self):
            super().__init__(ResponseOnEvent)

    class InterpretedResponse(Response):
        service_data: "ResponseOnEvent.ResponseData"

    @classmethod
    def make_request(cls) -> Request:
        raise NotImplementedError("Service is not implemented")

    @classmethod
    def interpret_response(cls, response: Response) -> InterpretedResponse:
        raise NotImplementedError("Service is not implemented")
