"""
Tests for JSON-RPC dispatcher.
"""

import json
from types import SimpleNamespace

import pytest
import mock

from jsonrpc.server import Dispatcher, receives_context, dispatcher_exclude


@pytest.mark.asyncio
async def test_invalid_not_list_or_object():
    dispatcher = Dispatcher()
    response = await dispatcher.dispatch('1')
    expected = dict(
        jsonrpc = "2.0",
        id = None,
        error = dict(
            code = -32600,
            message = "Invalid request",
            data = "payload must be an array or an object"
        )
    )
    assert json.loads(response) == expected


@pytest.mark.asyncio
async def test_empty_parameters():
    dispatcher = Dispatcher()
    test = mock.AsyncMock(return_value = 19)
    dispatcher.register(test, name = 'test')

    response = await dispatcher.dispatch('{"jsonrpc": "2.0", "method": "test", "id": 2}')
    expected = dict(jsonrpc = "2.0", result = 19, id = 2)
    assert json.loads(response) == expected
    # In the case of zero parameters, an empty dict is given to the method
    test.assert_called_once_with()


@pytest.mark.asyncio
async def test_positional_parameters():
    dispatcher = Dispatcher()
    subtract = mock.AsyncMock(return_value = 19)
    dispatcher.register(subtract, name = 'subtract')

    response = await dispatcher.dispatch('{"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1}')
    expected = dict(jsonrpc = "2.0", result = 19, id = 1)
    assert json.loads(response) == expected
    subtract.assert_called_once_with(42, 23)


@pytest.mark.asyncio
async def test_named_parameters():
    dispatcher = Dispatcher()
    subtract = mock.AsyncMock(return_value = 19)
    dispatcher.register(subtract, name = 'subtract')

    response = await dispatcher.dispatch('{"jsonrpc": "2.0", "method": "subtract", "params": {"subtrahend": 23, "minuend": 42}, "id": 2}')
    expected = dict(jsonrpc = "2.0", result = 19, id = 2)
    assert json.loads(response) == expected
    subtract.assert_called_once_with(subtrahend = 23, minuend = 42)


@pytest.mark.asyncio
async def test_scalar_result():
    dispatcher = Dispatcher()
    test = mock.AsyncMock(return_value = 19)
    dispatcher.register(test, name = 'test')

    response = await dispatcher.dispatch('{"jsonrpc": "2.0", "method": "test", "id": 2}')
    expected = dict(jsonrpc = "2.0", result = 19, id = 2)
    assert json.loads(response) == expected


@pytest.mark.asyncio
async def test_list_result():
    dispatcher = Dispatcher()
    test = mock.AsyncMock(return_value = [1, 2, 3, '4', {'nested': 'dict'}])
    dispatcher.register(test, name = 'test')

    response = await dispatcher.dispatch('{"jsonrpc": "2.0", "method": "test", "id": "4"}')
    expected = dict(jsonrpc = "2.0", result = [1, 2, 3, '4', {'nested': 'dict'}], id = "4")
    assert json.loads(response) == expected


@pytest.mark.asyncio
async def test_object_result():
    dispatcher = Dispatcher()
    test = mock.AsyncMock(return_value = dict(
        key1 = 1,
        key2 = 'test',
        key3 = ['nested', 'array'],
        key4 = dict(nested = 'dict')
    ))
    dispatcher.register(test, name = 'test')

    response = await dispatcher.dispatch('{"jsonrpc": "2.0", "method": "test", "id": "6579ce6c-da1b-4174-a8a2-6277de8684b8"}')
    expected = dict(
        jsonrpc = "2.0",
        result = dict(
            key1 = 1,
            key2 = 'test',
            key3 = ['nested', 'array'],
            key4 = {'nested': 'dict'}
        ),
        id = "6579ce6c-da1b-4174-a8a2-6277de8684b8"
    )
    assert json.loads(response) == expected


@pytest.mark.asyncio
async def test_notification_method_exists():
    dispatcher = Dispatcher()
    update = mock.AsyncMock()
    dispatcher.register(update, name = 'update')

    response = await dispatcher.dispatch('{"jsonrpc": "2.0", "method": "update", "params": [1,2,3,4,5]}')
    assert response == ''
    update.assert_called_once_with(1, 2, 3, 4, 5)


@pytest.mark.asyncio
async def test_notification_method_does_not_exist():
    dispatcher = Dispatcher()
    response = await dispatcher.dispatch('{"jsonrpc": "2.0", "method": "update", "params": [1,2,3,4,5]}')
    assert response == ''


@pytest.mark.asyncio
async def test_method_does_not_exist():
    dispatcher = Dispatcher()
    response = await dispatcher.dispatch('{"jsonrpc": "2.0", "method": "foobar", "id": "1"}')
    expected = dict(
        jsonrpc = "2.0",
        error = dict(
            code = -32601,
            message = "Method not found",
            data = "no such method: foobar"
        ),
        id = "1"
    )
    assert json.loads(response) == expected


@pytest.mark.asyncio
async def test_invalid_json():
    dispatcher = Dispatcher()
    response = await dispatcher.dispatch('{"jsonrpc": "2.0", "method": "foobar, "params": "bar", "baz]')
    expected = dict(
        jsonrpc = "2.0",
        error = dict(
            code = -32700,
            message = "Parse error",
            data = "Expecting ',' delimiter: line 1 column 40 (char 39)"
        ),
        id = None
    )
    assert json.loads(response) == expected


@pytest.mark.asyncio
async def test_invalid_request():
    dispatcher = Dispatcher()
    response = await dispatcher.dispatch('{"jsonrpc": "1.0", "method": 1, "params": "bar"}')
    expected = dict(
        jsonrpc = "2.0",
        error = dict(
            code = -32600,
            message = "Invalid request",
            data = [
                {
                    "loc": ["jsonrpc"],
                    "msg": "unexpected value; permitted: '2.0'",
                    "type": "value_error.const",
                    "ctx": {"given": "1.0", "permitted": ["2.0"]}
                },
                {
                    "loc": ["method"],
                    "msg": "str type expected",
                    "type": "type_error.str"
                },
                {
                    "loc": ["params"],
                    "msg": "value is not a valid list",
                    "type": "type_error.list"
                },
                {
                    "loc": ["params"],
                    "msg": "value is not a valid dict",
                    "type": "type_error.dict"
                }
            ]
        ),
        id = None
    )
    assert json.loads(response) == expected


@pytest.mark.asyncio
async def test_batch_invalid_json():
    dispatcher = Dispatcher()
    response = await dispatcher.dispatch(
        """
        [
            {"jsonrpc": "2.0", "method": "sum", "params": [1,2,4], "id": "1"},
            {"jsonrpc": "2.0", "method"
        ]
        """
    )
    expected = dict(
        jsonrpc = "2.0",
        error = dict(
            code = -32700,
            message = "Parse error",
            data = "Expecting ':' delimiter: line 5 column 9 (char 138)"
        ),
        id = None
    )
    assert json.loads(response) == expected


@pytest.mark.asyncio
async def test_batch_empty_array():
    dispatcher = Dispatcher()
    response = await dispatcher.dispatch('[]')
    expected = dict(
        jsonrpc = "2.0",
        error = dict(
            code = -32600,
            message = "Invalid request",
            data = "batch payload must contain at least one request"
        ),
        id =  None
    )
    assert json.loads(response) == expected


@pytest.mark.asyncio
async def test_batch():
    dispatcher = Dispatcher()
    sum = mock.AsyncMock(return_value = 20)
    dispatcher.register(sum, name = 'sum')
    notify_hello = mock.AsyncMock()
    dispatcher.register(notify_hello, name = 'notify_hello')
    subtract = mock.AsyncMock(return_value = 19)
    dispatcher.register(subtract, name = 'subtract')
    get_data = mock.AsyncMock(return_value = ['hello', 5])
    dispatcher.register(get_data, name = 'get_data')

    # Issue a patch request with a mixture of successful, invalid, errors and notifications
    response = await dispatcher.dispatch(
        """
        [
            {"jsonrpc": "2.0", "method": "sum", "params": [1,2,4], "id": "1"},
            {"jsonrpc": "2.0", "method": "notify_hello", "params": [7]},
            {"jsonrpc": "2.0", "method": "subtract", "params": [42,23], "id": "2"},
            {"foo": "boo"},
            {"jsonrpc": "2.0", "method": "foo.get", "params": {"name": "myself"}, "id": "5"},
            {"jsonrpc": "2.0", "method": "get_data", "id": 9}
        ]
        """
    )
    expected = [
        {"jsonrpc": "2.0", "result": 20, "id": "1"},
        {"jsonrpc": "2.0", "result": 19, "id": "2"},
        {
            "jsonrpc": "2.0",
            "error": {
                "code": -32600,
                "message": "Invalid request",
                "data": [
                    {
                        "loc": ["jsonrpc"],
                        "msg": "field required",
                        "type": "value_error.missing"
                    },
                    {
                        "loc": ["method"],
                        "msg": "field required",
                        "type": "value_error.missing"
                    },
                    {
                        "loc": ["foo"],
                        "msg": "extra fields not permitted",
                        "type": "value_error.extra"
                    }
                ]
            },
            "id": None
        },
        {
            "jsonrpc": "2.0",
            "error": {
                "code": -32601,
                "message": "Method not found",
                "data": "no such method: foo.get"
            },
            "id": "5"
        },
        {"jsonrpc": "2.0", "result": ["hello", 5], "id": 9}
    ]
    assert json.loads(response) == expected
    sum.assert_called_once_with(1, 2, 4)
    notify_hello.assert_called_once_with(7)
    subtract.assert_called_once_with(42, 23)
    get_data.assert_called_once_with()


@pytest.mark.asyncio
async def test_batch_all_notifications():
    dispatcher = Dispatcher()
    notify_sum = mock.AsyncMock()
    dispatcher.register(notify_sum, name = 'notify_sum')

    # One notification is a success, the other is an error, but the response should be empty
    # For notifications, errors are suppressed
    response = await dispatcher.dispatch(
        """
        [
            {"jsonrpc": "2.0", "method": "notify_sum", "params": [1,2,4]},
            {"jsonrpc": "2.0", "method": "notify_hello", "params": [7]}
        ]
        """
    )
    assert response == ''
    notify_sum.assert_called_once_with(1, 2, 4)


@pytest.mark.asyncio
async def test_context():
    dispatcher = Dispatcher()
    test_positional = receives_context(mock.AsyncMock(return_value = 10))
    dispatcher.register(test_positional, name = 'test_positional')
    test_keyword = receives_context(mock.AsyncMock(return_value = 11))
    dispatcher.register(test_keyword, name = 'test_keyword')

    # Call with a context and test that the same context gets passed to both methods
    # We also test the context passing with positional and keyword arguments
    response = await dispatcher.dispatch(
        """
        [
            {"jsonrpc": "2.0", "method": "test_positional", "params": [1,2,4], "id": "1"},
            {"jsonrpc": "2.0", "method": "test_keyword", "params": {"arg1": 1, "arg2": 2}, "id": "2"}
        ]
        """,
        dict(context_key1 = 'context value', context_key2 = 10)
    )
    expected = [
        {"jsonrpc": "2.0", "result": 10, "id": "1"},
        {"jsonrpc": "2.0", "result": 11, "id": "2"},
    ]
    assert json.loads(response) == expected
    test_positional.assert_called_once_with(
        dict(context_key1 = 'context value', context_key2 = 10),
        1, 2, 4
    )
    test_keyword.assert_called_once_with(
        dict(context_key1 = 'context value', context_key2 = 10),
        arg1 = 1, arg2 = 2
    )


@pytest.mark.asyncio
async def test_method_decorator():
    dispatcher = Dispatcher()
    # Test the name inference using a non-mocked function and use of a decorator
    @dispatcher.register
    async def subtract(x, y):
        return x - y
    no_context_args = mock.AsyncMock(return_value = 10)
    no_context_args.__name__ = 'no_context_args'
    dispatcher.register(no_context_args)
    no_context_kwargs = mock.AsyncMock(return_value = 9)
    no_context_kwargs.__name__ = 'no_context_kwargs'
    dispatcher.register(no_context_kwargs)
    with_context = receives_context(mock.AsyncMock(return_value = 11))
    with_context.__name__ = 'with_context'
    dispatcher.register(with_context)

    response = await dispatcher.dispatch(
        """
        [
            {"jsonrpc": "2.0", "method": "subtract", "params": [23, 42], "id": "1"},
            {"jsonrpc": "2.0", "method": "no_context_args", "params": [23, 42], "id": "2"},
            {"jsonrpc": "2.0", "method": "no_context_kwargs", "params": {"arg1": 23, "arg2": 42}, "id": "3"},
            {"jsonrpc": "2.0", "method": "with_context", "params": [23, 42], "id": "4"}
        ]
        """,
        dict(context_key = 'context value')
    )
    expected = [
        {"jsonrpc": "2.0", "result": -19, "id": "1"},
        {"jsonrpc": "2.0", "result": 10, "id": "2"},
        {"jsonrpc": "2.0", "result": 9, "id": "3"},
        {"jsonrpc": "2.0", "result": 11, "id": "4"}
    ]
    assert json.loads(response) == expected
    no_context_args.assert_called_once_with(23, 42)
    no_context_kwargs.assert_called_once_with(arg1 = 23, arg2 = 42)
    with_context.assert_called_once_with(dict(context_key = 'context value'), 23, 42)


@pytest.mark.asyncio
async def test_invalid_params():
    dispatcher = Dispatcher()

    @dispatcher.register
    async def test_positional_params(x, y, z):
        return [x, y, z]

    @dispatcher.register
    async def test_named_params(*, arg1, arg2 = 10):
        return [arg1, arg2]

    response = await dispatcher.dispatch(
        """
        [
            {"jsonrpc": "2.0", "method": "test_positional_params", "params": [23, 42], "id": "1"},
            {"jsonrpc": "2.0", "method": "test_named_params", "id": "2"},
            {"jsonrpc": "2.0", "method": "test_named_params", "params": {"arg2": 20}, "id": "3"},
            {"jsonrpc": "2.0", "method": "test_named_params", "params": {"arg1": 5}, "id": "4"},
            {"jsonrpc": "2.0", "method": "test_named_params", "params": {"arg1": 10, "arg2": 20}, "id": "5"}
        ]
        """
    )
    expected = [
        {
            "jsonrpc": "2.0",
            "error": {
                "code": -32602,
                "message": "Invalid params",
                "data": "missing a required argument: 'z'"
            },
            "id": "1"
        },
        {
            "jsonrpc": "2.0",
            "error": {
                "code": -32602,
                "message": "Invalid params",
                "data": "missing a required argument: 'arg1'"
            },
            "id": "2"
        },
        {
            "jsonrpc": "2.0",
            "error": {
                "code": -32602,
                "message": "Invalid params",
                "data": "missing a required argument: 'arg1'"
            },
            "id": "3"
        },
        {"jsonrpc": "2.0", "result": [5, 10], "id": "4"},
        {"jsonrpc": "2.0", "result": [10, 20], "id": "5"}
    ]
    assert json.loads(response) == expected


class CustomException(Exception):
    def __init__(self):
        super().__init__('custom exception message')


@pytest.mark.asyncio
async def test_method_execution_error():
    dispatcher = Dispatcher()
    runtime_error = mock.AsyncMock(side_effect = RuntimeError('test runtime error'))
    dispatcher.register(runtime_error, name = 'runtime_error')
    import_error = mock.AsyncMock(side_effect = lambda *a, **kw: exec('import does_not_exist'))
    dispatcher.register(import_error, name = 'import_error')
    custom_error = mock.AsyncMock(side_effect = CustomException())
    dispatcher.register(custom_error, name = 'custom_error')

    response = await dispatcher.dispatch(
        """
        [
            {"jsonrpc": "2.0", "method": "runtime_error", "id": "1"},
            {"jsonrpc": "2.0", "method": "import_error", "id": "2"},
            {"jsonrpc": "2.0", "method": "custom_error", "id": "3"}
        ]
        """
    )
    expected = [
        {
            "jsonrpc": "2.0",
            "error": {
                "code": -32099,
                "message": "Runtime error",
                "data": "test runtime error"
            },
            "id": "1"
        },
        {
            "jsonrpc": "2.0",
            "error": {
                "code": -32099,
                "message": "Module not found error",
                "data": "No module named 'does_not_exist'"
            },
            "id": "2"
        },
        {
            "jsonrpc": "2.0",
            "error": {
                "code": -32099,
                "message": "Custom exception",
                "data": "custom exception message"
            },
            "id": "3"
        },
    ]
    assert json.loads(response) == expected


@pytest.mark.asyncio
async def test_register_all():
    # Configure the method group
    method_group = SimpleNamespace()
    method_group.method_1 = mock.AsyncMock(return_value = 20)
    method_group.method_2 = receives_context(mock.AsyncMock(return_value = 21))
    # Add a non-callable attribute which will be specified in a request
    method_group.not_callable = 10
    # Add an attribute that is excluded using the decorator
    method_group.excluded_with_decorator = dispatcher_exclude(mock.AsyncMock(return_value = 22))

    # A group where methods are specifically included
    include_group = SimpleNamespace()
    include_group.included = mock.AsyncMock(return_value = 23)
    include_group.not_included = mock.AsyncMock(return_value = 24)

    # A group where some methods are specifically excluded
    exclude_group = SimpleNamespace()
    exclude_group.not_excluded_1 = mock.AsyncMock(return_value = 25)
    exclude_group.not_excluded_2 = mock.AsyncMock(return_value = 26)
    exclude_group.excluded = mock.AsyncMock(return_value = 27)

    # Configure the dispatcher
    dispatcher = Dispatcher()
    dispatcher.register_all(method_group, 'grouped')
    dispatcher.register_all(include_group, 'include', only = ['included'])
    dispatcher.register_all(exclude_group, 'exclude', exclude = ['excluded'])

    # Issue a patch request with a mixture of successful, invalid, errors and notifications
    response = await dispatcher.dispatch(
        """
        [
            {"jsonrpc": "2.0", "method": "grouped.method_1", "params": [1,2], "id": "1"},
            {"jsonrpc": "2.0", "method": "grouped.method_2", "params": [1,2], "id": "2"},
            {"jsonrpc": "2.0", "method": "grouped.not_callable", "params": [1,2], "id": "3"},
            {"jsonrpc": "2.0", "method": "grouped.excluded_with_decorator", "params": [1,2], "id": "4"},
            {"jsonrpc": "2.0", "method": "include.included", "params": [1,2], "id": "5"},
            {"jsonrpc": "2.0", "method": "include.not_included", "params": [1,2], "id": "6"},
            {"jsonrpc": "2.0", "method": "exclude.not_excluded_1", "params": [1,2], "id": "7"},
            {"jsonrpc": "2.0", "method": "exclude.not_excluded_2", "params": [1,2], "id": "8"},
            {"jsonrpc": "2.0", "method": "exclude.excluded", "params": [1,2], "id": "9"}
        ]
        """,
        dict(context_key1 = "1")
    )
    expected = [
        {"jsonrpc": "2.0", "result": 20, "id": "1"},
        {"jsonrpc": "2.0", "result": 21, "id": "2"},
        {
            "jsonrpc": "2.0",
            "error": {
                "code": -32601,
                "message": "Method not found",
                "data": "no such method: grouped.not_callable"
            },
            "id": "3"
        },
        {
            "jsonrpc": "2.0",
            "error": {
                "code": -32601,
                "message": "Method not found",
                "data": "no such method: grouped.excluded_with_decorator"
            },
            "id": "4"
        },
        {"jsonrpc": "2.0", "result": 23, "id": "5"},
        {
            "jsonrpc": "2.0",
            "error": {
                "code": -32601,
                "message": "Method not found",
                "data": "no such method: include.not_included"
            },
            "id": "6"
        },
        {"jsonrpc": "2.0", "result": 25, "id": "7"},
        {"jsonrpc": "2.0", "result": 26, "id": "8"},
        {
            "jsonrpc": "2.0",
            "error": {
                "code": -32601,
                "message": "Method not found",
                "data": "no such method: exclude.excluded"
            },
            "id": "9"
        },
    ]
    assert json.loads(response) == expected
    method_group.method_1.assert_called_once_with(1, 2)
    method_group.method_2.assert_called_once_with(dict(context_key1 = "1"), 1, 2)
    method_group.excluded_with_decorator.assert_not_called()
    include_group.included.assert_called_once_with(1, 2)
    include_group.not_included.assert_not_called()
    exclude_group.not_excluded_1.assert_called_once_with(1, 2)
    exclude_group.not_excluded_2.assert_called_once_with(1, 2)
    exclude_group.excluded.assert_not_called()
