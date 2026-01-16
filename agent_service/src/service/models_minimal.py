#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：autoEmailAgent 
@File    ：models_minimal.py
@IDE     ：PyCharm 
@Author  ：liangz
@Date    ：2026/1/12 16:00 
'''
"""
最小化的模型定义
由于工具函数都返回JSON字符串，不使用Pydantic模型进行验证，
这些模型仅作为类型定义和文档说明使用
"""
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

# Pydantic v2 配置
_model_config = ConfigDict(extra='ignore', strict=False)


# class OCRResult(BaseModel):
#     """OCR识别结果"""
#     model_config = _model_config
#     tool_name: Optional[str] = None
#     amount: Optional[float] = None
#     currency: Optional[str] = None
#     date: Optional[str] = None
#     raw_text: str = ""

