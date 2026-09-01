# 故障归零代码证据包与 C 静态排故规格

> 状态：已确认的本地规格；不发布远端 Issue。

## Problem Statement

用户需要用故障归零 Agent 排查一个 C 项目中跨多个源码和头文件的潜在问题，并把源码、构建信息、故障日志和已有资料共同用于根因归因。当前平台只能上传多个普通文件，不能将目录作为一个受控输入安全展开，也不能把 ZIP 自动转换为可递归检索的源码树；故障归零因此无法对多文件 C 项目建立完整、可审计的代码证据。

用户还需要清楚地区分“依据文档排故”和“依据代码排故”。平台不得根据文件扩展名猜测分析方法，更不得将模型推断或单条静态扫描告警误报为已经证实的根因。

## Solution

故障归零提供 Thread-bound 的只读 **Code Evidence Package**：用户在故障归零入口明确上传 ZIP 代码包，平台在授权 Thread 的隔离存储中完成安全校验和受限解压。代码包可包含 C 源码、头文件、可选构建元数据、故障日志与其他证据。

每个 Run 显式声明 **Evidence Mode**：`document`、`code` 或 `hybrid`。模式专用分支提取和验证证据，随后汇入同一套故障树、根因评估、验证计划和归零报告主干。代码模式只允许静态阅读、目录检索和预置静态扫描器分析，绝不构建或执行提交的程序。

报告对每项结论赋予 **Finding Confidence**：`confirmed`、`high_risk_candidate` 或 `pending_verification`。静态扫描告警单独存在时最高只能是 `high_risk_candidate`。

## User Stories

1. As a fault-analysis engineer, I want to explicitly select document, code, or hybrid evidence mode, so that the Run uses the evidence rules appropriate to my request.
2. As a fault-analysis engineer, I want to upload one ZIP Code Evidence Package for a C project, so that source-tree structure is preserved instead of flattened into unrelated attachments.
3. As a fault-analysis engineer, I want to include `.c`, `.h`, and relevant generated configuration files, so that cross-file interfaces and call paths can be inspected.
4. As a fault-analysis engineer, I want to include logs and problem descriptions with the code package, so that source observations can be correlated with the observed failure.
5. As a fault-analysis engineer, I want to include `compile_commands.json` when available, so that static analysis can use the project's real include paths, macros, and compiler flags.
6. As a fault-analysis engineer, I want a package without build metadata to remain analyzable, so that incomplete legacy projects are not rejected solely for lacking modern build files.
7. As a fault-analysis engineer, I want the report to disclose when real compilation configuration was unavailable, so that I understand the confidence limits of code findings.
8. As a fault-analysis engineer, I want the platform to inventory the source tree before analyzing it, so that I can verify which modules and files were considered.
9. As a fault-analysis engineer, I want generic C safety and reliability checks, so that common null dereferences, bounds issues, unchecked return values, resource leaks, dangerous APIs, and error-path defects are surfaced.
10. As a fault-analysis engineer, I want static-analysis findings tied to source locations and rule identifiers, so that a human can reproduce and review them.
11. As a fault-analysis engineer, I want the Agent to relate code findings to logs and documented symptoms, so that an alert is not treated as a root cause without contextual evidence.
12. As a fault-analysis engineer, I want hybrid mode to combine document and code evidence, so that design constraints and test records can corroborate or refute source-level hypotheses.
13. As a fault-analysis engineer, I want one common fault tree and verification plan regardless of evidence mode, so that reports remain comparable across investigations.
14. As a fault-analysis engineer, I want every conclusion labelled by Finding Confidence, so that confirmed causes, high-risk candidates, and pending hypotheses are not conflated.
15. As a fault-analysis engineer, I want a static-analysis alert alone to remain a high-risk candidate, so that I am not given false certainty.
16. As a Thread owner, I want my Code Evidence Package readable only through my authorized Thread, so that proprietary source code is isolated from other users and Threads.
17. As a Thread owner, I want the original ZIP, extracted source tree, and package manifest retained with the Thread until I delete them, so that I can reproduce and review a prior Run.
18. As a Thread owner, I want an explicit deletion action for the package, so that I can remove sensitive source material when it is no longer needed.
19. As a platform administrator, I want ZIP path traversal, absolute paths, symbolic links, oversized archives, excessive file counts, and compression bombs rejected, so that source uploads cannot escape their storage boundary or exhaust service resources.
20. As a platform administrator, I want rejected or skipped content reported clearly, so that users do not mistake incomplete package processing for complete analysis.
21. As a platform administrator, I want build outputs, dependency caches, and binary targets excluded from analysis by default, so that package capacity is spent on relevant evidence.
22. As a platform administrator, I want approved C analyzers preinstalled in the offline sandbox image, so that analysis does not download tools or depend on Internet access.
23. As a platform administrator, I want the Agent to invoke only a fixed static-analysis capability rather than arbitrary shell commands, so that untrusted packages cannot turn code analysis into general command execution.
24. As a platform administrator, I want the analyzer confined to the Code Evidence Package and its designated output location, so that it cannot read unrelated Thread data or modify submitted source.
25. As a platform administrator, I want scanner names, versions, selected rules, and results recorded in Run artifacts, so that an analysis result is auditable and reproducible.
26. As a workflow author, I want mode-specific evidence extraction to converge before fault-tree construction, so that downstream nodes do not duplicate their business logic.
27. As a workflow author, I want normal document attachment behavior unchanged, so that existing document-only fault-analysis users are not disrupted.
28. As a workflow author, I want a dedicated code-package upload path rather than implicit ZIP expansion in generic uploads, so that archive processing is intentional, visible, and governed.
29. As a security reviewer, I want the submitted executable never to be built or run, so that static analysis cannot become runtime execution of untrusted code.
30. As a future standards owner, I want generic C safety rules to be the first profile and MISRA C, CERT C, or organization-specific profiles to remain optional future extensions, so that initial delivery does not assume an unapproved compliance standard.

## Implementation Decisions

- Introduce Code Evidence Package as a Thread-bound, read-only input distinct from generic attachments and Agent/Skill archives.
- Provide a dedicated fault-zeroing UI affordance and authenticated upload API for ZIP packages. Generic ZIP attachments retain their existing behavior and are never silently expanded.
- Enforce these first-release limits: maximum compressed size 200 MiB, maximum expanded size 1 GiB, and maximum 20,000 archive members. Reject unsafe archives atomically and return a user-readable rejection reason.
- Validate archive members before extraction: forbid absolute paths, traversal segments, symbolic links, duplicate/conflicting extraction paths, and unsafe compression expansion. Preserve a package manifest recording accepted, excluded, and rejected members.
- Preserve source-tree paths. Exclude build outputs, dependency caches, and binary targets by default; do not remove project-owned source or required headers merely because they are nested in a larger tree.
- Retain the ZIP, extracted tree, and manifest in the owning Thread under existing authorization and audit rules. Deletion is explicit and removes the package materials together.
- Add Evidence Mode to a fault-zeroing Run with the three declared values `document`, `code`, and `hybrid`. Server-side validation binds code and hybrid modes only to a validated Code Evidence Package; clients do not submit arbitrary filesystem paths.
- Keep one shared fault-zeroing main flow. Document mode uses document and text extraction; code mode uses inventory, recursive source retrieval, log correlation, and C analysis; hybrid mode performs both extraction paths and normalizes their output before the shared fault-tree stage.
- Preserve the established node-level file-access boundary. Code-specific tools may access only the declared package root and their declared output artifacts; no global widening of filesystem permissions is allowed.
- Deliver one fixed C static-analysis capability backed by preinstalled `clang-tidy` and `cppcheck` in the isolated offline sandbox image. It has a constrained input contract, uses no free-form shell, has no network access, and never builds or executes submitted artifacts.
- Prefer `compile_commands.json`; use `CMakeLists.txt` or `Makefile` as fallback build metadata. If none exists, complete a read-and-search analysis but record that the project compilation configuration was not verified.
- Start with a general C safety and reliability rule profile. MISRA C, CERT C, company rule sets, runtime execution, dependency installation, and arbitrary analyzer arguments are separate future work.
- Normalize static results into source-linked evidence with scanner identity, version, rule identifier, location, message, and package-relative path. Store raw scanner output and a concise normalized summary as Run artifacts.
- Use Finding Confidence throughout the fault tree, verification plan, and report: `confirmed` requires corroborating evidence; `high_risk_candidate` may be supported by consistent static and contextual evidence; `pending_verification` is a hypothesis requiring a prescribed check.
- Use the existing single Run boundary as the highest feature seam: a valid package plus mode and problem description produces governed evidence and a report. Lower-level archive, analyzer, and UI tests support that seam rather than defining separate product behavior.

## Testing Decisions

- The primary acceptance test is a complete fault-zeroing Run at the public workflow boundary. It supplies a package, Evidence Mode, and problem description, then verifies the observable report, artifact inventory, and Finding Confidence rules rather than internal implementation calls.
- Package API integration tests cover Thread authorization, package persistence, list/delete behavior, required response metadata, and the stated size/member limits.
- Archive-security unit tests cover traversal paths, absolute paths, symbolic links, compression-ratio/expanded-size limits, duplicate paths, cleanup after failure, and exclusion-manifest accuracy.
- C-analysis contract tests use controlled fixture packages. They verify scanner invocation receives only the validated package root and output destination, does not execute a fixture program, and records scanner version/rules/results as artifacts.
- Workflow validation tests cover all three Evidence Modes, mode/input mismatches, file-access denial outside a package root, document-only backward compatibility, and hybrid evidence normalization before the shared fault-analysis nodes.
- Report tests cover all three Finding Confidence values and assert that a lone scanner alert never becomes `confirmed`.
- Frontend tests cover explicit mode selection, code-package-only upload affordance, progress and error states, skipped/excluded-member disclosure, and explicit deletion. End-to-end tests use the actual upload and Run entrypoints.
- Existing upload-router tests, filesystem-scope middleware tests, fault-zeroing workflow structure/runtime tests, and chat attachment tests are prior art. New tests should use their external contracts and fixtures, not assert private helper sequencing.
- Completion validation runs the relevant focused tests during each slice, then the backend standard lane, frontend standard lane, and `pr-standard`, because the feature crosses Agent, Workflow, upload, authorization, and frontend boundaries.

## Out of Scope

- Executing, building, linking, testing, or installing dependencies for submitted C code.
- General command execution or user-controlled static-analyzer flags.
- Automatic extraction of ZIP files uploaded through the ordinary chat attachment control.
- Mandatory `compile_commands.json`, `CMakeLists.txt`, or `Makefile` for package acceptance.
- A claim of complete C semantic understanding when preprocessors, generated headers, vendor SDKs, or build metadata are absent.
- MISRA C, CERT C, organization-specific rule profiles, and compliance certification.
- C++ and other language-specific structural analysis beyond safe text evidence handling.
- Replacing the existing document-only fault-zeroing workflow or changing generic attachment semantics.
- Remote Issue creation or publication for this specification.

## Further Notes

- The feature must remain compatible with offline/intranet delivery: scanner binaries and rule data are checked into or packaged with the deployable sandbox image; no analysis-time external fetches are permitted.
- Existing document analysis and source analysis differ only at evidence extraction. The fault tree, root-cause reasoning, verification plan, artifact gates, and report remain one governed product flow.
- Users should be guided to include a concise problem description and relevant logs. A code package without a symptom can yield review findings, but it cannot by itself establish an incident root cause.
- The existing ADRs for Code Evidence Package static analysis and explicit Evidence Modes are normative for this specification.
