from __future__ import annotations

import asyncio
from io import BytesIO

from fastapi import UploadFile
from starlette.datastructures import Headers


class FakeQuery:
    def __init__(self, result_one=None, result_all=None):
        self._result_one = result_one
        self._result_all = result_all or []

    def join(self, *args, **kwargs):
        return self

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._result_one

    def all(self):
        return self._result_all


class FakeOwuiSession:
    def __init__(self, group_obj, chat_user_rows):
        self._group_obj = group_obj
        self._chat_user_rows = chat_user_rows

    def query(self, *entities):
        if len(entities) == 1 and entities[0].__name__ == "OwuiGroup":
            return FakeQuery(result_one=self._group_obj)
        return FakeQuery(result_all=self._chat_user_rows)

    def close(self):
        return None


class Obj:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def make_upload_file(filename: str, content: bytes, content_type: str = "application/pdf") -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def run_async(coro):
    return asyncio.run(coro)
