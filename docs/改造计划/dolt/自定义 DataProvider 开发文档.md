# 自定义 DataProvider 开发指南

> 本文档详细说明如何在 TradingAgentX 中添加自定义数据源提供器，以 DoltProvider 为例进行完整演示。

文档包含了：
1. ✅ 完整的架构设计说明
2. ✅ 从零开始的开发流程
3. ✅ 前后端代码示例
4. ✅ 常见问题排查（包括您遇到的枚举问题、config_params 初始化问题）
5. ✅ 测试验证清单
6. ✅ 扩展阅读链接

这个文档可以作为团队开发新数据源的标准参考指南！

##  目录

- [概述](#概述)
- [架构设计](#架构设计)
- [完整开发流程](#完整开发流程)
- [前端配置界面开发](#前端配置界面开发)
- [常见问题与解决方案](#常见问题与解决方案)
- [完整示例代码](#完整示例代码)

---

## 概述

TradingAgentX 使用**策略模式**实现数据提供器的可扩展架构。所有数据提供器都继承自 `BaseStockDataProvider` 基类，确保接口统一。

### 核心组件

```
┌─────────────────────────────────────────┐
│         DataRouter (路由层)              │
│  - 管理所有 Provider                     │
│  - 自动选择最佳数据源                     │
──────────────┬──────────────────────────
               │
               ▼
┌─────────────────────────────────────────┐
│    BaseStockDataProvider (抽象基类)      │
│  - 定义统一接口                           │
│  - 提供通用功能                           │
──────────────┬──────────────────────────┘
               │
       ┌───────┴───────┬──────────┐
       ▼               ▼          ▼
  ┌────────┐    ┌──────────┐  ┌──────────┐
  │AkShare │    │  Dolt    │  │ Tushare  │
  │Provider│    │ Provider │  │ Provider │
  └────────┘    └──────────┘  └──────────┘
```

### mermaid图

``` mermaid
graph TD
    A[DataRouter<br/>路由层<br/>管理所有 Provider <br/>自动选择最佳数据源] --> B[BaseStockDataProvider<br/>抽象基类<br/> - 定义统一接口<br/>- 提供通用功能]
    
    B --> C[AkShare<br/>Provider]
    B --> D[Dolt<br/>Provider]
    B --> E[Tushare<br/>Provider]
    
    style A fill:#ffe4c4,stroke:#333
    style B fill:#e6e6fa,stroke:#333
    style C fill:#fffacd,stroke:#333
    style D fill:#fffacd,stroke:#333
    style E fill:#fffacd,stroke:#333
```
---

## 架构设计

### 1. 基类接口定义

所有数据提供器必须实现以下核心方法：

```python
# tradingagents/dataflows/providers/base.py

class BaseStockDataProvider(ABC):
    """数据提供器基类"""
    
    # === 必须实现的抽象方法 ===
    @abstractmethod
    async def get_historical_data(...) -> Optional[pd.DataFrame]:
        """获取历史行情数据"""
        pass
    
    # === 可选实现的虚方法 ===
    async def get_realtime_quotes(...) -> Optional[pd.DataFrame]:
        """获取实时行情（默认返回 None）"""
        return None
    
    async def get_financials(...) -> Optional[pd.DataFrame]:
        """获取财务数据（默认返回 None）"""
        return None
    
    # === 辅助方法 ===
    def _normalize_symbol(self, symbol: str) -> str:
        """标准化股票代码"""
        ...
    
    def _validate_period(self, period: str) -> str:
        """验证时间周期"""
        ...
```

### 2. 数据流路由机制

```python
# tradingagents/dataflows/data_router.py

class DataRouter:
    def __init__(self):
        self.providers = []  # Provider 列表
        self.register(AkShareProvider())
        self.register(DoltProvider())
        # ...
    
    async def get_data(self, symbol, data_type, **kwargs):
        """
        智能数据获取：
        1. 按优先级遍历 Provider
        2. 尝试获取数据
        3. 成功则返回，失败则继续下一个
        """
        for provider in self.providers:
            if provider.is_available:
                data = await provider.get_data(...)
                if data is not None:
                    return data
        return None
```

---

## 完整开发流程

### Step 1: 创建 Provider 类

#### 1.1 文件结构

```
tradingagents/dataflows/providers/china/
├── __init__.py          # 导出 Provider
├── akshare.py           # 现有 Provider
├── baostock.py          # 现有 Provider
└── dolt.py              # 🆕 新建 Provider
```

#### 1.2 核心实现

```python
"""
DoltProvider - 基于 Dolt 数据库的 A 股历史行情数据提供器

特性：
- 只读数据库，数据版本控制
- 支持离线运行
- 高性能 SQL 查询
"""

from typing import Optional, Union
from datetime import date
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from tradingagents.dataflows.providers.base import BaseStockDataProvider
from tradingagents.logger import get_logger

logger = get_logger(__name__)

class DoltProvider(BaseStockDataProvider):
    """Dolt历史行情数据提供器"""
    
    def __init__(self, connection_string: str = None, **db_kwargs):
        """
        初始化 DoltProvider
        
        Args:
            connection_string: 数据库连接字符串
                格式: mysql+pymysql://user:password@host:port/database
                示例: mysql+pymysql://root:@localhost:3306/investment_data
            **db_kwargs: 其他数据库参数
        """
        super().__init__("Dolt")
        
        # 默认连接配置
        self.connection_string = connection_string or \
            "mysql+pymysql://root:@localhost:3306/investment_data"
        
        self.engine: Optional[Engine] = None
        self.connected = False
        
        # 初始化数据库连接
        self._init_connection()
    
    def _init_connection(self):
        """初始化数据库连接"""
        try:
            self.engine = create_engine(
                self.connection_string,
                pool_pre_ping=True,  # 连接前 ping 测试
                pool_recycle=3600,   # 连接回收时间
                connect_args={
                    "connect_timeout": 10
                }
            )
            
            # 测试连接
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            self.connected = True
            logger.info("✅ DoltProvider 数据库连接成功")
            
        except Exception as e:
            self.connected = False
            logger.error(f"❌ DoltProvider 数据库连接失败: {e}")
    
    async def get_historical_data(
        self,
        symbol: str,
        start_date: Union[str, date],
        end_date: Union[str, date] = None,
        **kwargs
    ) -> Optional[pd.DataFrame]:
        """
        获取历史行情数据
        
        Args:
            symbol: 股票代码（如 '600519', '000001.SZ'）
            start_date: 开始日期
            end_date: 结束日期（可选）
            **kwargs: 其他参数
        
        Returns:
            DataFrame with columns:
            - date: 交易日期
            - open: 开盘价
            - high: 最高价
            - low: 最低价
            - close: 收盘价
            - volume: 成交量
            - amount: 成交额
            - adjclose: 复权收盘价
        """
        if not self.is_available:
            logger.warning("⚠️ DoltProvider 不可用")
            return None
        
        try:
            # 1. 标准化股票代码
            clean_symbol = self._normalize_symbol(symbol)
            
            # 2. 转换日期格式
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date) if end_date else pd.Timestamp.today()
            
            # 3. 构建 SQL 查询
            query = text("""
                SELECT 
                    tradedate as date,
                    symbol,
                    `open`,
                    high,
                    low,
                    `close`,
                    volume,
                    amount,
                    adjclose
                FROM final_a_stock_eod_price
                WHERE symbol = :symbol
                  AND tradedate >= :start_date
                  AND tradedate <= :end_date
                ORDER BY tradedate ASC
            """)
            
            # 4. 执行查询
            with self.engine.connect() as conn:
                result = conn.execute(
                    query,
                    {
                        "symbol": clean_symbol,
                        "start_date": start.strftime('%Y-%m-%d'),
                        "end_date": end.strftime('%Y-%m-%d')
                    }
                )
                rows = result.fetchall()
            
            if not rows:
                logger.warning(f"⚠️ Dolt 未找到 {clean_symbol} 的数据")
                return None
            
            # 5. 转换为 DataFrame
            df = pd.DataFrame(rows, columns=result.keys())
            
            # 6. 数据类型转换
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'adjclose']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 7. 设置索引
            df.set_index('date', inplace=True)
            df.index = pd.to_datetime(df.index)
            
            logger.info(f"✅ 从 Dolt 成功获取 {clean_symbol} 的 {len(df)} 条历史数据")
            return df
            
        except SQLAlchemyError as e:
            logger.error(f"❌ Dolt 数据库查询失败 {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Dolt 获取数据失败 {symbol}: {e}", exc_info=True)
            return None
    
    async def get_financials(self, symbol: str, **kwargs) -> Optional[pd.DataFrame]:
        """Dolt 不支持财务数据"""
        logger.warning("⚠️ DoltProvider 不提供财务数据")
        return None
    
    def is_available(self) -> bool:
        """检查 Provider 是否可用"""
        return self.connected and self.engine is not None
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        标准化股票代码
        
        支持格式：
        - '600519' -> '600519'
        - '000001.SZ' -> '000001'
        - '600519.SH' -> '600519'
        """
        if '.' in symbol:
            return symbol.split('.')[0]
        return symbol
```

#### 1.3 注册 Provider

编辑 `tradingagents/dataflows/providers/china/__init__.py`：

```python
"""
中国数据提供器模块
"""

from .akshare import AkShareProvider
from .baostock import BaoStockProvider
from .dolt import DoltProvider  # 🆕 新增

# 检查依赖是否可用
try:
    import akshare
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False

try:
    import baostock
    BAOSTOCK_AVAILABLE = True
except ImportError:
    BAOSTOCK_AVAILABLE = False

# Dolt 依赖 SQLAlchemy
try:
    import sqlalchemy
    DOLT_AVAILABLE = True
except ImportError:
    DOLT_AVAILABLE = False

__all__ = [
    'AkShareProvider',
    'BaoStockProvider',
    'DoltProvider',  # 🆕 导出
    'AKSHARE_AVAILABLE',
    'BAOSTOCK_AVAILABLE',
    'DOLT_AVAILABLE'  # 🆕 标志
]
```

---

### Step 2: 后端配置系统集成

#### 2.1 添加数据源类型枚举

**文件**: `app/models/config.py`

```python
from enum import Enum

class DataSourceType(str, Enum):
    """数据源类型枚举"""
    
    # 中国市场数据源
    TUSHARE = "tushare"
    AKSHARE = "akshare"
    BAOSTOCK = "baostock"
    DOLT = "dolt"  # 🆕 新增
    
    # 港股数据源
    YFINANCE_HK = "yfinance_hk"  # 🆕 新增
    IMPROVED_HK = "improved_hk"  # 🆕 新增
    HK_STOCK = "hk_stock"        # 🆕 新增
    
    # 美股数据源
    FINNHUB = "finnhub"
    YAHOO_FINANCE = "yahoo_finance"
    # ... 其他数据源
    
    # 专业数据源
    WIND = "wind"
    CHOICE = "choice"
    # ...
```

⚠️ **重要**：枚举修改后必须**重启后端服务**才能生效！

#### 2.2 注册数据源信息

**文件**: `tradingagents/constants/data_sources.py`

```python
from enum import Enum
from dataclasses import dataclass
from typing import List

@dataclass
class DataSourceInfo:
    """数据源信息"""
    code: str
    name: str
    display_name: str
    supported_markets: List[str]
    requires_api_key: bool = False
    is_free: bool = True
    features: List[str] = None

class DataSourceCode(str, Enum):
    """数据源编码枚举（必须与 app/models/config.py 同步）"""
    
    # 中国市场
    TUSHARE = "tushare"
    AKSHARE = "akshare"
    BAOSTOCK = "baostock"
    DOLT = "dolt"  # 🆕 新增
    
    # 港股
    YFINANCE_HK = "yfinance_hk"  #  新增
    IMPROVED_HK = "improved_hk"  # 🆕 新增
    HK_STOCK = "hk_stock"        # 🆕 新增
    
    # ... 其他数据源

# 数据源注册表
DATA_SOURCE_REGISTRY = {
    # ... 现有数据源
    
    # 🆕 新增 Dolt
    DataSourceCode.DOLT: DataSourceInfo(
        code="dolt",
        name="Dolt",
        display_name="Dolt 数据库",
        supported_markets=["cn_stocks"],
        requires_api_key=False,  # Dolt 使用数据库连接，不需要 API Key
        is_free=True,
        features=[
            "历史行情",
            "版本控制",
            "离线可用",
            "高性能查询",
            "完全免费"
        ],
    ),
    
    # 🆕 新增港股数据源
    DataSourceCode.YFINANCE_HK: DataSourceInfo(
        code="yfinance_hk",
        name="YFinanceHK",
        display_name="Yahoo Finance 港股",
        supported_markets=["hk_stocks"],
        requires_api_key=False,
        is_free=True,
        features=["历史行情", "实时行情", "港股专注", "完全免费"],
    ),
}
```

#### 2.3 添加连接测试逻辑

**文件**: `app/services/config_service.py`

```python
class ConfigService:
    async def test_data_source_config(self, ds_config: DataSourceConfig) -> dict:
        """
        测试数据源连接
        
        Args:
            ds_config: 数据源配置对象
        
        Returns:
            dict: 测试结果
        """
        ds_type = ds_config.config_params.get('type', ds_config.name)
        
        # ... 其他数据源的测试逻辑
        
        elif ds_type == "dolt":
            # 🆕 Dolt 数据源测试
            try:
                from sqlalchemy import create_engine, text
                
                # 从配置中获取连接参数
                connection_string = ds_config.config_params.get('connection_string', '')
                
                if not connection_string:
                    # 构建连接字符串
                    host = ds_config.config_params.get('host', 'localhost')
                    port = ds_config.config_params.get('port', 3306)
                    database = ds_config.config_params.get('database', 'investment_data')
                    username = ds_config.config_params.get('username', 'root')
                    password = ds_config.config_params.get('password', '')
                    
                    connection_string = f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
                
                # 创建引擎并测试连接
                engine = create_engine(
                    connection_string,
                    connect_args={"connect_timeout": 5}
                )
                
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT 1"))
                    if result.scalar() == 1:
                        return {
                            "success": True,
                            "message": "成功连接到 Dolt 数据源",
                            "data": {
                                "type": "dolt",
                                "connection_string": connection_string,
                                "tested_at": datetime.now().isoformat(),
                                "status": "connected"
                            }
                        }
                        
            except Exception as conn_error:
                error_msg = str(conn_error)
                
                # 根据错误类型返回友好的提示信息
                if "Connection refused" in error_msg:
                    return {
                        "success": False,
                        "message": f"无法连接到 MySQL 服务器\n\n请检查：\n1. MySQL/Dolt 服务是否正在运行\n2. 主机地址和端口是否正确\n3. 防火墙设置\n\n错误详情：{error_msg}",
                        "data": {"type": "dolt", "error": error_msg}
                    }
                elif "Access denied" in error_msg:
                    return {
                        "success": False,
                        "message": f"数据库访问被拒绝\n\n请检查：\n1. 用户名和密码是否正确\n2. 用户是否有权限访问该数据库\n\n错误详情：{error_msg}",
                        "data": {"type": "dolt", "error": error_msg}
                    }
                elif "Unknown database" in error_msg:
                    return {
                        "success": False,
                        "message": f"数据库不存在\n\n请检查：\n1. 数据库名是否正确\n2. 是否已创建数据库\n\n错误详情：{error_msg}",
                        "data": {"type": "dolt", "error": error_msg}
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Dolt 数据源连接失败: {error_msg}",
                        "data": {"type": "dolt", "error": error_msg}
                    }
```

---

### Step 3: 前端配置界面开发

#### 3.1 添加数据源类型选项

**文件**: `frontend/src/views/Settings/components/DataSourceConfigDialog.vue`

```javascript
const dataSourceTypes = [
  // 中国市场数据源
  {
    label: 'Tushare',
    value: 'tushare',
    register_url: 'https://tushare.pro/weborder/#/login?reg=tacn',
    register_guide: '如果您还没有 Tushare 账号，请先注册并获取 Token：'
  },
  {
    label: 'AKShare',
    value: 'akshare',
    register_url: 'https://akshare.akfamily.xyz/',
    register_guide: 'AKShare 是开源免费的金融数据接口库，无需注册即可使用。'
  },
  {
    label: 'Dolt',  // 🆕 新增
    value: 'dolt',
    register_url: 'https://www.dolthub.com/',
    register_guide: 'Dolt 是带版本控制的 SQL 数据库，可以本地部署。查看文档了解如何设置：'
  },
  // ... 其他数据源
]
```

#### 3.2 条件渲染专用表单

```vue
<template>
  <!-- 连接配置 -->
  <el-divider content-position="left">连接配置</el-divider>

  <!--  Dolt 特殊配置 -->
  <template v-if="formData.type === 'dolt'">
    <el-form-item label="主机地址" prop="config_params.host">
      <el-input
        v-model="formData.config_params.host"
        placeholder="localhost"
      />
    </el-form-item>

    <el-form-item label="端口" prop="config_params.port">
      <el-input-number
        v-model="formData.config_params.port"
        :min="1"
        :max="65535"
        controls-position="right"
        style="width: 100%"
      />
    </el-form-item>

    <el-form-item label="数据库名" prop="config_params.database">
      <el-input
        v-model="formData.config_params.database"
        placeholder="investment_data"
      />
    </el-form-item>

    <el-form-item label="用户名" prop="config_params.username">
      <el-input
        v-model="formData.config_params.username"
        placeholder="root"
      />
    </el-form-item>

    <el-form-item label="密码" prop="config_params.password">
      <el-input
        v-model="formData.config_params.password"
        type="password"
        placeholder="留空表示无密码"
        show-password
      />
    </el-form-item>

    <!-- 配置提示 -->
    <el-alert
      title="💡 Dolt 配置提示"
      type="info"
      :closable="false"
      class="mb-4"
    >
      <template #default>
        <div>
          <p>Dolt 是基于 MySQL 的版本控制数据库，需要：</p>
          <ul style="margin: 8px 0; padding-left: 20px;">
            <li>确保 MySQL/Dolt 服务正在运行</li>
            <li>创建数据库：<code>CREATE DATABASE investment_data;</code></li>
            <li>创建表：<code>final_a_stock_eod_price</code></li>
          </ul>
          <p>快速启动（Docker）：</p>
          <code style="display: block; background: #f5f7fa; padding: 8px; margin-top: 8px; border-radius: 4px;">
            docker run -d --name mysql -e MYSQL_ALLOW_EMPTY_PASSWORD=yes -e MYSQL_DATABASE=investment_data -p 3306:3306 mysql:8.0
          </code>
        </div>
      </template>
    </el-alert>
  </template>

  <!-- 标准 API 端点配置（非 Dolt 数据源） -->
  <el-form-item v-else label="API端点" prop="endpoint">
    <el-input
      v-model="formData.endpoint"
      placeholder="请输入API端点URL"
    />
  </el-form-item>
</template>
```

#### 3.3 智能字段显示

```javascript
// 判断是否需要显示 API Key 字段
const needsApiKey = computed(() => {
  const type = formData.value.type?.toLowerCase() || ''
  
  // Dolt 不需要 API Key，使用数据库连接配置
  if (type === 'dolt') return false
  
  // 以下数据源需要 API Key
  const requiresKey = [
    'tushare', 'finnhub', 'alpha_vantage', 'iex_cloud', 
    'wind', 'choice', 'quandl'
  ]
  return requiresKey.includes(type)
})

// 处理数据源类型变化
const handleTypeChange = () => {
  const selectedType = formData.value.type
  
  if (selectedType) {
    formData.value.name = selectedType
    
    // 自动填充显示名称
    if (!formData.value.display_name) {
      const sourceInfo = dataSourceTypes.find(ds => ds.value === selectedType)
      if (sourceInfo) {
        formData.value.display_name = sourceInfo.label
      }
    }
    
    //  根据数据源类型初始化 config_params
    if (selectedType === 'dolt') {
      // Dolt 数据源：初始化数据库连接配置
      formData.value.config_params = {
        host: 'localhost',
        port: 3306,
        database: 'investment_data',
        username: 'root',
        password: ''
      }
      // 清空不需要的字段
      formData.value.api_key = ''
      formData.value.endpoint = ''
      console.log('✅ 已初始化 Dolt 配置参数')
    } else {
      // 其他数据源：清空 config_params
      formData.value.config_params = {}
    }
  }
}
```

#### 3.4 默认表单数据

```javascript
const defaultFormData = {
  name: '',
  display_name: '',
  type: '',
  provider: '',
  api_key: '',
  api_secret: '',
  endpoint: '',
  timeout: 30,
  rate_limit: 100,
  enabled: true,
  priority: 0,
  config_params: {
    // Dolt 默认配置
    host: 'localhost',
    port: 3306,
    database: 'investment_data',
    username: 'root',
    password: ''
  } as Record<string, any>,
  description: '',
  market_categories: [] as string[]
}
```

---

## 常见问题与解决方案

### Q1: 添加新数据源后，前端报错 "Input should be 'mongodb', 'tushare'..."

**原因**: 后端枚举未更新或未重启服务

**解决方案**:
1. 检查 `app/models/config.py` 中的 `DataSourceType` 枚举是否包含新类型
2. 检查 `tradingagents/constants/data_sources.py` 中的 `DataSourceCode` 枚举是否同步
3. **重启后端服务**（必须！枚举值在服务启动时加载）

```bash
# 重启后端服务
docker compose restart backend
# 或
pkill -f "uvicorn app.main:app"
python -m uvicorn app.main:app --reload
```

### Q2: Dolt 连接测试失败 "Can't connect to MySQL server"

**原因**: MySQL/Dolt 服务未启动或配置错误

**解决方案**:

```bash
# 1. 检查 MySQL 是否运行
docker ps | grep mysql
# 或
mysqladmin -u root -p status

# 2. 使用 Docker 快速启动
docker run -d \
  --name mysql \
  -e MYSQL_ALLOW_EMPTY_PASSWORD=yes \
  -e MYSQL_DATABASE=investment_data \
  -p 3306:3306 \
  mysql:8.0

# 3. 创建数据表
docker exec -i mysql mysql -u root investment_data << EOF
CREATE TABLE IF NOT EXISTS final_a_stock_eod_price (
  id INT AUTO_INCREMENT PRIMARY KEY,
  symbol VARCHAR(20) NOT NULL,
  tradedate DATE NOT NULL,
  open DECIMAL(10,2),
  high DECIMAL(10,2),
  low DECIMAL(10,2),
  close DECIMAL(10,2),
  volume BIGINT,
  amount DECIMAL(15,2),
  adjclose DECIMAL(10,2)
);
EOF

# 4. 测试连接
docker exec -i mysql mysql -u root investment_data -e "SELECT 1"
```

### Q3: 前端配置界面显示"自定义参数"而不是专用表单

**原因**: `handleTypeChange` 函数未初始化 `config_params`

**解决方案**: 参考 [Step 3.3](#33-智能字段显示) 中的 `handleTypeChange` 实现

**关键代码**:
```javascript
// 当选择 Dolt 时，必须初始化 config_params
if (selectedType === 'dolt') {
  formData.value.config_params = {
    host: 'localhost',
    port: 3306,
    database: 'investment_data',
    username: 'root',
    password: ''
  }
}
```

### Q4: 编辑模式下配置丢失

**原因**: `watch` 中直接 spread 导致嵌套对象未正确合并

**解决方案**: 深度合并 `config_params`

```javascript
// ❌ 错误写法
formData.value = {
  ...defaultFormData,
  ...config
}

// ✅ 正确写法
formData.value = {
  ...defaultFormData,
  ...config,
  config_params: {
    ...defaultFormData.config_params,  // 先应用默认值
    ...(config.config_params || {})    // 再覆盖传入值
  }
}
```

---

## 完整示例代码

### 文件清单

```
✅ 后端实现
├── tradingagents/dataflows/providers/china/dolt.py          (Provider 核心实现)
├── tradingagents/dataflows/providers/china/__init__.py      (模块导出)
├── app/models/config.py                                     (数据源枚举)
├── tradingagents/constants/data_sources.py                  (数据源注册表)
└── app/services/config_service.py                           (连接测试逻辑)

✅ 前端实现
└── frontend/src/views/Settings/components/DataSourceConfigDialog.vue  (配置界面)
```

### 测试验证清单

- [ ] Provider 类正确实现 `BaseStockDataProvider` 接口
- [ ] `get_historical_data` 方法返回正确格式的 DataFrame
- [ ] 后端枚举 `DataSourceType` 包含新数据源
- [ ] 常量文件 `DataSourceCode` 与后端枚举同步
- [ ] 连接测试方法正确处理新数据源
- [ ] 前端 `dataSourceTypes` 数组包含新数据源
- [ ] 前端条件渲染正确显示专用表单
- [ ] 数据源类型切换时 `config_params` 正确初始化
- [ ] 编辑模式下配置正确加载
- [ ] 后端服务已重启（枚举生效）
- [ ] 数据库连接测试通过

---

## 扩展阅读

- [BaseStockDataProvider 源码](../../../tradingagents/dataflows/providers/base.py)
- [DataRouter 实现](../../../tradingagents/dataflows/data_router.py)
- [配置服务 API](../../../app/services/config_service.py)
- [前端配置组件](../../../frontend/src/views/Settings/components/DataSourceConfigDialog.vue)

---

## 贡献指南

添加新数据源时，请遵循以下步骤：

1. 在 `tradingagents/dataflows/providers/` 下创建 Provider 类
2. 更新后端枚举和注册表（两个文件必须同步）
3. 添加连接测试逻辑
4. 更新前端配置界面
5. 编写单元测试
6. 更新本文档

**重要**: 修改枚举后务必重启后端服务！

---

**最后更新**: 2026-05-27  
**作者**: TradingAgentX Team  
**版本**: v1.0.0