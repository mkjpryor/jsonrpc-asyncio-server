"""
Module containing JSON-RPC dispatcher.
"""

import asyncio
import functools
import inspect
import logging
from collections import UserDict

import json

from pydantic import ValidationError
from pydantic.json import pydantic_encoder

from . import models, exceptions


def receives_context(func):
    """
    Decorator that flags the decorated function as receiving the JSON-RPC
    context when invoked.
    """
    func.__receives_context__ = True
    return func


def dispatcher_exclude(func):
    """
    Decorator that flags the decorated function as being excluded from the
    dispatcher when using :py:meth:`Dispatcher.register_all`.
    """
    func.__dispatcher_exclude__ = True
    return func


class Dispatcher:
    """
    Class for an asynchronous JSON-RPC dispatcher.
    """
    def __init__(self):
        self.methods = {}
        self.logger = logging.getLogger(__name__)

    def register(self, func = None, name = None):
        """
        Register a function with the dispatcher as an available method.

        Can be used as a function decorator or called directly.

        Parameters:
          func: The function to register as a method.
          name: The method name to register with. Optional, defaults to function name.
        """
        if func:
            self.logger.info("Registering method: %s", name or func.__name__)
            self.methods[name or func.__name__] = func
            return func
        else:
            return lambda f: self.register(f, name)

    def register_all(self, obj, prefix, only = None, exclude = None):
        """
        Register all the callable attributes of an object, e.g. a module, as methods.

        Methods are registered with a prefix, e.g. ``<prefix>.<method name>``. If not given,
        the prefix will be the ``__name__`` of the object.

        Parameters:
          obj: The object whose attributes should be used as methods.
          prefix: The prefix for method names.
          only: An iterable of specific attributes to include.
          exclude: An iterable of specific attributes to exclude.
        """
        # Build the set of attributes that are candidates to be a JSON-RPC method
        # Start with all the attributes of the object
        candidates = set(dir(obj))
        # If only is specified use it, otherwise apply some default restrictions
        if only is not None:
            candidates = candidates.intersection(only)
        else:
            # For modules, only consider public attributes by default
            if inspect.ismodule(obj) and hasattr(obj, '__all__'):
                candidates = candidates.intersection(obj.__all__)
            # Only consider attributes that don't start with _
            candidates = set(c for c in candidates if not c.startswith('_'))
        # Apply exclude, if given
        if exclude is not None:
            candidates = candidates.difference(exclude)
        for name in candidates:
            method = getattr(obj, name)
            # The attribute must be callable to be a method
            if not callable(method): continue
            # Ignore any attributes that are specifically excluded
            if getattr(method, '__dispatcher_exclude__', False): continue
            self.register(method, name = f"{prefix}.{name}")

    async def dispatch(self, raw_input, context = None):
        """
        Receives raw input data as a string and processes JSON-RPC requests according to the
        specification. Returns raw response data as a string.

        Parameters:
          raw_input: The raw input data as a string.
          context: The context to pass to methods that request it.
        """
        # First, parse the input as JSON
        try:
            request_data = json.loads(raw_input)
        except (ValueError, TypeError) as exc:
            response = models.JsonRpcErrorResponse(error = exceptions.ParseError(str(exc)))
        else:
            response = await self.dispatch_obj(request_data, context)
        # Convert the response to JSON
        if response:
            return response.json()
        else:
            return ''

    async def dispatch_obj(self, input_obj, context = None):
        """
        Returns the resulting response from processing the input object as a JSON-RPC request.

        Parameters:
          input_obj: The input object.
          context: The context to pass to methods that request it.
        """
        if isinstance(input_obj, list):
            return (await self.dispatch_batch(input_obj, context))
        elif isinstance(input_obj, dict):
            return (await self.dispatch_one(input_obj, context))
        else:
            error = exceptions.InvalidRequest('payload must be an array or an object')
            return models.JsonRpcErrorResponse(error = error)

    async def dispatch_batch(self, requests, context = None):
        """
        Dispatch a batch of JSON-RPC requests.

        Parameters:
          requests: A list of request objects.
          context: The context to pass to methods that request it.
        """
        # There must be at least one item in a batch request
        if not requests:
            error = exceptions.InvalidRequest('batch payload must contain at least one request')
            return models.JsonRpcErrorResponse(error = error)
        self.logger.info("Processing batch with %d requests", len(requests))
        # Process all the requests at once using gather
        tasks = [self.dispatch_one(request, context) for request in requests]
        results = await asyncio.gather(*tasks)
        # Filter out any null entries from processing notifications
        response_data = [result for result in results if result]
        # If all the requests were notifications, there will be no response data
        if response_data:
            return models.JsonRpcBatchResponse.parse_obj(response_data)
        else:
            return None

    async def dispatch_one(self, request, context = None):
        """
        Dispatch a single JSON-RPC request.

        Parameters:
          request: The request object.
          context: The context to pass to methods that request it.
        """
        # First, try to process the request using the model
        try:
            request = models.JsonRpcRequest(**request)
        except ValidationError as exc:
            error = exceptions.InvalidRequest(exc.errors())
            return models.JsonRpcErrorResponse(error = error)
        self.logger.info(
            "Processing JSON-RPC request (id: %s, method: %s)",
            request.id,
            request.method
        )
        # Next, try to find the method
        try:
            method = self.methods[request.method]
        except KeyError:
            error = exceptions.MethodNotFound(f'no such method: {request.method}')
            response = models.JsonRpcErrorResponse(error = error, id = request.id)
        else:
            # Execute the method with the given parameters
            try:
                result = await self._invoke(method, request.params, context)
            except exceptions.JsonRpcException as exc:
                response = models.JsonRpcErrorResponse(error = exc, id = request.id)
            except Exception as exc:
                # Log any unexpected exceptions
                # We assume a JsonRpcException is an expected condition
                self.logger.exception(
                    "Unexpected error executing JSON-RPC request (id: %s, method: %s)",
                    request.id,
                    request.method
                )
                error = exceptions.MethodExecutionError(exc)
                response = models.JsonRpcErrorResponse(error = error, id = request.id)
            else:
                response = models.JsonRpcSuccessResponse(result = result, id = request.id)
        # Log the response information
        if response.is_error:
            self.logger.error(
                "Error processing JSON-RPC request: (id: %s, method: %s, code: %s, message: \"%s\")",
                response.id,
                request.method,
                response.error.code,
                response.error.message
            )
        else:
            self.logger.info(
                "JSON-RPC request completed: (id: %s, method: %s)",
                response.id,
                request.method
            )
        # We only need to produce a response if the request is not a notification
        if not request.is_notification:
            return response

    async def _invoke(self, func, params, context):
        """
        Invoke the given function with the given parameters and context.
        """
        # Try to bind the given arguments to the signature of the function
        # If it fails, raise an invalid params error
        signature = inspect.signature(func)
        if isinstance(params, list):
            args = params
            kwargs = {}
        else:
            args = []
            kwargs = params
        if getattr(func, '__receives_context__', False):
            args = [context] + args
        try:
            bound = signature.bind(*args, **kwargs)
        except TypeError as exc:
            raise exceptions.InvalidParams(str(exc))
        return (await func(*bound.args, **bound.kwargs))
