# Cortex Code Skills

## What are Skills?

Skills are **reusable instruction sets** that guide Cortex Code for specific tasks. They provide domain-specific context, workflows, and guardrails so the agent behaves correctly for a given domain — without you having to re-explain the context every time.

You invoke a skill with the `$` prefix:

```
$authoring-dags create a new ETL pipeline
$machine-learning train a classification model
```

---

## Where are Skills Stored?

Skills are loaded in **priority order** (first match wins):

| Priority | Location | Path |
|---|---|---|
| 1 | Project | `.cortex/skills/`, `.claude/skills/`, `.snova/skills/` |
| 2 | Global | `~/.snowflake/cortex/skills/` |
| 3 | Remote | Cached from remote GitHub repositories |
| 4 | Bundled | Shipped with Cortex Code installation |

Each skill is a directory with at minimum a `SKILL.md` file:

```
my-skill/
├── SKILL.md          # Required: instructions + frontmatter
├── templates/        # Optional
└── references/       # Optional
```

---

## Why are Skills Needed?

Without skills, you'd have to re-explain complex domain context every session. Skills solve this by:

- **Encoding expert knowledge** — e.g., the `$authoring-dags` skill knows Airflow best practices, DAG patterns, and conventions
- **Reducing prompt length** — agent gets focused instructions instead of a generic system prompt
- **Ensuring consistency** — same workflow every time for a given task type
- **Enabling specialization** — different skill for dbt, ML, governance, Streamlit, etc.

Think of them as **pre-packaged expertise** the agent loads on demand.

---

## How to Make a Skill Public

### 1. Publish to a GitHub Repository

Host skills in a public GitHub repo. Others configure it in `~/.snowflake/cortex/skills.json`:

```json
{
  "remote": [
    {
      "source": "https://github.com/your-org/your-skills-repo",
      "ref": "main",
      "skills": [{ "name": "your-skill-name" }]
    }
  ]
}
```

Cortex Code will fetch and cache it automatically.

### 2. Contribute to Cortex Code (Bundled Skills)

Bundled skills ship with Cortex Code itself and are available to all users. These go through Snowflake's contribution process and become first-class skills like `$machine-learning` or `$data-governance`.

---

## Skill File Structure

```
my-skill/
├── SKILL.md              # Required: main skill file
├── templates/            # Optional: templates
└── references/           # Optional: reference docs
```

### SKILL.md Format

```markdown
---
name: my-skill
description: "Purpose. Use when: situations. Triggers: keywords."
tools: ["bash", "edit"]   # Optional
---

# My Skill

## Workflow
1. Step one
2. Step two

## Stopping Points
- Before file changes: get user approval
- After major phases: confirm results
```

### Frontmatter Fields

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Unique identifier |
| `description` | Yes | Purpose + trigger keywords |
| `tools` | No | Recommended tools for the skill |

---

## Creating a Skill

### Via CLI

```bash
mkdir -p ~/.snowflake/cortex/skills/my-skill
# Then create SKILL.md with frontmatter and instructions
```

### Via Interactive Manager

```
/skill        # Opens skill manager — press 'a' to add a new skill
```

---

## Managing Skills

The `/skill` command opens an interactive manager where you can:

- View all skills by location
- Create new skills (global or project)
- Add skill directories
- Sync project skills to global
- Delete skills
- View skill details and conflicts

---

## Tips

1. Keep skills under 500 lines
2. Include clear stopping points so the agent pauses for user approval
3. Document trigger keywords in the description so the agent auto-loads them
4. Test incrementally as you build
5. Use project-level skills (`.cortex/skills/`) to scope skills to a specific repo
