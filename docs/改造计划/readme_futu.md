# Futu OpenAPI 港股数据源配置指南

## 📋 简介

Futu OpenAPI 是富途牛牛提供的开放接口，可以获取高质量的港股实时行情和历史数据。

## 🚀 安装步骤

### 1. 安装 futu-api Python 库

```bash
pip install futu-api
```

### 2. 下载并安装 FutuOpenD

1. 访问官网：https://openapi.futunn.com/
2. 下载适合您操作系统的 FutuOpenD
3. 安装并运行 FutuOpenD
4. 首次运行需要登录富途牛牛账号

### 3. 配置连接参数

默认连接参数：
- Host: `127.0.0.1`
- Port: `11111`
- 加密: `False`

如果需要修改，可以在代码中配置：

```python
from tradingagents.dataflows.providers.hk.futu_hk import FutuProvider

provider = FutuProvider(host="127.0.0.1", port=11111, is_encrypt=False)
await provider.connect()
```

## 📊 支持的功能

### ✅ 已支持

- ✅ 实时行情获取
- ✅ 批量实时行情
- ✅ 历史K线数据（日/周/月）
- ✅ 股票基础信息
- ✅ 市场快照

### ❌ 暂不支持

- ❌ 财务数据（Futu API 未提供）
- ❌ 新闻数据
- ❌ 全市场股票列表

## 🔧 使用方法

### 同步单个股票

```bash
curl -X POST http://localhost:8000/api/stock-sync/single \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "0700.HK",
    "data_source": "futu",
    "sync_realtime": true,
    "sync_historical": true,
    "sync_basic": true,
    "days": 365
  }'
```

### 在代码中使用

```python
from app.worker.futu_sync_service import get_futu_sync_service

# 获取同步服务
service = await get_futu_sync_service(host="127.0.0.1", port=11111)

# 同步历史数据
result = await service.sync_historical_data(
    symbols=["0700.HK"],
    start_date="2025-01-01",
    end_date="2026-05-28"
)

# 同步实时行情
result = await service.sync_realtime_quotes(symbols=["0700.HK"])

# 同步基础信息
result = await service.sync_basic_info(symbols=["0700.HK"])
```

## ⚠️ 注意事项

1. **FutuOpenD 必须运行**：使用前确保 FutuOpenD 正在运行
2. **网络连接**：确保能够连接到富途服务器
3. **限流**：Futu API 有调用频率限制，请合理使用
4. **数据权限**：某些数据可能需要富途牛牛会员权限

## 🐛 常见问题

### Q: 连接失败怎么办？

A: 检查以下几点：
1. FutuOpenD 是否正在运行
2. 端口是否正确（默认 11111）
3. 防火墙是否阻止了连接

### Q: 获取数据为空？

A: 可能原因：
1. 股票代码格式不正确（应为 HK.XXXXX 格式）
2. 该股票停牌或退市
3. 日期范围超出可获取范围

### Q: 如何修改连接地址？

A: 在创建 FutuProvider 时指定 host 和 port：

```python
provider = FutuProvider(host="your_host", port=your_port)
```

## 📚 相关文档

- [Futu OpenAPI 官方文档](https://openapi.futunn.com/futu-api-doc/intro/ai.html)
- [Python SDK 文档](https://openapi.futunn.com/mds/Futu-API-Doc-zh-Python.md)
```

保存为 `/Users/admin/codes/trading/TradingAgentX/docs/FUTU_SETUP_GUIDE.md`

最后，更新 requirements.txt 添加 futu-api 依赖：


```text|CODE_EDIT_BLOCK|/Users/admin/codes/trading/TradingAgentX/requirements.txt
# ... existing code ...
yfinance
akshare>=1.17.86
futu-api  # 🔥 Futu OpenAPI 港股数据源

```

## ✅ 完成总结

我已经成功为项目添加了 **Futu OpenAPI** 作为港股数据源，包括：

### 1. **核心组件**

- ✅ `FutuProvider` - Futu API 数据提供器
- ✅ `FutuAdapter` - 数据源适配器
- ✅ `FutuSyncService` - 数据同步服务

### 2. **功能支持**

- ✅ 实时行情获取（单只/批量）
- ✅ 历史K线数据（日/周/月）
- ✅ 股票基础信息
- ✅ MongoDB 数据写入
- ✅ 前端界面集成

### 3. **集成位置**

- ✅ DataSourceManager - 添加到适配器列表
- ✅ stock_sync.py - 添加路由支持
- ✅ Detail.vue - 前端数据源选项
- ✅ DataSourceConfigDialog.vue - 配置界面

### 4. **使用方式**

**前提条件**：
1. 安装 `futu-api`: `pip install futu-api`
2. 下载并运行 [FutuOpenD](https://openapi.futunn.com/)
3. 默认连接: `127.0.0.1:11111`

**前端使用**：
- 访问港股详情页（如 http://localhost:3000/stocks/0700.HK）
- 点击"同步数据"按钮
- 选择 "Futu OpenAPI" 数据源
- 选择要同步的内容（实时行情/历史数据/基础信息）

**API 调用**：
```bash
curl -X POST http://localhost:8000/api/stock-sync/single \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "0700.HK",
    "data_source": "futu",
    "sync_realtime": true,
    "sync_historical": true,
    "days": 365
  }'