# 双层授权与本地否决权

> audience: developers, architects, security reviewers
> status: accepted
> owner: engineering maintainers
> last-verified: 2026-09-08
> canonical-path: `docs/decisions/2026-09-08-local-authorization-veto.md`

## 决策摘要

本地执行采用双层授权：Server 决定「是否允许委派」（Assembly 阶段裁剪无权能力 + 资源范围授权），设备本地决定「是否允许真正执行」（Local Policy + User Consent 二次判断），两层必须同时通过，且 **Local DENY 永远优先于 Server ALLOW**。服务端授权只表示允许委派，不能强制设备执行。

## 背景与备选

Local Runtime 使服务端 Agent 能触达用户设备上的文件、脚本与本机软件。若只做服务端授权，设备沦为远程执行代理：服务端策略漏洞或凭证失窃即等于整盘沦陷；且设备上的合规要求（如本机不得访问某些目录）无法表达。若只做本地授权，则无法在企业层面统一治理谁能把什么委派给谁。

备选一是 Server 单层授权 + 设备无脑执行——被否决（安全边界缺失）。备选二是设备侧另建一套企业 RBAC——被否决，形成第二套授权真源，违反基线 Decision 3。备选三是基于 unrestricted remote shell 的通用远控——被否决，基线 §20 明确禁止。

## 决策

- Server 侧三层固定：Assembly Authorization（决定模型看到什么）→ Resource Scope Authorization（决定能操作哪些数据）→ 委派；本地不建企业 RBAC。
- Device 收到 Local Task 后独立复核：可信 Server、有效 session/task、capability、Allowed Roots、command policy、network policy、secret policy、user consent。
- 本地操作风险三级：Level 0 安全读可自动；Level 1 修改/执行按本地策略（always allow / ask first / deny）；Level 2 危险操作默认 DENY。
- User Consent 必须绑定当次 request hash，防止所批非所执。
- 通信方向固定：Local Runtime 主动建立 outbound 认证连接，Server 不主动连接用户设备。

## 后果

- 每个 Local Task 的证据链必须同时记录 Server 决定与本地决定（含 consent 记录），任一层缺失即证据不完整。
- 设备离线或本地拒绝时，任务语义为明确的失败/拒绝状态，不得静默降级到 Server 执行。
- 「Local DENY 优先」意味着 Server 侧审计显示"已授权"不等于"已执行"，运维报表必须区分两者。
