"""
Dolt数据提供器
基于Dolt数据库的investment_data.final_a_stock_eod_price表提供历史行情数据
"""
import logging
from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional, Union
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ..base_provider import BaseStockDataProvider

logger = logging.getLogger(__name__)


class DoltProvider(BaseStockDataProvider):
    """
    Dolt历史行情数据提供器
    
    从Dolt数据库的investment_data.final_a_stock_eod_price表获取A股历史行情数据
    专注于提供高质量的历史行情数据，不支持实时行情和基础信息
    """
    
    def __init__(self, connection_string: str = None, **db_kwargs):
        """
        初始化Dolt数据提供器
        
        Args:
            connection_string: 数据库连接字符串，格式如:
                - mysql+pymysql://user:password@host:port/database
                - mysql://user:password@host:port/database
            **db_kwargs: 其他数据库连接参数
        """
        super().__init__("Dolt")
        
        # 默认连接配置
        self.connection_string = connection_string or "mysql+pymysql://root:@localhost:3310/investment_data"
        self.db_kwargs = db_kwargs
        
        self.engine: Optional[Engine] = None
        self.connected = False
        
        logger.info(f"🔧 DoltProvider 初始化完成，目标数据库: {self.connection_string}")
    
    async def connect(self) -> bool:
        """
        连接到Dolt数据库
        
        Returns:
            bool: 连接是否成功
        """
        try:
            logger.info("🔌 正在连接到Dolt数据库...")
            
            # 创建SQLAlchemy引擎
            engine_kwargs = {
                'pool_size': 5,
                'max_overflow': 10,
                'pool_timeout': 30,
                'pool_recycle': 3600,
                'echo': False,
            }
            engine_kwargs.update(self.db_kwargs)
            
            self.engine = create_engine(self.connection_string, **engine_kwargs)
            
            # 测试连接
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                if result.scalar() == 1:
                    self.connected = True
                    logger.info("✅ Dolt数据库连接成功")
                    return True
                else:
                    logger.error("❌ Dolt数据库连接测试失败")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Dolt数据库连接失败: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """断开Dolt数据库连接"""
        if self.engine:
            try:
                self.engine.dispose()
                logger.info("✅ Dolt数据库连接已断开")
            except Exception as e:
                logger.warning(f"⚠️ 断开Dolt连接时出错: {e}")
            finally:
                self.engine = None
                self.connected = False
        else:
            await super().disconnect()
    
    async def get_stock_basic_info(self, symbol: str = None) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        获取股票基础信息
        
        Note: DoltProvider仅提供历史行情数据，此方法返回None
        如需股票基础信息，请使用AKShare、Tushare等其他数据源
        
        Args:
            symbol: 股票代码
            
        Returns:
            None (Dolt不提供基础信息)
        """
        logger.warning("⚠️ DoltProvider不提供股票基础信息，请使用其他数据源")
        return None
    
    async def get_stock_quotes(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取实时行情
        
        Note: DoltProvider仅提供历史行情数据，此方法返回None
        如需实时行情，请使用AKShare、Tushare等其他数据源
        
        Args:
            symbol: 股票代码
            
        Returns:
            None (Dolt不提供实时行情)
        """
        logger.warning("⚠️ DoltProvider不提供实时行情，请使用其他数据源")
        return None
    
    async def get_historical_data(
        self, 
        symbol: str, 
        start_date: Union[str, date], 
        end_date: Union[str, date] = None
    ) -> Optional[pd.DataFrame]:
        """
        从Dolt数据库获取历史行情数据
        
        Args:
            symbol: 股票代码，支持多种格式:
                - 6位代码: "600519", "000001", "300750"
                - 带后缀: "600519.SH", "000001.SZ", "300750.SZ"
            start_date: 开始日期，支持格式:
                - 字符串: "2024-01-01", "20240101"
                - date对象
            end_date: 结束日期，默认为今天
            
        Returns:
            历史数据DataFrame，包含以下列:
                - tradedate: 交易日期
                - symbol: 股票代码
                - open: 开盘价
                - high: 最高价
                - low: 最低价
                - close: 收盘价
                - adjclose: 复权收盘价
                - volume: 成交量
                - amount: 成交额
        """
        if not self.connected:
            logger.error("❌ Dolt数据库未连接，请先调用connect()")
            return None
        
        try:
            # 标准化股票代码（去除后缀）
            clean_symbol = self._normalize_symbol(symbol)
            
            # 处理日期
            start_date_str = self._format_date_for_query(start_date)
            end_date_str = self._format_date_for_query(end_date) if end_date else datetime.now().strftime('%Y-%m-%d')
            
            logger.info(f"📊 查询Dolt历史数据: symbol={clean_symbol}, start={start_date_str}, end={end_date_str}")
            
            # 构建SQL查询
            query = text("""
                SELECT 
                    tradedate,
                    symbol,
                    `open`,
                    high,
                    low,
                    `close`,
                    adjclose,
                    volume,
                    amount
                FROM final_a_stock_eod_price
                WHERE (symbol = CONCAT('SH', :symbol) OR symbol = CONCAT('SZ', :symbol))
                  AND tradedate >= :start_date
                  AND tradedate <= :end_date
                ORDER BY tradedate ASC
            """)
            
            # 执行查询
            with self.engine.connect() as conn:
                df = pd.read_sql_query(
                    query,
                    conn,
                    params={
                        'symbol': clean_symbol,
                        'start_date': start_date_str,
                        'end_date': end_date_str
                    }
                )
            
            if df.empty:
                logger.warning(f"⚠️ 未找到股票 {clean_symbol} 在 {start_date_str} 至 {end_date_str} 期间的数据")
                return None
            
            # 数据后处理
            df = self._post_process_dataframe(df, symbol)
            
            logger.info(f"✅ 成功获取 {len(df)} 条历史数据记录")
            return df
            
        except Exception as e:
            logger.error(f"❌ 查询Dolt历史数据失败: {e}", exc_info=True)
            return None
    
    async def get_stock_list(self, market: str = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取Dolt数据库中所有股票代码列表
        
        Args:
            market: 市场代码（暂未使用，保留接口兼容性）
            
        Returns:
            股票代码列表，每个元素为 {'symbol': 'xxx'} 字典
        """
        if not self.connected:
            logger.error("❌ Dolt数据库未连接，请先调用connect()")
            return None
        
        try:
            logger.info("📋 查询Dolt数据库中所有股票代码...")
            
            query = text("""
                SELECT DISTINCT symbol
                FROM final_a_stock_eod_price
                ORDER BY symbol ASC
            """)
            
            with self.engine.connect() as conn:
                result = conn.execute(query)
                symbols = [row[0] for row in result.fetchall()]
            
            stock_list = [{'symbol': s} for s in symbols]
            logger.info(f"✅ 成功获取 {len(stock_list)} 个股票代码")
            
            return stock_list
            
        except Exception as e:
            logger.error(f"❌ 查询股票代码列表失败: {e}", exc_info=True)
            return None
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        标准化股票代码，去除交易所后缀
        
        Args:
            symbol: 原始股票代码
            
        Returns:
            标准化后的6位代码
        """
        if not symbol:
            return symbol
        
        # 去除常见的后缀
        symbol = symbol.upper().strip()
        
        # 去除 SH, SZ 等前缀
        for prefix in ['SH', 'SZ']:
            if symbol.startswith(prefix):
                return symbol[:-len(prefix)]
        
        # 去除 .SH, .SZ, .SS 等后缀
        for suffix in ['.SH', '.SZ', '.SS', '.HK']:
            if symbol.endswith(suffix):
                return symbol[:-len(suffix)]
        
        # 如果已经是6位数字，直接返回
        if len(symbol) == 6 and symbol.isdigit():
            return symbol
        
        # 其他情况，尝试提取前6位数字
        import re
        match = re.search(r'(\d{6})', symbol)
        if match:
            return match.group(1)
        
        return symbol
    
    def _format_date_for_query(self, date_value: Union[str, date, datetime]) -> str:
        """
        格式化日期为SQL查询格式 (YYYY-MM-DD)
        
        Args:
            date_value: 日期值
            
        Returns:
            格式化后的日期字符串
        """
        if not date_value:
            return datetime.now().strftime('%Y-%m-%d')
        
        # 如果是date或datetime对象
        if isinstance(date_value, (date, datetime)):
            return date_value.strftime('%Y-%m-%d')
        
        # 如果是字符串
        date_str = str(date_value).strip()
        
        # 处理YYYYMMDD格式
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        
        # 处理YYYY/MM/DD格式
        if '/' in date_str:
            parts = date_str.split('/')
            if len(parts) == 3:
                return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
        
        # 假设已经是YYYY-MM-DD格式或其他可接受格式
        return date_str
    
    def _post_process_dataframe(self, df: pd.DataFrame, original_symbol: str) -> pd.DataFrame:
        """
        对查询结果进行后处理，确保数据格式统一
        
        Args:
            df: 原始DataFrame
            original_symbol: 原始股票代码
            
        Returns:
            处理后的DataFrame
        """
        if df.empty:
            return df
        
        # 确保日期列为datetime类型
        if 'tradedate' in df.columns:
            df['tradedate'] = pd.to_datetime(df['tradedate'])
        
        # 确保数值列为float类型
        numeric_columns = ['open', 'high', 'low', 'close', 'adjclose', 'volume', 'amount']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 添加标准化字段
        df['data_source'] = 'dolt'
        df['data_version'] = 1
        df['updated_at'] = datetime.utcnow()
        
        # 保持原始symbol用于追溯
        df['original_symbol'] = original_symbol
        
        return df
    
    def __repr__(self):
        return f"<DoltProvider(connected={self.connected}, db={self.connection_string})>"