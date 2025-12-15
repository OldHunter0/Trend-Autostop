# 📈 Trend-Autostop

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/FastAPI-0.109%2B-green)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template)

**摆脱盯盘焦虑，实现"开仓即忘" (Fire and Forget) 的加密货币自动止损管理系统。**

Trend-Autostop 是一个基于 Web 的自动化工具，旨在解决合约交易中的痛点：**手动调整止损线既耗时又容易受情绪影响**。本系统复刻了基于 SuperTrend 的趋势追踪策略，通过后端 Worker 定时监控行情，并根据趋势自动上移（做多）或下移（做空）止损线，锁定利润，保护本金。

---

## ✨ 核心功能

* **🛡️ 智能移动止损 (Trailing Stop)**：基于 ATR 和 SuperTrend 算法，自动计算动态支撑/阻力位，并更新交易所的止损单。
* **🤖 自动化托管**：只需在 Web 界面设置好策略参数，系统全自动运行，无需保持浏览器开启。
* **⚙️ 灵活参数配置**：
  - **Timeframe（时间周期）**：支持 10min / 15min / 30min / 1h / 4h
  - **SL Offset（止损偏移）**：在策略计算的止损线基础上，额外增加价格偏移
  - **Delay Bars（生效延迟）**：开仓后前 N 根 K 线不调整止损，避免过早被扫损
* **🔌 多交易所支持**：底层基于 [CCXT](https://github.com/ccxt/ccxt)，支持 Binance, OKX, Bybit 等主流交易所
* **🔒 资金安全优先**：API Key 采用 AES-256 标准加密存储，**系统绝不请求也不需要"提现"权限**
* **☁️ 云端原生**：专为 Railway 等 PaaS 平台设计，一键部署

---

## 🎯 策略参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| **Timeframe** | 策略计算基于的 K 线级别。每当该级别 K 线收盘时，计算新止损线 | 15min |
| **SL Offset** | 在策略计算的止损价格基础上，额外增加的价格偏移量。做多时向下偏移，做空时向上偏移 | 0 |
| **Delay Bars** | 开仓后前 N 根 K 线内不调整止损，给价格一定的波动空间 | 0 |

### 高级参数 (SuperTrend)

| 参数 | 说明 | 默认值 |
|------|------|--------|
| EMA Length | 基准 EMA 长度 | 8 |
| ATR Length | ATR 计算长度 | 14 |
| Base Multiplier | 基础 ATR 乘数 | 2.0 |
| Vol Lookback | 波动率回溯期 | 20 |
| Trend Lookback | 趋势记忆长度 | 25 |
| Trend Impact | 趋势影响因子 (0-1) | 0.4 |
| Mult Min/Max | 有效乘数范围 | 1.0 / 4.0 |
| Confirm Bars | 翻转确认 K 线数 | 1 |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Web Browser                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Web Server                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Pages UI   │  │  REST API   │  │  Static Files       │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐    ┌─────────────────────────────┐
│   APScheduler Worker    │    │      PostgreSQL Database    │
│  ┌───────────────────┐  │    │  ┌────────────────────────┐ │
│  │ SuperTrend Calc   │  │    │  │ Encrypted API Keys     │ │
│  │ Exchange Service  │  │    │  │ Position Configs       │ │
│  │ Stop Loss Update  │  │    │  │ Operation Logs         │ │
│  └───────────────────┘  │    │  └────────────────────────┘ │
└─────────────────────────┘    └─────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│              Exchange APIs (Binance/OKX/Bybit)              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始 (本地开发)

### 前置要求
* Python 3.10+
* PostgreSQL 数据库
* 交易所 API Key (仅开启**读取**和**合约交易**权限)

### 安装步骤

1. **克隆仓库**
   ```bash
   git clone https://github.com/your-username/Trend-Autostop.git
   cd Trend-Autostop
   ```

2. **创建虚拟环境并安装依赖**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **配置环境变量**
   复制 `env.example` 为 `.env` 并填入配置：
   ```ini
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/trend_autostop
   SECRET_KEY=your_super_secret_key_for_encryption
   ```

4. **运行服务**
   ```bash
   uvicorn app.main:app --reload
   ```
   访问 `http://127.0.0.1:8000` 即可看到操作界面。

---

## 🚄 部署到 Railway

本项目已针对 Railway 进行优化，可实现"零运维"部署。

### 方式一：使用 Railway CLI

```bash
# 安装 Railway CLI
npm install -g @railway/cli

# 登录
railway login

# 初始化项目
railway init

# 添加 PostgreSQL
railway add

# 设置环境变量
railway variables set SECRET_KEY=your_random_secret_key

# 部署
railway up
```

### 方式二：GitHub 集成

1. 将代码推送到 GitHub 仓库
2. 在 Railway 控制台创建新项目，选择 "Deploy from GitHub repo"
3. 选择你的仓库
4. 添加 **PostgreSQL** 插件
5. 在 Settings -> Variables 中添加：
   - `SECRET_KEY`: 生成一个复杂的随机字符串
6. Railway 会自动检测 `Dockerfile` 并构建部署

### 环境变量说明

| 变量 | 必需 | 说明 |
|------|------|------|
| `DATABASE_URL` | ✅ | PostgreSQL 连接 URL (Railway 自动注入) |
| `SECRET_KEY` | ✅ | API Key 加密密钥，请使用强随机字符串 |
| `PORT` | ❌ | 服务端口 (Railway 自动注入) |

---

## 📱 界面预览

### 仪表盘
- 实时查看所有托管仓位状态
- 统计活跃任务、暂停任务数量
- 显示未实现盈亏总计
- 查看最近操作日志

### 仓位管理
- 创建新的托管配置
- 设置策略参数 (Timeframe / SL Offset / Delay)
- 手动调整止损价格
- 暂停/恢复托管任务

### 设置
- 管理交易所 API 账户
- 加密存储 API Key
- 支持测试网模式

---

## 🔧 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/configs` | 获取所有托管配置 |
| POST | `/api/configs` | 创建托管配置 |
| PATCH | `/api/configs/{id}` | 更新托管配置 |
| DELETE | `/api/configs/{id}` | 删除托管配置 |
| POST | `/api/configs/{id}/pause` | 暂停托管 |
| POST | `/api/configs/{id}/resume` | 恢复托管 |
| POST | `/api/configs/{id}/adjust-stop` | 手动调整止损 |
| GET | `/api/credentials` | 获取 API 账户列表 |
| POST | `/api/credentials` | 添加 API 账户 |
| GET | `/api/logs` | 获取操作日志 |
| GET | `/health` | 健康检查 |

---

## ⚠️ 风险免责声明 (Disclaimer)

1. **软件即服务**：本软件仅作为辅助交易工具，**不构成任何投资建议**。
2. **API 权限**：请务必确保您的交易所 API Key **未勾选"提现 (Withdrawal)"权限**。作者不对因 Key 泄露导致的资金损失负责。
3. **算法差异**：虽然我们尽力复刻 TradingView 的算法，但由于数据源和计算精度的细微差异，Python 计算出的止损位可能与 TradingView 图表有极小偏差。
4. **市场风险**：在极端行情下，交易所可能会暂停服务或大幅滑点，导致止损无法按预期价格执行，请注意控制杠杆。

---

## 📁 项目结构

```
Trend-Autostop/
├── app/
│   ├── core/
│   │   ├── config.py        # 应用配置
│   │   ├── database.py      # 数据库连接
│   │   └── security.py      # 加密工具
│   ├── models/
│   │   └── position.py      # 数据库模型
│   ├── routers/
│   │   ├── api.py           # REST API 路由
│   │   └── pages.py         # 页面路由
│   ├── schemas/
│   │   └── position.py      # Pydantic 模型
│   ├── services/
│   │   ├── exchange.py      # 交易所服务
│   │   ├── scheduler.py     # 定时调度器
│   │   └── supertrend.py    # SuperTrend 策略
│   ├── static/
│   │   ├── css/style.css
│   │   └── js/app.js
│   ├── templates/           # Jinja2 模板
│   └── main.py              # 应用入口
├── supertrend.pine          # 原始 Pine Script
├── requirements.txt
├── Dockerfile
├── railway.json
└── README.md
```

---

## 🤝 贡献 (Contributing)

欢迎提交 Pull Request 或 Issue！如果你发现策略计算有误，请务必提供详细的复现步骤和 TradingView 对照截图。

## 📄 License

MIT License
