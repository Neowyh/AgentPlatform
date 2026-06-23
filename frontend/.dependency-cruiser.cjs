/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  forbidden: [
    {
      name: "no-circular",
      comment: "禁止循环依赖",
      severity: "error",
      from: {},
      to: { circular: true },
    },
    {
      name: "lib-no-upward",
      comment: "lib 层不可导入 core/components/app",
      severity: "error",
      from: { path: "^src/lib/" },
      to: { path: ["^src/core/", "^src/components/", "^src/app/"] },
    },
    {
      name: "core-no-components",
      comment:
        "core 层不可导入 components/app（已知例外：threads/hooks 和 artifacts/hooks 需要重构）",
      severity: "error",
      from: {
        path: "^src/core/",
        pathNot: [
          "^src/core/threads/hooks\\.ts$",
          "^src/core/artifacts/hooks\\.ts$",
        ],
      },
      to: { path: ["^src/components/", "^src/app/"] },
    },
    {
      name: "ui-no-business",
      comment: "通用 UI 组件不可依赖业务组件或 core",
      severity: "error",
      from: { path: "^src/components/ui/" },
      to: {
        path: [
          "^src/components/workspace/",
          "^src/components/ai-elements/",
          "^src/core/",
          "^src/app/",
        ],
      },
    },
    {
      name: "no-orphans",
      comment: "检测孤立文件（无任何导入/导出关系）",
      severity: "warn",
      from: {
        orphan: true,
        pathNot: "\\.(d\\.ts|spec\\.ts|test\\.ts|stories\\.ts)$",
      },
      to: {},
    },
    {
      name: "no-deprecated",
      comment: "禁止使用标记为 deprecated 的模块",
      severity: "warn",
      from: {},
      to: { dependencyTypes: ["deprecated"] },
    },
  ],
  options: {
    doNotFollow: {
      path: "node_modules",
      dependencyTypes: [
        "npm",
        "npm-dev",
        "npm-optional",
        "npm-peer",
        "npm-bundled",
      ],
    },
    tsPreCompilationDeps: true,
    tsConfig: { fileName: "tsconfig.json" },
    enhancedResolveOptions: {
      exportsFields: ["exports"],
      conditionNames: ["import", "require", "node", "default"],
      extensions: [".ts", ".tsx", ".js", ".jsx"],
    },
    reporterOptions: {
      dot: { theme: { graph: { rankdir: "LR" } } },
    },
  },
};
