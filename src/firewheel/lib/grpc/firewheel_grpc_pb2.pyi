from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetInfoRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetInfoResponse(_message.Message):
    __slots__ = ("version", "uptime", "experiment_running")
    VERSION_FIELD_NUMBER: _ClassVar[int]
    UPTIME_FIELD_NUMBER: _ClassVar[int]
    EXPERIMENT_RUNNING_FIELD_NUMBER: _ClassVar[int]
    version: str
    uptime: float
    experiment_running: bool
    def __init__(self, version: _Optional[str] = ..., uptime: _Optional[float] = ..., experiment_running: bool = ...) -> None: ...

class DestroyAllVMMappingsResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class DestroyVMMappingResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetExperimentLaunchTimeRequest(_message.Message):
    __slots__ = ("db",)
    DB_FIELD_NUMBER: _ClassVar[int]
    db: str
    def __init__(self, db: _Optional[str] = ...) -> None: ...

class ExperimentLaunchTime(_message.Message):
    __slots__ = ("db", "launch_time")
    DB_FIELD_NUMBER: _ClassVar[int]
    LAUNCH_TIME_FIELD_NUMBER: _ClassVar[int]
    db: str
    launch_time: _timestamp_pb2.Timestamp
    def __init__(self, db: _Optional[str] = ..., launch_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class GetExperimentStartTimeRequest(_message.Message):
    __slots__ = ("db",)
    DB_FIELD_NUMBER: _ClassVar[int]
    db: str
    def __init__(self, db: _Optional[str] = ...) -> None: ...

class ExperimentStartTime(_message.Message):
    __slots__ = ("db", "start_time")
    DB_FIELD_NUMBER: _ClassVar[int]
    START_TIME_FIELD_NUMBER: _ClassVar[int]
    db: str
    start_time: _timestamp_pb2.Timestamp
    def __init__(self, db: _Optional[str] = ..., start_time: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class InitializeExperimentStartTimeRequest(_message.Message):
    __slots__ = ("db",)
    DB_FIELD_NUMBER: _ClassVar[int]
    db: str
    def __init__(self, db: _Optional[str] = ...) -> None: ...

class InitializeExperimentStartTimeResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class VMMapping(_message.Message):
    __slots__ = ("db", "server_uuid", "server_name", "control_ip", "state", "current_time")
    DB_FIELD_NUMBER: _ClassVar[int]
    SERVER_UUID_FIELD_NUMBER: _ClassVar[int]
    SERVER_NAME_FIELD_NUMBER: _ClassVar[int]
    CONTROL_IP_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    CURRENT_TIME_FIELD_NUMBER: _ClassVar[int]
    db: str
    server_uuid: str
    server_name: str
    control_ip: str
    state: str
    current_time: str
    def __init__(self, db: _Optional[str] = ..., server_uuid: _Optional[str] = ..., server_name: _Optional[str] = ..., control_ip: _Optional[str] = ..., state: _Optional[str] = ..., current_time: _Optional[str] = ...) -> None: ...

class CountVMMappingsNotReadyResponse(_message.Message):
    __slots__ = ("db", "count")
    DB_FIELD_NUMBER: _ClassVar[int]
    COUNT_FIELD_NUMBER: _ClassVar[int]
    db: str
    count: int
    def __init__(self, db: _Optional[str] = ..., count: _Optional[int] = ...) -> None: ...

class CountVMMappingsNotReadyRequest(_message.Message):
    __slots__ = ("db",)
    DB_FIELD_NUMBER: _ClassVar[int]
    db: str
    def __init__(self, db: _Optional[str] = ...) -> None: ...

class ListVMMappingsRequest(_message.Message):
    __slots__ = ("db", "json_match_dict")
    DB_FIELD_NUMBER: _ClassVar[int]
    JSON_MATCH_DICT_FIELD_NUMBER: _ClassVar[int]
    db: str
    json_match_dict: str
    def __init__(self, db: _Optional[str] = ..., json_match_dict: _Optional[str] = ...) -> None: ...

class DestroyAllVMMappingsRequest(_message.Message):
    __slots__ = ("db",)
    DB_FIELD_NUMBER: _ClassVar[int]
    db: str
    def __init__(self, db: _Optional[str] = ...) -> None: ...

class VMMappingUUID(_message.Message):
    __slots__ = ("db", "server_uuid")
    DB_FIELD_NUMBER: _ClassVar[int]
    SERVER_UUID_FIELD_NUMBER: _ClassVar[int]
    db: str
    server_uuid: str
    def __init__(self, db: _Optional[str] = ..., server_uuid: _Optional[str] = ...) -> None: ...

class SetVMTimeByUUIDRequest(_message.Message):
    __slots__ = ("db", "server_uuid", "current_time")
    DB_FIELD_NUMBER: _ClassVar[int]
    SERVER_UUID_FIELD_NUMBER: _ClassVar[int]
    CURRENT_TIME_FIELD_NUMBER: _ClassVar[int]
    db: str
    server_uuid: str
    current_time: str
    def __init__(self, db: _Optional[str] = ..., server_uuid: _Optional[str] = ..., current_time: _Optional[str] = ...) -> None: ...

class SetVMStateByUUIDRequest(_message.Message):
    __slots__ = ("db", "server_uuid", "state")
    DB_FIELD_NUMBER: _ClassVar[int]
    SERVER_UUID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    db: str
    server_uuid: str
    state: str
    def __init__(self, db: _Optional[str] = ..., server_uuid: _Optional[str] = ..., state: _Optional[str] = ...) -> None: ...
