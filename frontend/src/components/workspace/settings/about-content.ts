/**
 * About iDeer markdown content. Inlined to avoid raw-loader dependency
 * (Turbopack cannot resolve raw-loader for .md imports).
 */
export const aboutMarkdown = `# 关于 iDeer 2.0

> **源于开源，回馈开源**

iDeer 是一个开源的**超级智能体框架**，通过编排**子智能体**、**记忆系统**和**沙箱环境**来完成几乎任何任务——并由**可扩展的技能系统**驱动。

---

## 核心功能

* **技能与工具**：内置丰富的可扩展技能和工具，让 iDeer 能处理几乎任何场景。
* **子智能体编排**：将复杂任务动态分解为子任务，由子智能体协作完成。
* **工作流引擎**：基于 YAML 的可视化工作流编排，自动化多步骤业务流程。
* **沙箱与文件系统**：在隔离的沙箱环境中安全执行代码和操作文件。
* **上下文工程**：子智能体上下文隔离与自动摘要，保持上下文窗口高效清晰。
* **长期记忆**：持续记录用户画像、关注焦点和对话历史。
* **MCP 服务器管理**：集成 MCP 协议，实现服务端资源与工具的发现和调用。
* **RBAC 权限管理**：基于角色的访问控制，支持团队多用户协作与权限隔离。
* **离线/内网部署**：支持 Docker 离线部署，适用于内网和隔离环境。

---

## 开源许可

iDeer 自豪地采用 **MIT 许可证** 开源发布。

---

## 致谢

我们衷心感谢所有让 iDeer 成为现实的开源项目和贡献者。我们真正站在巨人的肩膀上。

### 核心框架
- **[LangChain](https://github.com/langchain-ai/langchain)**：卓越的 LLM 交互与链式调用框架，为 iDeer 提供 AI 能力底座。
- **[LangGraph](https://github.com/langchain-ai/langgraph)**：实现复杂的多智能体编排与状态管理。
- **[Next.js](https://nextjs.org/)**：先进的 Web 应用构建框架，驱动前端界面。

### UI 组件库
- **[Shadcn](https://ui.shadcn.com/)**：极简风格的 UI 组件库，构建优雅的用户界面。
- **[SToneX](https://github.com/stonexer)**：感谢其对逐 token 可视化效果的卓越贡献。

这些优秀的项目构成了 iDeer 的基石，也展现了开源协作的变革力量。
`;
