from get_hot import find_overlap_stocks

# 调用 get_hot 模块中的 get_filtered_hot_stocks 函数
filtered_stocks = get_filtered_hot_stocks()

print("\n=== 从 get_hot 获取到的最终过滤后的股票列表 ===")
print(filtered_stocks)