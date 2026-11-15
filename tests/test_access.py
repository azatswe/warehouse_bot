import unittest
from unittest.mock import AsyncMock, MagicMock

from aiogram.types import Message

from main import AllowedUsersMiddleware


class AccessMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_user_outside_allowlist(self):
        middleware = AllowedUsersMiddleware(frozenset({10, 20}))
        message = MagicMock(spec=Message)
        message.answer = AsyncMock()
        handler = AsyncMock()

        result = await middleware(handler, message, {"event_from_user": MagicMock(id=99)})

        message.answer.assert_awaited_once_with("У вас нет доступа")
        handler.assert_not_awaited()
        self.assertIsNone(result)

    async def test_allows_user_from_allowlist(self):
        middleware = AllowedUsersMiddleware(frozenset({10, 20}))
        handler = AsyncMock(return_value="handled")
        event = object()
        data = {"event_from_user": MagicMock(id=20)}

        result = await middleware(handler, event, data)

        handler.assert_awaited_once_with(event, data)
        self.assertEqual(result, "handled")


if __name__ == "__main__":
    unittest.main()
