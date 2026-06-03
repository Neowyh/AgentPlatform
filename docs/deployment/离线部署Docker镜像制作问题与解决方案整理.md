# 离线部署 Docker 镜像制作问题与解决方案整理

日期：2026-05-28

## 一、背景

这份文档用于记录 iDeer 禁公网内网离线部署 Docker 镜像包制作、交付和现场启动过程中实际遇到过的问题。它不是预先设计出来的风险清单，而是根据昨晚到现在的打包、部署、排查和修复过程整理出来的复盘材料，供后续再次制作离线包、交接部署流程或排查同类故障时参考。

当时涉及的主要链路包括：

- 构建机执行 `scripts/package-intranet-offline.sh`，生成离线镜像包和源码包。
- 内网服务器拷贝离线包后，通过 `deploy-intranet.sh prepare` 生成运行时目录。
- 运维人员编辑 `runtime/config.yaml`、`runtime/.env` 等配置。
- 通过 `deploy-intranet.sh up` 导入镜像并启动 Gateway、Frontend、Nginx。

这些问题发生后，仓库里的脚本、compose、作业指导书和问题文档都做过对应调整。回头看，问题并不只来自 Docker 镜像构建本身，更多是离线包运行时配置、启动入口、健康检查、浏览器访问、智能体运行和 Git 交付边界没有一开始就讲清楚。

## 二、问题导读

下文按真实排查场景分为五类：构建打包、离线运行配置、服务健康检查、前端访问登录、归零智能体与长任务。每个问题都按 `问题现象`、`问题根因`、`解决方案` 三段记录，语气上尽量采用过去式，说明当时看到了什么、后来确认是什么原因、最终采取了什么处理方式。

这份文档不是完整安装手册，也不是要求每次部署都逐项执行的 checklist。它的重点是把发生过的问题讲清楚：现场看到的现象说明了什么，哪些判断后来被证明是误判，哪些修改已经沉淀到当前流程里。后续读者如果没经历过这轮排查，可以先按报错、页面表现或部署阶段找到对应问题，再看根因和处理方式；具体一步步部署仍以作业指导书为准。

## 三、构建与打包阶段

这一类问题先回答一个最基本的问题：离线包到底有没有真的做出来。能运行脚本、脚本语法没错，都不等于镜像 tar 已经生成。

### Docker socket 权限导致镜像包无法构建

#### 问题现象

构建机执行 `scripts/package-intranet-offline.sh` 时，脚本能找到 `docker` 命令，但实际 build 或 save 阶段报 `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`，离线镜像 tar 没有生成。

#### 问题根因

只验证了 Docker 客户端存在，没有验证当前 shell 是否能访问 Docker daemon。`docker version` 能显示客户端信息不等于构建权限可用，真正的前置检查应包含 `docker info`。

直白地说，能敲 `docker` 命令，不代表当前用户有权限让 Docker 真正去构建镜像。

#### 解决方案

构建前先执行 `docker version`、`docker compose version` 和 `docker info`。只有 `docker info` 成功，才继续执行 `scripts/package-intranet-offline.sh`。如果 socket 权限失败，先处理 Docker 服务状态和当前用户的 Docker 组权限；临时一次性打包可由有权限的运维账号执行，但不能把语法检查通过当成镜像构建完成。

### Shell 语法检查被误认为真实构建成功

#### 问题现象

脚本落地后只执行了 `bash -n scripts/package-intranet-offline.sh`，随后被误认为离线镜像包已制作完成，但 `dist/intranet/` 下没有可交付的 `ideer-images-*.tar`。

#### 问题根因

`bash -n` 只检查 shell 语法，不会执行 Docker build、Docker save、源码打包和校验文件生成。它只能证明脚本能被 shell 解析，不能证明离线制品已经形成。

可以把它理解成“检查菜谱有没有错别字”，不是“已经把菜做出来”。

#### 解决方案

将“脚本语法检查通过”和“离线包真实生成”分开记录。正式构建必须执行 `scripts/package-intranet-offline.sh --version <版本号>`，并确认镜像 tar、源码包和 `SHA256SUMS` 都已生成；没有这些文件时，只能视为脚本验证，不能进入内网部署环节。

### `uv run` 在禁公网内网访问 PyPI

#### 问题现象

离线服务器启动 Gateway 容器时，命令进入 `uv run ...` 后尝试解析或同步依赖，日志中出现访问 PyPI、企业源或网络超时，导致 Gateway 无法启动。

#### 问题根因

早期离线 compose 使用普通 `uv run uvicorn ...`。在某些环境下，`uv run` 会尝试做依赖同步；禁公网内网没有公网包索引访问能力，运行期依赖解析就会变成启动失败。

离线部署的要求很简单：镜像启动时不能再临时上网装东西，所有依赖都应提前放进镜像。

#### 解决方案

离线镜像必须在构建阶段安装好依赖，运行阶段只启动服务。`docker/docker-compose.intranet.yaml` 中 Gateway 命令应保持为 `uv run --no-sync uvicorn app.gateway.app:app ...`，后续回归检查也应覆盖这一点，避免 intranet compose 被改回会触发运行期同步的形式。

### 镜像 tar 进入 Git 历史导致 GH001

#### 问题现象

推送离线部署相关提交到 GitHub 时失败，提示 `GH001: Large files detected`。即使后续提交删除了 `dist/intranet` 下的 tar，推送仍然被拒绝。

#### 问题根因

镜像 tar 是数百 MB 级交付制品，一旦进入未发布提交历史，GitHub 会检查整个 push range。后续“删除文件”的提交只是在新提交里移除路径，旧提交中的大 blob 仍然存在。

也就是说，把大文件删掉再提交一次，并不能让 Git 历史里那个大文件自动消失。

#### 解决方案

`ideer-images-*.tar` 和 `dist/intranet/` 下的离线制品不要提交到普通 Git 历史。已经进入未发布历史时，需要改写未发布历史移除 blob，或改用 Git LFS、制品库、内网文件服务器、对象存储等交付渠道。

## 四、离线包运行时配置合同

这一类问题的核心是“部署时到底看哪一份配置”。离线包有自己的运行目录，不能把开发源码目录里的配置当成内网运行配置。

### `frontend.env` 与 `frontend/.env` 混淆

#### 问题现象

内网部署人员不知道应该修改源码目录 `frontend/.env`，还是部署目录下的 `runtime/frontend.env`。改错位置后，前端容器仍按旧配置启动，页面访问、登录回调或 SSR 请求继续异常。

#### 问题根因

早期脚本、compose fallback 和文档中的 env 路径没有完全统一，源码开发环境和离线运行环境的配置边界混在一起。

现场处理时只记一条：离线包运行看 `runtime/frontend.env`，不是看源码里的 `frontend/.env`。

#### 解决方案

离线部署只把 `runtime/frontend.env` 作为前端运行时 env 文件，`env.intranet` 中通过 `IDEER_FRONTEND_ENV_FILE` 把该路径传给 compose。部署人员不要修改源码目录 `frontend/.env` 来修复内网运行问题；所有运行态配置都应落在部署根目录的 `runtime/` 和 `env.intranet`。

### 内网部署根目录为 `/opt` 时路径假设失效

#### 问题现象

离线包被解压到内网服务器的 `/opt` 或 `/opt/ideer` 后，手工命令、诊断命令或 compose 路径引用仍沿用开发机目录，导致找不到 `source/docker/docker-compose.intranet.yaml`、`runtime/config.yaml` 或 env 文件。

#### 问题根因

部分排查动作默认了源码仓库根目录就是运行目录，但离线包的真实运行根目录由运维解压位置决定。内网环境常见路径是 `/opt`，不能依赖开发机上的绝对路径。

换句话说，命令要站在内网服务器实际解压出来的目录里执行，不能照搬开发机路径。

#### 解决方案

在内网服务器上以离线包解压后的 bundle root 为工作目录执行命令，例如先 `cd /opt/ideer`，再运行 `./deploy-intranet.sh prepare`、`./deploy-intranet.sh up`、`./deploy-intranet.sh status`。compose、env 和 runtime 路径都由 `deploy-intranet.sh` 统一拼接，不要直接复用开发机绝对路径。

### `models: null` 导致 `config.yaml` 启动失败

#### 问题现象

Gateway 容器启动时报 `config.yaml` 格式或类型错误，后端配置模型校验失败。现场查看配置时，`models:` 看起来存在，但实际 YAML 解析结果是 `null`，不是后端要求的列表。

#### 问题根因

早期 `prepare` 直接复制示例配置，示例里的裸 `models:` 会被 YAML 解析为 `null`。后端配置合同要求该字段是 list，因此空值会在启动校验阶段失败。

看起来“写了 models”不一定有用；对程序来说，`models:` 空着和 `models: []` 不是一回事。

#### 解决方案

`deploy-intranet.sh prepare` 生成运行时配置时必须产出合法列表，至少应为 `models: []`。运维后续再在 `runtime/config.yaml` 中补入真实模型服务配置；启动前也应校验 YAML 能解析，且 `models` 的类型是 list。

### 内部鉴权和登录密钥未稳定持久化

#### 问题现象

重新执行 prepare、重建 `env.intranet` 或多 worker 启动后，出现登录态失效、内部 Gateway 调用鉴权不稳定、服务间请求偶发失败等现象。

#### 问题根因

`BETTER_AUTH_SECRET` 和 `IDEER_INTERNAL_AUTH_TOKEN` 如果只临时写在 env 文件中，删除或重建 env 后会变化。多 worker 或多次重启时，不稳定的 token 会放大内部调用和会话校验问题。

这类密钥一旦变了，系统会把原来的登录态或内部请求当成“不可信”，表现出来就是登录或服务间调用异常。

#### 解决方案

将 `BETTER_AUTH_SECRET` 持久化到 `runtime/data/.better-auth-secret`，将 `IDEER_INTERNAL_AUTH_TOKEN` 持久化到 `runtime/data/.internal-auth-token`。`deploy-intranet.sh` 生成或修复 `env.intranet` 时应复用已有值，不覆盖已经存在的密钥。

### 源码包泄露本地 env、缓存或报告

#### 问题现象

离线源码包中可能夹带开发机的 `frontend/.env`、测试报告、缓存目录、构建产物或本地调试文件，内网交付时既有泄露风险，也会干扰部署人员判断真实运行配置位置。

#### 问题根因

早期打包排除规则不完整，把源码目录中的本地状态和正式离线运行配置混在一起。真正要在内网修改的是 bundle root 下的 `runtime/`，不是开发机遗留文件。

本地 `.env`、测试报告和缓存都是开发现场的痕迹，不应该进入正式交付包。

#### 解决方案

`scripts/package-intranet-offline.sh` 打源码包时排除真实 `.env`、测试报告、缓存和构建产物。离线运行配置只由 `deploy-intranet.sh prepare` 在 `runtime/config.yaml`、`runtime/.env`、`runtime/frontend.env`、`runtime/extensions_config.json` 中生成。

### 绕过 `deploy-intranet.sh` 直接运行根目录 compose

#### 问题现象

运维人员在离线包中直接执行根目录或源码目录下的 compose 命令，结果 env 文件、runtime 路径、镜像名和挂载目录与预期不一致，服务启动后表现为配置缺失或页面异常。

#### 问题根因

离线包曾出现参考 compose/env 文件，容易被误认为启动入口。实际离线部署需要先由脚本生成运行时目录、密钥和 env 合同，再用 intranet compose 启动。

直接跑 compose 等于跳过了“准备运行目录”这一步，后面的路径和密钥就可能对不上。

#### 解决方案

部署入口统一为 `./deploy-intranet.sh prepare`、`./deploy-intranet.sh up`、`./deploy-intranet.sh status`、`./deploy-intranet.sh logs`。不要绕过脚本直接在源码根目录跑 compose；需要查看最终 compose 时，也应基于部署根目录的 `env.intranet` 和 `source/docker/docker-compose.intranet.yaml`。

### Codex CLI 凭据只在宿主机存在

#### 问题现象

离线 Docker 启动后，使用 Codex 相关模型时报 `Codex CLI credential not found. Expected ~/.codex/auth.json or CODEX_AUTH_PATH.`，或者 `CodexChatModel` 初始化阶段直接失败。宿主机上可能确实有 `~/.codex/auth.json`，但容器内仍然找不到。

#### 问题根因

`CodexChatModel` 会在初始化时从容器内读取 `CODEX_AUTH_PATH`，未设置时再尝试读取容器用户家目录下的 `~/.codex/auth.json`。当前离线 compose 默认挂载的是运行配置、extensions、skills、runtime home 和 Docker socket，不会自动把宿主机个人目录中的 Codex 凭据传进 Gateway 容器。

宿主机上有 `auth.json`，不等于容器里也能看到这个文件；容器只看被挂载进去的路径。

#### 解决方案

普通离线部署不要默认依赖 `.claude` 或 `.codex` 这类个人 home 目录，避免把通用部署和个人 CLI 认证绑在一起。如果内网确实选择 Codex CLI provider，需要单独设计认证文件挂载，把宿主机或内网密钥目录中的 `auth.json` 以只读方式挂入 Gateway 容器，并设置 `CODEX_AUTH_PATH` 指向容器内路径；不使用 Codex provider 时，应改用已在 `runtime/config.yaml` 中配置好的非 Codex 模型提供方。

## 五、服务启动与健康检查

这一类问题最容易误判。后端接口活着，不代表网页一定能打开；容器显示 running，也不代表登录流程已经可用。

### 部署时出现 `healthy check skipped`

#### 问题现象

容器启动后，部署日志或 `docker compose ps` 中出现 `healthy check skipped`，现场容易误判为服务已经健康，或者反过来误判为健康检查失败。

#### 问题根因

`healthy check skipped` 通常表示当前检查链路没有执行到容器内健康检查，或者镜像、compose、运行环境缺少对应检查条件。它不是业务服务真实可用的证明。

看到 skipped 时，不要按“成功”处理，也不要马上按“失败”处理；它的意思是还需要换一种方式确认。

#### 解决方案

把 `healthy check skipped` 当成“需要外部确认”的信号。继续通过 Nginx 暴露入口检查 `/health`、`/api/v1/auth/setup-status` 和首页 `/`，再结合 `./deploy-intranet.sh logs gateway`、`logs frontend`、`logs nginx` 判断真实状态。当前 `deploy-intranet.sh up` 和 `restart` 会在启动后执行这三条 HTTP 检查，只有都返回正常才应进入浏览器验收。

### 内网服务器缺少 `curl` 导致诊断命令不可用

#### 问题现象

按作业指导书执行健康检查时，内网服务器提示 `curl: command not found`，导致 `/health`、首页和鉴权状态接口无法按原命令验证。

#### 问题根因

部分最小化内网服务器镜像没有预装 `curl`。这只是诊断工具缺失，不等于服务不可用，也不能因此跳过健康验证。

没有 `curl` 只是少了一个检查工具，不是系统已经坏了，也不是可以不检查。

#### 解决方案

当前 `deploy-intranet.sh` 会优先使用 `curl`，没有 `curl` 时依次尝试 `wget`、`python3`、`python` 做同样的 HTTP 健康检查。若这些工具都没有，脚本会明确失败；现场应安装至少一种 HTTP 诊断工具，或用浏览器访问 `http://<内网服务器IP>:2026/health` 和首页做替代验证，并同时查看 `./deploy-intranet.sh logs`。

### Nginx、Gateway、Frontend 健康检查链路不一致

#### 问题现象

`/health` 和 `/api/v1/auth/setup-status` 返回正常，但浏览器首页、登录页或 `/workspace` 仍然加载失败。现场只看 Gateway 健康状态时，会误以为整套部署已经可用。

#### 问题根因

`/health` 和 auth setup 状态主要覆盖 Gateway 链路，不代表 Nginx 到 Frontend、Frontend SSR 到 Gateway、浏览器访问域名和端口都正确。前端 SSR 登录态校验失败时，也会外显为页面不渲染。

简单说，接口能回包只说明后端大体活着；用户真正用的是网页，还要确认首页能打开、登录能走通。

#### 解决方案

验收顺序应覆盖完整链路：先看 Gateway `/health`，再看 `/api/v1/auth/setup-status`，最后看浏览器入口 `/`、初始化页、登录/注册和 `/workspace`。如果首页失败，不要只看 Gateway，应同时检查 Frontend 和 Nginx 日志。

### 容器内健康检查依赖工具缺失

#### 问题现象

容器状态没有进入预期 healthy，或者健康检查命令本身失败，但业务端口可能已经能访问。现场难以区分是服务失败，还是健康检查依赖的工具缺失。

#### 问题根因

健康检查脚本可能依赖容器内的 shell、HTTP 客户端或特定路径。离线镜像裁剪后，如果工具缺失，健康检查会失败或跳过，但这和业务进程是否监听端口不是同一个问题。

健康检查命令失败，有时失败的是“检查动作”本身，不一定是业务服务。

#### 解决方案

先用 `./deploy-intranet.sh logs <service>` 判断主进程是否启动，再从宿主机或浏览器访问 Nginx 暴露的 HTTP 路径确认业务可用。后续修复健康检查时，应把容器内依赖工具纳入镜像构建和 compose 回归检查。

## 六、前端访问与登录

这一类问题先从用户看到的页面入手。页面空白、停在 `/setup`、登录后回不去主页，不一定都是同一个原因。

### 老浏览器停在 `/setup` 或注册界面无法渲染

#### 问题现象

客户端访问 `http://<内网服务器IP>:2026` 后停留在 `/setup`，注册界面空白、按钮不可用或页面脚本加载失败；同一地址在新版 Chrome、Edge 或 Chromium 内核浏览器中可以正常打开。

#### 问题根因

内网客户端浏览器内核过旧，不支持当前 Next.js/React 打包产物使用的现代 JavaScript 或 CSS 能力。容器和后端接口健康时，问题仍可能只发生在特定旧浏览器上。

如果新浏览器能打开、旧浏览器打不开，优先按浏览器兼容问题处理，不要先去改后端。

#### 解决方案

将浏览器版本纳入部署验收项，优先使用近两年的 Chrome、Edge 或等价 Chromium 内核。出现 `/setup` 空白时，先用新版浏览器交叉验证，再查看浏览器 Console 是否有语法解析、API 不存在或模块加载错误；不要直接把它归因为 Gateway 注册接口失败。

### Gateway SSR/auth 配置错误导致登录页或注册页不加载

#### 问题现象

登录页、注册页或 `/workspace` 加载失败，页面可能表现为空白、跳转异常或登录后无法进入主页。Gateway 日志中可能伴随 auth me、setup status、内部 base URL 或 session 相关错误。

#### 问题根因

Frontend 的服务端渲染需要访问 Gateway 的鉴权接口。若 `IDEER_INTERNAL_GATEWAY_BASE_URL`、公开访问 URL、auth secret 或 Gateway 启动配置错误，前端会把后端配置问题外显为登录页或注册页不加载。

这里的直观理解是：前端页面在服务端先问一次后端“这个用户是谁”，这一步问不到，页面就可能直接加载不出来。

#### 解决方案

排障时先确认 Gateway 启动和 `/api/v1/auth/setup-status`，再确认 Frontend SSR 访问 Gateway 的内部地址，最后看 Nginx 入口。涉及登录接口 403 或跨域错误时，把访问域名、端口、Origin、前端 public URL 和后端允许来源放在同一组核对，保证浏览器实际访问地址与后端配置一致。

## 七、归零智能体与长任务

这一类问题要区分“文件带到了包里”和“系统运行时能用”。智能体能不能被用户看到，长任务能不能持续返回结果，都取决于运行态目录和 Gateway 进程状态。

### 归零智能体已打包但未进入运行时共享目录

#### 问题现象

离线包中可以看到归零排故智能体文件，但内网用户进入系统后看不到智能体入口，或只能在某个用户目录下看到残缺文件，管理 API 也不可用。

#### 问题根因

“随源码包交付”不等于“安装到运行态共享目录”。自定义智能体需要放在 `runtime/data/agents/fault-zeroing/` 这类共享路径，且配置中要开启智能体管理 API；如果仍停留在源码目录或单用户目录，前端和 API 层不一定能发现。

可以理解成：文件放在包里只是“带过去了”，放到共享运行目录才是“系统能看见”。

#### 解决方案

`deploy-intranet.sh prepare` 阶段应安装 `docs/fault-zeroing-agent/agent/` 到 `runtime/data/agents/fault-zeroing/`，并合并归零排故所需的 subagents。`config.yaml` 和 `SOUL.md` 是已整理好的成品资产，应原样安装，不做模板化改写。运行时配置中应保证：

```yaml
agents_api:
  enabled: true
```

如需临时跳过归零智能体安装，可以在部署命令前设置 `IDEER_INSTALL_FAULT_ZEROING=0`，但这只适合排查部署基础链路，不应作为正式交付默认状态。

### `agents_api.enabled` 未开启

#### 问题现象

归零智能体文件已经存在，但前端自定义智能体入口不可用，或相关 API 返回禁用、找不到入口、管理功能不可见。

#### 问题根因

示例配置中自定义智能体 API 可能默认关闭。只复制文件而不修改运行时 `config.yaml`，不会自动开放管理和发现能力。

也就是说，文件已经在磁盘上，不代表前端和 API 已经允许用户管理或调用它。

#### 解决方案

在 `runtime/config.yaml` 中将 `agents_api.enabled` 设为 `true`。这应由 `deploy-intranet.sh prepare` 自动修复，人工排查时也要把该字段作为归零智能体可见性的必查项。

### Agent 记忆写入用户 `agents/` 目录导致共享智能体被遮蔽

#### 问题现象

共享归零智能体已经安装在运行态共享目录，例如 `runtime/data/agents/fault-zeroing/config.yaml` 和 `SOUL.md` 都存在；但某个用户使用 `fault-zeroing` 后，系统可能在该用户目录下生成：

```text
runtime/data/users/<user_id>/agents/fault-zeroing/memory.json
```

后续再加载 `fault-zeroing` 时，自定义智能体解析逻辑会优先看到用户级 `users/<user_id>/agents/fault-zeroing/` 目录。这个目录里只有 `memory.json`，没有 `config.yaml` 和 `SOUL.md`，于是共享智能体可能表现为找不到配置、无法加载，或看起来被某个用户目录下的残缺同名目录遮蔽。

#### 问题根因

早期按 Agent 记忆和自定义 Agent 配置共用了同一个目录命名空间：`agents/`。自定义 Agent 配置资产使用：

```text
{base_dir}/users/{user_id}/agents/{agent_name}/config.yaml
{base_dir}/users/{user_id}/agents/{agent_name}/SOUL.md
```

但按 Agent 记忆也写到：

```text
{base_dir}/users/{user_id}/agents/{agent_name}/memory.json
```

这会让一次普通 memory 保存动作创建出用户级 `agents/<agent_name>/` 目录。对于 `fault-zeroing` 这类共享智能体，用户本来没有自己的同名自定义 Agent 配置；但 memory 写入创建了同名目录后，配置加载器会把它当成用户级 Agent 目录优先处理，从而遮蔽共享目录 `agents/fault-zeroing/`。

直白地说，记忆文件把“配置目录”占住了；目录名一样，系统先看到用户目录，就不再回退到共享智能体。

#### 解决方案

将按 Agent 记忆从配置命名空间中拆出来，固定写入新的 `agent-memory/` 目录：

```text
{base_dir}/users/{user_id}/agent-memory/{agent_name}/memory.json
{base_dir}/agent-memory/{agent_name}/memory.json
```

`agents/` 只保存 Agent 配置资产，例如 `config.yaml` 和 `SOUL.md`；`agent-memory/` 只保存 Agent 记忆状态。为兼容旧部署，读取 memory 时先读新路径，如果新路径不存在，再回退读取旧的 `agents/<agent_name>/memory.json`；但保存时始终写入新路径，不再创建 `users/<user_id>/agents/<agent_name>/`。

现场排查同类问题时，可以检查用户目录下是否存在只有 `memory.json` 的残缺目录：

```bash
find runtime/data/users -path '*/agents/fault-zeroing' -type d -print
find runtime/data/users -path '*/agents/fault-zeroing/config.yaml' -type f -print
find runtime/data/users -path '*/agent-memory/fault-zeroing/memory.json' -type f -print
```

修复后的预期状态是：新产生的记忆文件出现在 `users/<user_id>/agent-memory/fault-zeroing/memory.json`；用户没有自定义同名 Agent 时，不应再自动生成 `users/<user_id>/agents/fault-zeroing/`。旧路径下已经存在的 memory 文件不需要运行时自动迁移或删除，系统仍会在新路径不存在时兼容读取。

### 多 worker 与内存流状态导致 HTTP 409

#### 问题现象

离线 Docker 中执行归零分析或其他长任务时，刷新页面、SSE 重连或继续查看运行结果会返回 `HTTP 409`，错误类似 `Run ... is not active on this worker and cannot be streamed`。

#### 问题根因

Gateway 多 worker 启动时，run 任务、`MemoryStreamBridge` 和流式缓冲保存在创建任务的单个 worker 进程内。重连请求如果落到另一个 worker，该 worker 能从持久化记录看到 run，但没有进程内 active run 状态，于是返回 409。

白话说，就是任务在 A 进程里跑，浏览器刷新后连到了 B 进程；B 知道有这个任务记录，但不知道它正在 A 里面跑。

#### 解决方案

离线 Docker 默认使用 `GATEWAY_WORKERS=1`，保证长任务和流式重连落在同一进程内。新离线包通过 compose 默认值继承该修复；旧包必须在部署根目录 `env.intranet` 写入 `GATEWAY_WORKERS=1` 后重启，因为 `runtime/.env` 不参与 Compose 命令插值。重启后可用 `docker compose ... config | grep -- '--workers'` 或 `docker inspect ideer-gateway --format '{{json .Config.Cmd}}'` 确认启动命令已经是单 worker。验证修复时要新发起一轮归零分析，不要用修复前遗留的旧 run id 复测。

该方案适用于当前单机离线部署和内存态流式任务；如果未来要恢复多 worker，需要引入跨 worker 的任务状态和流缓冲共享机制，而不能只调大 worker 数。

## 八、最终推荐流程

构建机先确认 Docker daemon 可用，再执行 `scripts/package-intranet-offline.sh` 生成离线镜像包、源码包和校验文件；镜像 tar 作为交付制品管理，不进入普通 Git 历史。

内网服务器将离线包上传并解压到实际部署目录，例如 `/opt/ideer`，先用 `sha256sum -c SHA256SUMS` 校验包完整性，再通过 `./deploy-intranet.sh prepare` 和 `./deploy-intranet.sh up` 启动。首次启动会导入镜像；如果镜像已经提前 `docker load` 过，可以按脚本支持的 `--no-load` 路径跳过重复导入。

运行配置集中修改 `runtime/config.yaml`、`runtime/.env`、`runtime/frontend.env` 和部署根目录的 `env.intranet`，不要回到源码目录修改 `frontend/.env`。仅模型端点、密钥或访问域名变化时，优先修改运行配置后执行 `./deploy-intranet.sh restart`，不需要重新制作镜像。

启动后按完整链路验收：检查 `/health`、`/api/v1/auth/setup-status`、首页 `/`，再用新版 Chrome/Edge 访问初始化、登录/注册、`/workspace` 和归零智能体入口。若现场缺少 HTTP 诊断工具或健康检查被跳过，应改用浏览器和服务日志补充验证，不能直接把 skipped 状态当成业务健康。
