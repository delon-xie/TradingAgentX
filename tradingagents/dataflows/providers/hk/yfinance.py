"""
Yahoo Finance 港股数据提供器
基于 yfinance 库获取港股历史行情和基础信息
支持股票代码格式: 0700.HK, 00700.HK, 腾讯控股等
"""
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Union
import pandas as pd
import yfinance as yf

from ..base_provider import BaseStockDataProvider

logger = logging.getLogger(__name__)


class YFinanceHKProvider(BaseStockDataProvider):
    """
    Yahoo Finance 港股数据提供器
    
    基于 yfinance 库提供港股数据，支持：
    - 历史行情数据
    - 实时行情数据
    - 股票基础信息
    - 财务数据
    - 技术指标
    
    股票代码格式支持：
    - 带后缀: "0700.HK", "00700.HK"
    - 纯数字: "0700", "00700" (自动添加 .HK 后缀)
    - 中文名称: "腾讯控股" (需要名称映射)
    """
    
    def __init__(self):
        super().__init__("YFinance-HK")
        self.connected = False
        
        # 港股名称映射表（常用股票）
        self.stock_name_map = {
            # 金融与综合企业
            '长和': '0001.HK',
            '中电控股': '0002.HK',
            '香港中华煤气': '0003.HK',
            '九龙仓集团': '0004.HK',
            '汇丰控股': '0005.HK',
            '电能实业': '0006.HK',
            '电讯盈科': '0008.HK',
            '恒基地产': '0012.HK',
            '和黄医药': '0013.HK',
            '新鸿基地产': '0016.HK',
            '太古股份公司A': '0019.HK',
            '中信股份': '0267.HK',
            '华润啤酒': '0291.HK',
            '中银香港': '2388.HK',
            '建设银行': '0939.HK',
            '工商银行': '1398.HK',
            '中国平安': '2318.HK',
            '招商银行': '3968.HK',
            '中国银行': '3988.HK',

            # 科技与互联网
            '腾讯控股': '0700.HK',
            '联想集团': '0992.HK',
            '快手': '1024.HK',
            '小米集团': '1810.HK',
            '金蝶国际': '0268.HK',
            '中兴通讯': '0763.HK',
            '中国软件国际': '0354.HK',
            '金山软件': '3888.HK',
            '阿里巴巴': '9988.HK',
            '京东集团': '9618.HK',
            '网易': '9999.HK',
            '百度': '9888.HK',
            '携程集团': '9961.HK',
            '哔哩哔哩': '9626.HK',

            # 电信、能源与公用事业
            '中国联通': '0762.HK',
            '中国石油股份': '0857.HK',
            '中国海洋石油': '0883.HK',
            '中国移动': '0941.HK',
            '中国神华': '1088.HK',
            '中国石化': '0386.HK',
            '华能国际电力股份': '0902.HK',
            '华润电力': '0836.HK',
            '港铁公司': '0066.HK',

            # 消费、汽车与医药
            '银河娱乐': '0027.HK',
            '百威亚太': '1876.HK',
            '金沙中国': '1928.HK',
            '农夫山泉': '9633.HK',
            '吉利汽车': '0175.HK',
            '比亚迪股份': '1211.HK',
            '安踏体育': '2020.HK',
            '李宁': '2331.HK',
            '药明生物': '2269.HK',
            '石药集团': '1093.HK',
            '京东健康': '6618.HK',
            '华润万象生活': '1209.HK',

            # 工业与地产
            '德昌电机': '0179.HK',
            '中国海外发展': '0688.HK',
            '华润置地': '1109.HK',
            '碧桂园服务': '6098.HK',
            '申洲国际': '2313.HK',
            '中国中车': '1766.HK'
        }
        
        logger.info("🔧 YFinanceHKProvider 初始化完成")
    
    async def connect(self) -> bool:
        """
        连接到 Yahoo Finance
        
        Returns:
            bool: 连接是否成功
        """
        try:
            logger.info("🔌 正在连接到 Yahoo Finance...")
            
            # 测试连接：尝试获取一个简单的股票信息
            test_ticker = yf.Ticker("0700.HK")
            _ = test_ticker.info
            
            self.connected = True
            logger.info("✅ Yahoo Finance 连接成功")
            return True
            
        except Exception as e:
            logger.error(f"❌ Yahoo Finance 连接失败: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """断开连接"""
        self.connected = False
        logger.info("✅ Yahoo Finance 连接已断开")
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        标准化股票代码
        
        Args:
            symbol: 原始股票代码或名称
            
        Returns:
            标准化的股票代码（带 .HK 后缀）
        """
        if not symbol:
            raise ValueError("股票代码不能为空")
        
        symbol = str(symbol).strip()
        
        # 如果是中文名称，查找映射
        if '\u4e00' <= symbol[0] <= '\u9fff':  # 检查是否是中文字符
            if symbol in self.stock_name_map:
                return self.stock_name_map[symbol]
            else:
                raise ValueError(f"未找到股票名称 '{symbol}' 的映射，请使用股票代码")
        
        # 如果已经包含 .HK 后缀，直接返回（转大写）
        if symbol.upper().endswith('.HK'):
            return symbol.upper()
        
        # 如果是纯数字，添加 .HK 后缀
        if symbol.isdigit():
            # 确保是5位数字（港股标准格式）
            return f"{symbol.zfill(5)}.HK"
        
        # 其他情况，假设已经是正确的格式
        return symbol.upper()
    
    async def get_stock_basic_info(self, symbol: str = None) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        获取股票基础信息
        
        Args:
            symbol: 股票代码，为空则返回None（不支持批量获取）
            
        Returns:
            股票基础信息字典
        """
        if not symbol:
            logger.warning("⚠️ YFinanceHKProvider 不支持批量获取股票列表")
            return None
        
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            logger.info(f"📊 获取股票基础信息: {normalized_symbol}")
            
            ticker = yf.Ticker(normalized_symbol)
            info = ticker.info
            
            if not info:
                logger.warning(f"⚠️ 未找到股票 {normalized_symbol} 的信息")
                return None
            
            # 标准化返回数据
            result = {
                'symbol': normalized_symbol,
                'code': normalized_symbol.replace('.HK', ''),
                'name': info.get('shortName', info.get('longName', '')),
                'industry': info.get('industry', ''),
                'sector': info.get('sector', ''),
                'country': info.get('country', 'Hong Kong'),
                'currency': info.get('currency', 'HKD'),
                'exchange': info.get('exchange', 'HKG'),
                'market_cap': info.get('marketCap'),
                'website': info.get('website', ''),
                'description': info.get('longBusinessSummary', ''),
                'employees': info.get('fullTimeEmployees'),
                'data_source': 'yfinance',
                'updated_at': datetime.utcnow()
            }
            
            logger.info(f"✅ 成功获取 {result['name']} 的基础信息")
            return result
            
        except Exception as e:
            logger.error(f"❌ 获取股票基础信息失败 {symbol}: {e}", exc_info=True)
            return None
    
    async def get_stock_quotes(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取实时行情
        
        Args:
            symbol: 股票代码
            
        Returns:
            实时行情数据字典
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            logger.info(f"📊 获取实时行情: {normalized_symbol}")
            
            ticker = yf.Ticker(normalized_symbol)
            
            # 获取最新数据
            data = ticker.history(period='1d')
            
            if data.empty:
                logger.warning(f"⚠️ 未找到股票 {normalized_symbol} 的行情数据")
                return None
            
            # 获取最新一行数据
            latest = data.iloc[-1]
            
            # 构建标准化行情数据
            quote = {
                'symbol': normalized_symbol,
                'code': normalized_symbol.replace('.HK', ''),
                'name': ticker.info.get('shortName', ''),
                'close': float(latest.get('Close', 0)),
                'open': float(latest.get('Open', 0)),
                'high': float(latest.get('High', 0)),
                'low': float(latest.get('Low', 0)),
                'volume': int(latest.get('Volume', 0)),
                'amount': float(latest.get('Close', 0)) * int(latest.get('Volume', 0)),
                'pre_close': float(latest.get('Close', 0)),  # yfinance不直接提供昨收
                'change': 0.0,  # 需要计算
                'pct_chg': 0.0,  # 需要计算
                'trade_date': latest.name.strftime('%Y-%m-%d') if hasattr(latest.name, 'strftime') else str(latest.name),
                'currency': 'HKD',
                'market': 'HK',
                'data_source': 'yfinance',
                'timestamp': datetime.utcnow(),
                'updated_at': datetime.utcnow()
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
        
        try:
            all_quotes = []
            
            for symbol in symbols:
                # 调用单个股票的行情获取
                quote = await self.get_stock_quotes(symbol)
                
                if quote:
                    # 转换为 DataFrame 行
                    all_quotes.append(quote)
            
            if not all_quotes:
                logger.warning("⚠️ 未获取到任何实时行情数据")
                return None
            
            # 转换为 DataFrame
            df = pd.DataFrame(all_quotes)
            
            # 重命名列以匹配预期格式
            df = df.rename(columns={
                'trade_date': 'Date',
                'open': 'Open',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            })
            
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
        获取历史行情数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期，默认为今天
            
        Returns:
            历史数据DataFrame
        """
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            
            # 处理日期
            if isinstance(start_date, str):
                start_date_str = start_date
            elif isinstance(start_date, (date, datetime)):
                start_date_str = start_date.strftime('%Y-%m-%d')
            else:
                start_date_str = str(start_date)
            
            if end_date is None:
                end_date_dt = datetime.now()
            elif isinstance(end_date, str):
                end_date_dt = datetime.strptime(end_date, '%Y-%m-%d')
            elif isinstance(end_date, (date, datetime)):
                end_date_dt = datetime.combine(end_date, datetime.min.time()) if isinstance(end_date, date) else end_date
            else:
                end_date_dt = datetime.now()
            
            # yfinance 的 end_date 是exclusive，所以需要加一天
            end_date_inclusive = end_date_dt + timedelta(days=1)
            end_date_str = end_date_inclusive.strftime('%Y-%m-%d')
            
            logger.info(f"📊 获取历史数据: {normalized_symbol}, {start_date_str} 至 {end_date_str}")
            
            # 获取历史数据
            ticker = yf.Ticker(normalized_symbol)
            df = ticker.history(start=start_date_str, end=end_date_str)
            
            if df.empty:
                logger.warning(f"⚠️ 未找到股票 {normalized_symbol} 在 {start_date_str} 至 {end_date_str} 的历史数据")
                return None
            
            # 重置索引，将日期作为列
            df = df.reset_index()
            
            # 🔥 检查是否有 Adj Close 列，如果没有则使用 Close
            has_adj_close = 'Adj Close' in df.columns
            
            # 重命名列以符合标准格式
            rename_map = {
                'Date': 'tradedate',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            }
            
            # 如果有 Adj Close，也重命名
            if has_adj_close:
                rename_map['Adj Close'] = 'adjclose'
            
            df = df.rename(columns=rename_map)
            
            # 如果没有 Adj Close，使用 Close 作为 adjclose
            if not has_adj_close:
                logger.info(f"ℹ️ {normalized_symbol}: Yahoo Finance 未提供 Adj Close，使用 Close 代替")
                df['adjclose'] = df['close']
            
            # 添加额外字段
            df['symbol'] = normalized_symbol
            df['code'] = normalized_symbol.replace('.HK', '')
            df['amount'] = df['close'] * df['volume']  # 估算成交额
            df['data_source'] = 'yfinance'
            df['data_version'] = 1
            df['updated_at'] = datetime.utcnow()
            
            # 确保日期格式正确
            df['tradedate'] = pd.to_datetime(df['tradedate']).dt.strftime('%Y-%m-%d')
            
            # 🔥 动态构建列顺序（只包含存在的列）
            columns_order = [
                'tradedate', 'symbol', 'code', 'open', 'high', 'low', 
                'close', 'adjclose', 'volume', 'amount', 'data_source', 
                'data_version', 'updated_at'
            ]
            
            # 过滤掉不存在的列
            existing_columns = [col for col in columns_order if col in df.columns]
            df = df[existing_columns]
            
            logger.info(f"✅ 成功获取 {len(df)} 条历史数据记录")
            return df
            
        except Exception as e:
            logger.error(f"❌ 获取历史数据失败 {symbol}: {e}", exc_info=True)
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
        try:
            normalized_symbol = self._normalize_symbol(symbol)
            logger.info(f"📊 获取财务数据: {normalized_symbol}, 类型: {report_type}")
            
            ticker = yf.Ticker(normalized_symbol)
            
            # 根据报告类型选择不同的数据
            if report_type == "quarterly":
                financials = ticker.quarterly_financials
                balance_sheet = ticker.quarterly_balance_sheet
                cashflow = ticker.quarterly_cashflow
            else:
                financials = ticker.financials
                balance_sheet = ticker.balance_sheet
                cashflow = ticker.cashflow
            
            # 转换为字典格式
            result = {
                'symbol': normalized_symbol,
                'report_type': report_type,
                'financials': financials.to_dict() if not financials.empty else {},
                'balance_sheet': balance_sheet.to_dict() if not balance_sheet.empty else {},
                'cashflow': cashflow.to_dict() if not cashflow.empty else {},
                'data_source': 'yfinance',
                'updated_at': datetime.utcnow()
            }
            
            logger.info(f"✅ 成功获取 {normalized_symbol} 的财务数据")
            return result
            
        except Exception as e:
            logger.error(f"❌ 获取财务数据失败 {symbol}: {e}", exc_info=True)
            return None
    
    async def get_stock_list(self, market: str = None) -> Optional[List[Dict[str, Any]]]:
        """
        获取股票列表
        
        Note: yfinance 不支持获取市场所有股票列表
        此方法返回内置的股票名称映射
        
        Args:
            market: 市场代码（暂未使用）
            
        Returns:
            股票列表
        """
        logger.warning("⚠️ yfinance 不支持获取完整股票列表，返回内置映射表")
        
        stock_list = [
            {'symbol': code, 'name': name}
            for name, code in self.stock_name_map.items()
        ]
        
        return stock_list
    
    def __repr__(self):
        return f"<YFinanceHKProvider(connected={self.connected})>"