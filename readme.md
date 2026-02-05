# autoEmailAgent 使用说明

## 项目简介

基于OpenAI Agent SDK的自动处理AI工具报销邮件的智能助手。系统通过LLM循环调用工具，自动完成邮件读取、OCR识别、内容核对、数据入库和邮件回复等任务。

## 功能特性

- **邮件读取**: 自动读取邮箱内报销邮件，获取邮件内容和附件（支持自动下载和解压ZIP）
- **OCR识别**: 使用视觉模型（VLM）对支付凭证进行OCR识别，支持图片和PDF格式
- **内容核对**: 自动核对邮件内容与支付凭证是否一致（工具名称、金额、币种等）
- **数据管理**: 将报销信息存储到MySQL数据库，支持增删改查操作
- **智能回复**: 对于缺失材料或材料有误的邮件，自动生成并发送补充材料邮件


## 环境要求

- Python 3.8+
- MySQL 5.7+ 或 8.0+
- OpenAI Agent SDK
- LLM API Key（自建或OpenAI兼容API）
- VLM API Key（用于OCR，可选，默认使用LLM配置）
- Poppler工具（用于PDF转图片，可选，仅在使用PDF OCR时需要）

## 安装步骤

### 1. 克隆项目

```bash
cd agent_service/src
```

### 2. 安装依赖

```bash
pip install -r ../../requirements.txt
```

### 3. 安装Poppler（可选，仅PDF OCR需要）

**Windows:**
- 下载 [Poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases/)
- 解压到任意目录（如 `C:\Program Files\poppler`）
- 在`.env`中设置`POPPLER_PATH=C:\Program Files\poppler\bin`

或使用Chocolatey：
```bash
choco install poppler
```

**Linux:**
```bash
apt-get install poppler-utils
# 或
yum install poppler-utils
```

**macOS:**
```bash
brew install poppler
```

### 4. 配置环境变量

复制 `env.example` 为 `.env` 并填写配置：

```env
# Agent LLM配置（OpenAI Agent SDK使用 仅可配置openai支持的provider）
MOONSHOT_API_KEY=sk-...
MOONSHOT_API_BASE=https://api.moonshot.cn/v1
MOONSHOT_MODEL=litellm/moonshot/kimi-k2-turbo-preview

# LLM配置（自建或OpenAI兼容API）
# LLM API配置（用于文本处理、解析、核对等）
LLM_API_KEY=your_llm_api_key_here
LLM_BASE_URL=https://api.your-llm-service.com/v1
LLM_MODEL=your-llm-model-name

# 视觉模型配置（用于OCR识别支付凭证）
# 如果不配置，将使用LLM配置
VLM_API_KEY=your_vlm_api_key_here
VLM_BASE_URL=https://api.your-vlm-service.com/v1
VLM_MODEL=your-vlm-model-name

# 邮件配置（163邮箱示例）
EMAIL_IMAP_HOST=imap.163.com
EMAIL_IMAP_PORT=993
EMAIL_SMTP_HOST=smtp.163.com
EMAIL_SMTP_PORT=465
EMAIL_USER=your_email@163.com
EMAIL_PASSWORD=your_email_password_or_auth_code
EMAIL_FOLDER=INBOX

# 注意：163邮箱需要使用授权码（不是登录密码）
# 获取授权码：登录163邮箱 -> 设置 -> POP3/SMTP/IMAP -> 开启服务 -> 获取授权码

# MySQL配置
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DB=auto_email_agent
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password

# 附件存储目录 
ATTACHMENTS_DIR=storage/attachments

# 扫描配置
SCAN_DAYS=120
MAX_EMAILS_PER_RUN=20

# Poppler路径（用于PDF转图片）
# Windows若遇到PDF转换问题，请设置此项
POPPLER_PATH=
```

### 5. 初始化数据库

```bash
mysql -u root -p < core/init_db.sql
```

或手动执行SQL脚本创建数据库和表结构。

### 6. 创建必要的目录

```bash
mkdir -p storage/attachments
mkdir -p logs
```

## 使用方法

### 运行Agent

```bash
cd agent_service/src
python entrypoint.py
```

Agent会自动：
1. 初始化数据库连接池
2. 创建Agent实例（使用配置的LLM）
3. 连接邮箱
4. 扫描未处理的报销邮件
5. 对每封邮件执行完整处理流程
6. 将结果存储到数据库
7. 对于需要补充材料的邮件，自动发送回复邮件

### 处理流程

Agent会按照以下流程处理每封邮件：

1. **读取邮件**: 使用 `process_reimbursement_email` 获取邮件主题、发件人、正文内容、附件列表
2. **下载附件**: 自动下载邮件附件到本地存储
3. **解压ZIP**: 如果附件是ZIP文件，自动解压
4. **解析费用明细**: 使用LLM从邮件正文中提取报销信息（报销人、部门、工具列表、金额等）
5. **OCR识别**: 对图片/PDF附件进行OCR识别，提取支付凭证信息（支持PDF自动转换）
6. **核对内容**: 核对邮件中的费用明细与OCR识别结果是否一致
7. **检查完整性**: 检查材料是否齐全
8. **数据入库**: 将处理结果存储到数据库
9. **发送回复**: 如果材料缺失或不一致，自动生成并发送补充材料邮件

## 数据库表结构

### reimbursements 表（报销主表）

- `id`: 主键
- `email_id`: 邮件唯一ID
- `email_subject`: 邮件主题
- `email_from`: 发件人邮箱
- `email_date`: 邮件日期
- `applicant_name`: 报销人姓名
- `department`: 部门
- `tools_json`: 报销工具列表（JSON格式）
- `total_amount`: 总报销金额
- `currency`: 币种
- `materials_ok`: 材料是否齐全（0/1）
- `reimbursed_done`: 是否已完成报销（0/1）
- `status`: 状态（NEW/READY/NEED_INFO/IGNORED/PROCESSED）
- `issues_json`: 问题列表（JSON格式）
- `last_action`: 最后操作描述
- `email_content`: 邮件正文内容
- `created_at`: 创建时间
- `updated_at`: 更新时间

### attachments 表（附件表）

- `id`: 主键
- `reimbursement_id`: 关联的报销记录ID
- `email_id`: 邮件ID
- `file_name`: 附件文件名
- `file_path`: 附件存储路径
- `file_type`: 文件类型
- `file_size`: 文件大小
- `ocr_result`: OCR识别结果（JSON格式）
- `ocr_status`: OCR状态（PENDING/SUCCESS/FAILED）
- `created_at`: 创建时间
- `updated_at`: 更新时间

## 工具函数说明

### 邮件工具 (tools_email_unified.py)

- `process_reimbursement_email()`: **统一邮件处理工具**
  - 列出未处理的报销邮件
  - 获取指定邮件的详细信息
  - 自动下载附件
  - 自动解压ZIP文件
  - 返回邮件内容和附件信息

### OCR工具 (tools_ocr.py)

- `ocr_receipt()`: 对支付凭证进行OCR识别
  - 支持图片格式：jpg, jpeg, png, gif, bmp, webp
  - 支持PDF格式：自动转换为图片后识别
  - 返回JSON格式的识别结果
  
- `parse_email_expense_table()`: 解析邮件正文中的费用明细
  - 提取报销人、部门、工具列表、金额等信息
  - 返回JSON格式的解析结果

### 核对工具 (tools_reconcile.py)

- `reconcile()`: 核对邮件内容与支付凭证是否一致
  - 核对工具名称、金额、币种、日期等
  - 返回核对结果和问题列表

- `check_material_completeness()`: 检查材料是否齐全
  - 检查每项费用是否有对应的支付凭证
  - 返回材料完整性检查结果

### 数据库工具 (tools_db.py)

- `db_insert_reimbursement()`: 插入或更新报销记录（如果email_id已存在则更新）
- `db_update_reimbursement()`: 更新报销记录
- `db_get_reimbursement()`: 获取报销记录
- `db_delete_reimbursement()`: 删除报销记录
- `db_insert_attachment()`: 插入或更新附件记录（如果email_id和file_name已存在则更新）
- `db_list_pending()`: 列出待处理记录

### 回复工具 (tools_reply.py)

- `draft_reply_email()`: 撰写补充材料邮件草稿
- `send_reply_email()`: 发送回复邮件（通过SMTP，自动设置回复关系）
- `draft_and_send_reply_email()`: **推荐使用** - 撰写并发送补充材料邮件（一步完成）

## 配置说明

### LLM配置

系统支持使用自建LLM或OpenAI兼容API：

- `LLM_API_KEY`: LLM API密钥
- `LLM_BASE_URL`: LLM API基础URL
- `LLM_MODEL`: LLM模型名称

### VLM配置（视觉模型）

用于OCR识别，如果不配置则使用LLM配置：

- `VLM_API_KEY`: 视觉模型API密钥
- `VLM_BASE_URL`: 视觉模型API基础URL
- `VLM_MODEL`: 视觉模型名称

### 邮件配置

支持163邮箱等常见邮箱服务：

- `EMAIL_IMAP_HOST`: IMAP服务器地址
- `EMAIL_IMAP_PORT`: IMAP端口（通常993）
- `EMAIL_SMTP_HOST`: SMTP服务器地址
- `EMAIL_SMTP_PORT`: SMTP端口（通常465）
- `EMAIL_USER`: 邮箱账号
- `EMAIL_PASSWORD`: 邮箱密码或授权码（163邮箱需要使用授权码）

### Poppler配置

仅在使用PDF OCR时需要：

- `POPPLER_PATH`: Poppler工具的bin目录路径（Windows通常需要配置）

## 注意事项

1. **邮件安全**: 确保邮箱账户安全，建议使用应用专用密码或授权码
2. **API限制**: 注意LLM和VLM API的调用频率限制
3. **存储空间**: 附件会存储在本地，注意定期清理
4. **数据库备份**: 建议定期备份数据库
5. **错误处理**: 系统会自动处理常见错误，但建议定期检查日志
6. **PDF支持**: 如果使用PDF OCR，确保已安装Poppler并正确配置路径
7. **日志文件**: 日志文件保存在 `logs/` 目录，按日期分割

## 故障排查

### 邮件连接失败

- 检查邮箱配置是否正确
- 确认IMAP/SMTP服务已启用
- 163邮箱需要使用授权码（不是登录密码）
- 检查防火墙设置

### OCR识别失败

- 确认VLM或LLM API Key有效
- 检查图片/PDF格式是否支持
- 查看错误日志获取详细信息
- PDF转换失败时，检查Poppler是否正确安装和配置

### PDF转换失败

- Windows: 确保已安装Poppler，并在`.env`中设置`POPPLER_PATH`
- Linux/macOS: 确保已安装poppler-utils
- 检查PDF文件是否损坏

### 数据库连接失败

- 确认MySQL服务正在运行
- 检查数据库配置是否正确
- 确认数据库用户权限
- 检查连接池配置

### 模块导入错误

- 确保项目结构完整
- 检查 `utils/logger.py` 是否存在
- 确认所有依赖已正确安装

## 开发说明

项目基于OpenAI Agent SDK构建，采用LLM循环调用工具的方式工作。Agent会根据系统提示词和可用工具，自主决定如何完成任务。

### 系统架构

- **Agent**: 使用OpenAI Agent SDK，支持自建LLM
- **工具系统**: 所有工具使用 `@function_tool` 装饰器注册
- **数据库**: 使用连接池管理MySQL连接
- **日志系统**: 统一的日志记录，支持文件和控制台输出

### 扩展功能

如需扩展功能，可以：

1. 在 `service/` 目录下添加新的工具函数
2. 使用 `@function_tool` 装饰器注册工具
3. 在 `entrypoint.py` 中将新工具注册到Agent
4. 更新系统提示词以指导Agent使用新工具

### 日志系统

日志系统位于 `utils/logger.py`，提供：
- `setup_logger()`: 初始化日志系统
- `get_logger()`: 获取日志记录器
- `log_step()`: 记录处理步骤
- `log_tool_call()`: 记录工具调用

日志文件保存在 `logs/agent_YYYYMMDD.log`，按日期自动分割。

## 许可证

MIT License
