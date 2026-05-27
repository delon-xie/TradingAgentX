# DoltProvider - Dolt历史行情数据提供器

## 概述

DoltProvider 是一个专门用于从 Dolt 数据库获取 A 股历史行情数据的数据提供器。它基于 `investment_data.final_a_stock_eod_price` 表，提供高质量的历史行情数据。

## 特性

- ✅ 专注历史行情数据
- ✅ 支持多种股票代码格式（600519, 600519.SH, 000001.SZ 等）
- ✅ 灵活的日期范围查询
- ✅ 基于 SQLAlchemy 的连接池管理
- ✅ 与 TradingAgentX 其他数据源无缝集成
- ❌ 不提供实时行情（请使用 AKShare/Tushare）
- ❌ 不提供股票基础信息（请使用 AKShare/Tushare）

## 数据表结构

```sql
CREATE TABLE `final_a_stock_eod_price` (
  `tradedate` date NOT NULL,
  `symbol` varchar(100) NOT NULL,
  `high` double NOT NULL,
  `low` double NOT NULL,
  `open` double NOT NULL,
  `close` double NOT NULL,
  `adjclose` double NOT NULL,
  `volume` double NOT NULL,
  `amount` double,
  PRIMARY KEY (`tradedate`,`symbol`),
  KEY `symbol` (`symbol`),
  KEY `symbol_tradedate` (`symbol`,`tradedate`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
```

## 安装依赖

DoltProvider 依赖于 SQLAlchemy 和 PyMySQL：

```bash
pip install sqlalchemy pymysql
```

这些依赖通常已经包含在项目的 requirements.txt 中。

## 快速开始

### 基本用法

```python
import asyncio
from tradingagents.dataflows.providers.china import DoltProvider

async def main():
    # 创建并提供器
    provider = DoltProvider()
    
    # 连接数据库
    await provider.connect()
    
    # 获取历史数据
    df = await provider.get_historical_data(
        symbol="600519",
        start_date="2024-01-01",
        end_date="2024-01-31"
    )
    
    if df is not None:
        print(f"获取到 {len(df)} 条记录")
        print(df.head())
    
    # 断开连接
    await provider.disconnect()

asyncio.run(main())
```

### 自定义数据库连接

```python
# 方式1: 使用自定义连接字符串
provider = DoltProvider(
    connection_string="mysql+pymysql://user:password@host:3306/investment_data"
)

# 方式2: 使用额外连接参数
provider = DoltProvider(
    connection_string="mysql://root:@localhost:3306/investment_data",
    pool_size=10,
    max_overflow=20
)
```

### 与其他数据源集成

```python
from tradingagents.dataflows.providers.china import AKShareProvider, DoltProvider

# Dolt 用于历史数据
dolt = DoltProvider()
await dolt.connect()
hist_data = await dolt.get_historical_data("600519", "2024-01-01", "2024-01-31")

# AKShare 用于实时行情和基础信息
akshare = AKShareProvider()
await akshare.connect()
basic_info = await akshare.get_stock_basic_info("600519")
realtime_quote = await akshare.get_stock_quotes("600519")
```

## API 参考

### 构造函数

```python
DoltProvider(connection_string: str = None, **db_kwargs)
```

**参数:**
- `connection_string`: 数据库连接字符串，默认为 `"mysql+pymysql://root:@localhost:3306/investment_data"`
- `**db_kwargs`: 额外的 SQLAlchemy 引擎参数（如 pool_size, max_overflow 等）

### 主要方法

#### connect()

连接到 Dolt 数据库。

```python
success = await provider.connect()
```

**返回:** `bool` - 连接是否成功

#### disconnect()

断开数据库连接。

```python
await provider.disconnect()
```

#### get_historical_data(symbol, start_date, end_date=None)

获取历史行情数据。

```python
df = await provider.get_historical_data(
    symbol="600519",
    start_date="2024-01-01",
    end_date="2024-01-31"
)
```

**参数:**
- `symbol`: 股票代码，支持 "600519", "600519.SH", "000001.SZ" 等格式
- `start_date`: 开始日期，支持字符串 "2024-01-01" 或 date 对象
- `end_date`: 结束日期，默认为今天

**返回:** `pd.DataFrame` 或 `None`

**DataFrame 列:**
- `tradedate`: 交易日期
- `symbol`: 股票代码
- `open`: 开盘价
- `high`: 最高价
- `low`: 最低价
- `close`: 收盘价
- `adjclose`: 复权收盘价
- `volume`: 成交量
- `amount`: 成交额
- `data_source`: 数据来源标识 ("dolt")
- `data_version`: 数据版本
- `updated_at`: 更新时间

#### get_stock_list(market=None)

获取数据库中所有股票代码列表。

```python
stock_list = await provider.get_stock_list()
```

**返回:** `List[Dict]` - 股票代码列表，每个元素为 `{'symbol': 'xxx'}`

#### get_stock_basic_info(symbol=None)

⚠️ DoltProvider 不提供此功能，返回 `None`。

#### get_stock_quotes(symbol)

⚠️ DoltProvider 不提供此功能，返回 `None`。

## 配置示例

### 开发环境

```python
provider = DoltProvider(
    connection_string="mysql+pymysql://root:@localhost:3306/investment_data"
)
```

### 生产环境

```python
import os

provider = DoltProvider(
    connection_string=os.getenv("DOLT_DB_URL"),
    pool_size=20,
    max_overflow=50,
    pool_recycle=3600
)
```

### Docker 环境

```python
provider = DoltProvider(
    connection_string="mysql+pymysql://user:password@mysql-service:3306/investment_data"
)
```

## 最佳实践

### 1. 使用上下文管理器

```python
async with DoltProvider() as provider:
    df = await provider.get_historical_data("600519", "2024-01-01", "2024-01-31")
```

### 2. 错误处理

```python
try:
    df = await provider.get_historical_data("600519", "2024-01-01")
    if df is None:
        print("未获取到数据")
    else:
        # 处理数据
        pass
except Exception as e:
    print(f"查询失败: {e}")
```

### 3. 批量查询优化

```python
# 避免频繁连接/断开
await provider.connect()

symbols = ["600519", "000001", "300750"]
for symbol in symbols:
    df = await provider.get_historical_data(symbol, "2024-01-01", "2024-01-31")
    # 处理数据

await provider.disconnect()
```

### 4. 日期格式灵活性

```python
# 支持的日期格式
await provider.get_historical_data("600519", "2024-01-01")  # YYYY-MM-DD
await provider.get_historical_data("600519", "20240101")     # YYYYMMDD
await provider.get_historical_data("600519", date(2024, 1, 1))  # date对象
```

## 故障排除

### 连接失败

**问题:** `Dolt数据库连接失败`

**解决方案:**
1. 检查数据库服务是否运行
2. 验证连接字符串是否正确
3. 确认数据库用户权限
4. 检查防火墙设置

```python
# 测试连接
provider = DoltProvider()
success = await provider.connect()
if not success:
    print("请检查数据库配置")
```

### 查询无数据

**问题:** 查询返回 `None` 或空 DataFrame

**解决方案:**
1. 确认股票代码正确（使用6位数字代码）
2. 检查日期范围是否有数据
3. 验证表名是否为 `final_a_stock_eod_price`

```python
# 先获取股票列表确认证票代码存在
stock_list = await provider.get_stock_list()
print([s['symbol'] for s in stock_list[:10]])
```

### 性能问题

**问题:** 查询速度慢

**解决方案:**
1. 确保数据库有适当的索引
2. 调整连接池大小
3. 避免过大的日期范围

```python
# 优化连接池配置
provider = DoltProvider(
    pool_size=10,
    max_overflow=20
)
```

## 与其他 Provider 的对比

| 特性 | Dolt | AKShare | Tushare | Baostock |
|------|------|---------|---------|----------|
| 历史行情 | ✅ | ✅ | ✅ | ✅ |
| 实时行情 | ❌ | ✅ | ✅ | ❌ |
| 基础信息 | ❌ | ✅ | ✅ | ✅ |
| 财务数据 | ❌ | ✅ | ✅ | ❌ |
| 数据质量 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| 速度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| 稳定性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

## 许可证

与 TradingAgentX 项目相同。

## 贡献

欢迎提交 Issue 和 Pull Request！

# dolt 环境搭建

``` shell
# 构建 dolt 环境
cd /datas/dolt
dolt clone chenditc/investment_data
cd investment_data 
dolt pull
dolt schema show
dolt sql-server --host 0.0.0.0 --port 3310 --user root --password root
dolt sql-server --config ./config.yaml
```

# dolt 配置文件
```yaml
# Dolt SQL Server 配置
listener:
  host: 0.0.0.0
  port: 3310        # 自定义端口
  max_connections: 100

# 其他配置...
user: root
password: "root"
```

# 历史行情数据
``` sql
final_a_stock_eod_price @ working
CREATE TABLE `final_a_stock_eod_price` (
  `tradedate` date NOT NULL,
  `symbol` varchar(100) NOT NULL,
  `high` double NOT NULL,
  `low` double NOT NULL,
  `open` double NOT NULL,
  `close` double NOT NULL,
  `adjclose` double NOT NULL,
  `volume` double NOT NULL,
  `amount` double,
  PRIMARY KEY (`tradedate`,`symbol`),
  KEY `symbol` (`symbol`),
  KEY `symbol_tradedate` (`symbol`,`tradedate`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_bin;
```