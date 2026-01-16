#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：autoEmailAgent 
@File    ：logger.py
@IDE     ：PyCharm 
@Author  ：liangz
@Date    ：2026/1/12 19:00 
'''
import logging
import os
from datetime import datetime
from pathlib import Path


def setup_logger(name: str = "autoEmailAgent", log_dir: str = "logs") -> logging.Logger:
    """
    设置日志记录器
    
    Args:
        name: 日志记录器名称
        log_dir: 日志文件目录
    
    Returns:
        配置好的日志记录器
    """
    # 创建日志目录
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # 创建日志记录器
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # 避免重复添加handler
    if logger.handlers:
        return logger
    
    # 创建格式器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 文件处理器（按日期分割）
    log_file = log_path / f"agent_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # 控制台处理器（使用正常输出，不使用错误流）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    # 创建不带颜色的格式器（避免红色输出）
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    
    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# 全局日志记录器
_logger = None


def get_logger() -> logging.Logger:
    """获取全局日志记录器"""
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger


def log_step(step_name: str, details: str = "", level: str = "INFO"):
    """
    记录处理步骤
    
    Args:
        step_name: 步骤名称
        details: 详细信息
        level: 日志级别（INFO, DEBUG, WARNING, ERROR）
    """
    logger = get_logger()
    message = f"[步骤] {step_name}"
    if details:
        message += f": {details}"
    
    if level.upper() == "DEBUG":
        logger.debug(message)
    elif level.upper() == "WARNING":
        logger.warning(message)
    elif level.upper() == "ERROR":
        logger.error(message)
    else:
        logger.info(message)


def log_tool_call(tool_name: str, args: dict = None, result: str = ""):
    """
    记录工具调用
    
    Args:
        tool_name: 工具名称
        args: 工具参数
        result: 工具返回结果（可选，如果太长可以只记录摘要）
    """
    logger = get_logger()
    args_str = ""
    if args:
        # 只记录关键参数，避免日志过长
        args_str = ", ".join([f"{k}={str(v)[:50]}" for k, v in args.items() if k not in ['email_content', 'body_text', 'body_html']])
    
    message = f"[工具调用] {tool_name}"
    if args_str:
        message += f"({args_str})"
    
    logger.info(message)
    
    if result:
        # 只记录结果摘要
        result_summary = result[:200] if len(result) > 200 else result
        logger.debug(f"[工具结果] {tool_name}: {result_summary}")

