"""
Quart adapter for ``jsonrpc-async``.
"""

import asyncio

from quart import Blueprint, request, Response, websocket


def http_blueprint(dispatcher):
    """
    Return a Quart blueprint providing an HTTP endpoint for the given JSON-RPC dispatcher.
    """
    bp = Blueprint('jsonrpc_http', __name__)

    @bp.route('', methods = ['POST'])
    async def jsonrpc():
        request_data = await request.get_data()
        jsonrpc_response = await dispatcher.dispatch(request_data)
        return Response(
            jsonrpc_response,
            status = 200 if jsonrpc_response else 204,
            content_type = 'application/json'
        )

    return bp


def websocket_blueprint(dispatcher):
    """
    Return a Quart blueprint providing a websocket endpoint for the given JSON-RPC dispatcher.
    """
    bp = Blueprint('jsonrpc_websocket', __name__)

    @bp.websocket('')
    async def jsonrpc():
        # Each client has set of tasks to wait on for the next iteration
        # This will include websocket receive and any pending responses
        next_tasks = set()
        ws_receive = None
        try:
            while True:
                # If there is no task for receiving wesocket messages, add one
                if not ws_receive or ws_receive not in next_tasks:
                    ws_receive = asyncio.create_task(websocket.receive())
                    next_tasks.add(ws_receive)
                # Wait for the first task to return
                done, next_tasks = await asyncio.wait(next_tasks, return_when = asyncio.FIRST_COMPLETED)
                for task in done:
                    if task is ws_receive:
                        # Create a task to dispatch the request and add it for next iteration
                        next_tasks.add(asyncio.create_task(dispatcher.dispatch(task.result())))
                    else:
                        # Send the response for the completed request, if it is non-empty
                        # If it is empty, it is a notification and there is nothing to do
                        jsonrpc_response = task.result()
                        if jsonrpc_response:
                            await websocket.send(jsonrpc_response)
        finally:
            if ws_receive:
                ws_receive.cancel()

    return bp
