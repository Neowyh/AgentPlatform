# 性能优化方案

## 概述

本方案针对 iDeer 平台的性能瓶颈进行优化，包括数据库索引、连接池调优和前端加载优化。

> 注意：优化前应先建立性能基线（Lighthouse、EXPLAIN ANALYZE），避免盲目优化。

---

## 1. 数据库查询优化

### 1.1 现有索引

当前已有 4 个迁移文件，已创建的索引：

| 表 | 索引 | 来源迁移 |
|------|------|----------|
| users_ext | ix_users_ext_username (UNIQUE) | 16147afec43b |
| users_ext | ix_users_ext_role | f3a2b1c4d5e6 |
| users_ext | ix_users_ext_department_id | f3a2b1c4d5e6 |
| departments | departments_name (UNIQUE) | 16147afec43b |
| workflow_runs | ix_workflow_runs_name | d7e0060b1ebc |

### 1.2 需要新增的索引

**注意**：避免与已有索引重复。以下索引经过检查确认不存在。

```python
"""backend/packages/harness/ideer/persistence/migrations/versions/xxxx_add_performance_indexes.py"""

from alembic import op


revision = 'xxxx'
down_revision = 'previous_revision'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # workflow_runs 表：状态过滤 + 时间排序（常用查询）
    op.create_index(
        'ix_workflow_runs_status',
        'workflow_runs',
        ['status']
    )

    op.create_index(
        'ix_workflow_runs_created_at',
        'workflow_runs',
        ['created_at']
    )

    # 复合索引：按工作流名 + 状态过滤（列表页常用）
    op.create_index(
        'ix_workflow_runs_name_status',
        'workflow_runs',
        ['workflow_name', 'status']
    )

    # 复合索引：按工作流名 + 时间排序（分页查询）
    op.create_index(
        'ix_workflow_runs_name_created',
        'workflow_runs',
        ['workflow_name', 'created_at']
    )


def downgrade() -> None:
    op.drop_index('ix_workflow_runs_name_created', table_name='workflow_runs')
    op.drop_index('ix_workflow_runs_name_status', table_name='workflow_runs')
    op.drop_index('ix_workflow_runs_created_at', table_name='workflow_runs')
    op.drop_index('ix_workflow_runs_status', table_name='workflow_runs')
```

### 1.3 查询优化

在 `backend/packages/harness/ideer/workflows/store.py` 中优化查询：

```python
"""backend/packages/harness/ideer/workflows/store.py"""

from sqlalchemy import select, func, and_, or_
from typing import List, Optional, Tuple


class WorkflowStore:
    """Persistent storage with optimized queries."""

    async def list_workflows(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> Tuple[List[dict], int]:
        """List workflows with optimized queries."""
        sf = get_session_factory()
        if sf is None:
            return [], 0

        async with sf() as session:
            base_query = select(WorkflowRunRow).where(
                WorkflowRunRow.run_id.startswith("def:")
            )

            if status:
                base_query = base_query.where(WorkflowRunRow.status == status)

            if search:
                base_query = base_query.where(
                    or_(
                        WorkflowRunRow.workflow_name.ilike(f"%{search}%"),
                        WorkflowRunRow.workflow_yaml.ilike(f"%{search}%")
                    )
                )

            # 使用索引优化 count 查询
            count_query = select(func.count()).select_from(base_query.subquery())
            total = (await session.execute(count_query)).scalar() or 0

            # 使用复合索引优化分页
            query = (
                base_query
                .order_by(WorkflowRunRow.created_at.desc())
                .offset(offset)
                .limit(limit)
            )

            rows = (await session.execute(query)).scalars().all()

            results = []
            for row in rows:
                try:
                    wf = parse_workflow_string(row.workflow_yaml)
                    results.append({
                        "name": wf.name,
                        "description": wf.description,
                        "version": wf.version,
                        "steps_count": len(wf.steps),
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    })
                except Exception as e:
                    logger.warning("Failed to parse workflow %s: %s", row.workflow_name, e)

            return results, total

    async def list_runs(
        self,
        workflow_name: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None
    ) -> Tuple[List[dict], int]:
        """List workflow runs using composite index."""
        sf = get_session_factory()
        if sf is None:
            return [], 0

        async with sf() as session:
            base_query = select(WorkflowRunRow).where(
                and_(
                    WorkflowRunRow.workflow_name == workflow_name,
                    ~WorkflowRunRow.run_id.startswith("def:")
                )
            )

            if status:
                base_query = base_query.where(WorkflowRunRow.status == status)

            count_query = select(func.count()).select_from(base_query.subquery())
            total = (await session.execute(count_query)).scalar() or 0

            query = (
                base_query
                .order_by(WorkflowRunRow.created_at.desc())
                .offset(offset)
                .limit(limit)
            )

            rows = (await session.execute(query)).scalars().all()

            results = [
                {
                    "run_id": row.run_id,
                    "status": row.status,
                    "inputs": row.inputs,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                }
                for row in rows
            ]

            return results, total
```

---

## 2. 连接池优化

### 2.1 当前配置

`backend/packages/harness/ideer/persistence/engine.py` 当前配置：
- **SQLite**: 无显式 pool_size（SQLAlchemy 默认 5）
- **PostgreSQL**: `pool_size=5`, `pool_pre_ping=True`, `pool_recycle=1800`

### 2.2 优化建议

**SQLite 不需要调大 pool_size**（SQLite 是文件级锁，多连接反而降低性能）。

**PostgreSQL 可适当调大**：

```python
"""backend/packages/harness/ideer/persistence/engine.py"""

def init_engine(
    backend: str = "sqlite",
    url: str = "",
    echo: bool = False,
    pool_size: int = 5,  # 默认值保持不变
    sqlite_dir: str = "",
):
    """Initialize the database engine."""
    # ... existing code ...

    if backend == "postgres":
        # 生产环境建议 pool_size=10-20
        # 通过环境变量或配置文件调整，不硬编码
        engine = create_async_engine(
            url,
            echo=echo,
            pool_size=pool_size,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_timeout=30,
        )
```

**建议**：通过 `config.yaml` 的 `database.pool_size` 字段配置，而非硬编码。

---

## 3. 前端加载性能优化

### 3.1 当前状态

前端使用 **Nextra** 框架（基于 Next.js 的文档框架），配置文件为 `frontend/next.config.js`。

### 3.2 Next.js 配置优化

```javascript
/* frontend/next.config.js */

const nextConfig = {
  // 启用压缩
  compress: true,

  // 图片优化
  images: {
    formats: ['image/avif', 'image/webp'],
    minimumCacheTTL: 60 * 60 * 24 * 30, // 30 days
  },

  // Headers 配置
  async headers() {
    return [
      {
        // 静态资源缓存
        source: '/_next/static/(.*)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
    ];
  },
};
```

### 3.3 代码分割

Nextra 框架已内置路由级代码分割。对于重型组件（如 Monaco Editor、工作流图表），使用动态导入：

```tsx
/* frontend/src/app/workspace/workflows/[workflow_name]/page.tsx */

'use client';

import dynamic from 'next/dynamic';

const MonacoEditor = dynamic(
  () => import('@monaco-editor/react'),
  {
    loading: () => <div className="h-96 bg-gray-100 animate-pulse" />,
    ssr: false,
  }
);
```

### 3.4 性能监控

```tsx
/* frontend/src/lib/performance.ts */

export function reportWebVitals(metric: any) {
  if (process.env.NODE_ENV === 'production') {
    switch (metric.name) {
      case 'FCP':
      case 'LCP':
      case 'CLS':
      case 'FID':
      case 'TTFB':
        console.log(`${metric.name}: ${metric.value}`);
        break;
    }
  }
}
```

---

## 4. 性能测试

### 4.1 数据库性能测试

```python
"""backend/tests/test_performance.py"""

import pytest
import time
from ideer.workflows.store import WorkflowStore


class TestQueryPerformance:
    """Database query performance tests."""

    @pytest.mark.asyncio
    async def test_list_workflows_performance(self, db_session):
        store = WorkflowStore()

        # Insert test data
        for i in range(100):
            await store.save_workflow(f"workflow_{i}", f"name: workflow_{i}\nsteps: []")

        # Measure query time
        start = time.time()
        workflows, total = await store.list_workflows(limit=50, offset=0)
        duration = time.time() - start

        assert duration < 0.1  # Should complete in < 100ms
        assert len(workflows) == 50
        assert total == 100

    @pytest.mark.asyncio
    async def test_list_runs_performance(self, db_session):
        store = WorkflowStore()

        for i in range(100):
            await store.save_run_state(
                "test_workflow", f"run_{i}", {"status": "completed"}
            )

        start = time.time()
        runs, total = await store.list_runs("test_workflow", limit=50, offset=0)
        duration = time.time() - start

        assert duration < 0.1
        assert len(runs) == 50
        assert total == 100
```

### 4.2 前端性能测试

```bash
# 使用 Lighthouse 测试
cd frontend
pnpm exec lighthouse http://localhost:3000 --view
```

---

## 5. 总结

### 5.1 优化清单

| 优化项 | 预计工作量 | 预期收益 |
|--------|------------|----------|
| 数据库索引 | 0.5 天 | 查询提速 2-5x |
| 查询优化 | 1 天 | 减少全表扫描 |
| 连接池调优 | 0.5 天 | 减少连接等待 |
| 前端配置优化 | 1 天 | 静态资源缓存 |
| 代码分割 | 1 天 | 首屏加载提速 |
| **总计** | **4 天** | |

### 5.2 预期收益

| 查询类型 | 优化前 | 优化后 | 提升 |
|----------|--------|--------|------|
| 工作流列表 | 全表扫描 | 索引扫描 | 3-5x |
| 运行历史 | 全表扫描 | 复合索引 | 5-10x |
| 首屏加载 | 3-5 秒 | 1-2 秒 | 50%+ |
