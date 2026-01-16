#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：autoEmailAgent 
@File    ：settings.py
@IDE     ：PyCharm 
@Author  ：liangz
@Date    ：2026/1/12 14:58 
'''
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=False)
class Config:
    # LLM配置（自建或OpenAI兼容API）
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "gpt-4"
    
    # 视觉模型配置（用于OCR）
    vlm_api_key: str = ""
    vlm_base_url: str = ""
    vlm_model: str = "gpt-4-vision"
    
    # Gemini配置（可选，用于OCR）
    gemini_api_key: str = ""
    
    def __init__(self):
        # LLM配置（自建或OpenAI兼容API）
        self.llm_api_key = os.getenv("LLM_API_KEY", os.getenv("LLM_API_KEY", ""))
        self.llm_base_url = os.getenv("LLM_BASE_URL", os.getenv("LLM_BASE_URL", ""))
        self.llm_model = os.getenv("LLM_MODEL", os.getenv("LLM_MODEL", "gpt-4"))
        
        # 视觉模型配置（用于OCR）
        self.vlm_api_key = os.getenv("VLM_API_KEY", self.llm_api_key)
        self.vlm_base_url = os.getenv("VLM_BASE_URL", self.llm_base_url)
        self.vlm_model = os.getenv("VLM_MODEL", os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4-vision")))
        
        # Gemini配置（可选，用于OCR）
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        
        # 兼容旧配置（向后兼容）
        self.openai_api_key = self.llm_api_key
        self.openai_base_url = self.llm_base_url
        self.openai_model = self.llm_model
        
        # 邮件配置
        self.imap_host = os.getenv("EMAIL_IMAP_HOST", "")
        self.imap_port = int(os.getenv("EMAIL_IMAP_PORT", "993"))
        self.smtp_host = os.getenv("EMAIL_SMTP_HOST", "")
        self.smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "465"))
        self.email_user = os.getenv("EMAIL_USER", "")
        self.email_password = os.getenv("EMAIL_PASSWORD", "")
        self.email_folder = os.getenv("EMAIL_FOLDER", "INBOX")
        
        # MySQL配置
        self.mysql_host = os.getenv("MYSQL_HOST", "127.0.0.1")
        self.mysql_port = int(os.getenv("MYSQL_PORT", "3306"))
        self.mysql_db = os.getenv("MYSQL_DB", "auto_email_agent")
        self.mysql_user = os.getenv("MYSQL_USER", "root")
        self.mysql_password = os.getenv("MYSQL_PASSWORD", "")
        
        # 附件存储目录
        self.attachments_dir = os.getenv("ATTACHMENTS_DIR", "storage/attachments")
        
        # 扫描配置
        self.scan_days = int(os.getenv("SCAN_DAYS", "120"))
        self.max_emails_per_run = int(os.getenv("MAX_EMAILS_PER_RUN", "20"))
        
        # Poppler配置（PDF转图片工具）
        self.poppler_path = os.getenv("POPPLER_PATH", "D:\\tools\Release-25.12.0-0\poppler-25.12.0\Library\\bin")

CFG = Config()
