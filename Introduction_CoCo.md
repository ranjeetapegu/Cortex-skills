# Cortex Code Overview

## What is Cortex Code?

**Cortex Code** (CoCo) is Snowflake's official AI-powered coding assistant CLI. It is purpose-built for the Snowflake ecosystem, running as an interactive terminal REPL that understands your Snowflake environment natively.

### Key Capabilities

- Execute SQL, query Snowflake tables, and manage connections directly from the chat
- Native Snowflake tools: semantic views, dbt, Cortex Analyst, data quality, governance, pipelines (Airflow), ML, and more
- Persistent memory and task tracking across sessions (`cortex ctx`)
- Skills system: domain-specific instruction packs (e.g., `$authoring-dags`, `$machine-learning`)
- MCP integration for extending with external tools
- File editing, bash execution, and code generation in your local repo
- Subagent/team system for parallelizing complex multi-step work
- Hooks for customizing behavior on tool events

---

## How it Differs from Claude Code and ChatGPT Codex

| Dimension | Cortex Code | Claude Code | ChatGPT Codex |
|---|---|---|---|
| **Maker** | Snowflake | Anthropic | OpenAI |
| **Primary focus** | Snowflake data + local code | General software engineering | General code generation |
| **Snowflake integration** | Native (SQL, objects, connections, governance) | None | None |
| **Interface** | Interactive terminal REPL | Terminal REPL | Web / API |
| **Persistent memory** | Yes (`cortex ctx`) | Yes (project memory) | Limited |
| **Skills system** | Domain-specific Snowflake skill packs | No | No |
| **Data tools** | Semantic views, data quality, lineage, governance | None | None |
| **Underlying model** | Claude (Anthropic) via Snowflake | Claude (Anthropic) | GPT-4o / o-series |

---

## Summary

- **Claude Code** and **Cortex Code** are both terminal-based agents built on Claude, but Cortex Code is Snowflake-specific. It has deep integrations for Snowflake objects, SQL execution, data pipelines, governance, and more — all running inside your Snowflake account context.
- **ChatGPT Codex** is OpenAI's general-purpose code model (web/API), with no native data warehouse integration.

Cortex Code is essentially Claude Code + a full Snowflake platform layer — the right tool when your work lives in or around Snowflake.
