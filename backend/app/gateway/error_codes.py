"""Standardized API error codes.

Each error code maps to an HTTP status code and a default Chinese message.
Use ``ApiException`` to raise structured errors that the global handler
converts into the ``{success, data, error}`` response format.
"""

from __future__ import annotations

from fastapi import HTTPException


class ApiException(HTTPException):
    """HTTP exception carrying a structured error code."""

    def __init__(self, code: str, message: str, status_code: int | None = None) -> None:
        entry = ERROR_CODES.get(code)
        if entry is None:
            raise ValueError(f"Unknown error code: {code}")
        self.code = code
        self.message = message or entry["message"]
        super().__init__(status_code=status_code or entry["status_code"], detail=self.message)


# ---------------------------------------------------------------------------
# Error code registry
# ---------------------------------------------------------------------------

ERROR_CODES: dict[str, dict] = {
    "PERMISSION_DENIED": {
        "status_code": 403,
        "message": "无权限执行该操作",
    },
    "RESOURCE_NOT_FOUND": {
        "status_code": 404,
        "message": "资源不存在",
    },
    "RESOURCE_CONFLICT": {
        "status_code": 409,
        "message": "资源名已存在",
    },
    "VERSION_CONFLICT": {
        "status_code": 409,
        "message": "乐观锁冲突，需刷新重试",
    },
    "ADMIN_LIMIT_EXCEEDED": {
        "status_code": 400,
        "message": "管理员人数已达上限",
    },
    "INVALID_VISIBILITY": {
        "status_code": 400,
        "message": "无效的 visibility 值",
    },
    "PENDING_APPLICATION_EXISTS": {
        "status_code": 409,
        "message": "该资源已有 pending 的变更申请",
    },
    "APPROVER_NOT_FOUND": {
        "status_code": 400,
        "message": "无可用审批人",
    },
    "SELF_REVIEW_FORBIDDEN": {
        "status_code": 403,
        "message": "dept_admin 不可审批自己的申请",
    },
    "USER_DISABLED": {
        "status_code": 403,
        "message": "用户已被禁用",
    },
    "FILE_FORMAT_INVALID": {
        "status_code": 400,
        "message": "导入文件格式不合法",
    },
    "TRANSFER_REQUIRED": {
        "status_code": 400,
        "message": "用户删除前需完成资源重分配",
    },
    "INVALID_REQUEST_BODY": {
        "status_code": 400,
        "message": "请求体格式不合法",
    },
    "INTERNAL_ERROR": {
        "status_code": 500,
        "message": "服务器内部错误",
    },
}
