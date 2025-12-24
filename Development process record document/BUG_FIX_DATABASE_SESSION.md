# 下载功能数据库会话问题修复

## 🔍 问题诊断

### 发现日期
2025-11-01

### 问题症状
用户尝试下载视频时，任务能成功创建并添加到队列，但在实际执行下载时立即失败，日志显示：

```
Download failed: (sqlite3.ProgrammingError) Cannot operate on a closed database.
[SQL: SELECT download_tasks.id, ... FROM download_tasks WHERE download_tasks.task_id = ?]
```

### 根本原因分析

在 `backend/src/api/downloads.py` 文件中，存在严重的**数据库会话生命周期管理错误**：

#### 问题代码位置 1：`_process_queue()` 函数（第141-168行）

```python
async def _process_queue():
    """处理下载队列"""
    try:
        next_task_id = await download_queue.start_next_task()
        if next_task_id:
            # 获取任务信息
            from src.models import get_session
            async for db in get_session():  # ⚠️ 会话在这里创建
                result = await db.execute(...)
                task = result.scalar_one_or_none()
                if task:
                    # 执行下载
                    asyncio.create_task(_execute_download(next_task_id, request, db))  # ❌ 传递会话
                break  # ⚠️ 循环结束，会话被关闭
```

**问题点：**
1. `async for db in get_session()` 创建了一个数据库会话
2. 会话被传递给后台异步任务 `_execute_download`
3. `break` 语句导致循环结束，会话的 `__aexit__` 被调用，会话关闭
4. 后台任务仍在运行，但持有的 `db` 引用已经是关闭状态
5. 当后台任务尝试使用 `db` 时，抛出 "Cannot operate on a closed database" 错误

#### 问题代码位置 2：`_execute_download()` 函数（第171-251行）

该函数接收已关闭的会话，并在多处尝试使用：
- 第175-182行：更新任务状态为下载中
- 第218-224行：更新任务完成状态
- 第237-244行：更新任务失败状态

## 🔧 修复方案

### 修复策略
**关键原则：后台异步任务必须管理自己的数据库会话，不能依赖外部传入的会话。**

### 代码修改

#### 修改 1：`_process_queue()` 函数

**修改前：**
```python
asyncio.create_task(_execute_download(next_task_id, request, db))
```

**修改后：**
```python
# 不传递db会话，让任务自己创建新会话
asyncio.create_task(_execute_download(next_task_id, request))
```

#### 修改 2：`_execute_download()` 函数签名

**修改前：**
```python
async def _execute_download(task_id: str, request: DownloadRequest, db: AsyncSession):
```

**修改后：**
```python
async def _execute_download(task_id: str, request: DownloadRequest):
```

#### 修改 3：在 `_execute_download()` 中创建独立会话

**更新任务状态为下载中：**
```python
# 创建独立的数据库会话
from src.models import get_session

async for db in get_session():
    result = await db.execute(
        select(DownloadTask).where(DownloadTask.task_id == task_id)
    )
    task = result.scalar_one_or_none()
    if task:
        task.status = 'downloading'
        task.started_at = datetime.now()
        await db.commit()
    break
```

**更新任务完成状态：**
```python
async for db in get_session():
    result_task = await db.execute(
        select(DownloadTask).where(DownloadTask.task_id == task_id)
    )
    task = result_task.scalar_one_or_none()
    if task:
        task.status = 'completed'
        task.filename = result.get('filename')
        task.filesize = result.get('filesize')
        task.completed_at = datetime.now()
        task.progress = 100.0
        await db.commit()
    break
```

**更新任务失败状态（异常处理）：**
```python
async for db in get_session():
    result = await db.execute(
        select(DownloadTask).where(DownloadTask.task_id == task_id)
    )
    task = result.scalar_one_or_none()
    if task:
        task.status = 'failed'
        task.error_message = str(e)
        await db.commit()
    break
```

## ✅ 修复验证

### 验证步骤
1. 启动后端服务
2. 通过前端或API创建下载任务
3. 观察日志，确认：
   - 任务成功创建
   - 任务加入队列
   - 任务开始执行
   - 数据库更新正常
   - 下载正常进行

### 预期结果
- ✅ 不再出现 "Cannot operate on a closed database" 错误
- ✅ 任务状态正常更新（pending → downloading → completed）
- ✅ 进度回调正常工作
- ✅ 多任务并发下载正常

## 📝 技术要点

### SQLAlchemy 异步会话管理最佳实践

1. **短生命周期原则**
   - 每个数据库操作都应该使用独立的会话
   - 会话应该尽快创建，尽快提交/回滚，尽快关闭

2. **不要跨边界传递会话**
   - 不要将会话传递给后台任务
   - 不要将会话传递给回调函数
   - 不要将会话存储为实例变量

3. **使用上下文管理器**
   ```python
   async for session in get_session():
       # 使用 session
       await session.commit()
       break  # 确保会话关闭
   ```

4. **后台任务数据库访问**
   ```python
   async def background_task(task_id: str):
       # 在任务内部创建新会话
       async for db in get_session():
           # 执行数据库操作
           break
   ```

## 🔍 相关代码位置

- **修复文件**: `backend/src/api/downloads.py`
- **相关文件**: `backend/src/models/database.py`
- **测试文件**: `backend/tests/test_downloads.py`

## 📚 参考资料

- [SQLAlchemy Async Session](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Python Asyncio Task Management](https://docs.python.org/3/library/asyncio-task.html)
- [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)

## 🎯 后续优化建议

1. **添加会话池监控**
   - 监控会话创建和关闭
   - 检测会话泄漏

2. **添加单元测试**
   - 测试并发下载场景
   - 测试会话管理正确性

3. **性能优化**
   - 考虑使用连接池（虽然 SQLite 使用 NullPool）
   - 批量更新进度以减少数据库操作

4. **错误处理增强**
   - 添加更详细的错误日志
   - 区分不同类型的数据库错误

---

**修复人员**: AI Assistant  
**修复日期**: 2025-11-01  
**版本**: v1.0

