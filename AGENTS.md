# AI Job Intelligence Agent

This project builds a daily AI industry digest for an entry-level AI product manager, AI solution consultant, or AI application developer candidate.

## Output Rules

- Classify source items into `【今日必读】`, `【值得留意】`, and `【可忽略】`.
- Include only major AI product updates, measurable industry deployments, AI hiring or salary trends, and practical AI application development topics in `【今日必读】`.
- Write a title plus a Markdown source link and exactly two Chinese sentences for each must-read item: one core summary and one job-seeker implication.
- List titles with Markdown source links in `【值得留意】`; combine excluded material into one line in `【可忽略】`.
- Use only URLs provided in the source data. Do not place an item without a source URL in `【今日必读】` or `【值得留意】`.
- Keep the complete digest within 500 visible Chinese characters excluding URLs.
- Never fabricate source facts or claim that Feishu delivery succeeded without a confirmed API response.

## Runtime

- Configuration: `config/config.json`
- Raw source drops: `data/inbox`
- Collected source cache: `data/raw`
- Generated digests: `outputs`
- Evening command: `scripts/run_evening.ps1`
- Morning command: `scripts/run_morning.ps1`

The scheduled agent must read `AGENTS.md`, use the configured collectors, generate the digest, save it, and send the exact saved text. If credentials or sources are missing, report the missing item instead of inventing data.
