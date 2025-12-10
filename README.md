# 📈 LuxyTrend-AutoStop

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/FastAPI-0.95%2B-green)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new)

**摆脱盯盘焦虑，实现“开仓即忘” (Fire and Forget) 的加密货币自动止损管理系统。**

LuxyTrend-AutoStop 是一个基于 Web 的自动化工具，旨在解决合约交易中的痛点：**手动调整止损线既耗时又容易受情绪影响**。本系统复刻了 TradingView 上流行的 [Luxy Super Duper SuperTrend](https://cn.tradingview.com/script/AcNWmGMV-Luxy-Super-Duper-SuperTrend-Predictor-Engine-and-Buy-Sell-signal/) 策略逻辑，通过后端 Worker 定时监控行情，并根据趋势自动上移（做多）或下移（做空）止损线，锁定利润，保护本金。

---

## ✨ 核心功能

* **🛡️ 智能移动止损 (Trailing Stop)**：基于 ATR 和 SuperTrend 算法，自动计算动态支撑/阻力位，并更新交易所的止损单。
* **🤖 自动化托管**：只需在 Web 界面设置好策略参数（如 ATR 周期、乘数），系统全自动运行，无需保持浏览器开启。
* **🔌 多交易所支持**：底层基于 [CCXT](https://github.com/ccxt/ccxt)，理论支持 Binance, OKX, Bybit 等主流交易所（目前主要适配 Binance Futures）。
* **🔒 资金安全优先**：API Key 采用 AES-256 标准加密存储，**系统绝不请求也不需要“提现”权限**。
* **☁️ 云端原生**：专为 Railway 等 PaaS 平台设计，一键部署，自带数据库集成。
* **📱 响应式 UI**：提供简洁的 Dashboard，随时查看仓位状态和托管日志。

---

## 🏗️ 系统架构

本项目采用 B/S 架构，由 Web 服务端和后台调度器组成：

1.  **Web Server (FastAPI)**: 处理用户请求、API Key 管理、前端页面渲染。
2.  **Scheduler (APScheduler)**: 核心引擎。定期拉取 K 线数据 -> 计算 Python 版 SuperTrend 指标 -> 对比当前止损位 -> 调用交易所 API 修改订单。
3.  **Database (PostgreSQL)**: 存储加密后的 Key、用户配置的任务、操作日志。

---

## 🚀 快速开始 (本地开发)

### 前置要求
* Python 3.10+
* PostgreSQL 数据库
* 交易所 API Key (仅开启**读取**和**合约交易**权限)

### 安装步骤

1.  **克隆仓库**
    ```bash
    git clone [https://github.com/your-username/LuxyTrend-AutoStop.git](https://github.com/your-username/LuxyTrend-AutoStop.git)
    cd LuxyTrend-AutoStop
    ```

2.  **创建虚拟环境并安装依赖**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **配置环境变量**
    复制 `.env.example` 为 `.env` 并填入配置：
    ```ini
    DATABASE_URL=postgresql://user:pass@localhost:5432/luxytrend
    SECRET_KEY=your_super_secret_key_for_encryption
    ALGORITHM=HS256
    ```

4.  **运行服务**
    ```bash
    uvicorn app.main:app --reload
    ```
    访问 `http://127.0.0.1:8000` 即可看到操作界面。

---

## 🚄 部署到 Railway

本项目已针对 Railway 进行优化，可实现“零运维”部署。

1.  点击上方的 **"Deploy on Railway"** 按钮（或手动在 Railway 创建项目）。
2.  在 Railway 项目中添加 **PostgreSQL** 插件。
3.  进入 Settings -> Variables，添加以下环境变量：
    * `SECRET_KEY`: 生成一个复杂的随机字符串（用于加密 API Key）。
    * `PORT`: `8000` (Railway 会自动注入，通常无需手动设，但需确保 Dockerfile 暴露此端口)。
    * `DATABASE_URL`: Railway 会自动注入此变量，**无需手动填写**。
4.  等待构建完成，Railway 会生成一个公网域名，访问即可使用。

---

## 🛠️ 策略参数说明

在托管页面，你可以针对每个仓位设置以下参数：

* **ATR Length (周期)**: 计算波动率的时间窗口，默认 `10`。
* **Factor (乘数)**: 决定止损线与价格的距离。
    * `3.0` - `4.0`: 宽松，适合长线趋势，不易被震荡洗出。
    * `1.0` - `2.0`: 紧凑，适合快速锁利，但容易被打止损。
* **Timeframe (K线周期)**: 建议与你开仓的级别保持一致（如 `15m`, `1h`, `4h`）。

---

## ⚠️ 风险免责声明 (Disclaimer)

1.  **软件即服务**：本软件仅作为辅助交易工具，**不构成任何投资建议**。
2.  **API 权限**：请务必确保您的交易所 API Key **未勾选“提现 (Withdrawal)”权限**。作者不对因 Key 泄露导致的资金损失负责。
3.  **算法差异**：虽然我们尽力复刻 TradingView 的算法，但由于数据源（交易所 K 线数据）和计算精度的细微差异，Python 计算出的止损位可能与 TradingView 图表有极小偏差。
4.  **市场风险**：在极端行情下，交易所可能会暂停服务或大幅滑点，导致止损无法按预期价格执行，请注意控制杠杆。

---

## 🗺️ Roadmap

- [ ] 集成 Telegram Bot 通知（止损移动/触发时发送消息）
- [ ] 支持更多平滑算法 (RMA, EMA, SMA)
- [ ] 增加“分批止盈”功能
- [ ] 增加 Bybit V5 接口支持

## 🤝 贡献 (Contributing)

欢迎提交 Pull Request 或 Issue！如果你发现策略计算有误，请务必提供详细的复现步骤和 TradingView 对照截图。

## 📄 License

MIT License
