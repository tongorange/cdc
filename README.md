# 基于变长分块的重复数据删除系统

该项目为 Python 实现的重复数据删除实验项目，支持：

- 固定长度分块
- 变长分块（CDC）
- 文件/目录备份与恢复
- 去重统计
- 对比实验

## 项目结构

- `main.py`：命令行入口
- `dedup/`：核心代码
- `make_test_data.py`：生成实验数据
- `run_experiment.py`：运行实验
- `test_data/`：实验数据集
- `results/`：实验结果
- `tests/`：测试代码

## 基本运行

在项目根目录下执行：

```bash
python main.py --help
```

### 备份目录

```bash
python main.py backup test_data/scenarios/D_prefix_insert --data-dir data --chunking cdc
```

### 恢复目录

```bash
python main.py restore 1 restored_dir --kind snapshot --data-dir data
```

### 查看统计信息

```bash
python main.py stat --data-dir data
```

## 生成实验数据

```bash
python make_test_data.py
```

## 运行实验

运行全部实验：

```bash
python run_experiment.py
```

只运行某一类实验：

```bash
python run_experiment.py --experiment correctness
python run_experiment.py --experiment scenario
python run_experiment.py --experiment cdc-params
python run_experiment.py --experiment scale
```

## 运行测试

```bash
python -m unittest discover -s tests -v
```

## 结果文件

实验结果保存在 `results/` 目录下，包括：

- `correctness_results.csv`
- `scenario_results.csv`
- `cdc_parameter_results.csv`
- `scale_results.csv`
