"""
Dolt data source adapter
从 Dolt 数据库获取历史行情数据
"""
from typing import Optional, Dict, List
import logging
from datetime import datetime, timedelta
import pandas as pd
import asyncio

from .base import DataSourceAdapter

logger = logging.getLogger(__name__)


class DoltAdapter(DataSourceAdapter):
    """Dolt数据源适配器"""

    def __init__(self):
        super().__init__()
        self.provider = None

    @property
    def name(self) -> str:
        return "dolt"

    def _get_default_priority(self) -> int:
        return 5  # 🔥 高优先级（仅次于 Tushare）

    def is_available(self) -> bool:
        """检查Dolt是否可用"""
        try:
            from tradingagents.dataflows.providers.china.dolt import DoltProvider
            
            if self.provider is None:
                self.provider = DoltProvider()
            
            # 尝试连接
            if not self.provider.is_available():
                loop = asyncio.new_event_loop()
                try:
                    connected = loop.run_until_complete(self.provider.connect())
                    return connected
                finally:
                    loop.close()
            
            return True
        except Exception as e:
            logger.warning(f"Dolt 不可用: {e}")
            return False

    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """获取股票列表（Dolt 不提供此功能）"""
        logger.debug("Dolt: get_stock_list not supported")
        return None

    def get_daily_basic(self, trade_date: str) -> Optional[pd.DataFrame]:
        """
        获取每日基础财务数据（Dolt 不提供此功能）
        
        Args:
            trade_date: 交易日期 (YYYY-MM-DD)
            
        Returns:
            DataFrame 或 None
        """
        logger.debug(f"Dolt: get_daily_basic not supported for {trade_date}")
        return None

    def find_latest_trade_date(self) -> Optional[str]:
        """
        查找最新交易日期
        
        Returns:
            最新交易日期字符串 (YYYY-MM-DD) 或 None
        """
        try:
            if self.provider is None:
                self.provider = None  # 延迟初始化
            
            from tradingagents.dataflows.providers.china.dolt import DoltProvider
            
            if self.provider is None:
                self.provider = DoltProvider()
            
            # 确保已连接
            if not self.provider.is_available():
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(self.provider.connect())
                finally:
                    loop.close()
            
            if not self.provider.is_available():
                logger.error("Dolt: Connection failed")
                return None
            
            # 查询最新的交易日期
            loop = asyncio.new_event_loop()
            try:
                # 使用一个常见股票代码查询最新日期
                df = loop.run_until_complete(
                    self.provider.get_historical_data(
                        symbol="600000",  # 浦发银行作为示例
                        start_date=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
                        end_date=datetime.now().strftime('%Y-%m-%d')
                    )
                )
                
                if df is not None and not df.empty:
                    # 🔥 从 tradedate 列获取最新日期
                    if 'tradedate' in df.columns:
                        latest_date = df['tradedate'].max()
                    elif 'trade_date' in df.columns:
                        latest_date = df['trade_date'].max()
                    elif 'date' in df.columns:
                        latest_date = df['date'].max()
                    else:
                        logger.error(f"Dolt: DataFrame 缺少日期列，可用列: {df.columns.tolist()}")
                        return None
                    
                    if hasattr(latest_date, 'strftime'):
                        return latest_date.strftime('%Y-%m-%d')
                    else:
                        return str(latest_date)[:10]
                else:
                    logger.warning("Dolt: No data found for finding latest trade date")
                    return None
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"Dolt: find_latest_trade_date failed: {e}", exc_info=True)
            return None

    def get_realtime_quotes(self) -> Optional[Dict[str, Dict[str, Optional[float]]]]:
        """
        获取全市场实时快照（Dolt 不提供实时行情）
        
        Returns:
            { '000001': {'close': 10.0, 'pct_chg': 1.2, 'amount': 1.2e8}, ... } 或 None
        """
        logger.debug("Dolt: get_realtime_quotes not supported (no realtime data)")
        return None

    def get_kline(self, code: str, period: str = "day", limit: int = 120, adj: Optional[str] = None):
        """
        从 Dolt 获取 K 线数据
        
        Args:
            code: 股票代码
            period: 周期 (day/week/month/5m/15m/30m/60m)
            limit: 数据条数
            adj: 复权类型 (none/qfq/hfq) - Dolt 不支持复权
            
        Returns:
            K线数据列表
        """
        if not self.is_available():
            logger.warning("Dolt: Provider not available")
            return None
        
        try:
            from tradingagents.dataflows.providers.china.dolt import DoltProvider
            
            # 初始化 Provider
            if self.provider is None:
                self.provider = DoltProvider()
            
            # 确保已连接
            if not self.provider.is_available():
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(self.provider.connect())
                finally:
                    loop.close()
            
            if not self.provider.is_available():
                logger.error("Dolt: Connection failed")
                return None
            
            # 标准化代码
            code6 = str(code).zfill(6)
            
            # 计算日期范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=limit * 2)  # 多获取一些数据
            
            # 🔥 Dolt 只支持日线数据
            if period not in ("day", "week", "month"):
                logger.warning(f"Dolt: 不支持的周期 {period}，仅支持 day/week/month")
                return None
            
            # 获取历史数据
            loop = asyncio.new_event_loop()
            try:
                df = loop.run_until_complete(
                    self.provider.get_historical_data(
                        symbol=code6,
                        start_date=start_date.strftime('%Y-%m-%d'),
                        end_date=end_date.strftime('%Y-%m-%d')
                    )
                )
            finally:
                loop.close()
            
            if df is None or df.empty:
                logger.warning(f"Dolt: 未获取到 {code} 的数据")
                return None
            
            # 🔥 检查是否有 tradedate 列
            if 'tradedate' not in df.columns and 'trade_date' not in df.columns and 'date' not in df.columns:
                logger.error(f"Dolt: DataFrame 缺少日期列，可用列: {df.columns.tolist()}")
                return None
            
            # 转换为列表格式
            items = []
            for idx, row in df.tail(limit).iterrows():
                # 🔥 从列中获取日期，而不是从索引
                date_value = row.get('tradedate') or row.get('trade_date') or row.get('date')
                
                if date_value is None:
                    logger.warning(f"Dolt: 第 {idx} 行缺少日期数据，跳过")
                    continue
                
                # 格式化日期
                if hasattr(date_value, 'strftime'):
                    # datetime 对象
                    date_str = date_value.strftime('%Y-%m-%d')
                elif isinstance(date_value, str):
                    # 字符串，截取前10位
                    date_str = str(date_value)[:10]
                else:
                    # 其他类型，尝试转换
                    try:
                        date_str = pd.to_datetime(date_value).strftime('%Y-%m-%d')
                    except:
                        logger.warning(f"Dolt: 无法解析日期 {date_value}，跳过")
                        continue
                
                items.append({
                    "time": date_str,
                    "open": float(row.get('open', 0)),
                    "high": float(row.get('high', 0)),
                    "low": float(row.get('low', 0)),
                    "close": float(row.get('close', 0)),
                    "volume": float(row.get('volume', 0)),
                    "amount": float(row.get('amount', 0)),
                })
            
            logger.info(f"✅ Dolt: 获取到 {code} 的 {len(items)} 条K线数据")
            return items
            
        except Exception as e:
            logger.error(f"❌ Dolt: 获取K线失败 {code}: {e}", exc_info=True)
            return None

    def get_news(self, code: str, days: int = 2, limit: int = 50, include_announcements: bool = True):
        """
        获取新闻/公告（Dolt 不提供此功能）
        
        Args:
            code: 股票代码
            days: 天数
            limit: 限制数量
            include_announcements: 是否包含公告
            
        Returns:
            [{title, source, time, url, type}] 或 None
        """
        logger.debug(f"Dolt: get_news not supported for {code}")
        return None
