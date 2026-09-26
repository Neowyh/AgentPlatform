---
triage: ready-for-agent
---

# 保持 iDeer 原有前端体验并接入 DeerFlow 新功能

## Problem Statement

合并 DeerFlow 后，工作台的部分前端界面和入口被上游实现覆盖。原来使用聊天、专家·技能·连接器、工作流、资料库、设置和文件预览的用户，需要重新寻找入口或面对重复的管理页面；某些新面板还会在用户没有点击时改变聊天布局。新对话页多出了欢迎标题下的长篇介绍和“最近的对话”卡片，挤占原有任务入口及输入区的空间。输入框里的控件字偏小，输入框下还有与场景入口重复的快捷按钮；底部提示和最近任务卡片位置也不理想。输入 `/` 与点击右下角技能按钮选择技能后会出现不同的输入状态，其中一种还会改变输入框高度。离线部署中出现不可用的云服务入口，也会让用户误以为功能可用。用户希望继续按合并前熟悉的页面位置、外观、文案和常用操作路径完成工作，同时逐项获得 DeerFlow 新能力。

## Solution

以合并前 iDeer 前端为体验基准，恢复原有工作台结构和常用流程。新对话页保留欢迎标题，移除其下的 DeerFlow 长篇介绍和页面内“最近的对话”卡片，调整剩余模块高度，确保任务入口与输入区完整可用。输入框控件与页面正文使用一致的字号，移除输入框下方重复的静态快捷按钮；保留最近任务卡片并上移，让核查提示固定在页面内容底部。输入 `/` 与右下角技能按钮采用同一种选择结果，选中技能不改变新对话页输入框的尺寸。把 DeerFlow 能力放在用户能理解的原位置或明确的新入口，按部署和当前对话的实际能力显示；需要侧边面板时先提示，由用户点击打开。原有“专家·技能·连接器”是唯一的能力中心，定时任务单独排在旧菜单之后。登录页保留原邮箱密码表单，按实际配置增加可选登录方式。

## User Stories

1. As a returning workbench user, I want the original chat, Expert-Skill-Connector, Workflow, and Library destinations in their familiar order, so that I can keep using my usual path.
2. As a returning workbench user, I want the original page layout and wording on those destinations, so that I recognize each screen after the merge.
3. As a chat user, I want the original attachment, model, and Skill controls to remain where I expect them, so that sending a task feels familiar.
4. As an Expert user, I want Expert creation and settings in the existing Expert page, so that I do not have to choose between two Expert management entries.
5. As a Skill user, I want Skill management in the existing Skill page, so that there is one place to find and manage Skills.
6. As a Connector user, I want MCP connection configuration in the existing Connector page, so that the former Settings “Tools” entry does not lead to a second management screen.
7. As a user with an old Settings link, I want Skill and MCP links to open the corresponding capability page, so that existing bookmarks and navigation still lead somewhere useful.
8. As an administrator, I want system-tool governance to remain in the administrator surface, so that moving MCP configuration does not change authorization boundaries.
9. As a Workflow user, I want the original Workflow entry and editor path to stay in place, so that scheduled conversations do not replace my multi-step work.
10. As a user of scheduled tasks, I want a separate Scheduled Tasks entry after all original menu destinations, so that I can find time-triggered conversations without confusing them with Workflow.
11. As a Settings user, I want Account, Appearance, Notifications, Memory, and About in their original positions, so that familiar settings remain easy to find.
12. As an offline-deployment user, I want unavailable public-network Channels and Integrations hidden, so that I do not try features that cannot work in my environment.
13. As an intranet-deployment user, I want a configured and usable internal Channel to appear, so that I can use an approved internal message path.
14. As a deployment with approved Feishu access, I want its integration shown only when that access is configured and usable, so that the entry reflects a real capability.
15. As a chat user, I want my current text and selected Skill draft retained for the current conversation, so that a temporary navigation does not erase what I was writing.
16. As a chat user, I want a submitted draft cleared, so that old text does not reappear after sending.
17. As a chat user, I want voice dictation directly below the input when my browser supports it, so that I can speak a message without searching in another menu.
18. As a chat user, I want an input-polish button directly below the input, so that I can improve a draft and decide whether to send the result.
19. As a chat user, I want to edit and rerun my latest question from that message's More menu, so that I can correct a prompt without starting over.
20. As a chat user, I want the rerun action to make clear that prior file or external-service effects are not undone, so that I understand what a rerun changes.
21. As a chat user, I want to branch from a completed AI reply through that reply's More menu, so that I can explore a different direction in a new conversation.
22. As a user with many conversations, I want to pin one from its More menu, so that I can reach it quickly from recent chats.
23. As a user reading a long conversation, I want an outline only when the conversation is long enough to need it, so that I can jump to a section without clutter in short chats.
24. As a user reading an AI reply, I want to select text and explicitly open a side conversation about that quote, so that the ordinary chat layout stays unchanged until I need the side panel.
25. As a user whose Agent changed working files, I want a change prompt that opens the review when clicked, so that I can inspect actual changes without an empty panel appearing.
26. As a user whose Agent has not changed files, I want no file-change prompt, so that normal chat remains uncluttered.
27. As a user in a browser-enabled deployment, I want the Agent-operated browser entry only when the current conversation can use it, so that the entry reflects an available task capability.
28. As a chat user, I want new Agent browser frames to produce a prompt rather than automatically opening the right panel, so that my chat area does not unexpectedly narrow.
29. As a user without Agent browser capability, I want no live-browser control, so that I do not confuse the Agent browser with the WebUI tab I am already using.
30. As a user opening generated files, I want the original preview entry and panel, so that I can find files in the familiar way.
31. As a user previewing a generated file, I want to edit it there and download a file archive there, so that new file actions are available without a second viewer.
32. As an email-password user, I want the original login form and a visible Remember me checkbox that starts unchecked, so that I can choose whether to remain signed in on this device.
33. As a user of a shared computer, I want an unchecked Remember me choice to avoid a persistent login cookie, so that the platform does not deliberately keep me signed in beyond the browser session.
34. As a user who chooses Remember me, I want my session to persist according to the deployment's secure cookie policy, so that I do not need to sign in every time I reopen my browser.
35. As an employee whose deployment has a reachable enterprise identity provider, I want an Enterprise account login button beside the original form, so that I can use my work account.
36. As a user of a deployment without enterprise identity configured, I want only the original email-password entry, so that I am not shown a button that cannot work.
37. As a user opening a new conversation, I want the iDeer welcome title without the long “欢迎使用 iDeer，一个完全开源的超级智能体…” description beneath it, so that I can reach the task entry quickly.
38. As a user opening a new conversation, I want no page-level “最近的对话” card, so that the welcome area stays focused on starting a task.
39. As a returning user, I want conversation history to remain available in the original left-side navigation and conversation list, so that removing the new-conversation card does not take away history access.
40. As a user opening a new conversation with every remaining home module visible, I want the welcome title, scenario entries, and composer to fit the supported desktop viewport without clipping or overlap, so that I can use them without losing a control below the screen edge.
41. As a user on a narrow or short screen, I want the new-conversation content to reflow or scroll naturally without clipping, overlap, or controls hidden behind fixed elements, so that every module remains usable.
42. As a user starting a new conversation, I want the text on the composer controls, including model and Skill displays, to match the page body text size, so that I can read and identify them without straining.
43. As a user starting a new conversation, I want the attachment and voice controls to have icons and hit areas that remain clear alongside the body-sized labels, so that I can find and use them easily.
44. As a user starting a new conversation, I want the redundant “小惊喜”, “写作”, “研究”, and other static prompt buttons below the composer removed while the scenario and Expert quick entries above it remain, so that I see one clear set of starting choices.
45. As a user starting a new conversation, I want the “内容由AI生成，重要信息请务必核查” notice at the bottom of the page and the “工作复盘？iDeer带你回到过去” recent-task cards higher up, so that the history cards are easier to reach without moving the notice into the middle of the page.
46. As a user selecting a Skill, I want typing `/` and clicking the composer's Skill button to produce the same visible draft and invocation behavior, without changing the composer's width or height on the new-conversation page, so that the two entry paths feel consistent.
47. As a user starting a new conversation, I want the page modules to keep their intended size and position while I switch between available input, model, Skill, voice, and scenario states, so that the page does not jump or deform during normal use; a missing recent-task section when I have no history is an expected exception.

## Implementation Decisions

- Treat the premerge iDeer frontend at `dbb2a813` as the experience baseline and DeerFlow `0f7d8709` as the upstream comparison. Route availability alone does not satisfy visual or interaction parity.
- Preserve the original workbench destination order; append Scheduled Tasks after the original destinations. Keep Expert management inside Expert-Skill-Connector and remove the duplicate Expert destination.
- On the new-conversation page, keep the iDeer welcome title and remove only the long general description below it. Remove the page-level Recent Chats card, including its empty/nonempty variants. Keep the separate left-side recent-conversation/history navigation and full conversation list.
- Rebalance the new-conversation page's remaining module heights and spacing as one responsive layout. At the supported desktop visual-test viewport, the welcome title, scenario entries, and composer must all be fully visible together in the initial viewport. At narrower or shorter viewports, allow normal vertical scrolling while preventing clipped, overlapping, or inaccessible controls; conditional modules must obey the same rule when present.
- Match the visible text size of composer controls, model and Skill selectors, and their labels to the page body type scale. Icon-only attachment and voice controls retain accessible names, readable visual size, and usable hit areas; do not increase text by shrinking the controls.
- Remove the static prompt suggestion row below the new-conversation composer, including “小惊喜、写作、研究”等 entries and code used only by that row. Keep the distinct scenario and Expert quick entries above the composer. Do not remove contextual follow-up suggestions shown after a response.
- Keep the separate “工作复盘？iDeer带你回到过去” recent-task cards when there is history, and move them upward into the space recovered from the removed suggestion row. These are different from the DeerFlow “最近的对话” card already excluded from the new-conversation page. Place the “内容由AI生成，重要信息请务必核查” notice as the bottom page note, below the recent-task cards when present and at the bottom when they are absent.
- Use the existing bottom-right Skill button as the behavior reference for both Skill entry paths: after selecting the same allowed Skill, typing `/` or clicking the button yields the same visible Skill invocation text, caret behavior, selection restrictions, and submission result. Keep unrelated built-in slash commands available. Avoid switching to a differently sized chip editor for one path. On the new-conversation page, selecting, changing, or removing a Skill leaves the outer composer width and height unchanged; typed user content may still follow its normal multiline growth rules.
- Review the new-conversation layout across its normal branch states after the preceding page changes. Opening selectors or changing model, Skill, voice, and scenario state must not cause unrelated modules to resize or shift unexpectedly. Expected content changes, overlay appearance, normal multiline input growth, and omission of recent-task cards when there is no history are permitted.
- Keep Skill management in Skill and MCP server configuration in Connector. Preserve existing administrator permissions for MCP changes and leave system-tool governance in the administrator surface. Legacy Settings links redirect to the corresponding capability page.
- Preserve the original Settings sections and expose Channels and Integrations according to capabilities actually configured and usable in the deployment. A disconnected or unconfigured cloud provider does not get an actionable entry in an offline environment.
- Place voice dictation and input polishing directly below the composer. Preserve the original attachment, model, and Skill control positions. Polishing edits the draft for user review; it does not send automatically.
- Adopt the seven agreed chat additions: current-conversation draft retention, latest-question edit and rerun, reply branching, conversation pinning, long-conversation outline, voice dictation, and input polishing. Put edit/rerun and branching in the relevant message's More menu, and pinning in the conversation's More menu. Show the outline only under its existing long-conversation condition.
- Current draft behavior covers text and selected Skill for the active tab/session; attachment retention and recovery after the tab closes are not part of this scope. A sent draft is cleared.
- Open a quote-based side conversation only after the user selects AI reply text and chooses the action. Show workspace changes only when files changed; open the review on click.
- Distinguish the Agent-operated browser from the user's WebUI browser. Expose it only when the deployment enables the browser runtime and the current conversation can use it. A new frame prompts the user; only a click opens the side panel. Do not resize ordinary chat automatically.
- Keep the original artifact preview entry and panel, adding direct editing and archive download within that same experience.
- Keep the existing email-password login form. Add Remember me initially unchecked and send that explicit choice to the Gateway, because the current server default can persist login over HTTPS or localhost. Preserve server-owned HTTP-only session cookies; never store passwords or access tokens in frontend storage. Show Enterprise account login only for a configured, reachable identity provider.
- Preserve the established authentication, visibility, and permission boundaries when relocating controls or adding entry points. A hidden control is not a substitute for server authorization.

## Testing Decisions

- The primary test seam is the rendered workbench with a controlled backend: exercise navigation, Settings, chat actions, preview, conditional side panels, and capability-gated controls through user-visible clicks and resulting screens. Prefer this existing end-to-end seam over tests of private component state.
- Use the existing visual acceptance approach to compare the restored old screens with the premerge baseline, including desktop and mobile where prior snapshots exist. Cover the workbench, login, Expert page, Workflow editor, Settings, and file preview. Record screenshots for intentional new states separately from the old resting layout.
- Exercise a new conversation with both empty and populated history through the existing page-level seam: the long welcome description and page-level Recent Chats card must be absent in both states, while left-side history remains usable. At the existing desktop visual-test viewport, show all remaining home modules together without vertical clipping or overlap; at mobile and short viewports, verify every control stays reachable through normal scrolling and clear of fixed elements.
- Extend the new-conversation page-level and visual checks to compare composer control labels against the page body type scale, including model and Skill displays; confirm attachment and voice controls remain discoverable and operable. Check both desktop and narrow layouts.
- With no history and with recent tasks present, confirm the static “小惊喜、写作、研究”等 row is absent, scenario and Expert quick entries still work, the recent-task cards remain available and sit above the bottom disclaimer, and the disclaimer occupies the page-bottom position. Contextual follow-up suggestions after a response remain usable.
- Compare the two Skill entry paths at the rendered composer seam: choose the same Skill via `/` and via the bottom-right button, then check equal visible draft text, caret placement, allowed-skill filtering, and submitted behavior. Confirm unrelated built-in slash commands still work. Capture the outer composer bounds before and after choosing, changing, and removing a Skill on the new-conversation page; its width and height must remain stable apart from ordinary multiline typing.
- At the same page-level seam, capture module bounds across the normal branch states: initial load, with or without recent tasks, scenario change, model choice, Skill picker and selection, voice availability or use, and input focus. Check that unrelated modules do not move or deform; allow the explicit empty-history exception and intended overlays or content growth. Use the existing visual acceptance viewport and at least one narrow viewport.
- Exercise capability variants through the same page-level seam: offline/unconfigured deployment, configured internal Channel, reachable enterprise login, and available Agent-operated browser. Assert what users can see and open, not how feature flags are computed internally.
- Exercise the seven chat additions from the visible composer, message, and recent-conversation controls. Check that the More menus contain the expected actions, that short chats have no outline, and that a new browser frame or file change does not open a panel without a click.
- The second necessary seam is an authentication session contract check through the Gateway: unchecked Remember me must create a browser-session cookie, and checked Remember me must follow the secure persistence policy. Browser-level login tests should confirm the visible checkbox and configured enterprise button.
- Prior art already exists in workspace and login visual snapshots; chat, thread history, artifact preview, Settings, MCP settings, and login end-to-end scenarios; and focused component/authentication tests. Extend these before introducing a new test harness.
- A good test verifies the user's visible result or the externally observable session cookie contract. Avoid asserting private React state, storage implementation, or internal function calls unless a public contract cannot be observed at a higher seam.

## Out of Scope

- Redesigning the original pages, renaming their familiar controls, or moving the original destinations to accommodate new features.
- Removing the left-side conversation history, the full conversation-list page, or the iDeer welcome title when simplifying the new-conversation page.
- Removing the separate recent-task cards or post-response contextual follow-up suggestions when deleting the redundant static prompt row.
- Replacing Workflow with Scheduled Tasks or merging the two concepts.
- Adding new public-network providers or guaranteeing connectivity in an air-gapped deployment.
- Treating the Agent-operated browser as a general browser for the person using the WebUI.
- Persisting unsent attachments or guaranteeing draft recovery after closing the tab.
- Reversing previous Agent file changes or external-service effects when a question is rerun.
- Changing server authorization, resource ownership, or administrator boundaries as a side effect of moving UI entry points.

## Further Notes

The glossary defines the frontend experience baseline, Expert-Skill-Connector, Scheduled Task, Workflow, and Agent-operated browser. The navigation decision refines ADR 0001 through ADR 0005. The detailed, WebUI-oriented decision list is the companion adoption record. Current implementation contains some underlying capabilities without a visible login control, and some upstream UI behavior opens the browser panel automatically; this specification describes the intended finished experience, not the current state.
