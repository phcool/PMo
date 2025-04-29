# DLMonitor Cron Scripts

这个目录包含用于设置和运行定时任务的脚本，这些脚本用于替代web应用中内置的调度器，避免多个gunicorn进程同时执行定时任务的问题。

## 文件说明

- `fetch_papers.py`: 从arXiv获取论文并存储到数据库和向量索引中
- `analyze_papers.py`: 分析尚未被分析的论文
- `setup_cron.sh`: 帮助设置cron作业的脚本

## 使用方法

### 1. 禁用web应用中的内置调度器

编辑`.env`文件，添加以下配置：

```
DISABLE_SCHEDULER=true
```

这将防止web应用启动内置的调度器，避免与cron作业重复执行任务。

### 2. 设置cron作业

运行设置脚本：

```bash
cd /home/phcool/dlmonitor/backend
source venv/bin/activate  # 激活虚拟环境（如果使用）
./scripts/setup_cron.sh
```

这将自动设置以下cron作业：

1. 每4小时获取论文：`0 */4 * * * python /path/to/fetch_papers.py`
2. 每4小时30分钟后分析论文：`30 */4 * * * python /path/to/analyze_papers.py`

### 3. 自定义cron计划

如果需要自定义cron作业的执行计划，可以使用`crontab -e`命令手动编辑。

例如，要每12小时执行一次获取论文的任务：

```
0 */12 * * * /path/to/python /path/to/fetch_papers.py >> /path/to/logs/cron_fetch.log 2>&1
```

### 4. 查看日志

cron作业的日志存储在`/home/phcool/dlmonitor/backend/logs/`目录下：

- `cron_fetch.log`: 获取论文的日志
- `cron_analyze.log`: 分析论文的日志

### 5. 论文分析脚本参数

`analyze_papers.py`脚本提供了以下命令行参数：

- `--batch`: 使用批处理模式，每次只分析一小批论文（默认是分析所有待处理论文）
- `--limit N`: 限制最多处理N篇论文

例如：

```bash
# 处理所有待分析论文
python scripts/analyze_papers.py

# 仅处理一批论文（批大小由代码中的ANALYSIS_BATCH_SIZE环境变量设置）
python scripts/analyze_papers.py --batch

# 最多处理20篇论文
python scripts/analyze_papers.py --limit 20

# 批量模式下最多处理10篇论文
python scripts/analyze_papers.py --batch --limit 10
```

### 6. 其他特性

- 单篇论文分析有2分钟的超时限制，超时后会跳过该论文继续处理下一篇
- 对于每个新获取的批次，最多会分析前15页内容（避免过长导致分析不准确）
- 处理文本中的无效字符以确保数据库存储和API调用的兼容性

### 7. 手动执行脚本

也可以手动执行这些脚本：

```bash
cd /home/phcool/dlmonitor/backend
source venv/bin/activate  # 激活虚拟环境（如果使用）
python scripts/fetch_papers.py
python scripts/analyze_papers.py
```

## 服务器重启后

如果服务器重启，cron作业会自动恢复运行，无需手动干预。但应确保web应用也正确重启并且`.env`中的`DISABLE_SCHEDULER=true`设置仍然有效。 