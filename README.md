# 创建测试文件
echo "hello hello hello hello" > sample.txt

# 固定分块存储
python -m dedup.cli store sample.txt --data-dir data --chunking fixed --chunk-size 4

# 查看文件列表
python -m dedup.cli list --data-dir data

# 恢复文件
python -m dedup.cli restore 1 restored.txt --data-dir data

# 比较
diff sample.txt restored.txt   # 应无输出

# 统计信息
python -m dedup.cli stat --data-dir data

# CDC 存储示例
python -m dedup.cli store sample.txt --data-dir data_cdc --chunking cdc --min-size 16 --avg-size 32 --max-size 64 --window-size 8