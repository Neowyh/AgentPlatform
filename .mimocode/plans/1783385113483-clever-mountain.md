# 修复 ApiException VERSION_CONFLICT 缺少 message 参数

## 问题

3 处 `ApiException("VERSION_CONFLICT")` 只传了 1 个参数，缺少必填的 `message` 参数，导致乐观锁保护完全失效。

## 修改文件

1. `backend/app/gateway/routers/agents.py` 第 628 行
2. `backend/app/gateway/routers/skills.py` 第 333 行
3. `backend/app/gateway/routers/workflows.py` 第 310 行

## 修改内容

每处将：
```python
raise ApiException("VERSION_CONFLICT")
```
改为：
```python
raise ApiException("VERSION_CONFLICT", "乐观锁冲突，需刷新重试")
```

## 验证

1. 运行现有测试：`cd backend && python -m pytest tests/test_concurrent_updates.py -v`
2. 运行 agents/skills/workflows 相关测试确认无回归
