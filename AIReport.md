# AI Report Specification

This file defines the stable report contract for the local A-share workbench AI analyst feature. The AI must use only the provided structured page content and optional screenshot. Missing, stale, failed, or empty data must be stated explicitly. The report is research commentary only and must not be framed as a trading instruction.

## Output Format

Return a self-contained HTML fragment. Do not include scripts, external assets, forms, or remote CSS. Use semantic headings, compact tables, and dark financial styling compatible with the app preview.

The first screen must contain:

- `{symbol} {name}`
- `评分：0-100`
- `倾向：看多 / 中性 / 看空`
- Core conclusion
- Key invalidation or contrary evidence
- Data timestamps and source limitations

The first heading must follow this exact content pattern:

```html
<h1>{symbol} {name} | 评分：{0-100} | 倾向：看多/中性/看空</h1>
```

## Required Analysis Order

Use these sections in order. Keep sections concise, evidence-backed, and traceable to source fields, URLs, `source`, `fetched_at`, or chart timestamps.

1. 核心结论
2. 行情层
3. 指标层
4. 基础数据
5. 公告层
6. 新闻层
7. 研报层
8. 资金面/筹码层
9. 信号层
10. 期权层
11. 反证与失效条件
12. 数据质量与来源限制

## Indicator Layer Rules

- 指标层必须优先使用 `daily_indicator_context`，而不是只看当前 K 线图上已经勾选的指标。
- 日线指标必须覆盖 `indicator_catalog` 中的全部指标，并参考 `indicator_coverage` 判断字段可用性。
- 对 `status=no_data`、`status=failed` 或缺失字段的指标，必须明确写成“无数据/失败/不可用”，不得补全或推断。
- 如果指标之间互相冲突，必须分别说明趋势、动量、波动率、量能和资金类指标给出的相反证据。

## Scoring Rules

- `看多`: evidence is broadly supportive, with manageable contrary evidence.
- `中性`: evidence is mixed, sparse, stale, or lacks confirmation.
- `看空`: evidence is broadly negative or risk evidence dominates.
- Score must be an integer from 0 to 100.
- Do not infer certainty from missing data. Missing data usually lowers confidence, not automatically the score.

## Evidence Rules

- Prefer structured page content over screenshots.
- Use screenshots only to cross-check layout, visible chart state, and UI context.
- Cite time windows and source freshness where available.
- Include URLs from input rows when discussing news, announcements, or research reports.
- Never invent financial facts, events, analyst views, option data, or source URLs.
- Do not provide unconditional buy, sell, add, reduce, long, or short instructions.
