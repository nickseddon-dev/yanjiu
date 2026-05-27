# 加密货币社交情绪预测系统 — 完整开发文档

> 版本 v1.0 | 2026年5月 | 适用对象：一人团队 + AI 代理组织

---

## 一、项目概述

### 1.1 项目目标

本项目旨在构建一套以**加密货币社交情绪为驱动**的量化 Alpha 发现与自动化交易系统。系统从 X（Twitter）、Reddit 和 Polymarket 实时捕获热点事件，经情绪评估与事件因子检验，最终转化为标准化交易信号，并通过跨主机信号发布机制发送到另一台已部署 NautilusTrader 的主机执行实盘交易。[cite:161][cite:163][cite:166]

核心目标定义为三层：
- **研究目标**：从社交热点中提取可量化、可验证、可复现的事件因子。[cite:160]
- **执行目标**：因子验证通过后，通过自动化流水线完成信号发布、下单、风控。[cite:163]
- **平台目标**：研究、执行、风控、监控全部模块化，新增策略/数据源/交易所只需插新模块，不重写系统。[cite:169]

### 1.2 设计原则

- **模块化解耦**：研究、执行、风控严格分层，互不侵入。[cite:163]
- **不重造轮子**：核心复用 NautilusTrader 和 Qlib，只在外围扩展。[web:194][web:28]
- **成本驱动优先**：先免费数据验证，有效后再升级付费源。[web:244][web:243]
- **AI 代理辅助**：AI agent 承担脚手架、测试、文档、监控面板，人力聚焦于架构、策略和风控。[cite:166]
- **渐进上线**：shadow trading → paper trading → 小仓实盘 → 扩仓。[web:251]

---

## 二、系统架构

### 2.1 六层架构总览

```
┌──────────────────────────────────────────────────────┐
│                   Platform Layer                      │
│  Orchestrator / Registry / Scheduler / Dashboard      │
├──────────────────────────────────────────────────────┤
│                    Risk Layer                         │
│  PreTradeGate / Kill Switch / Exposure / Limit Check  │
├──────────────────────────────────────────────────────┤
│                  Execution Layer                      │
│  StrategyExecutor / OrderManager / Venue Router       │
├──────────────────────────────────────────────────────┤
│                  Strategy Layer                       │
│  Event Detector / Alpha Estimator / Position Sizer    │
├──────────────────────────────────────────────────────┤
│                  Research Layer                       │
│  Feature Factory / Label Factory / Backtest / Report  │
├──────────────────────────────────────────────────────┤
│                   Data Layer                          │
│  Market Data / Event Stream / Social / On-chain       │
└──────────────────────────────────────────────────────┘
```

每层向上提供接口，向下消费服务；任一层的内部实现可以替换而不影响其他层。研究/信号主机与实盘执行主机物理分离，研究侧只负责生成和发布信号，不直接访问交易所账户。[cite:163][web:194]

### 2.2 主机职责拆分

系统采用双主机架构：

| 主机 | 职责 | 是否连接交易所 |
|---|---|---|
| 研究/信号主机 | 数据采集、事件处理、特征生成、研究回测、信号发布 | 否 |
| Nautilus 实盘主机 | 接收远端信号、二次风控、订单执行、持仓管理、成交回报 | 是 [web:194] |

这样的拆分可以把交易账户和研究环境隔离开，降低误操作、密钥暴露和实验代码影响实盘的风险。

### 2.2 数据流向

```
X / Reddit / Polymarket / On-chain
        ↓
  Event Gateway（去重、时间对齐、打快照）
        ↓
  Feature Service（情绪评分、热度信号、事件向量）
        ↓
  Research Runner（因子IC、分层收益、容量、成本回测）
        ↓
  Signal Publisher（标准化信号表 / 消息队列 / HTTP webhook）
        ↓
  Remote Execution Gateway（跨主机投递）
        ↓
  NautilusTrader Host（另一台主机的实盘执行层）
        ↓
  Order Manager → Exchange Venue
        ↓
  Risk Control（持续监控、熔断、止损）
        ↓
  Report Generator（每日收益、事件溯源）
```

---

## 三、Monorepo 项目结构

### 3.1 仓库目录

```
quant-os/
├── libs/
│   ├── nautilus_ext/            # fork of NautilusTrader
│   └── qlib_ext/                # fork of Qlib
│
├── packages/
│   ├── common_schema/           # 统一数据结构定义
│   ├── event_schema/            # 事件类型与字段规范
│   ├── feature_registry/        # 特征注册与版本管理
│   ├── model_registry/          # 模型注册、打包、发布
│   ├── risk_rules/              # 风控规则库
│   ├── cost_models/             # 手续费、滑点、冲击成本
│   └── adapters/                # 外部系统适配器
│       ├── exchange/            # 交易所接口
│       ├── social/              # X、Reddit 接口
│       ├── polymarket/          # 预测市场接口
│       └── onchain/             # 链上数据接口
│
├── services/
│   ├── orchestrator/            # 任务调度与编排
│   ├── data_gateway/            # 市场数据统一入口
│   ├── event_gateway/           # 事件流处理与快照
│   ├── feature_service/         # 特征计算服务
│   ├── research_runner/         # 自动化研究流水线
│   ├── signal_publisher/        # 信号发布服务
│   ├── execution_control/       # 入场与仓位决策引擎（研究主机）
│   ├── signal_bridge/           # 跨主机信号投递桥
│   ├── risk_control/            # 研究侧风控服务
│   └── report_generator/        # 报告生成服务
│
├── apps/
│   └── ops_dashboard/           # 运营监控面板
│
├── infra/
│   ├── docker/                  # Dockerfile 集合
│   ├── compose/                 # Docker Compose 文件
│   ├── monitoring/              # Prometheus + Grafana 配置
│   └── ci/                      # GitHub Actions CI
│
└── docs/
    ├── architecture/
    └── runbooks/
```

### 3.2 Fork 策略

| 仓库 | Fork 原则 | 禁止修改 | 可扩展位置 |
|---|---|---|---|
| NautilusTrader | 只在 adapters、risk、replay 外围改 | 核心撮合引擎 | adapters/、risk/、replay/ [web:194] |
| Qlib | 只扩展 data handler、feature、cost、export | workflow 核心逻辑 | contrib/data/、contrib/feature/ [web:28] |

保持 `upstream/main` 分支追踪上游，每月执行一次 `git rebase` 或 `cherry-pick` 同步安全补丁。[web:194][web:28]

---

## 四、核心模块设计

### 4.1 Data Layer

#### 4.1.1 统一接口

所有数据源实现同一接口：

```python
class DataSource(ABC):
    def fetch_ohlcv(self, symbol, interval, start, end) -> pd.DataFrame: ...
    def fetch_orderbook(self, symbol) -> dict: ...
    def fetch_funding_rate(self, symbol) -> pd.DataFrame: ...
    def health_check(self) -> bool: ...
```

#### 4.1.2 推荐数据源

| 层级 | 数据源 | 用途 | 成本 |
|---|---|---|---|
| 核心行情 | 交易所原始 API | 回测与执行 | 免费 [web:243] |
| 行情聚合 | CoinGecko API | 价格、元数据、历史 | 免费/低价 [web:243] |
| 细粒度行情 | AllTick / iTick | 高频、低延迟行情 | 按量付费 [web:234][web:237] |
| 衍生品 | Coinglass | 资金费率、OI、爆仓 | 免费/付费 [web:239] |
| 社交舆情 | X API / Reddit API | 提及量、情绪、热度 | 免费/付费 [web:233] |
| 预测市场 | Polymarket | 事件概率先验 | 免费 [web:43] |
| 链上数据 | 链上公开接口 | 资金流、巨鲸、活跃地址 | 免费/付费 [web:241] |
| 宏观 | 公开宏观 API | 利率、流动性、风险偏好 | 免费 [web:244] |

#### 4.1.3 事件 Schema

```python
@dataclass
class EventSnapshot:
    event_id: str          # UUID
    event_type: str        # SOCIAL_SURGE / POLYMARKET_JUMP / ONCHAIN_INFLOW
    source: str            # X / REDDIT / POLYMARKET / ONCHAIN
    symbol: str            # BTC / ETH / SOL
    timestamp: datetime
    confidence: float      # 0-1
    intensity: float       # 归一化强度
    decay_window_h: int    # 事件影响衰减窗口
    raw_payload: dict      # 原始数据快照
```

### 4.2 Research Layer

#### 4.2.1 特征工厂

特征分五组建立，每组对应不同 alpha 来源：

| 特征组 | 典型特征 | 数据源 |
|---|---|---|
| 热度类 | X 提及量 z-score、Reddit 帖子/评论增速 | X、Reddit [web:233] |
| 情绪类 | 情绪均值、极性偏度、情绪变化率 | NLP 模型 [web:244] |
| 分歧类 | 多空评论比、中立占比 | Reddit、X [web:238] |
| 扩散类 | 跨平台传播速度、热度峰值时间 | X、Reddit [web:238] |
| 预期类 | Polymarket 概率变化、概率跳变幅度 | Polymarket [web:43] |

#### 4.2.2 标签工厂

同一事件生成多个时间窗口的标签，覆盖不同持有期策略：

| 标签 | 定义 |
|---|---|
| ret_1h | 事件后 1 小时收益率 |
| ret_4h | 事件后 4 小时收益率 |
| ret_24h | 事件后 24 小时收益率 |
| vol_spike | 事件后波动是否放大超阈值 |
| volume_spike | 事件后成交量是否放大超阈值 |
| event_realized | 事件是否在 24h 内兑现（分类标签）|

#### 4.2.3 因子检验流程

每个新因子进入系统必须通过以下检验，未达标不允许进入策略层：

1. **IC / RankIC 计算**：单品种和横截面均需检验。
2. **分层收益检验**：10 分位分层，验证单调性。
3. **容量估算**：最大可承载仓位评估。
4. **Regime Split 检验**：牛市/熊市/震荡市分别检验稳定性。[web:244]
5. **成本后收益**：扣除手续费、滑点、资金费率后净收益是否仍为正。[cite:165]
6. **衰减分析**：信号随时间的 IC 衰减曲线。

### 4.3 Strategy Layer

#### 4.3.1 策略分三段

每个事件驱动策略拆成三个子模块；研究主机只负责前两段与执行建议，真正下单由另一台 NautilusTrader 主机完成：

```
EventDetector → AlphaEstimator → ExecutionDecision
    (是否发生)     (方向/强度/置信)     (生成标准化执行建议)
```

分离的好处是研究主机与执行主机职责边界清晰：研究侧负责信号质量，执行侧负责撮合、订单生命周期与交易所连接。[cite:163]

#### 4.3.2 策略 Spec 标准

```python
@dataclass
class StrategySpec:
    strategy_id: str
    version: str
    target_symbols: list[str]
    max_capacity_usd: float       # 策略最大容量
    signal_decay_h: int           # 信号有效期
    entry_conditions: dict        # 入场条件阈值
    exit_conditions: dict         # 出场条件
    max_position_pct: float       # 最大仓位占投资组合比例
    cost_model: str               # 引用 cost_models 中的成本模型
    risk_rules: list[str]         # 引用 risk_rules 中的规则
```

### 4.4 Execution Layer

#### 4.4.1 Entry Decision Engine

研究主机上的 `Entry Decision Engine` 不直接下单，而是把事件、强度、方向、目标仓位和执行约束打包成标准信号，由 `Signal Bridge` 投递到另一台 NautilusTrader 主机。实盘切入不是"抄底"，而是通过 `PreTradeGate` 五项条件逐步确认后分批进场：[web:251][web:252]

```python
class PreTradeGate:
    def evaluate(self, event, market_ctx, portfolio_ctx) -> EntryDecision:
        """
        Returns: NO_TRADE / SMALL_TEST / PARTIAL_ENTER / FULL_ENTER
        """
        checks = [
            self.check_regime(market_ctx),          # 大盘 regime 是否允许
            self.check_event_score(event),           # 事件强度是否达阈值
            self.check_structure(market_ctx),        # 价格结构确认
            self.check_cost(market_ctx),             # 点差/手续费是否可接受
            self.check_risk_budget(portfolio_ctx),   # 风险预算是否充足
        ]
        return self.resolve_decision(checks)
```



#### 4.4.2 Signal Bridge 设计

研究主机与实盘主机之间通过标准信号协议通信，推荐至少支持两种方式：

| 方式 | 说明 | 适用场景 |
|---|---|---|
| HTTP webhook | 研究主机向实盘主机推送 JSON 信号 | 简单直接，便于快速落地 |
| 消息队列（Redis Streams / NATS） | 研究主机发布，实盘主机订阅 | 更适合高可用与重放 |

推荐信号消息格式：

```json
{
  "signal_id": "uuid",
  "strategy_id": "social_event_v1",
  "symbol": "BTCUSDT",
  "side": "BUY",
  "signal_strength": 0.87,
  "target_position_pct": 0.15,
  "entry_mode": "SMALL_TEST",
  "max_slippage_bps": 8,
  "ttl_seconds": 900,
  "created_at": "2026-05-27T16:30:00Z",
  "risk_tags": ["event", "social", "high_vol"]
}
```

信号桥必须具备以下能力：
- 幂等处理：同一 `signal_id` 不重复执行。
- ACK 机制：实盘主机需返回已接收/已拒绝/已执行状态。
- TTL 机制：超时信号自动失效，防止旧信号误下单。
- 重放能力：可用于事后审计与故障恢复。
- 签名校验：跨主机传输必须验签，避免伪造信号。


#### 4.4.3 分层切入逻辑

| 阶段 | 仓位比例 | 条件 |
|---|---|---|
| 第一层（试单） | 10-20% 目标仓位 | 事件触发 + 初步确认 [web:251] |
| 第二层（建仓） | 补到 50-70% | 信号继续确认 + 成交质量良好 [web:252] |
| 第三层（满仓） | 补到 90-100% | 事件强化 + 流动性稳定 + 风险预算充足 [web:259] |

#### 4.4.4 执行内核（位于另一台已部署 NautilusTrader 的主机）

新增以下模块：[web:194][web:199]

```
nautilus_ext/
  adapters/
    social/            # 社交事件流接入
    polymarket/        # 预测市场接入
    onchain/           # 链上数据接入
  risk/
    capacity/          # 容量风控
    exposure/          # 暴露控制
    kill_switch/       # 紧急熔断
  execution/
    venue_router/      # 交易所路由
    smart_order/       # 智能拆单
  replay/
    event_snapshot/    # 事件快照
    hybrid_replay/     # 行情+事件混合回放
```

### 4.5 Risk Layer

研究侧风控与实盘侧风控需要双层存在：研究主机决定“是否值得发信号”，实盘主机决定“是否允许真正下单”。

#### 4.5.1 五维风控

风控必须在信号进入执行层前完成所有检查：

| 维度 | 具体指标 | 操作 |
|---|---|---|
| 单币种风险 | 单币最大仓位 % | 超限拒单 |
| 单叙事风险 | 同一事件叙事最大暴露 | 超限拒单 |
| 单交易所风险 | 单 venue 仓位上限 | 自动分散 |
| 组合波动率 | 实时组合 VaR | 超阈值降仓 |
| 最大回撤 | 日内/月度最大回撤 | 触发 kill switch [web:163] |

#### 4.5.2 Kill Switch 设计

```python
class KillSwitch:
    triggers = [
        ("daily_drawdown", ">", 0.05),     # 日内回撤超 5%
        ("data_source_failure", ">=", 2),   # 2 个以上数据源失联
        ("order_reject_rate", ">", 0.3),    # 拒单率超 30%
        ("exchange_latency_ms", ">", 2000), # 交易所延迟超 2s
    ]
    
    def check(self, state) -> bool:
        for metric, op, threshold in self.triggers:
            if eval(f"{state[metric]} {op} {threshold}"):
                self.fire(reason=metric)
                return True
        return False
```

---

## 五、Fork 改造计划

### 5.1 NautilusTrader fork

**目标**：把实时事件流纳入统一事件驱动框架，支持 market data + event data 混合回放。[web:194][web:199]

改造重点：

- 把"行情事件"扩展为"广义事件"，支持社交、链上和预测市场输入。
- 新增 `EventSnapshotActor`，在 replay 中同步回放历史事件数据。
- 新增 `CapacityRiskEngine`，实时监控各策略容量占用。
- 新增 `VenueRouter`，根据深度、延迟、手续费、资金费率综合评分路由。
- 新增 `ShadowTradingHook`，在 paper trading 模式下并行记录模拟成交。

**禁止修改**：核心 Rust 撮合引擎、事件总线基类、数据类型序列化。[web:194]

### 5.2 Qlib fork

**目标**：把 Qlib 的 workflow 和 experiment manager 适配到加密 24/7 市场和事件驱动研究场景。[web:28][web:226]

改造重点：

- 新增 `CryptoDataHandler`：支持 24/7 市场、非标准开收盘、资金费率等字段。
- 新增 `EventLabelGenerator`：围绕事件生成多窗口标签。
- 新增社交情绪、链上特征和 Polymarket 特征 loader。
- 新增 `CryptoCostModel`：含手续费率、滑点、资金费率、冲击成本。
- 新增 `NautilusSignalExporter`：把 Qlib 输出的信号表转成 Nautilus 可直接消费的格式。

**禁止修改**：recorder 核心 API、workflow 调度逻辑、数据层基类接口。[web:28]

---

## 六、12 个月开发路线

### 第 1 阶段（Month 1-2）：打地基

**核心目标**：统一接口，搭好 monorepo，跑通基础研究任务。[cite:163][cite:165]

交付物：
- `common_schema`、`event_schema`、`feature_registry` 基础版本
- Monorepo 搭建完毕，fork 拉入，CI/CD 配置
- Postgres + Parquet + DuckDB 存储层
- Redis Streams 或 NATS 事件总线
- Prefect 任务编排基础配置
- Docker Compose 部署第一版

资源投入：
- 机器：2 台云机（研究/编排 1 台，执行测试 1 台）[cite:168]
- 人力：你主导架构和 schema，AI agent 负责脚手架和测试
- 算力：CPU 为主，不需要 GPU

### 第 2 阶段（Month 2-4）：跨主机执行链路打通

**核心目标**：让研究主机输出的标准信号可以被另一台已部署 NautilusTrader 的实盘主机稳定消费和执行。[web:194][web:199]

交付物：
- Signal Bridge（Webhook / MQ）
- Signal schema 与签名机制
- ACK / retry / TTL / dead-letter 机制
- Nautilus 侧 signal consumer
- Shadow trading 模式

验收标准：研究主机发出的信号可被实盘主机稳定接收、去重、确认，并在 paper/shadow 模式下完成端到端闭环。[web:199]

### 第 3 阶段（Month 4-6）：Qlib 研究平台升级

**核心目标**：研究流程从 notebook 升级为平台化自动流水线。[web:28][web:226]

交付物：
- CryptoDataHandler
- EventLabelGenerator
- Social/Polymarket/On-chain 特征 loader
- 自动研究报告生成器
- NautilusSignalExporter

验收标准：新事件因子从数据接入到信号输出全流程自动完成，无需手动介入。[web:226][web:40]

### 第 4 阶段（Month 6-9）：执行与风控内核

**核心目标**：打通 signal → order → risk → feedback 全闭环。[cite:163]

交付物：
- PreTradeGate 完整版
- 分层切入逻辑
- Kill Switch + Circuit Breaker
- 多交易所 Venue Router
- Paper trading → 小仓实盘切换

验收标准：系统可在没有人工干预的情况下完成完整的开仓、风控、止损、平仓周期。[web:251][web:259]

### 第 5 阶段（Month 9-12）：平台自动化

**核心目标**：让研究、上线、监控和报告全部自动化。[cite:169][web:184]

交付物：
- 策略注册与版本化
- 模型注册表
- 自动报表与告警
- 一键上线/回滚
- 特征 lineage 追踪
- Ops Dashboard

---

## 七、财务预算

### 7.1 资金分桶

| 资金桶 | 作用 | 原则 |
|---|---|---|
| Core Trading Capital | 实盘交易本金 | 不与系统成本混用 [web:265] |
| Operating Budget | 云、数据、代理、API、监控 | 每月严格上限 [web:261] |
| Growth Budget | 新数据试用、临时算力、实验 | 按因子验证结果决定是否续费 [web:265] |
| Reserve / Runway | 6-12 个月运营储备 | 绝不挪用 [web:262] |

### 7.2 月度运营成本

| 项目 | 最低配 | 标准配 | 扩张配 |
|---|---|---|---|
| 云主机（2-4台） | 200 | 500 | 1200 |
| 存储与数据库 | 20 | 60 | 120 |
| 监控与日志 | 0 | 20 | 50 |
| 数据 API | 0 | 100 | 500 |
| 代理与网络 | 0 | 50 | 200 |
| LLM / AI API | 20 | 100 | 300 |
| 安全与备份 | 0 | 20 | 50 |
| 新数据试用 | 0 | 100 | 300 |
| 临时 GPU | 0 | 200 | 800 |
| **月度合计** | **240** | **1150** | **3520** |

> 所有金额单位：美元（USD）。[web:261][web:265]

### 7.3 成本控制原则

- 当月经营支出 ≤ 当月净利润的 20-40%，或在 Runway 的 1/12 以内。
- 每增加一个数据源必须先能量化其对因子 IC 或 Sharpe 的边际贡献。
- 临时 GPU 只在批量回测或模型训练任务期间按时租用，不长期持有。[web:265][web:266]

---

## 八、数据质量与治理

### 8.1 数据质量五项评估标准

| 标准 | 说明 |
|---|---|
| 完整性 | 缺失率低，历史可回补 [web:243] |
| 时效性 | 时间戳明确，延迟可控 [web:237] |
| 一致性 | 字段定义稳定，口径不随意变化 [web:243] |
| 可复现性 | 同一时间两次拉取结果一致或差异可解释 [web:244] |
| 可交易性 | 能转化成可验证的交易因子，而不仅仅是"有趣" [web:242] |

### 8.2 数据分级

| 等级 | 描述 | 进入研究层条件 |
|---|---|---|
| Level 1 | 完整、时效、已验证 | 直接进入 Feature Registry |
| Level 2 | 有少量缺失，可插值 | 经 QA 脚本处理后进入 |
| Level 3 | 不稳定、口径有问题 | 隔离测试环境，不进入生产 |

---

## 九、开发规范

### 9.1 代码规范

- 每个服务有独立的 `Dockerfile` 和 `requirements.txt` / `pyproject.toml`。
- 所有外部接口通过抽象基类定义，禁止直接在策略层调用第三方库。
- 数据类型定义统一放在 `common_schema`，其他包通过依赖引用。
- 禁止在 fork 内部改动上游核心逻辑，所有扩展必须通过 adapter 或 plugin 方式注入。[web:194][web:28]

### 9.2 分支策略

```
main                   # 生产分支，经过 review 才可合并
develop                # 集成分支
feature/{name}         # 功能开发分支
upstream/main          # 追踪上游 fork 原始分支（只读）
hotfix/{name}          # 紧急修复分支
```

### 9.3 每月维护

- 每月第一周执行 upstream fork 同步（`git rebase upstream/main`）。
- 每月检查数据源连通性和字段口径是否变化。
- 每月检查云成本账单，与预算对比，超支发送告警。[web:261][web:262]

### 9.4 上线流程

```
研究验证通过
   ↓
Shadow Trading（并行模拟，不实际下单）
   ↓
Paper Trading（模拟下单，完整流程验证）
   ↓
小仓实盘（10% 目标仓位，2 周观察期）
   ↓
正常仓位（全量运行）
```

任何阶段出现异常可一键回滚到上一阶段。[web:251][web:259]

---

## 十、里程碑与验收

| 里程碑 | 时间 | 验收标准 |
|---|---|---|
| M1：接口统一 | Month 1 | 所有模块可通过统一接口通信，CI 全绿 |
| M2：事件研究跑通 | Month 2 | 新事件因子自动生成研究报告 |
| M3：Nautilus fork 完成 | Month 4 | 事件驱动回放与 shadow trading 可运行 |
| M4：Qlib 研究平台完成 | Month 6 | 全流程无手动介入自动输出信号 |
| M5：执行风控闭环 | Month 9 | 全自动实盘运行 2 周无重大异常 |
| M6：平台自动化 | Month 12 | 一键上线/回滚，自动报告，策略注册可用 |

---

## 附录：推荐技术栈

| 层次 | 技术选型 | 备注 |
|---|---|---|
| 执行内核 | NautilusTrader（部署在独立实盘主机） | Rust 核心，消费远端信号并负责实盘执行 [web:194] |
| 研究平台 | Qlib（fork） | 工作流、实验管理、recorder [web:28] |
| 任务编排 | Prefect | 轻量，支持调度与依赖管理 [web:265] |
| 关系数据库 | PostgreSQL | 稳定，适合结构化事件和策略数据 [cite:165] |
| 列式存储 | Parquet + DuckDB | 高效回测数据读取 [cite:165] |
| 消息总线 | Redis Streams / NATS | 研究主机发布信号，实盘主机订阅执行 |
| 监控 | Prometheus + Grafana | 指标采集与可视化 [web:261] |
| 实验追踪 | MLflow | 模型与因子实验记录 [web:28] |
| 容器化 | Docker + Docker Compose | 一人团队优先，后期可升级 k3s [cite:162][cite:172] |
| CI/CD | GitHub Actions | 自动测试、lint、部署 |
| 云基础设施 | Hetzner（研究/信号）+ 独立 Nautilus 实盘主机 | 研究与交易账户隔离，降低执行风险 [cite:168] |

