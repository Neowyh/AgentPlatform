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
