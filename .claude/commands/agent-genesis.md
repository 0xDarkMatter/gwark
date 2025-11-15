---
description: Generate Claude Code expert agent prompts for any technology platform
---

# Agent Genesis - Expert Agent Prompt Generator

Generate high-quality, comprehensive expert agent prompts for Claude Code.

## Usage Modes

### Mode 1: Single Agent Generation
Generate one expert agent prompt for a specific technology platform.

**Prompt for:**
- Technology platform/framework name
- Focus areas (optional: specific features, patterns, use cases)
- Output format (markdown file or clipboard-ready text)

### Mode 2: Batch Agent Generation
Create multiple agent prompts from a list of technology platforms.

**Accept:**
- Multi-line list of technology platforms
- Common focus areas (optional)
- Output format (individual .md files in `.claude/agents/` or consolidated text)

### Mode 3: Architecture Analysis
Analyze a tech stack or architecture description and suggest relevant agents.

**Process:**
1. Read architecture description (from user input or file)
2. Identify all technology platforms/services
3. Present checkbox selector for agent creation
4. Generate selected agents

## Agent File Format

All agents MUST be created as Markdown files with **YAML frontmatter** in `.claude/agents/`:

**File Structure:**
```markdown
---
name: technology-name-expert
description: When this agent should be used. Can include examples and use cases. No strict length limit - be clear and specific. Include "use PROACTIVELY" for automatic invocation.
model: inherit
color: blue
---

[Agent system prompt content here]
```

**YAML Frontmatter Fields:**
- `name` (required): Unique identifier, lowercase-with-hyphens (e.g., "asus-router-expert")
- `description` (required): Clear, specific description of when to use this agent
  - No strict length limit - prioritize clarity over brevity
  - Can include examples, use cases, and context
  - Use "use PROACTIVELY" or "MUST BE USED" to encourage automatic invocation
  - Multi-line YAML string format is fine for lengthy descriptions
- `model` (optional): Specify model ("sonnet", "opus", "haiku", or "inherit" to use main session model)
- `color` (optional): Visual identifier in UI ("blue", "green", "purple", etc.)

**File Creation:**
Agents can be created programmatically using the Write tool:
```
Write to: .claude/agents/[platform]-expert.md
```

After creation, the agent is immediately available for use with the Task tool.

## Generation Requirements

For each agent, create a comprehensive expert prompt with:

**Agent Content Structure:**
```markdown
# [Technology Platform] Expert Agent

**Purpose**: [1-2 sentence description]

**Core Capabilities**:
- [Key capability 1]
- [Key capability 2]
- [Key capability 3]

**Official Documentation & Resources**:
- [Official Docs URL]
- [Best Practices URL]
- [Architecture Patterns URL]
- [API Reference URL]
- [GitHub/Examples URL]
- [Community Resources URL]
- [Blog/Articles URL]
- [Video Tutorials URL]
- [Troubleshooting Guide URL]
- [Migration Guide URL]
- [Minimum 10 authoritative URLs]

**Expertise Areas**:
- [Specific feature/pattern 1]
- [Specific feature/pattern 2]
- [Specific feature/pattern 3]

**When to Use This Agent**:
- [Scenario 1]
- [Scenario 2]
- [Scenario 3]

**Integration Points**:
- [How this tech integrates with common tools/platforms]

**Common Patterns**:
- [Pattern 1 with canonical reference]
- [Pattern 2 with canonical reference]

**Anti-Patterns to Avoid**:
- [What NOT to do]

---

*Refer to canonical resources for code samples and detailed implementations.*
```

**Requirements:**
- YAML frontmatter at top with required fields (name, description)
- Concise, actionable system prompt (not verbose)
- Minimum 10 official/authoritative URLs
- No code samples in prompt (agent will generate as needed)
- Focus on patterns, best practices, architecture
- Include canonical references for expansion
- Markdown formatted for direct use
- Description field can be lengthy with examples if needed for clarity

## Output Options

**Ask user to choose:**
1. **Clipboard-ready** - Output complete markdown (with YAML frontmatter) in code block
2. **File creation** - Use Write tool to save to `.claude/agents/[platform]-expert.md`
3. **Both** - Create file using Write tool AND show complete content in chat for review

**File Creation Process:**
When creating files programmatically:
1. Generate complete agent content with YAML frontmatter
2. Use Write tool with path: `.claude/agents/[platform-name]-expert.md`
3. Verify file was created successfully
4. Agent is immediately available for use

## Examples

### Example 1: Single Agent
```
User: /agent-genesis
Agent: What technology platform?
User: Redis
Agent: Any specific focus areas? (leave blank for general)
User: caching patterns, pub/sub
Agent: Output format? (1) Clipboard (2) File (3) Both
User: 3
Agent: [Generates Redis expert prompt with caching & pub/sub focus]
```

### Example 2: Batch Generation
```
User: /agent-genesis
Agent: Enter mode: (1) Single (2) Batch (3) Architecture Analysis
User: 2
Agent: Enter platforms (one per line, empty line to finish):
User: PostgreSQL
User: Redis
User: RabbitMQ
User:
Agent: Output format? (1) Clipboard (2) Files (3) Both
User: 2
Agent: [Creates 3 .md files in .claude/agents/]
```

### Example 3: Architecture Analysis
```
User: /agent-genesis
Agent: Enter mode: (1) Single (2) Batch (3) Architecture Analysis
User: 3
Agent: Describe your architecture or provide file path:
User: E-commerce platform: Next.js frontend, Node.js API, PostgreSQL, Redis cache, Stripe payments, AWS S3 storage, SendGrid emails
Agent: Found platforms: Next.js, Node.js, PostgreSQL, Redis, Stripe, AWS S3, SendGrid
Select agents to create:
[ ] nextjs-expert
[ ] nodejs-expert
[ ] postgres-expert
[ ] redis-expert
[ ] stripe-expert
[ ] aws-s3-expert
[ ] sendgrid-expert
User: [Selects via checkbox]
Agent: [Generates selected agents]
```

## Implementation Steps

1. **Prompt for mode** (Single, Batch, Architecture Analysis)

2. **For Single Mode:**
   - Ask for technology platform
   - Ask for focus areas (optional)
   - Generate comprehensive prompt
   - Ask for output format
   - Create file and/or display

3. **For Batch Mode:**
   - Accept multi-line platform list
   - For each platform:
     - Generate expert prompt
     - Save to `.claude/agents/[platform]-expert.md`
   - Report completion with file paths

4. **For Architecture Analysis:**
   - Accept architecture description
   - Parse and identify technologies
   - Present checkbox selector using AskUserQuestion
   - Generate selected agents
   - Save to files

5. **Generate Each Agent Prompt:**
   - Research official docs (WebSearch or WebFetch)
   - Find 10+ authoritative URLs
   - Structure according to template above
   - Focus on patterns and best practices
   - Keep concise (500-800 words)
   - Markdown formatted

6. **Output:**
   - If file: Use Write tool to create `.claude/agents/[platform]-expert.md` with complete YAML frontmatter + system prompt
   - If clipboard: Display complete markdown (including frontmatter) in code block
   - Confirm creation and next steps
   - Remind user agent is immediately available via Task tool

## Quality Checklist

Before outputting each agent prompt, verify:
- ✅ YAML frontmatter present with required fields (name, description)
- ✅ Name uses lowercase-with-hyphens format
- ✅ Description is clear and specific (length is flexible)
- ✅ 10+ authoritative URLs included in system prompt
- ✅ No code samples (agent generates as needed)
- ✅ Concise and scannable system prompt
- ✅ Clear use cases defined
- ✅ Integration points identified
- ✅ Common patterns referenced
- ✅ Anti-patterns listed
- ✅ Proper markdown formatting throughout
- ✅ Filename matches name field: `[name].md`

## Post-Generation

After creating agents, remind user:
1. Review generated prompts
2. Test agent with sample questions
3. Refine based on actual usage
4. Add to version control if satisfied

---

**Execute this command to generate expert agent prompts on demand!**
