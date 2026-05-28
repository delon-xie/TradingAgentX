"""
DoltProvider 使用示例
演示如何配置和使用Dolt历史行情数据源
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
print(str(project_root))
sys.path.insert(0, str(project_root))

import asyncio
from datetime import datetime, timedelta
from tradingagents.dataflows.providers.china import DoltProvider


async def example_basic_usage():
    """基本使用示例"""
    print("=" * 60)
    print("DoltProvider 基本使用示例")
    print("=" * 60)
    
    # 方式1: 使用默认连接字符串
    provider = DoltProvider()
    
    # 方式2: 自定义连接字符串
    # provider = DoltProvider(
    #     connection_string="mysql+pymysql://root:@127.0.0.1:3310/investment_data"
    # )
    
    # 方式3: 使用额外参数
    # provider = DoltProvider(
    #     connection_string="mysql://root:@127.0.0.1:3310/investment_data",
    #     pool_size=10,
    #     max_overflow=20
    # )
    
    # 连接数据库
    success = await provider.connect()
    if not success:
        print("❌ 连接失败")
        return
    
    try:
        # 示例1: 获取单只股票的历史数据
        print("\n📊 示例1: 获取贵州茅台(600519)最近30天的历史数据")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        df = await provider.get_historical_data(
            symbol="600519",
            start_date=start_date,
            end_date=end_date
        )
        
        if df is not None and not df.empty:
            print(f"✅ 获取到 {len(df)} 条记录")
            print("\n数据预览:")
            print(df.head())
            print(f"\n数据列: {list(df.columns)}")
            print(f"\n数据统计:")
            print(df[['open', 'high', 'low', 'close', 'volume']].describe())
        else:
            print("⚠️ 未获取到数据")
        
        # 示例2: 获取不同格式的股票代码
        print("\n\n📊 示例2: 测试不同股票代码格式")
        test_symbols = ["000001", "000001.SZ", "300750", "300750.SZ"]
        
        for symbol in test_symbols:
            df = await provider.get_historical_data(
                symbol=symbol,
                start_date="2024-01-01",
                end_date="2024-01-10"
            )
            if df is not None:
                print(f"✅ {symbol}: 获取到 {len(df)} 条记录")
            else:
                print(f"⚠️ {symbol}: 未获取到数据")
        
        # 示例3: 获取所有股票代码列表
        print("\n\n📋 示例3: 获取数据库中所有股票代码")
        stock_list = await provider.get_stock_list()
        if stock_list:
            print(f"✅ 共有 {len(stock_list)} 只股票")
            print("前10只股票:", [s['symbol'] for s in stock_list[:10]])
        
        # 示例4: 长时间跨度的历史数据
        print("\n\n📊 示例4: 获取宁德时代(300750)2023年全年数据")
        df = await provider.get_historical_data(
            symbol="300750",
            start_date="2023-01-01",
            end_date="2023-12-31"
        )
        
        if df is not None and not df.empty:
            print(f"✅ 获取到 {len(df)} 条记录")
            print(f"日期范围: {df['tradedate'].min()} 至 {df['tradedate'].max()}")
            print(f"价格范围: ¥{df['close'].min():.2f} - ¥{df['close'].max():.2f}")
    
    finally:
        # 断开连接
        await provider.disconnect()
        print("\n✅ 连接已关闭")


async def example_integration_with_other_providers():
    """与其他数据源集成示例"""
    print("\n" + "=" * 60)
    print("DoltProvider 与其他数据源集成示例")
    print("=" * 60)
    
    # DoltProvider 专注于历史数据
    dolt = DoltProvider()
    await dolt.connect()
    
    try:
        # 从Dolt获取历史数据
        print("\n📊 从Dolt获取历史行情数据...")
        hist_df = await dolt.get_historical_data(
            symbol="600519",
            start_date="2024-01-01",
            end_date="2024-01-31"
        )
        
        if hist_df is not None:
            print(f"✅ Dolt历史数据: {len(hist_df)} 条记录")
            print("   包含字段: open, high, low, close, adjclose, volume, amount")
            
            # 这里可以结合其他数据源获取的信息
            # 例如：使用AKShare获取实时行情、基本面信息等
            print("\n💡 提示: 可以结合其他数据源使用:")
            print("   - AKShare/Tushare: 获取实时行情、股票基础信息")
            print("   - Dolt: 获取高质量历史行情数据")
            print("   - 组合使用以获得完整的数据视图")
    
    finally:
        await dolt.disconnect()


def example_configuration():
    """配置示例"""
    print("\n" + "=" * 60)
    print("DoltProvider 配置示例")
    print("=" * 60)
    
    print("\n1️⃣ 基本配置:")
    print("""
    # 使用默认配置（本地MySQL）
    provider = DoltProvider()
    # 默认连接: mysql+pymysql://0.0.0.0:3310/investment_data
    """)
    
    print("\n2️⃣ 自定义数据库连接:")
    print("""
    # 指定完整的连接字符串
    provider = DoltProvider(
        connection_string="mysql+pymysql://user:password@host:port/database"
    )
    
    # 常见连接字符串格式:
    # - mysql+pymysql://root:123456@192.168.1.100:3306/investment_data
    # - mysql://root:@localhost:3306/investment_data
    """)
    
    print("\n3️⃣ 高级连接池配置:")
    print("""
    provider = DoltProvider(
        connection_string="mysql://...",
        pool_size=10,          # 连接池大小
        max_overflow=20,       # 最大溢出连接数
        pool_timeout=30,       # 连接超时时间(秒)
        pool_recycle=3600      # 连接回收时间(秒)
    )
    """)
    
    print("\n4️⃣ 环境变量配置(推荐):")
    print("""
    import os
    
    # 设置环境变量
    os.environ['DOLT_DB_URL'] = 'mysql+pymysql://...'
    
    # 使用环境变量
    provider = DoltProvider(
        connection_string=os.getenv('DOLT_DB_URL')
    )
    """)


if __name__ == "__main__":
    print("🚀 DoltProvider 使用示例\n")
    
    # 运行基本使用示例
    asyncio.run(example_basic_usage())
    
    # 运行集成示例
    asyncio.run(example_integration_with_other_providers())
    
    # 显示配置示例
    example_configuration()
    
    print("\n" + "=" * 60)
    print("✨ 示例运行完成")
    print("=" * 60)