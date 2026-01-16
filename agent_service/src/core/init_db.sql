-- 初始化数据库表结构
CREATE DATABASE IF NOT EXISTS auto_email_agent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE auto_email_agent;

-- 报销邮件主表
CREATE TABLE IF NOT EXISTS reimbursements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email_id VARCHAR(255) NOT NULL COMMENT '邮件唯一ID',
    email_subject VARCHAR(500) COMMENT '邮件主题',
    email_from VARCHAR(255) NOT NULL COMMENT '发件人邮箱',
    email_date DATETIME COMMENT '邮件日期',
    applicant_name VARCHAR(100) COMMENT '报销人姓名',
    department VARCHAR(100) COMMENT '部门',
    tools_json JSON COMMENT '报销工具列表，格式：[{"name":"Cursor","amount":192.00,"currency":"USD","date":"2025-12-18"}]',
    total_amount DECIMAL(10, 2) COMMENT '总报销金额',
    currency VARCHAR(10) DEFAULT 'USD' COMMENT '币种',
    materials_ok TINYINT(1) DEFAULT 0 COMMENT '报销材料是否齐全无误：0-否，1-是',
    reimbursed_done TINYINT(1) DEFAULT 0 COMMENT '是否已完成报销：0-否，1-是',
    status VARCHAR(20) DEFAULT 'NEW' COMMENT '状态：NEW-新邮件，READY-材料齐全，NEED_INFO-需要补充材料，IGNORED-已忽略，PROCESSED-已处理',
    issues_json JSON COMMENT '问题列表，格式：["缺少ChatGPT支付凭证","金额不一致"]',
    last_action VARCHAR(500) COMMENT '最后操作描述',
    email_content TEXT COMMENT '邮件正文内容',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_email_id (email_id),
    KEY idx_status (status),
    KEY idx_applicant (applicant_name),
    KEY idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报销邮件主表';

-- 附件表
CREATE TABLE IF NOT EXISTS attachments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    reimbursement_id INT NOT NULL COMMENT '关联的报销记录ID',
    email_id VARCHAR(255) NOT NULL COMMENT '邮件ID',
    file_name VARCHAR(500) NOT NULL COMMENT '附件文件名',
    file_path VARCHAR(1000) COMMENT '附件存储路径',
    file_type VARCHAR(50) COMMENT '文件类型：image/jpeg, application/pdf, application/zip等',
    file_size BIGINT COMMENT '文件大小（字节）',
    ocr_result JSON COMMENT 'OCR识别结果',
    ocr_status VARCHAR(20) DEFAULT 'PENDING' COMMENT 'OCR状态：PENDING-待处理，SUCCESS-成功，FAILED-失败',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY idx_reimbursement_id (reimbursement_id),
    KEY idx_email_id (email_id),
    KEY idx_ocr_status (ocr_status),
    FOREIGN KEY (reimbursement_id) REFERENCES reimbursements(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='附件表';

