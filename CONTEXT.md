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
