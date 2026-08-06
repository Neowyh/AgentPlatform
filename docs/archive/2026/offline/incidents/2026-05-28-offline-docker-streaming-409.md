# 离线 Docker 归零分析 409 问题原因与修复

## 问题现象

离线 Docker 部署后，使用归零智能体发起分析时，前端可能出现如下错误：

```text
HTTP 409: {"detail":"Run 565e99e2-28c9-49ee-a4e7-1e581722b9b0 is not active on this worker and cannot be streamed"}
```

该错误不是归零智能体本身的推理错误，也不是模型服务直接返回的错误，而是 Gateway 在处理已有 run 的流式重连时返回的运行时状态错误。

## 根因分析

旧离线包中的 `source/docker/docker-compose.intranet.yaml` 默认 Gateway 启动参数为：

```yaml
--workers ${GATEWAY_WORKERS:-4}
```

如果部署目录根部的 `env.intranet` 中没有设置 `GATEWAY_WORKERS`，Docker Compose 会使用默认值 `4`，也就是启动 4 个 Gateway worker 进程。

当前 iDeer 的 run 任务、取消控制状态和 `MemoryStreamBridge` 流式事件缓冲都保存在单个 Python 进程内存中。多 worker 场景下可能出现如下链路：

1. 前端发起归零分析，请求落到 worker A，run 任务和 SSE 流缓冲也在 worker A 内存中创建。
2. 页面刷新、网络重连或 SDK `joinStream` 请求落到 worker B。
3. worker B 可以从 SQLite 持久化记录中读到该 run，所以知道 run 存在。
4. 但 worker B 没有该 run 的内存任务和流式缓冲，因此无法继续 stream。
5. 后端返回 409：`Run ... is not active on this worker and cannot be streamed`。

因此，根因是“多 worker 进程”与“进程内 MemoryStreamBridge / active run 状态”不匹配。

## env.intranet 与 runtime/.env 的区别

修复旧部署时，`GATEWAY_WORKERS=1` 必须写入部署目录根部的：

```text
env.intranet
```

不要只写入：

```text
runtime/.env
```

原因是 `--workers ${GATEWAY_WORKERS:-4}` 是 Docker Compose 解析 compose 文件时完成变量替换的，`deploy-intranet.sh` 调用 Compose 时使用的是：

```bash
docker compose -p ideer -f source/docker/docker-compose.intranet.yaml --env-file env.intranet ...
```

所以 `${GATEWAY_WORKERS:-4}` 读取的是 `env.intranet`。

`runtime/.env` 是通过 compose 的 `env_file:` 注入到 Gateway 容器内部的环境变量文件。它在容器启动时才进入容器环境，已经晚于 Compose 对 `--workers ${GATEWAY_WORKERS:-4}` 的插值阶段，因此不能影响 worker 数。

## 当前源码修复措施

当前源码已将 Docker compose 的默认 Gateway worker 数从 4 改为 1：

```yaml
--workers ${GATEWAY_WORKERS:-1}
```

涉及文件：

```text
docker/docker-compose.yaml
docker/docker-compose.intranet.yaml
```

该修改使新打包的离线包在未显式设置 `GATEWAY_WORKERS` 时默认使用单 worker，避免 run 创建、stream 重连和取消控制落到不同 worker。

## 未部署 Docker 镜像 / 新离线包修复方案

对于尚未部署的新离线包，直接基于当前源码重新打包：

```bash
scripts/package-intranet-offline.sh --version <version> --force
```

在内网环境按原流程部署：

```bash
./deploy-intranet.sh prepare
./deploy-intranet.sh up
```

部署后确认实际 worker 数：

```bash
docker compose -p ideer -f source/docker/docker-compose.intranet.yaml --env-file env.intranet config | grep -- '--workers'
```

期望输出中包含：

```text
--workers 1
```

注意：如果新包部署后在 `env.intranet` 中手工设置了 `GATEWAY_WORKERS=4`，仍会覆盖 compose 默认值，问题可能复现。

## 已部署旧镜像 / 旧离线包修复方案

已部署旧离线包时，无需重新打镜像。进入离线部署目录，修改部署目录根部的 `env.intranet`。

如果没有该字段，追加：

```bash
printf '\nGATEWAY_WORKERS=1\n' >> env.intranet
```

如果已有该字段，将其改为：

```text
GATEWAY_WORKERS=1
```

然后重启并强制重建容器：

```bash
./deploy-intranet.sh restart
```

确认 Compose 解析结果：

```bash
docker compose -p ideer -f source/docker/docker-compose.intranet.yaml --env-file env.intranet config | grep -- '--workers'
```

确认运行中容器命令：

```bash
docker inspect ideer-gateway --format '{{json .Config.Cmd}}'
```

两处都应体现：

```text
--workers 1
```

## 验证建议

重启 Gateway 后，浏览器可能仍会尝试重连重启前的旧 run。旧 run 已经失去原 worker 内存状态，可能残留一次 409。判断修复是否生效，应以重启后新发起的一轮归零分析是否仍复现为准。

建议验证步骤：

1. 修改 `env.intranet`。
2. 执行 `./deploy-intranet.sh restart`。
3. 确认 `docker compose ... config` 输出为 `--workers 1`。
4. 确认 `docker inspect ideer-gateway ...` 输出为 `--workers 1`。
5. 刷新浏览器页面。
6. 新建或重新发起一轮归零智能体分析。
7. 观察是否仍出现 `not active on this worker and cannot be streamed`。

## 后续扩展说明

单 worker 是当前离线 Docker 部署下的正确默认值。若未来需要恢复多 worker 或多副本部署，需要先将 StreamBridge 和 active run 控制状态改为进程外共享机制，例如 Redis StreamBridge 或等价的共享运行时状态服务。否则多 worker 仍可能在流式重连、取消 run、继续 stream 等场景中出现状态不一致。
