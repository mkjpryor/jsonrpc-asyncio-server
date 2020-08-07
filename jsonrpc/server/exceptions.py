"""
Module containing JSON-RPC exceptions.
"""

import re

from .models import JsonRpcError


class JsonRpcException(Exception):
    """
    Base class for all JSON-RPC exceptions.
    """
    code = -32000
    message = "Server error"

    def __init__(self, data, code = None, message = None):
        self.data = data
        self.code = code or self.code
        self.message = message or self.message

    def as_error(self):
        return JsonRpcError.from_orm(self)


class ParseError(JsonRpcException):
    """
    Raised when a parse error occurs.
    """
    code = -32700
    message = "Parse error"


class InvalidRequest(JsonRpcException):
    """
    Raised for an invalid request.
    """
    code = -32600
    message = "Invalid request"


class MethodNotFound(JsonRpcException):
    """
    Raised when a method does not exist or is not available.
    """
    code = -32601
    message = "Method not found"


class InvalidParams(JsonRpcException):
    """
    Raised when invalid parameters are given.
    """
    code = -32602
    message = "Invalid params"


class InternalError(JsonRpcException):
    """
    Raised when an internal JSON-RPC error occurs.
    """
    code = -32603
    message = "Internal error"


class MethodExecutionError(JsonRpcException):
    """
    Raised when an exception occurs during method execution that is not itself a
    `JsonRpcException`.
    """
    code = -32099

    def __init__(self, exc):
        # Convert the exception name to words for the message
        words = re.findall(r'[A-Z](?:[a-z]+|[A-Z]*(?=[A-Z]|$))', exc.__class__.__name__)
        # Recombine and capitalise
        message = ' '.join(words).lower().capitalize()
        super().__init__(data = str(exc), message = message)
