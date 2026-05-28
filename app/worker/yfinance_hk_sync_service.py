"""
Yahoo Finance 港股数据同步服务
基于YFinanceHKProvider的统一数据同步方案
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.core.database import get_mongo_db
from tradingagents.dataflows.providers.hk.yfinance_hk import YFinanceHKProvider

logger = logging.getLogger(__name__)

# 全局单例
_yfinance_hk_sync_service = None


class YFinanceHKSyncService:
    """
    Yahoo Finance 港股数据同步服务
    
    提供基于 Yahoo Finance 的港股数据同步功能：
    - 历史数据同步
    - 实时行情同步
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
            
            # 初始化 Yahoo Finance 港股提供器
            self.provider = YFinanceHKProvider()
            
            # 🔥 连接到 Yahoo Finance
            if not await self.provider.connect():
                raise RuntimeError("❌ Yahoo Finance 连接失败，无法启动同步服务")
            
            self.connected = True
            logger.info("✅ Yahoo Finance 港股同步服务初始化完成")
            
        except Exception as e:
            logger.error(f"❌ Yahoo Finance 港股同步服务初始化失败: {e}")
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
        
        logger.info(f"🔄 开始从 Yahoo Finance 同步港股历史数据...")
        
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
                # 如果没有指定，从 stock_basic_info 获取港股股票
                basic_info_cursor = self.db.stock_basic_info.find(
                    {"market": {"$in": ["HK", "港股"]}},
                    {"code": 1}
                )
                symbols = [doc["code"] async for doc in basic_info_cursor]
            
            if not symbols:
                logger.warning("⚠️ 没有找到要同步的港股股票")
                return stats
            
            stats["total_processed"] = len(symbols)
            logger.info(f"📊 准备同步 {len(symbols)} 只港股股票的历史数据")
            
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
                
                # 限流（Yahoo Finance 有速率限制）
                if i + self.batch_size < len(symbols):
                    await asyncio.sleep(1.0)
            
            # 4. 完成统计
            stats["end_time"] = datetime.utcnow()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            
            logger.info(
                f"✅ Yahoo Finance 港股历史数据同步完成: "
                f"处理 {stats['total_processed']} 只，成功 {stats['success_count']} 只，"
                f"失败 {stats['error_count']} 只，共 {stats['total_records']} 条记录，"
                f"耗时 {stats['duration']:.2f}秒"
            )
            
        except Exception as e:
            logger.error(f"❌ Yahoo Finance 港股历史数据同步失败: {e}")
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
                # 标准化股票代码（港股格式：0700.HK）
                clean_symbol = symbol
                if '.' not in symbol:
                    # 如果只有代码，添加 .HK 后缀
                    clean_symbol = f"{symbol}.HK"
                
                logger.info(f"🔍 正在从 Yahoo Finance 获取 {symbol} (clean: {clean_symbol}) 的历史数据: {start_date} ~ {end_date}")
                
                # 从 Yahoo Finance 获取历史数据
                df = await self.provider.get_historical_data(
                    symbol=clean_symbol,
                    start_date=start_date,
                    end_date=end_date
                )
                
                if df is None or df.empty:
                    logger.warning(f"⚠️ {symbol}: Yahoo Finance 未返回数据 (df is None: {df is None}, empty: {df.empty if df is not None else 'N/A'})")
                    stats["error_count"] += 1
                    stats["errors"].append({
                        "symbol": symbol,
                        "error": "Yahoo Finance 未返回数据",
                        "context": "get_historical_data"
                    })
                    continue
                
                logger.info(f"✅ {symbol}: Yahoo Finance 返回 {len(df)} 条记录，准备写入 MongoDB")
                
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
            # 🔥 获取日期
            trade_date = None
            date_from_column = row.get('Date') or row.get('date') or row.get('trade_date') or row.get('tradedate')
            
            if date_from_column is not None:
                if hasattr(date_from_column, 'strftime'):
                    trade_date = date_from_column.strftime('%Y-%m-%d')
                else:
                    trade_date = str(date_from_column)[:10]
            elif hasattr(idx, 'strftime'):
                trade_date = idx.strftime('%Y-%m-%d')
            else:
                trade_date = str(idx)[:10]
            
            # 🔥 标准化记录格式
            clean_symbol = symbol.split('.')[0] if '.' in symbol else symbol
            
            record = {
                "symbol": clean_symbol,
                "code": clean_symbol,  # 🔥 添加 code 字段
                "full_symbol": symbol,  # 🔥 保留完整代码（如 0700.HK）
                "market": "HK",  # 🔥 港股市场
                "trade_date": trade_date,
                "period": "daily",  # 🔥 添加 period 字段
                "data_source": "yfinance_hk",  # 🔥 添加 data_source 字段
                "open": float(row.get('Open', row.get('open', 0))),
                "high": float(row.get('High', row.get('high', 0))),
                "low": float(row.get('Low', row.get('low', 0))),
                "close": float(row.get('Close', row.get('close', 0))),
                "volume": float(row.get('Volume', row.get('volume', 0))),
                "amount": float(row.get('amount', 0)),
                "adj_close": float(row.get('Close', row.get('close', 0))),
                "pre_close": float(row.get('Pre Close', 0)),  # 🔥 添加 pre_close
                "change": float(row.get('Change', 0)),  # 🔥 添加 change
                "pct_chg": float(row.get('Pct Change', 0)),  # 🔥 添加 pct_chg
                "created_at": dt.utcnow(),
                "updated_at": dt.utcnow(),
                "version": 1
            }
            records.append(record)
        
        logger.info(f"✅ {symbol}: 已转换 {len(records)} 条记录，开始批量写入 MongoDB")
        
        if records:
            # 🔥 使用 bulk_write 批量更新
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
        同步实时行情
        
        Args:
            symbols: 股票代码列表
            force: 强制执行
            
        Returns:
            同步结果
        """
        if not self.connected:
            await self.initialize()
        
        logger.info(f"🔄 开始从 Yahoo Finance 同步港股实时行情...")
        
        stats = {
            "success_count": 0,
            "error_count": 0,
            "total_records": 0,
            "errors": []
        }
        
        try:
            if symbols is None:
                logger.warning("⚠️ Yahoo Finance 港股实时行情需要指定股票代码列表")
                return stats
            
            for symbol in symbols:
                try:
                    clean_symbol = symbol
                    if '.' not in symbol:
                        clean_symbol = f"{symbol}.HK"
                    
                    # 获取实时行情
                    quote_df = await self.provider.get_realtime_quotes([clean_symbol])
                    
                    if quote_df is None or quote_df.empty:
                        logger.debug(f"⚠️ {symbol}: 未获取到实时行情")
                        stats["error_count"] += 1
                        continue
                    
                    # 保存到 market_quotes 集合
                    await self._save_realtime_to_mongodb(clean_symbol, quote_df)
                    stats["success_count"] += 1
                    stats["total_records"] += 1
                    
                    await asyncio.sleep(0.5)  # 限流
                    
                except Exception as e:
                    logger.error(f"❌ {symbol}: 实时行情同步失败 - {e}")
                    stats["error_count"] += 1
                    stats["errors"].append({
                        "symbol": symbol,
                        "error": str(e)
                    })
            
            logger.info(
                f"✅ Yahoo Finance 港股实时行情同步完成: "
                f"成功 {stats['success_count']} 只，失败 {stats['error_count']} 只"
            )
            
        except Exception as e:
            logger.error(f"❌ Yahoo Finance 港股实时行情同步失败: {e}")
            stats["errors"].append({
                "error": str(e),
                "context": "sync_realtime_quotes"
            })
        
        return stats
    
    async def _save_realtime_to_mongodb(self, symbol: str, df) -> None:
        """
        将实时行情保存到 MongoDB
        
        Args:
            symbol: 股票代码
            df: 行情数据 DataFrame
        """
        if df.empty:
            return
        
        row = df.iloc[0]
        doc = {
            "code": symbol.split('.')[0] if '.' in symbol else symbol,
            "trade_date": datetime.now().strftime('%Y-%m-%d'),
            "open": float(row.get('Open', 0)),
            "high": float(row.get('High', 0)),
            "low": float(row.get('Low', 0)),
            "close": float(row.get('Close', 0)),
            "volume": int(row.get('Volume', 0)),
            "updated_at": datetime.utcnow(),
            "source": "yfinance_hk"
        }
        
        await self.db.market_quotes.update_one(
            {"code": doc["code"]},
            {"$set": doc},
            upsert=True
        )
    
    async def sync_basic_info(self, symbols: List[str] = None) -> Dict[str, Any]:
        """
        同步股票基础信息
        
        Args:
            symbols: 股票代码列表
            
        Returns:
            同步结果统计
        """
        if not self.connected:
            await self.initialize()
        
        logger.info(f"🔄 开始从 Yahoo Finance 同步港股基础信息...")
        
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
                    # 标准化股票代码
                    clean_symbol = symbol
                    if '.' not in symbol:
                        clean_symbol = f"{symbol}.HK"
                    
                    logger.info(f"🔍 正在获取 {symbol} 的基础信息...")
                    
                    # 从 Yahoo Finance 获取基础信息
                    basic_info = await self.provider.get_stock_basic_info(clean_symbol)
                    
                    if basic_info is None:
                        logger.warning(f"⚠️ {symbol}: 未获取到基础信息")
                        stats["error_count"] += 1
                        continue
                    
                    # 保存到 MongoDB
                    await self._save_basic_info_to_mongodb(clean_symbol, basic_info)
                    stats["success_count"] += 1
                    
                    logger.info(f"✅ {symbol}: 基础信息同步成功")
                    
                    # 限流
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"❌ {symbol}: 基础信息同步失败 - {e}")
                    stats["error_count"] += 1
                    stats["errors"].append({
                        "symbol": symbol,
                        "error": str(e)
                    })
            
            logger.info(
                f"✅ Yahoo Finance 港股基础信息同步完成: "
                f"处理 {stats['total_processed']} 只，成功 {stats['success_count']} 只，"
                f"失败 {stats['error_count']} 只"
            )
            
        except Exception as e:
            logger.error(f"❌ Yahoo Finance 港股基础信息同步失败: {e}")
            stats["errors"].append({
                "error": str(e),
                "context": "sync_basic_info"
            })
        
        return stats
    
    async def _save_basic_info_to_mongodb(self, symbol: str, basic_info: Dict[str, Any]) -> None:
        """
        将基础信息保存到 MongoDB
        
        Args:
            symbol: 股票代码
            basic_info: 基础信息字典
        """
        try:
            # 提取代码（去掉 .HK 后缀）
            code = symbol.split('.')[0] if '.' in symbol else symbol
            
            # 构建文档
            doc = {
                "code": code,
                "symbol": code,
                "name": basic_info.get('shortName') or basic_info.get('longName', ''),
                "market": "HK",
                "exchange": "Hong Kong Stock Exchange",
                "currency": basic_info.get('currency', 'HKD'),
                "sector": basic_info.get('sector', ''),
                "industry": basic_info.get('industry', ''),
                "website": basic_info.get('website', ''),
                "description": basic_info.get('longBusinessSummary', ''),
                "employees": basic_info.get('fullTimeEmployees', 0),
                "source": "yfinance_hk",
                "updated_at": datetime.utcnow()
            }
            
            # 添加到 stock_basic_info 集合
            await self.db.stock_basic_info.update_one(
                {"code": code, "source": "yfinance_hk"},
                {"$set": doc},
                upsert=True
            )
            
            logger.debug(f"💾 {symbol}: 基础信息已保存")
            
        except Exception as e:
            logger.error(f"❌ {symbol}: 保存基础信息失败 - {e}")
            raise
    
    async def sync_financial_data(self, symbols: List[str] = None, report_type: str = "annual") -> Dict[str, Any]:
        """
        同步财务数据
        
        Args:
            symbols: 股票代码列表
            report_type: 报告类型 (annual/quarterly)
            
        Returns:
            同步结果统计
        """
        if not self.connected:
            await self.initialize()
        
        logger.info(f"🔄 开始从 Yahoo Finance 同步港股财务数据...")
        
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
                    # 标准化股票代码
                    clean_symbol = symbol
                    if '.' not in symbol:
                        clean_symbol = f"{symbol}.HK"
                    
                    logger.info(f"🔍 正在获取 {symbol} 的财务数据 ({report_type})...")
                    
                    # 从 Yahoo Finance 获取财务数据
                    financial_data = await self.provider.get_financial_data(clean_symbol, report_type)
                    
                    if financial_data is None:
                        logger.warning(f"⚠️ {symbol}: 未获取到财务数据")
                        stats["error_count"] += 1
                        continue
                    
                    # 保存到 MongoDB
                    await self._save_financial_data_to_mongodb(clean_symbol, financial_data, report_type)
                    stats["success_count"] += 1
                    
                    logger.info(f"✅ {symbol}: 财务数据同步成功")
                    
                    # 限流
                    await asyncio.sleep(1.0)
                    
                except Exception as e:
                    logger.error(f"❌ {symbol}: 财务数据同步失败 - {e}")
                    stats["error_count"] += 1
                    stats["errors"].append({
                        "symbol": symbol,
                        "error": str(e)
                    })
            
            logger.info(
                f"✅ Yahoo Finance 港股财务数据同步完成: "
                f"处理 {stats['total_processed']} 只，成功 {stats['success_count']} 只，"
                f"失败 {stats['error_count']} 只"
            )
            
        except Exception as e:
            logger.error(f"❌ Yahoo Finance 港股财务数据同步失败: {e}")
            stats["errors"].append({
                "error": str(e),
                "context": "sync_financial_data"
            })
        
        return stats
    
    async def _save_financial_data_to_mongodb(self, symbol: str, financial_data: Dict[str, Any], report_type: str) -> None:
        """
        将财务数据保存到 MongoDB
        
        Args:
            symbol: 股票代码
            financial_data: 财务数据字典
            report_type: 报告类型
        """
        try:
            # 提取代码
            code = symbol.split('.')[0] if '.' in symbol else symbol
            
            # 构建文档
            doc = {
                "code": code,
                "symbol": code,
                "report_type": report_type,
                "data": financial_data,
                "source": "yfinance_hk",
                "updated_at": datetime.utcnow()
            }
            
            # 添加到 stock_financial_data 集合
            await self.db.stock_financial_data.update_one(
                {
                    "code": code,
                    "report_type": report_type,
                    "source": "yfinance_hk"
                },
                {"$set": doc},
                upsert=True
            )
            
            logger.debug(f"💾 {symbol}: 财务数据已保存")
            
        except Exception as e:
            logger.error(f"❌ {symbol}: 保存财务数据失败 - {e}")
            raise


async def get_yfinance_hk_sync_service() -> YFinanceHKSyncService:
    """获取 Yahoo Finance 港股同步服务单例"""
    global _yfinance_hk_sync_service
    if _yfinance_hk_sync_service is None:
        _yfinance_hk_sync_service = YFinanceHKSyncService()
        await _yfinance_hk_sync_service.initialize()
    return _yfinance_hk_sync_service
