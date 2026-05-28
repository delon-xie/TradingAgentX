"""
Futu OpenAPI 港股数据提供器
基于富途牛牛开放接口获取港股实时行情、历史数据和基础信息
文档: https://openapi.futunn.com/futu-api-doc/intro/ai.html
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Union
import pandas as pd
import sys

logger = logging.getLogger(__name__)

# 尝试导入 futu-api
try:
    import futu
    
    # 检查必要的类是否存在
    required_attrs = ['OpenQuoteContext']
    missing = [attr for attr in required_attrs if not hasattr(futu, attr)]
    
    if missing:
        raise ImportError(f"futu 模块缺少必要的属性: {', '.join(missing)}")
    
    # 动态获取类（兼容不同版本）
    OpenQuoteContext = futu.OpenQuoteContext
    Market = getattr(futu, 'Market', None)
    KLType = getattr(futu, 'KLType', None)
    AuType = getattr(futu, 'AuType', None)
    SubType = getattr(futu, 'SubType', None)
    
    # 🔥 RetType 可能不存在，使用 RET_OK 和 RET_ERROR 常量
    RetType = getattr(futu, 'RetType', None)
    RET_OK = getattr(futu, 'RET_OK', 0)
    RET_ERROR = getattr(futu, 'RET_ERROR', -1)
    
    FUTU_AVAILABLE = True
    logger.info(f"✅ futu-api 库导入成功 (version: {getattr(futu, '__version__', 'unknown')})")
    
except ImportError as e:
    FUTU_AVAILABLE = False
    logger.error(f"❌ futu-api 库导入失败: {e}")
    logger.error(f"   Python 可执行文件: {sys.executable}")
    logger.error(f"   请运行: {sys.executable} -m pip install futu-api")
except Exception as e:
    FUTU_AVAILABLE = False
    logger.error(f"❌ futu-api 库导入时发生未知错误: {type(e).__name__}: {e}", exc_info=True)

from ..base_provider import BaseStockDataProvider

logger = logging.getLogger(__name__)


class FutuProvider(BaseStockDataProvider):
    """
    Futu OpenAPI 港股数据提供器
    
    支持功能：
    - 实时行情订阅
    - 历史K线数据
    - 股票基础信息
    - 市场快照
    
    使用前需要：
    1. 安装 futu-api: pip install futu-api
    2. 下载并运行 FutuOpenD (富途开放接口桌面端)
    3. 配置 host 和 port
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 11111, is_encrypt: bool = False):
        """
        初始化 Futu Provider
        
        Args:
            host: FutuOpenD 主机地址
            port: FutuOpenD 端口
            is_encrypt: 是否启用加密连接
        """
        super().__init__(provider_name="FutuProvider")
        
        if not FUTU_AVAILABLE:
            logger.error("❌ futu-api 库未安装，请运行: pip install futu-api")
        
        self.host = host
        self.port = port

    async def connect(self) -> bool:
        """连接到 FutuOpenD"""
        if not FUTU_AVAILABLE:
            logger.error("❌ futu-api 不可用")
            return False
        
        try:
            # 创建行情上下文
            self.quote_ctx = OpenQuoteContext(host=self.host, port=self.port)
            
            # 测试连接
            ret, data = self.quote_ctx.get_global_state()
            if ret == RET_OK:
                self.connected = True
                logger.info(f"✅ Futu OpenAPI 连接成功: {self.host}:{self.port}")
                return True
            else:
                logger.error(f"❌ Futu OpenAPI 连接失败: {data}")
                self.close()
                return False
                
        except Exception as e:
            logger.error(f"❌ Futu OpenAPI 连接异常: {e}")
            self.close()
            return False
    
    def close(self):
        """关闭连接"""
        if self.quote_ctx:
            try:
                self.quote_ctx.close()
                logger.info("🔒 Futu OpenAPI 连接已关闭")
            except Exception as e:
                logger.error(f"关闭 Futu 连接失败: {e}")
            finally:
                self.quote_ctx = None
                self.connected = False
    
    def is_available(self) -> bool:
        """检查是否可用"""
        return FUTU_AVAILABLE and self.connected
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        标准化股票代码为 Futu 格式
        
        Args:
            symbol: 原始代码 (如 0700, 0700.HK, 腾讯控股)
            
        Returns:
            Futu 格式代码 (如 HK.00700)
        """
        if not symbol:
            return ""
        
        symbol = str(symbol).strip().upper()
        
        # 如果已经是 Futu 格式 (HK.XXXXX)
        if symbol.startswith("HK."):
            # 🔥 确保是5位数字
            code_part = symbol[3:]  # 去掉 "HK."
            if code_part.isdigit():
                code_part = code_part.zfill(5)
                return f"HK.{code_part}"
            return symbol
        
        # 处理 .HK 后缀
        if symbol.endswith(".HK"):
            code = symbol.replace(".HK", "").zfill(5)  # 🔥 改为5位
            return f"HK.{code}"
        
        # 纯数字代码
        if symbol.isdigit():
            code = symbol.zfill(5)  # 🔥 改为5位
            return f"HK.{code}"
        
        # 其他情况，尝试直接使用
        logger.warning(f"⚠️ 无法识别的股票代码格式: {symbol}，尝试直接使用")
        return symbol
    
    async def get_stock_quotes(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取实时行情
        
        Args:
            symbol: 股票代码
            
        Returns:
            实时行情数据字典
        """
        if not self.is_available():
            logger.error("❌ Futu 未连接")
            return None
        
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            logger.info(f"📊 获取实时行情: {normalized_symbol}")
            
            # 订阅行情
            ret_sub, err_message = self.quote_ctx.subscribe([normalized_symbol], [SubType.QUOTE], subscribe_push=False)
            if ret_sub != RET_OK:
                logger.error(f"❌ 订阅失败: {err_message}")
                return None

            # 获取行情快照
            ret, data = self.quote_ctx.get_stock_quote([normalized_symbol])
            if ret != RET_OK or data is None or data.empty:
                logger.warning(f"⚠️ 未获取到行情数据: {normalized_symbol}")
                return None
            
            row = data.iloc[0]
            
            # 构建标准化行情数据
            quote = {
                'symbol': normalized_symbol,
                'code': normalized_symbol.replace('HK.', ''),
                'name': row.get('stock_name', ''),
                'price': float(row.get('last_price', 0)),
                'open': float(row.get('open_price', 0)),
                'high': float(row.get('high_price', 0)),
                'low': float(row.get('low_price', 0)),
                'close': float(row.get('last_price', 0)),
                'prev_close': float(row.get('prev_close_price', 0)),
                'volume': float(row.get('volume', 0)),
                'amount': float(row.get('turnover', 0)),
                'change': float(row.get('change_val', 0)),
                'change_percent': float(row.get('change_rate', 0)),
                'trade_date': datetime.now().strftime('%Y-%m-%d'),
                'updated_at': datetime.utcnow(),
                'source': 'futu'
            }
            
            logger.info(f"✅ 成功获取 {normalized_symbol} 的实时行情")
            return quote
            
        except Exception as e:
            logger.error(f"❌ 获取实时行情失败 {symbol}: {e}", exc_info=True)
            return None
    
    async def get_realtime_quotes(self, symbols: List[str]) -> Optional[pd.DataFrame]:
        """
        批量获取实时行情（返回 DataFrame）
        
        Args:
            symbols: 股票代码列表
            
        Returns:
            实时行情数据 DataFrame
        """
        if not symbols:
            return None
        
        if not self.is_available():
            logger.error("❌ Futu 未连接")
            return None
        
        try:
            normalized_symbols = [self._normalize_symbol(s) for s in symbols]
            logger.info(f"📊 批量获取实时行情: {len(normalized_symbols)} 只股票")
            logger.info(f"   标准化后的代码: {normalized_symbols}")
            
            # 订阅行情
            logger.info(f"🔌 正在订阅行情: {normalized_symbols}")
            ret_sub, err_message = self.quote_ctx.subscribe(normalized_symbols, [SubType.QUOTE], subscribe_push=False)
            if ret_sub != RET_OK:
                logger.error(f"❌ 批量订阅失败: ret={ret_sub}, error={err_message}")
                return None
            
            logger.info(f"✅ 订阅成功，正在获取行情快照...")

            # 获取行情快照
            ret, data = self.quote_ctx.get_stock_quote(normalized_symbols)
            logger.info(f"📊 get_stock_quote 返回: ret={ret}, data_type={type(data)}, data_shape={data.shape if data is not None else 'None'}")
            
            if ret != RET_OK:
                logger.error(f"❌ 获取行情失败: ret={ret}")
                return None
            
            if data is None or data.empty:
                logger.warning("⚠️ 未获取到批量行情数据（可能原因：股票停牌、非交易时间、FutuOpenD权限不足）")
                return None
            
            logger.info(f"✅ 成功获取 {len(data)} 条行情记录")
            
            # 转换为标准格式
            all_quotes = []
            for _, row in data.iterrows():
                quote = {
                    'symbol': row.get('code', ''),
                    'code': row.get('code', '').replace('HK.', ''),
                    'name': row.get('stock_name', ''),
                    'price': float(row.get('last_price', 0)),
                    'open': float(row.get('open_price', 0)),
                    'high': float(row.get('high_price', 0)),
                    'low': float(row.get('low_price', 0)),
                    'close': float(row.get('last_price', 0)),
                    'prev_close': float(row.get('prev_close_price', 0)),
                    'volume': float(row.get('volume', 0)),
                    'amount': float(row.get('turnover', 0)),
                    'change': float(row.get('change_val', 0)),
                    'change_percent': float(row.get('change_rate', 0)),
                    'trade_date': datetime.now().strftime('%Y-%m-%d'),
                    'updated_at': datetime.utcnow(),
                    'source': 'futu'
                }
                all_quotes.append(quote)
            
            if not all_quotes:
                return None
            
            df = pd.DataFrame(all_quotes)
            logger.info(f"✅ 成功获取 {len(df)} 只股票的实时行情")
            return df
            
        except Exception as e:
            logger.error(f"❌ 批量获取实时行情失败: {e}", exc_info=True)
            return None
    
    async def get_historical_data(
        self, 
        symbol: str, 
        start_date: Union[str, date], 
        end_date: Union[str, date] = None
    ) -> Optional[pd.DataFrame]:
        """
        获取历史K线数据（支持超过1000条记录，自动分批次获取）
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期，默认为今天
            
        Returns:
            历史数据DataFrame
        """
        if not self.is_available():
            logger.error("❌ Futu 未连接")
            return None
        
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            
            # 处理日期
            if isinstance(start_date, str):
                start_date_str = start_date
                start_date_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            elif isinstance(start_date, (date, datetime)):
                start_date_dt = start_date if isinstance(start_date, datetime) else datetime.combine(start_date, datetime.min.time())
                start_date_str = start_date_dt.strftime('%Y-%m-%d')
            else:
                start_date_str = str(start_date)
                start_date_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            
            if end_date is None:
                end_date_dt = datetime.now()
            elif isinstance(end_date, str):
                end_date_dt = datetime.strptime(end_date, '%Y-%m-%d')
            elif isinstance(end_date, (date, datetime)):
                end_date_dt = datetime.combine(end_date, datetime.min.time()) if isinstance(end_date, date) else end_date
            else:
                end_date_dt = datetime.now()
            
            end_date_str = end_date_dt.strftime('%Y-%m-%d')
            
            logger.info(f"📊 获取历史数据: {normalized_symbol}, {start_date_str} 至 {end_date_str}")
            
            # 计算 K 线类型
            kl_type = KLType.K_DAY if hasattr(KLType, 'K_DAY') else getattr(KLType, 'KL_DAY', None)
            if kl_type is None:
                logger.error("❌ 无法找到正确的 KLType 枚举值")
                return None
            
            # 计算总天数
            total_days = (end_date_dt - start_date_dt).days
            logger.info(f"📅 总天数为: {total_days} 天")
            
            # 获取复权类型
            autype = AuType.QFQ if hasattr(AuType, 'QFQ') else getattr(AuType, 'AU_TYPE_QFQ', None)
            
            all_data = []
            page_req_key = None
            batch_count = 0
            
            # 分批次获取数据
            while True:
                batch_count += 1
                logger.info(f"📦 开始第 {batch_count} 批次数据获取...")
                
                # 获取历史 K 线
                if batch_count == 1:
                    # 第一次请求，指定完整的日期范围
                    ret, data, page_req_key = self.quote_ctx.request_history_kline(
                        code=normalized_symbol,
                        start=start_date_str,
                        end=end_date_str,
                        ktype=kl_type,
                        max_count=1000,  # 单次最多1000条
                        autype=autype
                    )
                else:
                    # 后续请求使用分页令牌
                    if page_req_key is None:
                        break
                    ret, data, page_req_key = self.quote_ctx.request_history_kline(
                        code=normalized_symbol,
                        start=start_date_str,
                        end=end_date_str,
                        ktype=kl_type,
                        max_count=1000,
                        autype=autype,
                        page_req_key=page_req_key
                    )
                
                if ret != RET_OK:
                    logger.warning(f"⚠️ 第 {batch_count} 批次获取数据失败")
                    break
                
                if data is None or data.empty:
                    logger.info(f"ℹ️ 第 {batch_count} 批次无数据")
                    break
                
                logger.info(f"✅ 第 {batch_count} 批次获取到 {len(data)} 条记录")
                all_data.append(data)
                
                # 检查是否还有更多数据
                if page_req_key is None or page_req_key == "":
                    logger.info("🎯 已获取所有数据")
                    break
            
            if not all_data:
                logger.warning(f"⚠️ 未找到股票 {normalized_symbol} 的历史数据")
                return None
            
            # 合并所有批次的数据
            combined_data = pd.concat(all_data, ignore_index=True)
            
            # 去重处理（可能有重叠的数据）
            combined_data = combined_data.drop_duplicates(subset=['time_key'])
            combined_data = combined_data.sort_values('time_key').reset_index(drop=True)
            
            logger.info(f"📈 合并后总数据量: {len(combined_data)} 条")
            
            # 重置索引
            df = combined_data.reset_index(drop=True)
            
            # 重命名列以符合标准格式
            df = df.rename(columns={
                'time_key': 'tradedate',
                'open': 'open',
                'high': 'high',
                'low': 'low',
                'close': 'close',
                'volume': 'volume',
                'turnover': 'amount'
            })
            
            # 添加额外字段
            df['symbol'] = normalized_symbol
            df['code'] = normalized_symbol.replace('HK.', '')
            df['adjclose'] = df['close']  # Futu 已提供复权数据
            df['data_source'] = 'futu'
            df['data_version'] = 1
            df['updated_at'] = datetime.utcnow()
            
            # 确保日期格式正确
            df['tradedate'] = pd.to_datetime(df['tradedate']).dt.strftime('%Y-%m-%d')
            
            # 选择并排序列
            columns_order = [
                'tradedate', 'symbol', 'code', 'open', 'high', 'low', 
                'close', 'adjclose', 'volume', 'amount', 'data_source', 
                'data_version', 'updated_at'
            ]
            
            # 过滤掉不存在的列
            existing_columns = [col for col in columns_order if col in df.columns]
            df = df[existing_columns]
            
            # 检查数据是否完整
            expected_days = min(total_days, len(df) + 100)  # 考虑周末和节假日
            if len(df) < expected_days * 0.7:  # 如果获取的数据少于预期的70%
                logger.warning(f"⚠️ 获取的数据量可能不完整: 预期约{expected_days}天，实际{len(df)}条")
                
            logger.info(f"✅ 成功获取 {len(df)} 条历史数据记录")
            return df
            
        except Exception as e:
            logger.error(f"❌ 获取历史数据失败 {symbol}: {e}", exc_info=True)
            return None    
    async def get_stock_basic_info(self, symbol: str = None) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        获取股票基础信息
        
        Args:
            symbol: 股票代码，为空则返回None
            
        Returns:
            股票基础信息字典
        """
        if not symbol:
            logger.warning("⚠️ FutuProvider 不支持批量获取股票列表")
            return None
        
        if not self.is_available():
            logger.error("❌ Futu 未连接")
            return None
        
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            logger.info(f"📊 获取股票基础信息: {normalized_symbol}")
            
            # 获取股票基本信息
            ret, data = self.quote_ctx.get_market_snapshot([normalized_symbol])
            if ret != RET_OK or data is None or data.empty:
                logger.warning(f"⚠️ 未获取到基础信息: {normalized_symbol}")
                return None

            row = data.iloc[0]
            
            # 构建基础信息
            info = {
                'symbol': normalized_symbol,
                'code': normalized_symbol.replace('HK.', ''),
                'name': row.get('stock_name', ''),
                'market': 'HK',
                'exchange': 'Hong Kong Stock Exchange',
                'currency': 'HKD',
                'lot_size': int(row.get('lot_size', 0)),
                'stock_type': row.get('stock_type', ''),
                'listing_date': row.get('list_time', ''),
                'delisting': row.get('delisting', False),
                'sector': row.get('industry', ''),
                'updated_at': datetime.utcnow(),
                'source': 'futu'
            }
            
            logger.info(f"✅ 成功获取 {normalized_symbol} 的基础信息")
            return info
            
        except Exception as e:
            logger.error(f"❌ 获取基础信息失败 {symbol}: {e}", exc_info=True)
            return None
    
    async def get_financial_data(self, symbol: str, report_type: str = "annual") -> Optional[Dict[str, Any]]:
        """
        获取财务数据
        
        Args:
            symbol: 股票代码
            report_type: 报告类型 (annual/quarterly)
            
        Returns:
            财务数据字典
        """
        if not self.is_available():
            logger.error("❌ Futu 未连接")
            return None
        
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            logger.info(f"📊 获取财务数据: {normalized_symbol}, 类型: {report_type}")
            
            # Futu API 目前不直接提供财务数据，返回 None
            logger.warning(f"⚠️ Futu API 暂不支持财务数据: {normalized_symbol}")
            return None
            
        except Exception as e:
            logger.error(f"❌ 获取财务数据失败 {symbol}: {e}", exc_info=True)
            return None
    
    def find_latest_trade_date(self) -> Optional[str]:
        """查找最新交易日期"""
        if not self.is_available():
            return None
        
        try:
            # 获取当前日期作为最新交易日
            latest_date = datetime.now().strftime('%Y-%m-%d')
            logger.info(f"Futu: Latest trade date: {latest_date}")
            return latest_date
        except Exception as e:
            logger.error(f"Futu: find_latest_trade_date failed: {e}")
            return None
    
    def get_daily_basic(self, trade_date: str) -> Optional[pd.DataFrame]:
        """获取每日基本面数据"""
        logger.debug(f"Futu: get_daily_basic not supported for {trade_date}")
        return None
    
    def get_news(self, code: str, days: int = 2, limit: int = 50, include_announcements: bool = True):
        """获取新闻"""
        logger.debug(f"Futu: get_news not supported for {code}")
        return None
    
    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """获取股票列表"""
        logger.debug("Futu: get_stock_list not supported")
        return None
    
    def __repr__(self):
        return f"<FutuProvider(connected={self.connected}, host={self.host}:{self.port})>"