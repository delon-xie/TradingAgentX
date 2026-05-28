"""
Futu 港股数据同步服务
基于FutuProvider的统一数据同步方案
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.core.database import get_mongo_db
from tradingagents.dataflows.providers.hk.futu_hk import FutuProvider

logger = logging.getLogger(__name__)

# 全局单例
_futu_sync_service = None


class FutuSyncService:
    """
    Futu 港股数据同步服务
    
    提供基于 Futu OpenAPI 的港股数据同步功能：
    - 历史数据同步
    - 实时行情同步
    - 基础信息同步
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 11111):
        self.provider = None
        self.db = None
        self.batch_size = 50
        self.connected = False
        self.host = host
        self.port = port
    
    async def initialize(self):
        """初始化同步服务"""
        try:
            # 初始化数据库连接
            self.db = get_mongo_db()
            
            # 初始化 Futu 提供器
            self.provider = FutuProvider(host=self.host, port=self.port)
            
            # 连接到 FutuOpenD
            if not await self.provider.connect():
                raise RuntimeError("❌ Futu OpenAPI 连接失败，无法启动同步服务")
            
            self.connected = True
            logger.info("✅ Futu 港股同步服务初始化完成")
            
        except Exception as e:
            logger.error(f"❌ Futu 港股同步服务初始化失败: {e}")
            raise
    
    async def sync_historical_data(
        self,
        start_date: str = None,
        end_date: str = None,
        symbols: List[str] = None,
        incremental: bool = True,
        period: str = "daily"
    ) -> Dict[str, Any]:
        """同步历史数据"""
        logger.info(f"🔍 sync_historical_data 被调用: symbols={symbols}, start_date={start_date}, end_date={end_date}")
        
        if not self.connected:
            logger.info("🔄 Futu 未连接，正在初始化...")
            await self.initialize()
        
        logger.info(f"🔄 开始从 Futu 同步港股历史数据...")
        
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
            
            logger.info(f"📅 日期范围: {start_date} ~ {end_date}")
            
            # 2. 确定要同步的股票列表
            if symbols is None:
                basic_info_cursor = self.db.stock_basic_info.find(
                    {"market": {"$in": ["HK", "港股"]}},
                    {"code": 1}
                )
                symbols = [doc["code"] async for doc in basic_info_cursor]
            
            if not symbols:
                logger.warning("⚠️ 没有找到要同步的港股股票")
                return stats
            
            stats["total_processed"] = len(symbols)
            logger.info(f"📊 准备同步 {len(symbols)} 只港股股票的历史数据: {symbols[:5]}...")  # 只显示前5个
            
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
                    await asyncio.sleep(1.0)
            
            # 4. 完成统计
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            
            logger.info(
                f"✅ Futu 港股历史数据同步完成: "
                f"处理 {stats['total_processed']} 只，成功 {stats['success_count']} 只，"
                f"失败 {stats['error_count']} 只，共 {stats['total_records']} 条记录，"
                f"耗时 {stats['duration']:.2f}秒"
            )
            
        except Exception as e:
            logger.error(f"❌ Futu 港股历史数据同步失败: {e}")
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
        """处理一批股票的历史数据"""
        stats = {
            "success_count": 0,
            "error_count": 0,
            "total_records": 0,
            "errors": []
        }
        
        for symbol in symbols:
            try:
                # 标准化股票代码（港股格式：0700.HK 或 00700）
                clean_symbol = symbol
                if '.' not in symbol and not symbol.startswith('HK.'):
                    code = symbol.zfill(5)
                    clean_symbol = f"HK.{code}"
                elif '.' in symbol and not symbol.startswith('HK.'):
                    code = symbol.replace('.HK', '').zfill(5)
                    clean_symbol = f"HK.{code}"
                
                logger.info(f"🔍 正在从 Futu 获取 {symbol} (clean: {clean_symbol}) 的历史数据: {start_date} ~ {end_date}")
                
                # 从 Futu 获取历史数据
                df = await self.provider.get_historical_data(
                    symbol=clean_symbol,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if df is None or df.empty:
                    logger.warning(f"⚠️ {symbol}: Futu 未返回数据")
                    stats["error_count"] += 1
                    stats["errors"].append({
                        "symbol": symbol,
                        "error": "Futu 未返回数据",
                        "context": "get_historical_data"
                    })
                    continue
                
                logger.info(f"✅ {symbol}: Futu 返回 {len(df)} 条记录，准备写入 MongoDB")
                
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
        """将历史数据保存到 MongoDB"""
        if df.empty:
            logger.warning(f"⚠️ {symbol}: DataFrame 为空，跳过写入")
            return 0
        
        from datetime import datetime as dt
        
        logger.info(f"💾 {symbol}: 开始转换 {len(df)} 条记录为 MongoDB 格式")
        
        records = []
        for idx, row in df.iterrows():
            # 获取日期
            trade_date = None
            date_from_column = row.get('tradedate') or row.get('trade_date') or row.get('date')
            
            if date_from_column is not None:
                if hasattr(date_from_column, 'strftime'):
                    trade_date = date_from_column.strftime('%Y-%m-%d')
                else:
                    trade_date = str(date_from_column)[:10]
            elif hasattr(idx, 'strftime'):
                trade_date = idx.strftime('%Y-%m-%d')
            else:
                trade_date = str(idx)[:10]
            
            # 标准化记录格式
            code = symbol.replace('HK.', '') if symbol.startswith('HK.') else symbol
            
            record = {
                "symbol": code,
                "code": code,
                "full_symbol": symbol,
                "market": "HK",
                "trade_date": trade_date,
                "period": "daily",
                "data_source": "futu",
                "open": float(row.get('open', 0)),
                "high": float(row.get('high', 0)),
                "low": float(row.get('low', 0)),
                "close": float(row.get('close', 0)),
                "volume": float(row.get('volume', 0)),
                "amount": float(row.get('amount', 0)),
                "adj_close": float(row.get('adjclose', row.get('close', 0))),
                "created_at": dt.utcnow(),
                "updated_at": dt.utcnow(),
                "version": 1
            }
            records.append(record)
        
        logger.info(f"✅ {symbol}: 已转换 {len(records)} 条记录，开始批量写入 MongoDB")
        
        if records:
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
            
            if operations:
                try:
                    result = await self.db.stock_daily_quotes.bulk_write(operations)
                    logger.info(f"✅ {symbol}: 批量写入完成 - matched={result.matched_count}, modified={result.modified_count}, upserted={result.upserted_count}")
                    return len(records)
                except Exception as e:
                    logger.error(f"❌ {symbol}: 批量写入失败 - {e}", exc_info=True)
                    raise
        
        return len(records)
    
    async def sync_realtime_quotes(self, symbols: List[str] = None) -> Dict[str, Any]:
        """同步实时行情"""
        if not self.connected:
            await self.initialize()
        
        logger.info(f"🔄 开始从 Futu 同步港股实时行情...")
        
        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "total_records": 0,
            "errors": []
        }
        
        try:
            if symbols is None or len(symbols) == 0:
                logger.warning("⚠️ 没有指定要同步的股票")
                return stats
            
            stats["total_processed"] = len(symbols)
            
            # 🔥 记录正在处理的股票
            logger.info(f"📊 开始获取 {len(symbols)} 只股票的实时行情: {symbols}")
            
            # 批量获取实时行情
            df = await self.provider.get_realtime_quotes(symbols)
            
            if df is None or df.empty:
                error_msg = f"Futu 未返回实时行情数据（可能原因：FutuOpenD未运行、股票代码格式错误、网络连接问题）"
                logger.warning(f"⚠️ {error_msg}")
                stats["error_count"] = len(symbols)
                stats["errors"].append({
                    "symbols": symbols,
                    "error": error_msg,
                    "context": "get_realtime_quotes_returned_empty"
                })
                return stats
            
            logger.info(f"✅ Futu 返回了 {len(df)} 条行情记录")
            
            # 保存到 MongoDB
            for _, row in df.iterrows():
                try:
                    await self._save_realtime_to_mongodb(row)
                    stats["success_count"] += 1
                    stats["total_records"] += 1
                except Exception as e:
                    logger.error(f"❌ 保存行情失败: {e}")
                    stats["error_count"] += 1
                    stats["errors"].append({
                        "error": str(e),
                        "context": "save_to_mongodb"
                    })
            
            logger.info(
                f"✅ Futu 港股实时行情同步完成: "
                f"处理 {stats['total_processed']} 只，成功 {stats['success_count']} 只"
            )
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"❌ Futu 港股实时行情同步失败: {e}")
            logger.error(f"📋 完整错误堆栈:\n{error_traceback}")
            stats["errors"].append({
                "error": str(e),
                "traceback": error_traceback,
                "context": "sync_realtime_quotes_exception"
            })
        
        return stats
    
    async def _save_realtime_to_mongodb(self, row) -> None:
        """将实时行情保存到 MongoDB"""
        code = row.get('code', '')
        
        doc = {
            "code": code,
            "trade_date": datetime.now().strftime('%Y-%m-%d'),
            "open": float(row.get('open', 0)),
            "high": float(row.get('high', 0)),
            "low": float(row.get('low', 0)),
            "close": float(row.get('close', 0)),
            "volume": float(row.get('volume', 0)),
            "amount": float(row.get('amount', 0)),
            "updated_at": datetime.utcnow(),
            "source": "futu"
        }
        
        await self.db.market_quotes.update_one(
            {"code": code},
            {"$set": doc},
            upsert=True
        )
    
    async def sync_basic_info(self, symbols: List[str] = None) -> Dict[str, Any]:
        """同步基础信息"""
        if not self.connected:
            await self.initialize()
        
        logger.info(f"🔄 开始从 Futu 同步港股基础信息...")
        
        stats = {
            "total_processed": 0,
            "success_count": 0,
            "error_count": 0,
            "errors": []
        }
        
        try:
            if symbols is None or len(symbols) == 0:
                logger.warning("⚠️ 没有指定要同步的股票")
                return stats
            
            stats["total_processed"] = len(symbols)
            
            for symbol in symbols:
                try:
                    clean_symbol = symbol
                    if '.' not in symbol and not symbol.startswith('HK.'):
                        code = symbol.zfill(5)
                        clean_symbol = f"HK.{code}"
                    elif '.' in symbol and not symbol.startswith('HK.'):
                        code = symbol.replace('.HK', '').zfill(5)
                        clean_symbol = f"HK.{code}"
                    
                    logger.info(f"🔍 正在获取 {symbol} 的基础信息...")
                    
                    basic_info = await self.provider.get_stock_basic_info(clean_symbol)
                    
                    if basic_info is None:
                        logger.warning(f"⚠️ {symbol}: 未获取到基础信息")
                        stats["error_count"] += 1
                        continue
                    
                    await self._save_basic_info_to_mongodb(clean_symbol, basic_info)
                    stats["success_count"] += 1
                    
                    logger.info(f"✅ {symbol}: 基础信息同步成功")
                    
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"❌ {symbol}: 基础信息同步失败 - {e}")
                    stats["error_count"] += 1
                    stats["errors"].append({
                        "symbol": symbol,
                        "error": str(e)
                    })
            
            logger.info(
                f"✅ Futu 港股基础信息同步完成: "
                f"处理 {stats['total_processed']} 只，成功 {stats['success_count']} 只，"
                f"失败 {stats['error_count']} 只"
            )
            
        except Exception as e:
            logger.error(f"❌ Futu 港股基础信息同步失败: {e}")
            stats["errors"].append({
                "error": str(e),
                "context": "sync_basic_info"
            })
        
        return stats
    
    async def _save_basic_info_to_mongodb(self, symbol: str, basic_info: Dict[str, Any]) -> None:
        """将基础信息保存到 MongoDB"""
        try:
            code = symbol.replace('HK.', '') if symbol.startswith('HK.') else symbol
            
            doc = {
                "code": code,
                "symbol": code,
                "name": basic_info.get('name', ''),
                "market": "HK",
                "exchange": basic_info.get('exchange', 'Hong Kong Stock Exchange'),
                "currency": basic_info.get('currency', 'HKD'),
                "lot_size": basic_info.get('lot_size', 0),
                "sector": basic_info.get('sector', ''),
                "listing_date": basic_info.get('listing_date', ''),
                "source": "futu",
                "updated_at": datetime.utcnow()
            }
            
            await self.db.stock_basic_info.update_one(
                {"code": code, "source": "futu"},
                {"$set": doc},
                upsert=True
            )
            
            logger.debug(f"💾 {symbol}: 基础信息已保存")
            
        except Exception as e:
            logger.error(f"❌ {symbol}: 保存基础信息失败 - {e}")
            raise


async def get_futu_sync_service(host: str = "127.0.0.1", port: int = 11111) -> FutuSyncService:
    """获取 Futu 港股同步服务单例"""
    global _futu_sync_service
    if _futu_sync_service is None:
        _futu_sync_service = FutuSyncService(host=host, port=port)
        await _futu_sync_service.initialize()
    return _futu_sync_service