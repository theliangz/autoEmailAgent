#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：autoEmailAgent 
@File    ：db_client.py
@IDE     ：PyCharm 
@Author  ：liangz
@Date    ：2026/1/12 17:30 
'''
from __future__ import annotations
import json
from mysql.connector import pooling, Error
from typing import Any, Dict, Optional, Tuple, List
from config import CFG


class DatabaseClient:
    """统一的数据库连接管理类（单例模式 + 连接池）"""
    
    _pool: Optional[pooling.MySQLConnectionPool] = None
    _initialized: bool = False
    
    @classmethod
    def initialize(cls, pool_size: int = 5, pool_reset_session: bool = True):
        """
        初始化数据库连接池（在项目启动时调用）
        Args:
            pool_size: 连接池大小，默认5
            pool_reset_session: 是否重置会话，默认True
        """
        if cls._initialized:
            return
        
        try:
            cls._pool = pooling.MySQLConnectionPool(
                pool_name="autoEmailAgentPool",
                pool_size=pool_size,
                host=CFG.mysql_host,
                port=CFG.mysql_port,
                database=CFG.mysql_db,
                user=CFG.mysql_user,
                password=CFG.mysql_password,
                autocommit=True,
                pool_reset_session=pool_reset_session,
                charset='utf8mb4',
                collation='utf8mb4_unicode_ci',
                # 连接超时设置（秒）
                connection_timeout=10,
            )
            cls._initialized = True
            print(f"数据库连接池初始化成功 (pool_size={pool_size})")
        except Error as e:
            print(f"数据库连接池初始化失败: {e}")
            raise
    
    @classmethod
    def get_pool(cls) -> pooling.MySQLConnectionPool:
        """
        获取连接池（如果未初始化则自动初始化）
        
        Returns:
            数据库连接池
        """
        if not cls._initialized:
            cls.initialize()
        if cls._pool is None:
            raise RuntimeError("数据库连接池未初始化，请先调用 DatabaseClient.initialize()")
        return cls._pool
    
    @classmethod
    def get_connection(cls):
        """
        从连接池获取一个连接
        
        Returns:
            数据库连接对象
        """
        pool = cls.get_pool()
        return pool.get_connection()
    
    @classmethod
    def execute(cls, sql: str, params: Tuple[Any, ...] = ()) -> int:
        """
        执行SQL语句（INSERT, UPDATE, DELETE等）
        
        Args:
            sql: SQL语句
            params: 参数元组
        
        Returns:
            受影响的行数
        """
        cnx = cls.get_connection()
        try:
            cur = cnx.cursor()
            cur.execute(sql, params)
            return cur.rowcount
        except Error as e:
            print(f"数据库执行错误: {e}, SQL: {sql[:100]}")
            raise
        finally:
            cur.close()
            cnx.close()
    
    @classmethod
    def fetchone(cls, sql: str, params: Tuple[Any, ...] = ()) -> Optional[Dict[str, Any]]:
        """
        执行SQL查询，返回单条记录
        
        Args:
            sql: SQL查询语句
            params: 参数元组
        
        Returns:
            单条记录字典，如果没有记录则返回None
        """
        cnx = cls.get_connection()
        try:
            cur = cnx.cursor(dictionary=True)
            cur.execute(sql, params)
            return cur.fetchone()
        except Error as e:
            print(f"数据库查询错误: {e}, SQL: {sql[:100]}")
            raise
        finally:
            cur.close()
            cnx.close()
    
    @classmethod
    def fetchall(cls, sql: str, params: Tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
        """
        执行SQL查询，返回所有记录
        
        Args:
            sql: SQL查询语句
            params: 参数元组
        
        Returns:
            记录列表
        """
        cnx = cls.get_connection()
        try:
            cur = cnx.cursor(dictionary=True)
            cur.execute(sql, params)
            return list(cur.fetchall())
        except Error as e:
            print(f"数据库查询错误: {e}, SQL: {sql[:100]}")
            raise
        finally:
            cur.close()
            cnx.close()
    
    @classmethod
    def execute_many(cls, sql: str, params_list: List[Tuple[Any, ...]]) -> int:
        """
        批量执行SQL语句
        
        Args:
            sql: SQL语句
            params_list: 参数列表
        
        Returns:
            受影响的总行数
        """
        cnx = cls.get_connection()
        try:
            cur = cnx.cursor()
            cur.executemany(sql, params_list)
            return cur.rowcount
        except Error as e:
            print(f"数据库批量执行错误: {e}, SQL: {sql[:100]}")
            raise
        finally:
            cur.close()
            cnx.close()
    
    @classmethod
    def test_connection(cls) -> bool:
        """
        测试数据库连接
        
        Returns:
            连接是否成功
        """
        try:
            cnx = cls.get_connection()
            cur = cnx.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
            cnx.close()
            return True
        except Error as e:
            print(f"数据库连接测试失败: {e}")
            return False
    
    @classmethod
    def close_pool(cls):
        """
        关闭连接池（通常在程序退出时调用）
        """
        if cls._pool:
            # MySQL连接池会自动管理连接，这里主要是标记为未初始化
            cls._initialized = False
            cls._pool = None
            print("数据库连接池已关闭")
    
    @staticmethod
    def dumps_json(obj: Any) -> str:
        """
        将对象转换为JSON字符串
        
        Args:
            obj: 要转换的对象
        
        Returns:
            JSON字符串
        """
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

