# LLM Provider Audit

[![CI](https://github.com/benbenlijie/llm-provider-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/benbenlijie/llm-provider-audit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/benbenlijie/llm-provider-audit/blob/main/LICENSE)

`llm-provider-audit` 是一个面向 LLM provider 审计的 CLI 框架，用来判断某个 provider 声称提供的模型，是否真的接近你的参考模型，还是存在偷偷换模、降级、fallback 污染或路由异常。

它不是一个通用 benchmark。它主要回答这个问题：

> 这个 provider 实际返回的模型行为，还是不是它声称的那个模型？

## 适用场景

- 审计第三方中转、代理或聚合路由是否疑似调包
- 对比多个 provider 是否真实接近同一官方模型
- 跟踪某个 provider 是否随时间发生行为漂移
- 为周期性巡检、告警或后续 Web 平台提供结构化证据

## 核心方法

- `reference calibration`：先估计参考 provider 自身的自然波动，避免把正常随机性误判成换模
- `negative controls`：引入已知不同档位或不同代际模型，避免“看起来像 official，实际上也同样像低档模型”
- `fingerprinting`：结合最近邻锚点和 `open_set` 阈值，识别目标是否落在已知分布外
- `JSON + Markdown` 报告：保留聚合分数、每 case 指标、异常样本摘录和最终 verdict

## 快速开始

```bash
uv sync
cp ".env.example" ".env"
mkdir -p "configs/local"
cp "configs/audits/openai-compatible-template.yaml" "configs/local/target-provider.yaml"
uv run llm-provider-audit inspect-router --config "configs/local/target-provider.yaml"
uv run llm-provider-audit run --config "configs/local/target-provider.yaml"
```

先在 `.env` 中填这几个值：

- `MODEL_CHECKER_ROUTER_ROOT`
- `MODEL_CHECKER_ROUTER_ENV_FILE`
- `MODEL_CHECKER_TARGET_BASE_URL`
- `MODEL_CHECKER_TARGET_API_KEY`

CLI 会自动从当前目录及其父目录搜索 `.env`，且不会覆盖已经存在的系统环境变量。

如果你不是在仓库根目录直接执行命令，或希望当前 shell 显式拿到变量，可以再执行：

```bash
set -a
. ".env"
set +a
```

首次公开前，还应检查 `RELEASING.md` 中的发布清单。

## 常用命令

查看配置中的 provider 健康状态：

```bash
uv run llm-provider-audit inspect-router --config "configs/local/target-provider.yaml"
```

执行 reference calibration：

```bash
uv run llm-provider-audit calibrate --config "configs/audits/openai-compatible-template.yaml"
```

执行 reference anchor calibration：

```bash
uv run llm-provider-audit anchor-calibrate --config "configs/audits/openai-compatible-deep-template.yaml"
```

执行一次完整审计：

```bash
uv run llm-provider-audit run --config "configs/local/target-provider.yaml"
```

使用已生成的 reference anchor calibration 修正 `open_set` 阈值后再跑深度审计：

```bash
uv run llm-provider-audit run \
  --config "configs/audits/openai-compatible-deep-template.yaml" \
  --reference-anchor-calibration "artifacts/anchor-calibrations/<run-id>/anchor_calibration.json"
```

根据已有 `run.json` 重新生成 Markdown 报告：

```bash
uv run llm-provider-audit report --run "artifacts/runs/<run-id>"
```

## 配置约定

- `configs/audits/*.yaml` 是可公开提交的模板配置
- `configs/local/` 用来放你的私有、本机可直接运行的配置，这个目录已加入 `.gitignore`
- 公开模板只应包含占位符或环境变量，不应包含真实 endpoint、密钥和本机路径
- 仓库仍保留少量历史样例模板用于研究复现，但首页默认展示的是通用模板

## 报告结论

- `likely_match`：目标 provider 与参考 provider 足够接近
- `suspicious_mismatch`：存在偏离，但证据还不够强
- `strong_mismatch`：多项指标显著偏离，疑似换模型或降级
- `insufficient_evidence`：样本或稳定性不足，无法下结论

Markdown 报告会同时包含：

- 聚合指标
- 每个 case 的相似度、tail probability 和失败率
- 最具代表性的差异样本摘录
- 目标 provider 相对最佳负样本的边距
- `fingerprint` 使用的 `open_set` 阈值及其来源

## 开源注意事项

- 不要把 `configs/local/`、`.env`、`artifacts/runs/`、`artifacts/anchor-calibrations/` 提交到公开仓库
- 如果你新增了 provider，优先先写公共模板，再在本地复制一份做真实接入
- 如果 provider 需要额外 headers 或鉴权方式，优先在模板里保持占位符，不要提交真实值

## 未来路线

- SQLite 历史记录
- Web 报告页
- 定时巡检与告警
- 更强的统计检验和模型指纹能力
