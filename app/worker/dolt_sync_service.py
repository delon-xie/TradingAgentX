"""
Dolt数据同步服务
基于DoltProvider的统一数据同步方案
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.core.database import get_mongo_db
from tradingagents.dataflows.providers.china.dolt import DoltProvider

logger = logging.getLogger(__name__)

# 全局单例
_dolt_sync_service = None


class DoltSyncService:
    """
    Dolt数据同步服务
    
    提供基于Dolt数据库的数据同步功能：
    - 历史数据同步
    """
    
    def __init__(self):
        self.provider = None
        self.db = None
        self.batch_size = 50
        self.connected = False
    
    async def initialize(self):
        """初始化同步服务"""
        try:
            # 初始化数据库连接
            self.db = get_mongo_db()
            
            # 初始化Dolt提供器
            self.provider = DoltProvider()
            
            #  连接到 Dolt 数据库
            if not await self.provider.connect():
                raise RuntimeError("❌ Dolt连接失败，无法启动同步服务")
            
            self.connected = True
            logger.info("✅ Dolt同步服务初始化完成")
            
        except Exception as e:
            logger.error(f"❌ Dolt同步服务初始化失败: {e}")
            raise
    
    async def sync_historical_data(
        self,
        start_date: str = None,
        end_date: str = None,
        symbols: List[str] = None,
        incremental: bool = True,
        period: str = "daily"
    ) -> Dict[str, Any]:
        """
        同步历史数据
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            symbols: 指定股票代码列表
            incremental: 是否增量同步
            period: 数据周期 (daily)
            
        Returns:
            同步结果统计
        """
        if not self.connected:
            await self.initialize()
        
        logger.info(f"🔄 开始从 Dolt 同步历史数据...")
        
        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "total_records": 0,
            "start_time": datetime.utcnow(),
            "end_time": None,
            "duration": 0,
            "errors": []
        }
        
        try:
            # 1. 确定日期范围
            if not end_date:
                end_date = datetime.now().strftime('%Y-%m-%d')
            if not start_date:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            
            # 2. 确定要同步的股票列表
            if symbols is None:
                # 如果没有指定，从 stock_basic_info 获取所有股票
                basic_info_cursor = self.db.stock_basic_info.find({}, {"code": 1})
                symbols = [doc["code"] async for doc in basic_info_cursor]
            
            if not symbols:
                logger.warning("⚠️ 没有找到要同步的股票")
                return stats
            
            stats["total_processed"] = len(symbols)
            logger.info(f"📊 准备同步 {len(symbols)} 只股票的历史数据")
            
            # 3. 批量处理
            for i in range(0, len(symbols), self.batch_size):
                batch = symbols[i:i + self.batch_size]
                batch_stats = await self._process_historical_batch(
                    batch, start_date, end_date
                )
                
                stats["success_count"] += batch_stats["success_count"]
                stats["error_count"] += batch_stats["error_count"]
                stats["total_records"] += batch_stats["total_records"]
                stats["errors"].extend(batch_stats["errors"])
                
                logger.info(
                    f"📈 批次 {i//self.batch_size + 1}/{len(symbols)//self.batch_size + 1}: "
                    f"成功 {batch_stats['success_count']} 只，失败 {batch_stats['error_count']} 只"
                )
                
                # 限流
                if i + self.batch_size < len(symbols):
                    await asyncio.sleep(0.1)
            
            # 4. 完成统计
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            
            logger.info(
                f"✅ Dolt历史数据同步完成: "
                f"处理 {stats['total_processed']} 只，成功 {stats['success_count']} 只，"
                f"失败 {stats['error_count']} 只，共 {stats['total_records']} 条记录，"
                f"耗时 {stats['duration']:.2f}秒"
            )
            
        except Exception as e:
            logger.error(f" Dolt历史数据同步失败: {e}")
            stats["errors"].append({
                "error": str(e),
                "context": "sync_historical_data"
            })
        
        return stats
    
    async def _process_historical_batch(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """
        处理一批股票的历史数据
        
        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            批次统计
        """
        stats = {
            "success_count": 0,
            "error_count": 0,
            "total_records": 0,
            "errors": []
        }
        
        for symbol in symbols:
            try:
                # 标准化股票代码（去掉 .SH/.SZ 后缀）
                clean_symbol = symbol.split('.')[0] if '.' in symbol else symbol
                
                logger.info(f"🔍 正在从 Dolt 获取 {symbol} (clean: {clean_symbol}) 的历史数据: {start_date} ~ {end_date}")
                
                # 从 Dolt 获取历史数据
                df = await self.provider.get_historical_data(
                    symbol=clean_symbol,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if df is None or df.empty:
                    logger.warning(f"⚠️ {symbol}: Dolt 未返回数据 (df is None: {df is None}, empty: {df.empty if df is not None else 'N/A'})")
                    stats["error_count"] += 1
                    continue
                
                logger.info(f"✅ {symbol}: Dolt 返回 {len(df)} 条记录，准备写入 MongoDB")
                
                # 写入 MongoDB
                records = await self._save_to_mongodb(clean_symbol, df)
                stats["total_records"] += records
                stats["success_count"] += 1
                
                logger.info(f"✅ {symbol}: 成功同步 {records} 条记录到 MongoDB")
                
            except Exception as e:
                logger.error(f"❌ {symbol}: 同步失败 - {e}", exc_info=True)
                stats["error_count"] += 1
                stats["errors"].append({
                    "symbol": symbol,
                    "error": str(e)
                })
        
        return stats
    
    async def _save_to_mongodb(self, symbol: str, df) -> int:
        """
        将历史数据保存到 MongoDB
        
        Args:
            symbol: 股票代码
            df: 历史数据 DataFrame
            
        Returns:
            保存的记录数
        """
        if df.empty:
            logger.warning(f"⚠️ {symbol}: DataFrame 为空，跳过写入")
            return 0
        
        from datetime import datetime as dt
        
        logger.info(f"💾 {symbol}: 开始转换 {len(df)} 条记录为 MongoDB 格式")
        
        records = []
        for idx, row in df.iterrows():
            # 🔥 获取日期 - 优先从列中获取，其次使用索引
            trade_date = None
            date_from_column = row.get('date') or row.get('trade_date')
            
            if date_from_column is not None:
                # 从列中获取日期
                if hasattr(date_from_column, 'strftime'):
                    trade_date = date_from_column.strftime('%Y-%m-%d')
                else:
                    trade_date = str(date_from_column)[:10]  # 截取前10位 YYYY-MM-DD
            elif hasattr(idx, 'strftime'):
                # 从索引获取日期
                trade_date = idx.strftime('%Y-%m-%d')
            else:
                trade_date = str(idx)[:10]
            
            # 🔥 标准化记录格式（与 historical_data_service 保持一致）
            record = {
                "symbol": symbol,
                "code": symbol,  # 🔥 添加 code 字段
                "full_symbol": f"{symbol}.SH" if symbol.startswith('6') else f"{symbol}.SZ",  # 🔥 根据代码判断市场
                "market": "CN",  # 🔥 A股市场
                "trade_date": trade_date,
                "period": "daily",  # 🔥 添加 period 字段
                "data_source": "dolt",  # 🔥 添加 data_source 字段
                "open": float(row.get('open', 0)),
                "high": float(row.get('high', 0)),
                "low": float(row.get('low', 0)),
                "close": float(row.get('close', 0)),
                "volume": float(row.get('volume', 0)),  # 🔥 改为 float 保持一致
                "amount": float(row.get('amount', 0)),
                "adj_close": float(row.get('adjclose', row.get('close', 0))),
                "pre_close": float(row.get('pre_close', 0)),  # 🔥 添加 pre_close
                "change": float(row.get('change', 0)),  # 🔥 添加 change
                "pct_chg": float(row.get('pct_chg', 0)),  # 🔥 添加 pct_chg
                "turnover_rate": float(row.get('turnover_rate', 0)),  # 🔥 添加换手率
                "created_at": dt.utcnow(),
                "updated_at": dt.utcnow(),
                "version": 1
            }
            records.append(record)
        
        logger.info(f"✅ {symbol}: 已转换 {len(records)} 条记录，开始批量写入 MongoDB")
        
        if records:
            # 🔥 使用 bulk_write 批量更新（提高性能）
            from pymongo import ReplaceOne
            operations = []
            
            for record in records:
                filter_doc = {
                    "symbol": record["symbol"],
                    "trade_date": record["trade_date"],
                    "data_source": record["data_source"],
                    "period": record["period"]
                }
                
                operations.append(ReplaceOne(
                    filter=filter_doc,
                    replacement=record,
                    upsert=True
                ))
            
            # 执行批量写入
            if operations:
                try:
                    result = await self.db.stock_daily_quotes.bulk_write(operations)
                    logger.info(f"✅ {symbol}: 批量写入完成 - matched={result.matched_count}, modified={result.modified_count}, upserted={result.upserted_count}")
                    return len(records)
                except Exception as e:
                    logger.error(f"❌ {symbol}: 批量写入失败 - {e}", exc_info=True)
                    raise
        
        return len(records)
    
    async def sync_realtime_quotes(self, symbols: List[str] = None, force: bool = False) -> Dict[str, Any]:
        """
        同步实时行情（Dolt 不支持实时行情）
        
        Args:
            symbols: 股票代码列表
            force: 强制执行
            
        Returns:
            同步结果
        """
        logger.warning("️ Dolt 不提供实时行情数据，返回空结果")
        return {
            "success_count": 0,
            "error_count": 0,
            "total_records": 0,
            "errors": [],
            "message": "Dolt 仅支持历史数据同步"
        }


async def get_dolt_sync_service() -> DoltSyncService:
    """获取 Dolt 同步服务单例"""
    global _dolt_sync_service
    if _dolt_sync_service is None:
        _dolt_sync_service = DoltSyncService()
        await _dolt_sync_service.initialize()
    return _dolt_sync_service