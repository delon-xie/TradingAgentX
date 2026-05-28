"""
Futu数据源适配器
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .base import DataSourceAdapter
from tradingagents.dataflows.providers.hk.futu_hk import FutuProvider

logger = logging.getLogger(__name__)


class FutuAdapter(DataSourceAdapter):
    """Futu数据源适配器"""

    def __init__(self, host: str = "127.0.0.1", port: int = 11111):
        super().__init__()
        self.provider = None
        self.host = host
        self.port = port

    @property
    def name(self) -> str:
        return "futu"

    def _get_default_priority(self) -> int:
        return 3  # 中等优先级

    def _run_async_safe(self, coro):
        """安全地运行异步协程，兼容 uvloop"""
        import sys
        
        # 检查是否有运行中的事件循环
        try:
            loop = asyncio.get_running_loop()
            
            # 🔥 如果是 uvloop，直接创建新循环（uvloop 不支持 nest_asyncio）
            if 'uvloop' in str(type(loop)):
                logger.debug(f"Futu: 检测到 uvloop，创建新事件循环")
                new_loop = asyncio.new_event_loop()
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()
            
            # 对于其他类型的循环，尝试使用 nest_asyncio
            try:
                import nest_asyncio
                nest_asyncio.apply()
                return asyncio.run(coro)
            except Exception as e:
                logger.warning(f"Futu: nest_asyncio 失败 - {e}，创建新循环")
                new_loop = asyncio.new_event_loop()
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()
            
        except RuntimeError:
            # 没有运行中的循环，可以安全创建
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

    def is_available(self) -> bool:
        """检查Futu是否可用"""
        try:
            # 🔥 直接尝试导入 futu-api，而不是依赖模块级别的标志
            try:
                from futu import OpenQuoteContext
                futu_imported = True
            except ImportError:
                futu_imported = False
                logger.warning("Futu: futu-api 库未安装")
                return False
            
            if self.provider is None:
                self.provider = FutuProvider(host=self.host, port=self.port)
            
            if not self.provider.is_available():
                # 🔥 检查是否有运行中的事件循环
                try:
                    loop = asyncio.get_running_loop()
                    # 如果有运行中的循环，使用 nest_asyncio
                    import nest_asyncio
                    nest_asyncio.apply()
                    connected = asyncio.run(self.provider.connect())
                except RuntimeError:
                    # 没有运行中的循环，创建新循环
                    loop = asyncio.new_event_loop()
                    try:
                        connected = loop.run_until_complete(self.provider.connect())
                    finally:
                        loop.close()
                return connected
            
            return True
        except Exception as e:
            logger.warning(f"Futu 不可用: {e}")
            return False

    def get_stock_list(self) -> Optional[List]:
        logger.debug("Futu: get_stock_list not supported")
        return None

    def get_daily_basic(self, trade_date: str) -> Optional:
        logger.debug(f"Futu: get_daily_basic not supported for {trade_date}")
        return None

    def find_latest_trade_date(self) -> Optional[str]:
        """查找最新交易日期"""
        try:
            # 🔥 直接尝试导入 futu-api
            try:
                from futu import OpenQuoteContext
                futu_imported = True
            except ImportError:
                logger.warning("Futu: futu-api 库未安装")
                return None
            
            if self.provider is None:
                self.provider = FutuProvider(host=self.host, port=self.port)
            
            if not self.provider.is_available():
                # 🔥 检查是否有运行中的事件循环
                try:
                    loop = asyncio.get_running_loop()
                    import nest_asyncio
                    nest_asyncio.apply()
                    asyncio.run(self.provider.connect())
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    try:
                        loop.run_until_complete(self.provider.connect())
                    finally:
                        loop.close()
            
            if not self.provider.is_available():
                return None
            
            return self.provider.find_latest_trade_date()
        except Exception as e:
            logger.error(f"Futu: find_latest_trade_date failed: {e}", exc_info=True)
            return None

    def get_realtime_quotes(self) -> Optional[Dict]:
        logger.debug("Futu: get_realtime_quotes requires specific symbols")
        return None

    def get_kline(self, code: str, period: str = "day", limit: int = 120, adj: Optional[str] = None):
        """从 Futu 获取 K 线数据"""
        if not self.is_available():
            logger.warning("Futu: Provider not available")
            return None
        
        try:
            if self.provider is None:
                self.provider = FutuProvider(host=self.host, port=self.port)
            
            if not self.provider.is_available():
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(self.provider.connect())
                finally:
                    loop.close()
            
            if not self.provider.is_available():
                logger.error("Futu: Connection failed")
                return None
            
            # 标准化代码
            code6 = str(code).zfill(5)  # 港股是5位
            
            # 计算日期范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=limit * 2)
            
            # Futu 只支持日线数据
            if period not in ("day", "week", "month"):
                logger.warning(f"Futu: 不支持的周期 {period}，仅支持 day/week/month")
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
                logger.warning(f"Futu: 未获取到 {code} 的数据")
                return None
            
            # 转换为列表格式
            items = []
            for idx, row in df.tail(limit).iterrows():
                # 从 tradedate 列获取日期
                date_value = row.get('tradedate') or row.get('trade_date') or row.get('date')
                
                if date_value is None:
                    logger.warning(f"Futu: 第 {idx} 行缺少日期数据，跳过")
                    continue
                
                # 格式化日期
                if hasattr(date_value, 'strftime'):
                    date_str = date_value.strftime('%Y-%m-%d')
                elif isinstance(date_value, str):
                    date_str = str(date_value)[:10]
                else:
                    try:
                        import pandas as pd
                        date_str = pd.to_datetime(date_value).strftime('%Y-%m-%d')
                    except:
                        logger.warning(f"Futu: 无法解析日期 {date_value}，跳过")
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
            
            logger.info(f"✅ Futu: 获取到 {code} 的 {len(items)} 条K线数据")
            return items
            
        except Exception as e:
            logger.error(f"❌ Futu: 获取K线失败 {code}: {e}", exc_info=True)
            return None

    def get_news(self, code: str, days: int = 2, limit: int = 50, include_announcements: bool = True):
        logger.debug(f"Futu: get_news not supported for {code}")
        return None