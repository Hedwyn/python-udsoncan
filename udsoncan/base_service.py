"""
Base class and model for all UDS services
"""

from __future__ import annotations
from typing import (
    Iterable,
    Optional,
    Union,
    Iterator,
    TypeVar,
    cast,
    Any,
    Self,
    ClassVar,
    Final,
    TYPE_CHECKING,
)
import inspect
import struct
from abc import ABC
from dataclasses import dataclass, Field, field, fields
from functools import cache

from .standards import StandardVersion
from .response_code import ResponseCode

if TYPE_CHECKING:
    from .response import Response

# --- Constants --- #
_ENDIANNESS: Final[str] = ">"
NO_SUBFUNCTION: Final[int] = 0
_FIELD_DEFAULTS: Final[dict[str, Any]] = {
    k: v.default
    for k, v in inspect.signature(field).parameters.items()
    if v.default is not inspect.Parameter.empty
}

# --- Type aliasing --- #
UdsPayloadTypes = Union[int, float, bytes, str]
T = TypeVar("T", bound=UdsPayloadTypes)

# ---Errors --- #
# aliasing struct.error to get a more compelling error name
TranscodeError = struct.error


class UdsField(Field):
    """
    An extended dataclasses `Field` that carry extra metadata
    required fopr UDS.
    Parameters that are added on top of regular `Field` are detailed below.

    Parameters
    ----------
    fmt: str
        The format string defining how struct module should encode/decode the value.
        Refer to struct module to learn about the format characters.
        Note that the format for a given dataclass is built by iterating over the
        UdsField format in declaration order.

    subfunctions: int | Iterable[int]
        A list of subfunctions that this field applies to.
        This field vlaue will only be included if encoding a subfunction that is supported.
        Passing no value (empty tuple, which is the default) will include this field for
        ALL subfunctions.

    resolution: int | float
        Optional, for integer values allows to scaling the value to a float.
        Should be use for UDS parameters that need to be rescaled with a predefined resolution.
    """

    def __init__(
        self,
        *args: Any,
        fmt: str,
        subfunctions: int | Iterable[int] = (),
        resolution: int | float = 1,
        **kwargs,
    ) -> None:
        self.subfunctions: set[int] = (
            set((subfunctions,)) if isinstance(subfunctions, int) else set(subfunctions)
        )
        self.fmt = fmt
        self.resolution = resolution
        # Note: for those confused, 1 / 1 = 1.0 and not 1
        # i.e. you get a float instead of int - which will not work on sequences
        self.scale_factor = 1 if resolution == 1 else 1.0 / self.resolution
        super().__init__(*args, **kwargs)

    @property
    def has_variable_length(self) -> bool:
        """
        Returns
        -------
        bool
            True the length of the binary is not statically known.
            False otherwise
        """
        return "{}" in self.fmt

    def supports_subfonction(self, subfunction: int) -> bool:
        """
        Returns
        -------
        bool
            True if the field should be included for this subfunction
            False otherwise
        """
        return not self.subfunctions or subfunction in self.subfunctions


def uds_field(
    default: T, fmt: str, subfunctions: int | Iterable[int] = (), **field_kwargs: Any
) -> T:
    """
    Equivalent of dataclasses `field` for `UdsField`.
    Builds an UdsField from the given data.

    Example
    -------
    @dataclass
    class AdvancedServiceData(ServiceData):
        an_int: int = uds_field(42, "d")
        a_float: float = uds_field(3.14, "f", subfunctions=1)

    Notes
    -----
    This function deliberately uses a incorrect return type annotation.
    This is required for the dataclasses declaration to be interpreted correctly
    by the type checker.
    Note that type checkers uses the exact same trick internally by stubbing
    the return type of `field` to T instead of Field[T].
    """
    kwargs = _FIELD_DEFAULTS.copy()
    kwargs.update(field_kwargs)
    kwargs["default"] = default
    # cast is required for uds fields to be handled properly by type checkers
    return cast(T, UdsField(subfunctions=subfunctions, fmt=fmt, **kwargs))


@dataclass
class ServiceData:
    """
    Base class for Request/Response data

    """

    subfunction: int = field(default=NO_SUBFUNCTION)
    # maps each subfunction to the binary format that should be used by struct
    # to pack the data

    @classmethod
    def _iter_parameter_fields(
        cls, subfunction: int = NO_SUBFUNCTION
    ) -> Iterator[UdsField]:
        """
        Yields
        ------
        UdsField
            All the fields that are relevant to the given subfunction
        """
        for f in fields(cls):
            # print(type(f), f)
            if isinstance(f, UdsField) and f.supports_subfonction(subfunction):
                yield f

    @classmethod
    def _iter_parameter_names(cls, subfunction: int = NO_SUBFUNCTION) -> Iterator[str]:
        """
        Yields
        ------
        str
            Name of the parameters that should be included for the passed subfunction
        """
        for f in cls._iter_parameter_fields(subfunction):
            yield f.name

    @classmethod
    @cache
    def get_payload_fmt(cls, subfunction: int = NO_SUBFUNCTION) -> str:
        """
        Returns
        -------
        str
            The format string used for the binary data in this object.
            Note that for services with dynamic data lengths, it requires format arguments
            for the lengths of the fields.
        """
        return _ENDIANNESS + "".join(
            f.fmt for f in cls._iter_parameter_fields(subfunction)
        )

    @classmethod
    @cache
    def _iter_payload_fmt(cls, subfunction: int = NO_SUBFUNCTION) -> tuple[str, ...]:
        """
        Returns
        -------
        tuple[str, ...]
            A series of format strings of known size.
            Since struct cnanot handle dynamic-length fields, we have to split
            the format strings into length terminated chunks,
            then inject the length at the beginning of each chunk
            by formatting the next format string.

        """
        joined_fmt = "".join(f.fmt for f in cls._iter_parameter_fields(subfunction))
        static_chunks = joined_fmt.split("{}")
        if not static_chunks:
            return ()
        return (
            _ENDIANNESS + static_chunks[0],
            *(_ENDIANNESS + "{}" + chunk for chunk in static_chunks[1:]),
        )

    @classmethod
    @cache
    def get_parameter_names(cls, subfunction: int = NO_SUBFUNCTION) -> tuple[str, ...]:
        """
        Returns
        -------
        tuple[str, ...]
            Name of the parameters that should be included for the passed subfunction
        """
        return tuple(cls._iter_parameter_names(subfunction))

    @classmethod
    @cache
    def get_variadic_parameter_names(
        cls, subfunction: int = NO_SUBFUNCTION
    ) -> tuple[str, ...]:
        """
        Returns
        ------
        tuple[str, ...]
            Name of the parameters that should be included for the passed subfunction
        """
        return tuple(
            (
                f.name
                for f in cls._iter_parameter_fields(subfunction)
                if f.has_variable_length
            )
        )

    @classmethod
    @cache
    def get_parameter_resolutions(
        cls, subfunction: int = NO_SUBFUNCTION
    ) -> tuple[float, ...]:
        """
        Returns
        -------
        tuple[float, ...]
            The resolutions to apply to parameters when decoding,
            as a vector.
        """
        return tuple(f.resolution for f in cls._iter_parameter_fields(subfunction))

    @classmethod
    @cache
    def get_parameter_scaling_factors(
        cls, subfunction: int = NO_SUBFUNCTION
    ) -> tuple[float, ...]:
        """
        Returns
        -------
        tuple[float, ...]
            The scaling factors to apply to parameters when encoding,
            basically the inverse of resolution
        """
        return tuple(f.scale_factor for f in cls._iter_parameter_fields(subfunction))

    def get_parameter_values(
        self, subfunction: int = NO_SUBFUNCTION, scale: bool = False
    ) -> Iterator[UdsPayloadTypes]:
        """
        Yields
        ------
        str
            Name of the parameters that should be included for the passed subfunction

        scale: bool
            If enabled, rescales the parameters that have defined a resolution.
            You should typically enable this flag if when extracting this data to
            encode it in binary.
        """
        base_map = map(self.__getattribute__, self._iter_parameter_names(subfunction))
        if not scale:
            return base_map
        # otherwise applying resolutions
        return (
            val * factor
            for val, factor in zip(
                base_map, self.get_parameter_scaling_factors(subfunction)
            )
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ServiceData):
            return NotImplemented
        return all(
            (
                kv_1 == kv_2
                for kv_1, kv_2 in zip(
                    self.get_parameter_items(), other.get_parameter_items()
                )
            )
        )

    def get_parameter_items(
        self, subfunction: int = NO_SUBFUNCTION
    ) -> Iterator[tuple[str, UdsPayloadTypes]]:
        """
        Yields
        ------
        str
            Name of the parameters that should be included for the passed subfunction
        """
        return zip(
            self.get_parameter_names(subfunction),
            self.get_parameter_values(subfunction, scale=True),
        )

    @classmethod
    def _get_fmt_size_pairs(cls) -> tuple[tuple[str, int], ...]:
        return tuple(
            (fmt, struct.calcsize(fmt.replace("{}", "")))
            for fmt in cls._iter_payload_fmt()
        )

    @classmethod
    def unpack(
        cls, data: bytes | None = None, subfunction: int = NO_SUBFUNCTION
    ) -> Self:
        """
        Parameters
        ----------
        data: bytes | None
            Data from which to build this object

        subfunction: int
            ID of the subfunction that was used by this request.
            Note that it is extracted independently from the payload,
            thus has to be treated separately.
        """
        parameter_names = cls.get_parameter_names(subfunction)
        if not parameter_names:
            if data:
                raise ValueError(
                    f"Binary data got passed to {cls.__name__} despite expecting no parameter "
                    f"expected by subfunction {subfunction}. "
                    "Consider checking the subfunction ID"
                )
            return cls()

        if not data:
            raise ValueError(
                f"{cls.__name__} expects parameters {parameter_names} yet no data was passed"
            )

        format_strings = cls._iter_payload_fmt(subfunction)
        if format_strings.__len__() == 1:
            (fmt,) = format_strings
            args = struct.unpack(fmt, data)

            resolutions = cls.get_parameter_resolutions(subfunction)
            kwargs = {
                k: v * res for k, v, res in zip(parameter_names, args, resolutions)
            }
            return cls(subfunction=subfunction, **kwargs)

        start_index = 0
        end_index = 0
        args = []
        for fmt, size in cls._get_fmt_size_pairs():
            if args:
                next_length = args.pop()
                end_index += next_length
                fmt = fmt.format(next_length)
            end_index += size
            args.extend(struct.unpack(fmt, data[start_index:end_index]))
            start_index = end_index

        resolutions = cls.get_parameter_resolutions(subfunction)
        kwargs = {k: v * res for k, v, res in zip(parameter_names, args, resolutions)}
        return cls(subfunction=subfunction, **kwargs)

    @classmethod
    @cache
    def has_variadic_fields(cls, subfunction: int = NO_SUBFUNCTION) -> bool:
        return any(
            (f.has_variable_length for f in cls._iter_parameter_fields(subfunction))
        )

    @classmethod
    @cache
    def get_variadic_fields_indexes(
        cls, subfunction: int = NO_SUBFUNCTION
    ) -> tuple[int, ...]:
        return tuple(
            i
            for i, f in enumerate(cls._iter_parameter_fields(subfunction))
            if f.has_variable_length
        )

    def pack(self) -> bytes:
        """
        Converts this object to bytes
        """
        subfunction = self.subfunction
        format_strings: tuple[str, ...] = self._iter_payload_fmt(subfunction)

        if not format_strings:
            return b""

        subfunction_params = self.get_parameter_names(self.subfunction)
        # generator accessing the values of arguments in this object
        value_getter = map(self.__getattribute__, subfunction_params)
        # another comprehension applying the scaling factors to the values
        args: Iterable[UdsPayloadTypes] = (
            val * scale
            for val, scale in zip(
                value_getter, self.get_parameter_scaling_factors(self.subfunction)
            )
        )
        # In case of only static-lengths, we can use the struct.pack function directly
        if format_strings.__len__() == 1:
            return struct.pack(format_strings[0], *args)

        # Otherwise, we have to inject the required length one-by-one

        arg_list = list(args)
        # Getting the positions of length parameters within the packed format (cached)
        length_indexes = self.get_variadic_fields_indexes(subfunction)

        # Computing these lengths
        lengths = tuple(map(len, (arg_list[i] for i in length_indexes)))
        # inserting the lengths in the argument list
        for length, position in zip(lengths, length_indexes):
            arg_list.insert(position, length)

        # Injecting the lenghts into the struct format string
        fmt = self.get_payload_fmt().format(*lengths)

        # Now can can pack
        return struct.pack(fmt, *arg_list)


class BaseResponseData:
    """
    Legacy implementation
    """

    def __init__(self, service_class):
        if not issubclass(service_class, BaseService):
            raise ValueError("service_class must be a service class")

        self.service_class = service_class

    def __repr__(self):
        return "<%s (%s) at 0x%08x>" % (
            self.__class__.__name__,
            self.service_class.__name__,
            id(self),
        )


class BaseSubfunction:
    @classmethod
    def get_name(cls, subfn_id: int) -> str:
        attributes = inspect.getmembers(cls, lambda a: not (inspect.isroutine(a)))
        subfn_list = [
            a for a in attributes if not (a[0].startswith("__") and a[0].endswith("__"))
        ]

        for subfn in subfn_list:
            if isinstance(subfn[1], int):
                if subfn[1] == subfn_id:  # [1] is value
                    return subfn[0]  # [0] is property name
            elif isinstance(subfn[1], tuple):
                if subfn_id >= subfn[1][0] or subfn_id <= subfn[1][1]:
                    return subfn[0]
        name = (
            cls.__name__ if not hasattr(cls, "__pretty_name__") else cls.__pretty_name__
        )
        return "Custom %s" % name


class EmptyServiceData(ServiceData):
    """
    Default class to use for Request/Response that do no take any parameter
    """

    payload_fmt: ClassVar[str | None] = None


class BaseService(ABC):
    always_valid_negative_response = [
        ResponseCode.GeneralReject,
        ResponseCode.ServiceNotSupported,
        ResponseCode.ResponseTooLong,
        ResponseCode.BusyRepeatRequest,
        ResponseCode.NoResponseFromSubnetComponent,
        ResponseCode.FailurePreventsExecutionOfRequestedAction,
        ResponseCode.SecurityAccessDenied,  # ISO-14229:2006 Table A.1:  "Besides the mandatory use of this negative response code as specified in the applicable services within ISO 14229, this negative response code can also be used for any case where security is required and is not yet granted to perform the required service."
        ResponseCode.AuthenticationRequired,  # ISO-14229:2020 Figure 5 - General server response behaviour
        ResponseCode.SecureDataTransmissionRequired,  # ISO-14229:2020 Figure 5 - General server response behaviour
        ResponseCode.SecureDataTransmissionNotAllowed,  # ISO-14229:2020 Figure 5 - General server response behaviour
        ResponseCode.RequestCorrectlyReceived_ResponsePending,
        ResponseCode.ServiceNotSupportedInActiveSession,
        ResponseCode.ResourceTemporarilyNotAvailable,
    ]

    _sid: int
    _use_subfunction: bool
    supported_negative_response: list[int]

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
        return EmptyServiceData

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
        return EmptyServiceData

    @classmethod  # Returns the service ID used for a client request
    def request_id(cls) -> int:
        return cls._sid

    @classmethod  # Returns the service ID used for a server response
    def response_id(cls) -> int:
        return cls._sid + 0x40

    @classmethod
    def _interpret_response(
        cls,
        response: Response,
        standard_version: StandardVersion = StandardVersion.latest(),
    ) -> ServiceData:
        """
        Base internal primitive to interpret a response.
        """
        response_cls = cls.get_response_cls(standard_version)
        if response.data is None:
            return response_cls()
        if cls.use_subfunction():
            # for services that support subfonctions,
            subfunction = response.data[0]
            data = response.data[1:]
            print(data, type(data))

        else:
            subfunction = cls.default_subfonction_id()
            data = response.data

        return response_cls.unpack(data, subfunction=subfunction)

    @staticmethod
    def __get_all_subclasses(cls) -> list[type[BaseService]]:
        import udsoncan.services  # This import is required for __subclasses__ to have a value. Python never import twice the same package.

        # this gets all subclasses and returns a list where the "most original" subclasses are listed in front of the other subclasses
        # This enables subclasses of any BaseService outside of udsoncan.services to be available, enabling specialization of calls in
        # cases where a CAN message is similar to one found in official UDS documentation but has a different service ID
        # This also allows for custom UDS service creation where a nonstandard extension is more easily played ontop of the protocol
        lst = []
        lst.extend(cls.__subclasses__())
        for x in cls.__subclasses__():
            subclasses = BaseService.__get_all_subclasses(x)
            if len(subclasses) > 0:
                lst.extend(subclasses)
        return lst

    @classmethod  # Returns an instance of the service identified by the service ID (Request)
    def from_request_id(cls, given_id: int) -> Optional[type[BaseService]]:
        classes = BaseService.__get_all_subclasses(cls)
        for obj in classes:
            if obj.request_id() == given_id:
                return obj
        return None

    @classmethod  # Returns an instance of the service identified by the service ID (Response)
    def from_response_id(cls, given_id: int) -> Optional[type[BaseService]]:
        classes = BaseService.__get_all_subclasses(cls)
        for obj in classes:
            if obj.response_id() == int(given_id):
                return obj
        return None

    @classmethod
    def default_subfonction_id(cls) -> int:
        """
        The subfonction ID to default to when not passed explicitly.
        """
        return 0

    @classmethod  # Tells if this service includes a subfunction byte
    def use_subfunction(cls) -> bool:
        if hasattr(cls, "_use_subfunction"):
            return cls._use_subfunction
        else:
            return True

    @classmethod
    def has_response_data(cls) -> bool:
        if hasattr(cls, "_no_response_data"):
            return False if cls._no_response_data else True
        else:
            return True

    @classmethod  # Returns the service name. Shortcut that works on class and instances
    def get_name(cls) -> str:
        return cls.__name__

    @classmethod  # Tells if the given response code is expected for this service according to UDS standard.
    def is_supported_negative_response(cls, code: int) -> bool:
        supported = False
        if code in cls.supported_negative_response:
            supported = True

        if code in cls.always_valid_negative_response:
            supported = True

        # As specified by Annex A, negative response code ranging above 0x7F can be used anytime if the service can return ConditionNotCorrect
        if (
            code >= 0x80
            and code < 0xFF
            and ResponseCode.ConditionsNotCorrect in cls.supported_negative_response
        ):
            supported = True

        # ISO-14229:2006 Table A.1 : "This response code shall be supported by each diagnostic service with a subfunction parameter"
        if (
            code == ResponseCode.SubFunctionNotSupportedInActiveSession
            and cls.use_subfunction()
        ):
            supported = True

        return supported
