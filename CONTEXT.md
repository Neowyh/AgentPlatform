# iDeer

iDeer is an agent application that composes conversation, Agent, Skill, and Workflow resources into executable runs.

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

## Testing

**Test Lane**:
A named level of verification for iDeer changes. A Test Lane specifies the required checks for a feedback stage, such as a pull request, main branch, or release.
_Avoid_: Test bundle, test mode
