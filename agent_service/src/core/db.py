#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：autoEmailAgent 
@File    ：db.py
@IDE     ：PyCharm 
@Author  ：liangz
@Date    ：2026/1/12 14:59 
'''
# 向后兼容：导出DatabaseClient的方法作为函数
from core.db_client import DatabaseClient

# 导出函数接口（保持向后兼容）
def get_pool():
    """获取连接池（向后兼容函数）"""
    return DatabaseClient.get_pool()

def execute(sql: str, params=()) -> int:
    """执行SQL语句（向后兼容函数）"""
    return DatabaseClient.execute(sql, params)

def fetchone(sql: str, params=()):
    """获取单条记录（向后兼容函数）"""
    return DatabaseClient.fetchone(sql, params)

def fetchall(sql: str, params=()):
    """获取所有记录（向后兼容函数）"""
    return DatabaseClient.fetchall(sql, params)

def dumps_json(obj):
    """JSON序列化（向后兼容函数）"""
    return DatabaseClient.dumps_json(obj)
