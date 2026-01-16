#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：autoEmailAgent 
@File    ：llm_client.py
@IDE     ：PyCharm 
@Author  ：liangz
@Date    ：2026/1/12 17:00 
'''
from typing import Optional, List, Dict, Any
from config import CFG


class LLMClient:
    """统一的LLM和VLM客户端管理类"""
    
    _llm_client = None
    _vlm_client = None
    _use_new_api = True
    
    @classmethod
    def _init_llm_client(cls):
        """初始化LLM客户端"""
        if cls._llm_client is None:
            try:
                from openai import OpenAI
                cls._llm_client = OpenAI(
                    api_key=CFG.llm_api_key,
                    base_url=CFG.llm_base_url if CFG.llm_base_url else None
                )
                cls._use_new_api = True
            except ImportError:
                import openai
                openai.api_key = CFG.llm_api_key
                if CFG.llm_base_url:
                    openai.api_base = CFG.llm_base_url
                cls._llm_client = openai
                cls._use_new_api = False
    
    @classmethod
    def _init_vlm_client(cls):
        """初始化VLM客户端"""
        if cls._vlm_client is None:
            try:
                from openai import OpenAI
                # 使用VLM配置，如果未配置则回退到LLM配置
                vlm_api_key = CFG.vlm_api_key or CFG.llm_api_key
                vlm_base_url = CFG.vlm_base_url or CFG.llm_base_url
                cls._vlm_client = OpenAI(
                    api_key=vlm_api_key,
                    base_url=vlm_base_url if vlm_base_url else None
                )
                cls._use_new_api = True
            except ImportError:
                import openai
                # 使用VLM配置，如果未配置则回退到LLM配置
                vlm_api_key = CFG.vlm_api_key or CFG.llm_api_key
                vlm_base_url = CFG.vlm_base_url or CFG.llm_base_url
                openai.api_key = vlm_api_key
                if vlm_base_url:
                    openai.api_base = vlm_base_url
                cls._vlm_client = openai
                cls._use_new_api = False
    
    @classmethod
    def get_llm_client(cls):
        """获取LLM客户端"""
        cls._init_llm_client()
        return cls._llm_client
    
    @classmethod
    def get_vlm_client(cls):
        """获取VLM客户端"""
        cls._init_vlm_client()
        return cls._vlm_client
    
    @classmethod
    def call_llm(
        cls,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        调用LLM进行文本处理
        
        Args:
            prompt: 提示词
            model: 模型名称，如果为None则使用配置的LLM模型
            temperature: 温度参数
            max_tokens: 最大token数
            **kwargs: 其他参数
        
        Returns:
            LLM返回的文本内容
        """
        cls._init_llm_client()
        model = model or CFG.llm_model
        
        if cls._use_new_api:
            response = cls._llm_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response.choices[0].message.content
        else:
            response = cls._llm_client.ChatCompletion.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response.choices[0].message.content
    
    @classmethod
    def call_vlm(
        cls,
        prompt: str,
        image_path: str,
        model: Optional[str] = None,
        temperature: float = 0,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        调用VLM进行视觉识别（OCR等）
        
        Args:
            prompt: 提示词
            image_path: 图片路径
            model: 模型名称，如果为None则使用配置的VLM模型
            temperature: 温度参数
            max_tokens: 最大token数
            **kwargs: 其他参数
        
        Returns:
            VLM返回的文本内容
        """
        import base64
        from PIL import Image
        
        cls._init_vlm_client()
        model = model or CFG.vlm_model or CFG.llm_model or "gpt-4o"
        
        # 编码图片
        with open(image_path, 'rb') as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        
        if cls._use_new_api:
            response = cls._vlm_client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response.choices[0].message.content
        else:
            response = cls._vlm_client.ChatCompletion.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            return response.choices[0].message.content
    
    @classmethod
    def is_new_api(cls) -> bool:
        """检查是否使用新API"""
        return cls._use_new_api
