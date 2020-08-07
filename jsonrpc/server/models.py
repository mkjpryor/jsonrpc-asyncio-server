"""
Pydantic models describing the JSON-RPC specification.
"""

import abc

from typing import Any, List, Dict, Union, Optional
from typing_extensions import Literal

from pydantic import BaseModel, Field, constr, validator


class JsonRpcRequest(BaseModel):
    """
    Model for a JSON-RPC request.
    """
    #: The JSON-RPC version
    jsonrpc: Literal["2.0"]
    #: The id of the request
    #: If no id is given, or the given id is null, the request is assumed to be a notification
    #: We use `Any` as the type with a custom validator to prevent any coercion as this could
    #: lead to violations of the spec, e.g. str('1') being converted to int(1)
    id: Any = None
    #: The method to invoke
    method: constr(min_length = 1)
    #: The parameters for the method invocation
    #: Can be either a list for positional args or a dict for kwargs
    params: Union[List[Any], Dict[str, Any]] = Field(default_factory = dict)

    @validator('id')
    def check_id(cls, value):
        if value is None:
            return value
        if not isinstance(value, (int, str)):
            raise ValueError('if given, id must be an int or string')
        return value

    @validator('method', pre = True)
    def check_method(cls, value):
        # We don't want to allow coercion as this is a violation of the spec
        if not isinstance(value, str):
            raise ValueError('method must be a string')
        return value

    @property
    def is_notification(self):
        """
        Returns true if the request is a notification, false otherwise.
        """
        return self.id is None


class JsonRpcError(BaseModel):
    """
    Model for a JSON-RPC error.
    """
    class Config:
        orm_mode = True

    #: The error code
    code: int
    #: The error message
    message: constr(min_length = 1)
    #: Additional information about the error
    data: Optional[Any]


class JsonRpcResponse(BaseModel, abc.ABC):
    """
    Model for a JSON-RPC response.
    """
    class Config:
        orm_mode = True

    #: The JSON-RPC version
    jsonrpc: Literal["2.0"] = "2.0"
    #: The id of the corresponding request
    #: If the request is a notification or the id could not be detected, this should be null
    #: We use `Any` as the type with a custom validator to prevent any coercion as this could
    #: lead to violations of the spec, e.g. str('1') being converted to int(1)
    id: Any = None

    @validator('id')
    def check_id(cls, value):
        if value is None:
            return value
        if not isinstance(value, (int, str)):
            raise ValueError('if given, id must be an int or string')
        return value

    @property
    def is_error(self):
        """
        Returns true is the response is an error response, false otherwise.
        """
        return hasattr(self, 'error')


class JsonRpcSuccessResponse(JsonRpcResponse):
    """
    Model for a successful JSON-RPC response.
    """
    #: The result of executing the method
    result: Any


class JsonRpcErrorResponse(JsonRpcResponse):
    """
    Model for a JSON-RPC error response.
    """
    #: The error that occurred
    error: JsonRpcError


class JsonRpcBatchResponse(BaseModel):
    """
    Model for a JSON-RPC batch response.
    """
    __root__: List[JsonRpcResponse]
