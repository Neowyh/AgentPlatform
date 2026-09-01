# iDeer

iDeer is an agent application that composes Thread, Agent, Skill, and Workflow resources into executable Runs.

## Scenario Entry

**Scenario Tab**:
The top-level new-conversation category that groups Agent Pills. Current canonical labels are the three welcome-page categories, not executable resources.
_Avoid_: Scenario tag

**Agent Pill**:
An entry under a Scenario Tab representing one Agent to be selected for a new conversation.
_Avoid_: Group, scene group, agent tag

**Task Chip**:
An entry under an Agent Pill representing exactly one preinstalled Skill and its prompt template.
_Avoid_: Task tag, skill tag

**Selected Task**:
The Task Chip chosen for a message; it declares the Skill that the model should preferentially use for that message.
_Avoid_: Forced skill invocation

## Product Experience

**Embedded software knowledge brief**:
A source-cited, human-reviewable digest of a specified chip model and package that contains the information needed to start embedded software development; it is not a replacement for the manufacturer data sheet or a hardware design database.
_Avoid_: Pin table, complete data sheet, schematic source of truth

**Chip data-sheet extraction**:
The task of deriving an Embedded software knowledge brief from a native-text PDF data sheet for one specified chip model and package.
_Avoid_: Generic document summary, OCR-first document conversion, multi-package merge

**Chip software source set**:
The mutually consistent documents for one specified chip model and package: its data sheet, Reference Manual or Programming Manual, and any applicable errata.
_Avoid_: Datasheet alone, mixed-family documents, unqualified web excerpts

**Chip software development package**:
The pair of deliverables from a Chip software source set: a source-cited Markdown knowledge brief and a controlled structured appendix for review and later automation; it excludes application initialization code.
_Avoid_: Uncited chat answer, generated firmware, hardware design database

**Evidence status**:
The confidence label on a fact in a Chip software development package: `confirmed` when directly supported by consistent source documents, or `review_required` when it remains ambiguous, conflicting, or incomplete; both statuses remain visible to the user.
_Avoid_: Implicit confidence, silently discarded uncertainty, treating unreviewed content as confirmed

**Task-first entry**:
The default platform entry helps a user describe what they want to accomplish before exposing Agent, Skill, or Workflow concepts. Recent work and workspace status support the task entry without replacing it.
_Avoid_: Resource-first entry

**Layered density**:
The interface keeps enough visible structure for users to understand available capabilities and for experienced users to work efficiently, while revealing advanced details progressively instead of showing every platform concept at once.
_Avoid_: Sparse minimalism, undifferentiated information wall

**Warm research desk**:
The product's visual direction combines the warmth and materiality of a study or editorial workspace with the order and professional clarity of a modern research institute.
_Avoid_: Generic SaaS dashboard, decorative luxury, cold control room

**Role surface**:
The platform uses one coherent workbench for ordinary and professional users. Ordinary users receive clear shortcut entries, while professional users can reveal advanced options that require additional operation. Administrative governance remains a separate surface when needed.
_Avoid_: Three unrelated products, one overloaded interface for every role

**Persistent workbench navigation**:
The primary navigation remains present while users move between work areas, without switching between a desktop navigation model and a mobile navigation model.
_Avoid_: Navigation that disappears by page, device-specific information architecture

**Task-first home**:
The workbench home keeps the iDeer identity and a welcoming greeting while making task description the primary action, with recent work and capability entry points supporting it.
_Avoid_: Resource-first home, equal-weight dashboard

**Current progress**:
A user-facing thread of goal, current state, completed work, and next available action that helps users understand ongoing work across the workbench. It is guidance, not a new executable resource or forced process.
_Avoid_: Task graph, forced workflow, platform-internal status dump

**Workbench welcome**:
The workbench home uses the fixed main title “iDeer，实现你的idea” for brand recognition and concept communication. A scenario-oriented subtitle explains the available entry points and invites the user into a concrete task.
_Avoid_: Capability catalogue as the hero, generic greeting without a next action

**Current progress placement**:
Current progress appears below the page title as the page's contextual summary, rather than as a permanently fixed global banner or a runtime-only indicator.
_Avoid_: Global status strip, hidden progress, runtime-only status

**Workbench home order**:
The workbench home presents the fixed iDeer welcome title first, followed by scenario-oriented quick entries, the open task input, and recent tasks. Agent, Skill, and Connector capability entries remain in the persistent left navigation rather than competing with the home task flow.
_Avoid_: Resource-first hero, task input before all guidance, capability catalogue in the main home sequence

**Quick entry**:
A scenario-oriented starting point for a common user goal, usually expressed as a plain-language task template. It helps a user start without requiring them to understand Agent or Skill structure.
_Avoid_: Resource selector, guaranteed Skill invocation, capability configuration

**Connector**:
An external system or data-source connection, such as MCP, a database, a file system, or a third-party API, that can be made available to work in iDeer.
_Avoid_: Generic Tool, Skill, Agent

**Capability navigation**:
Agent, Skill, and Connector are browsable and configurable from the persistent left navigation. The input box may invoke an already available capability for the current task without forcing the user through the configuration surface.
_Avoid_: Capability cards as the home hero, configuration-only invocation

**Workbench navigation**:
The persistent workbench navigation exposes New conversation, Conversation history, Expert-Skill-Connector, Workflow, and Library in that order. Expert-Skill-Connector groups the platform's reusable working capabilities rather than scattering them through Settings.
_Avoid_: A flat resource catalogue, capability configuration hidden in Settings

**Expert-Skill-Connector**:
The user-facing capability center grouping Expert, Skill, and Connector. Expert is the user-facing name for an Agent; Connector means MCP connection configuration, not a generic Tool.
_Avoid_: Agent terminology in user-facing navigation, Tool as a synonym for Connector

**Capability resource page**:
Each Expert, Skill, or Connector page supports the resource lifecycle and task use from one place: create, browse, edit, delete, favorite, call in a conversation, import, export, and request a visibility change, subject to the user's authorization.
_Avoid_: Read-only catalogues separated from management actions, actions that bypass authorization

**Capability summary**:
A concise, persisted user-facing explanation of an Expert or Skill's purpose and scope, derived from its published source when an explicit description is absent.
_Avoid_: Runtime model-generated copy, a full SOUL.md or SKILL.md transcript

**Bundled resource seed**:
The idempotent provisioning of manifest-declared public Skills, Experts, and Workflows into the canonical resource catalog for a local or deployed runtime.
_Avoid_: A frontend-only catalog, manually copied Agent directories, one-time private installer state

**Scenario selection granularity**:
The home keeps three fixed scenario groups and the three-level Scenario Tab → Agent Pill → Task Chip entry. A user may start with no selection, select only a Scenario Tab, select an Agent Pill, or continue from an Agent Pill to its Task Chips; Task Chips do not appear without an Agent Pill selection.
_Avoid_: Calling these entries tags, requiring all three levels, presenting platform concepts before the user needs them

**Scenario selector layout**:
Scenario Tabs remain fixed at the top of the selector. The same lower selector position switches between the current Scenario's Agent Pills and the selected Agent's Task Chips, so the page does not shift or stack both levels at once.
_Avoid_: Independent Task Chips, three simultaneous selector rows, layout shifts between levels

**Recent task visual identity**:
Recent task cards show task name, type, status, and a visual summary of the latest conversation content that helps recognition. Visual treatment should support identification rather than become unrelated decoration.
_Avoid_: Abstract decoration without task meaning, metadata-only recent-task list

**Scenario groups**:
The fixed Scenario Tabs are “日常办公”, “创意设计”, and “专业任务”, with “创意设计” as the default entry group.
_Avoid_: Unstable top-level categories, platform-internal category names

**Agent and task distinction**:
An Agent Pill communicates what an Agent is good at, while a Task Chip communicates the concrete action to complete. Task Chips appear only after an Agent Pill is selected and cannot be selected independently.
_Avoid_: Orphan Task Chips, full capability inventories in every selector, treating Agent and Task as synonyms

**Progressive current progress**:
Current progress is a one-line summary below the page title and expands into a side panel when the user asks for detail.
_Avoid_: Permanent full-status panel, status-only badge, runtime-only progress

**Task index ribbon**:
The visual signature combines the selected scenario/Agent context with the current progress into a compact task index ribbon, for example: “创意设计 · 研究助理 / 目标：完成市场分析 · 当前：整理材料 · 下一步：生成结论”. It travels across the home, Thread, Workflow, and library surfaces.
_Avoid_: Decorative-only signature, context hidden in unrelated panels, a global status banner that displaces page content

**Typography direction**:
The platform uses a modern sans-serif typography system throughout to preserve readability and information density. Warmth and distinction come from material palette, spacing, hierarchy, and the task index ribbon rather than a serif display face.
_Avoid_: Decorative typography, mixed type personalities that reduce scanning speed

**Conversation visual summary**:
Recent task cards show one key excerpt from the latest conversation plus a task-type color band, giving the card both recognizable content and a consistent visual marker.
_Avoid_: Full message transcript, keyword-only summary, chat-bubble thumbnail

**Visual prototype coverage**:
The next visual prototype compares the design system across the workbench home, Thread, Agent/Skill/Connector capability surfaces, Workflow, library, and settings.
_Avoid_: Homepage-only approval, treating a single card grid as platform-wide validation

**Readable density**:
Information density must remain compatible with comfortable reading for somewhat older users: primary text, controls, and selection targets use a visibly generous size and spacing rather than compact dashboard defaults.
_Avoid_: Tiny labels, dense controls that require precise vision, sacrificing readability for visible item count

**Scenario module prominence**:
The Scenario Tab → Agent Pill → Task Chip selector is a core workbench module, not a secondary navigation strip. On the home it receives a clearly bounded, explanatory, visually prominent region before the task input.
_Avoid_: Small tab row, selector hidden as decoration, input dominating before the user understands the available starting directions

**Primary visual direction**:
The warm paper workbench is the lead design direction. Other prototype directions may test structural alternatives, but production visual decisions should default to its warm material palette, clear hierarchy, and readable scale.
_Avoid_: Treating all visual directions as equally final, returning to cold compact dashboard styling

**Concise interface copy**:
Each surface should use restrained, task-oriented wording: keep the title, current state, decision, and next action; remove repeated explanations and decorative editorial copy.
_Avoid_: Multiple labels saying the same thing, explanatory paragraphs beside obvious controls, copy used to fill space

**Efficient warm workbench**:
Warm paper styling must still behave like a productive software workspace. Use the available screen width for task content, compact vertical rhythm, restrained borders and shadows, and readable controls instead of magazine-like panels and oversized empty areas.
_Avoid_: Flat editorial spread, decorative card wall, large empty hero areas

**Guidance hierarchy**:
Scenario Tabs and Agent/Task quick entries are a low-emphasis guidance layer. The task composer is the primary visual anchor and should receive the strongest contrast and affordance on the workbench home.
_Avoid_: Quick-entry controls competing with the main task action, every control using the same visual weight

**Reference calibration**:
When taking interaction cues from WorkBuddy, borrow the compact segmented scenario control and restrained quick-entry chips, while preserving iDeer's warm paper palette, task-first language, and capability model.
_Avoid_: Copying brand assets, treating reference layout as the product's complete information architecture

**Typography budget**:
The prototype and eventual workbench UI use a single sans-serif family and no more than three functional sizes: page title, readable body/control text, and supporting metadata. Weight and spacing carry hierarchy instead of additional typefaces or tiny labels.
_Avoid_: Serif display type, monospace utility labels, many near-identical font sizes

**Welcome alignment**:
The workbench welcome title and scenario selector are centered as the opening focal point. The scenario selector does not include a redundant “也可直接输入” prompt; the composer below communicates direct input.
_Avoid_: Left-drifting welcome hero, redundant input instructions, shortcut controls competing with the welcome title

**Welcome home restraint**:
The welcome home does not show a persistent current-task progress ribbon. Its subtitle is concise and guides the user to choose a work scenario, while the task composer remains the next primary action.
_Avoid_: Unrequested task status in the welcome state, multiple helper captions above the composer, welcome labels that repeat “工作台”

**Centered entry stack**:
The welcome title, scenario selector, and task composer share a centered visual axis. The composer keeps its functional controls in the lower toolbar and does not use separate upper-left and upper-right helper descriptions.
_Avoid_: Misaligned entry blocks, duplicated composer instructions, helper copy competing with the task input

**Welcome activity restraint**:
The welcome state does not include a separate activity action beside the greeting. Activity and history remain available through the broader workbench navigation or task surfaces.
_Avoid_: Competing secondary action beside the brand welcome, status controls in the first visual moment

**Home content alignment**:
The recent-task heading and cards align to the same centered content width as the scenario selector and task composer on the lead warm-paper home.
_Avoid_: Recent tasks drifting wider than the entry stack, unrelated content widths on the home surface

**Welcome headline**:
The welcome home uses the concise fixed headline “iDeer，落地你的idea” without a separate welcome subtitle or a “工作台” eyebrow.
_Avoid_: Brand title plus redundant platform label, long welcome explanation

**Module guidance copy**:
The scenario selector, task composer, and recent-task module each receive one short conversational guidance sentence that explains the next action. The sentences are functional labels, not promotional copy.
_Avoid_: No guidance for novice users, multiple helper captions, slogan-like instructions

**Unified home axis**:
The welcome headline block, scenario selector, task composer, and recent-task block share the same centered content width and horizontal axis.
_Avoid_: Welcome content using a different alignment grid, recent tasks drifting away from the entry modules

**One-line module guidance**:
The scenario selector, task composer, and recent-task module each use one single-line question-and-answer sentence. The question uses a quiet neutral color and the answer uses the product accent, so the guidance is scannable without adding vertical height.
_Avoid_: Multi-line helper paragraphs, equal-color question and answer, guide text pushing core controls downward

**Module label restraint**:
The one-line guidance sentence is the label for the scenario, task-input, and recent-task modules; redundant headings such as “选择一个场景”, “开始任务”, and “最近任务” are removed. The type hierarchy is limited to welcome title > module guidance > input and recent-task content.
_Avoid_: A heading repeating the guidance sentence, several competing text sizes, module labels smaller than card content

**Home module guidance copy**:
The lead wording is: “方向不明？iDeer帮你找对帮手”, “目标明确？iDeer帮你落地实现”, and “工作复盘？iDeer带你回到过去”. These are parallel, conversational prompts that explain the next action for each module.
_Avoid_: Promotional slogans, technical labels, uneven sentence patterns, instructions detached from the module action

**Discoverable capability invocation**:
The task input keeps a plain-language placeholder and also exposes a visible capability-invocation menu. Experienced users may continue to use direct slash-style Skill invocation.
_Avoid_: Hidden-only commands, navigation-only invocation, permanently exposing all advanced controls

**Home task input**:
The task input is a horizontal primary input below the quick entries. It supports attachments, Skill invocation, model choice, and sending a task.
_Avoid_: Separate advanced input page, capability configuration as the default input flow

**Navigation task order**:
Persistent left navigation follows the user path: start working, capability center, then management and settings. Recent tasks remain a home content module rather than a separate task-navigation section.
_Avoid_: Agent-first navigation, flat platform-object catalogue, duplicated task navigation

**Recent task presentation**:
Recent tasks are visually prominent cards rather than a plain table. Each card retains basic recognition information and emphasizes the task's visual identity and current state.
_Avoid_: Time-only list, decorative cards without recognition information

**Content-shaped density**:
Operational content uses rows and lists, choices use cards, and complex details use a side panel so information density follows the user's action rather than one universal component shape.
_Avoid_: Card-only interface, table-only interface, excessive step-by-step fragmentation

## Core Resources

**Agent**:
A named resource that configures model, tool groups, and selected Skills to handle a class of conversations.
_Avoid_: Assistant, Bot

**Skill**:
A reusable capability package defined by a SKILL.md directory that extends an Agent; either PUBLIC (built-in, read-only) or CUSTOM (user-authored, editable).
_Avoid_: Plugin, Tool, Prompt

**Workflow**:
A declarative execution graph of typed nodes (action, route, fork, join, interrupt) and edges that orchestrates deterministic multi-step work.
_Avoid_: Flow, Pipeline, DAG

## Execution

**Thread**:
A persistent conversation container that holds messages, artifacts, and todos across multiple Runs, identified by thread_id.
_Avoid_: Conversation, Session, Chat

**Run**:
A single execution attempt of an Agent or Workflow within one Thread, tracked through pending, running, success, error, timeout, or interrupted.
_Avoid_: Execution, Job, Task

## Access & Visibility

**Resource**:
A canonical catalog entry for a Skill, Agent, or Workflow with owner, visibility, lifecycle status, and versioned content.
_Avoid_: ResourceVersion, ResourceDraft

**Department**:
An organizational unit that scopes users and department-visible Resources.
_Avoid_: Team, Group

**Visibility**:
The access scope of a Resource: private (owner only), department (owner's department), or public (all users). A Resource cannot be more visible than its dependencies, and raising visibility may require approval via VisibilityApplication.
_Avoid_: Permission, Scope

**UserRole**:
The platform role determining capabilities: viewer, user, department_admin, or super_admin.
_Avoid_: Role, Permission level

## Memory & Artifacts

**Memory**:
Per-user long-term memory comprising structured summaries (workContext, personalContext, topOfMind, history) and discrete MemoryFacts.
_Avoid_: Chat history, Context

**Artifact**:
A file produced during a Run and attached to its Thread, addressable at /api/threads/{thread_id}/artifacts/{path}.
_Avoid_: File, Attachment, Output

**Code Evidence Package**:
A Thread-bound read-only ZIP input for a fault-zeroing Run that preserves a source tree and fault evidence, with optional build metadata that raises analysis confidence.
_Avoid_: Code folder, project upload, Agent archive

**Finding Confidence**:
The evidence grade of a fault-zeroing conclusion: confirmed, high-risk candidate, or pending verification. A static-analysis alert alone is never confirmed.
_Avoid_: Severity, certainty, bug status

**Evidence Mode**:
The explicit fault-zeroing input classification: document, code, or hybrid. It selects evidence extraction rules while retaining one shared fault-analysis and reporting flow.
_Avoid_: Auto-detected file type, workflow variant, analysis guess

**Todo**:
A task item within a Thread's state, with status pending, in_progress, or completed.
_Avoid_: Task, Checklist item

## Workflow Internals

**Workflow Node**:
A step in a Workflow graph, typed as action, route, fork, join, or interrupt, declaring writes, preconditions, and retry policy.
_Avoid_: Node, Step

**Workflow Edge**:
A directed connection between Workflow Nodes, optionally bounded by max_iterations.
_Avoid_: Link, Transition

## Testing

**Test Lane**:
A named level of verification for iDeer changes. A Test Lane specifies the required checks for a feedback stage, such as a pull request, main branch, or release.
_Avoid_: Test bundle, test mode
