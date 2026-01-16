#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：autoEmailAgent 
@File    ：entrypoint.py
@IDE     ：PyCharm 
@Author  ：liangz
@Date    ：2026/1/12 14:24 
'''
import os
import sys
import atexit

from openai import AsyncOpenAI

# 添加src目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agents import Agent, Runner, set_default_openai_client, ModelSettings, set_default_openai_api, \
    set_tracing_disabled
from core.db_client import DatabaseClient
from agent_service.src.utils.logger import setup_logger, log_step
from service.tools_email_unified import process_reimbursement_email
from service.tools_ocr import ocr_receipt, parse_email_expense_table
from service.tools_reconcile import reconcile, check_material_completeness
from service.tools_db import (
    db_insert_reimbursement, db_update_reimbursement, db_get_reimbursement,
    db_insert_attachment, db_list_pending, db_delete_reimbursement
)
from service.tools_reply import draft_reply_email, draft_and_send_reply_email, send_reply_email


SYSTEM_INSTRUCTIONS = """
你是 autoEmailAgent，一个只处理"公司 AI 工具报销邮件"的自动化助手。
你的工作完全通过可用工具完成；除非需要给报销人发补充材料邮件，否则不要输出自然语言总结给用户。

处理规则：
1) 只处理与AI工具订阅/充值相关的报销：例如 Cursor、ChatGPT Plus、OpenAI/ChatGPT、Claude、Gemini 等。非此类邮件标记为 IGNORED 并入库记录原因。
2) 对每封邮件必须完成：
   - 使用 process_reimbursement_email 获取待处理邮件
   - 使用 process_reimbursement_email 根据获取的待处理邮件id获取邮件内容、下载附件、自动解压ZIP
   - 使用 parse_email_expense_table 解析邮件正文中的费用明细
   - 使用 ocr_receipt 对下载的图片附件进行OCR识别
   - 使用 reconcile 核对邮件费用明细与OCR识别结果
   - 使用 check_material_completeness 检查材料是否齐全
   - 使用 db_insert_reimbursement 或 db_update_reimbursement 写入或更新 MySQL 主表
   - 使用 db_insert_attachment 写入附件记录
3) 根据核对结果判断处理方式：
   a) 若材料齐全且核对通过：直接调用 db_insert_reimbursement 或 db_update_reimbursement，设置 status=READY，materials_ok=1，reimbursed_done=0（是否完成报销由后续工具或人工流程更新），无需发送邮件
   b) 若材料缺失或不一致：先调用 db_insert_reimbursement 或 db_update_reimbursement，设置 status=NEED_INFO，materials_ok=0，reimbursed_done=0，然后调用工具撰写并发送补充材料回复邮件（自动通过SMTP发送，使用IMAP获取原邮件信息以正确设置回复关系）
5) 所有关键结论必须写入数据库字段（issues_json、last_action 等），不要只写在对话里。
6) 优先少调用模型，多用工具获取确定信息；无法确定时，发补充材料邮件。
7) 报销以邮件正文内容为依据，附件为证明材料，邮件正文报销的AI工具均需要提供对应附件
8) 关于币种：以附件中币种为准，若邮件正文与附件中币种不一致，则生成回复邮件要求更正邮件正文内容与附件中币种保持一致；
"""
os.environ["MOONSHOT_API_KEY"] = "sk-HA5wnPhgit2HvlxenyQEr9H0rsziKbblOAodCsmr3PxvJe7n"
os.environ["MOONSHOT_API_BASE"] = "https://api.moonshot.cn/v1"

def create_agent():
    print("初始化自建 LLM Client...")

    # if not CFG.llm_api_key or not CFG.llm_base_url:

    #     raise RuntimeError("必须配置 LLM_API_KEY 和 LLM_BASE_URL")
    #
    # # 创建 OpenAI-compatible client
    # custom_client = AsyncOpenAI(
    #     api_key=CFG.llm_api_key,
    #     base_url=CFG.llm_base_url
    # )
    custom_client = AsyncOpenAI(
        api_key=os.environ["MOONSHOT_API_KEY"],
        base_url=os.environ["MOONSHOT_API_BASE"]
    )
    set_default_openai_client(client=custom_client, use_for_tracing=False)
    set_default_openai_api("chat_completions")
    set_tracing_disabled(disabled=True)



    # print(f"Agent LLM → {CFG.llm_base_url} | model = {CFG.llm_model}")

    # 3️ 创建 Agent
    agent = Agent(
        name="autoEmailAgent",
        instructions=SYSTEM_INSTRUCTIONS,
        # model=CFG.llm_model,
        model="litellm/moonshot/kimi-k2-turbo-preview",
        tools=[
            # 邮件处理（合并工具）
            process_reimbursement_email,
            # 解析工具
            parse_email_expense_table, ocr_receipt,
            # 核对工具
            check_material_completeness, reconcile,
            # 数据库工具
            db_insert_reimbursement, db_update_reimbursement, db_get_reimbursement,
            db_delete_reimbursement, db_insert_attachment, db_list_pending,
            # 回复工具
            draft_reply_email, send_reply_email,
        ],

        model_settings=ModelSettings(
            temperature=0,
            max_tokens=20000,
            parallel_tool_calls=True
        )
    )
    return agent
# 延迟创建agent，确保配置已加载
agent = None

def main():
    global agent
    # 初始化日志系统
    logger = setup_logger()
    log_step("系统启动", "开始初始化autoEmailAgent")
    # 初始化数据库连接池
    try:
        log_step("数据库初始化", "正在初始化连接池...")
        DatabaseClient.initialize(pool_size=5)
        # 测试连接
        if not DatabaseClient.test_connection():
            logger.warning("数据库连接测试失败，但继续运行...")
            log_step("数据库初始化", "连接测试失败，但继续运行", "WARNING")
        else:
            # logger.info("数据库连接池初始化成功")
            log_step("数据库初始化", "连接池初始化成功")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}", exc_info=True)
        log_step("数据库初始化", f"初始化失败: {e}", "ERROR")
        return
    
    # 注册退出时关闭连接池
    atexit.register(DatabaseClient.close_pool)
    
    # 创建Agent
    try:
        log_step("Agent创建", "正在创建Agent实例...")
        agent = create_agent()
        # logger.info("Agent创建成功")
        log_step("Agent创建", "Agent创建成功")
    except Exception as e:
        logger.error(f"Agent创建失败: {e}", exc_info=True)
        log_step("Agent创建", f"创建失败: {e}", "ERROR")
        return
    
    # 触发一次"批处理任务"——让agent自行循环处理（LLM loop）
    task = """
            连接邮箱后，处理所有未入库或status=NEW的"AI工具报销邮件"：
            - 对每封邮件：读取->解析费用表->下载/解压附件->OCR->核对->入库/更新
            - 对缺材料或不一致的：生成补充材料邮件并直接发送回复邮件、更新DB状态（报销表和附件表）
            - 材料齐全：无需回复邮件，更新DB状态即可。
            - 处理完成后停止
            """
    
    try:
        log_step("任务开始", "开始执行批处理任务")
        logger.info(f"任务内容: {task.strip()}")
        
        # 使用run_sync并捕获中间输出
        result = Runner.run_sync(
            agent, 
            task, 
            max_turns=50,
        )
        
        # 输出最终结果
        log_step("任务完成", "批处理任务执行完成")
        logger.info("=" * 80)
        logger.info("最终输出:")
        logger.info(result.final_output if result.final_output else "无输出")
        logger.info("=" * 80)
        
        print("\n" + "=" * 80)
        print("最终输出:")
        print(result.final_output if result.final_output else "无输出")
        print("=" * 80)
        
    except Exception as e:
        logger.error(f"任务执行失败: {e}", exc_info=True)
        log_step("任务失败", f"执行失败: {e}", "ERROR")
    finally:
        # 确保关闭连接池
        log_step("系统关闭", "正在关闭数据库连接池...")
        DatabaseClient.close_pool()
        logger.info("程序结束")

if __name__ == "__main__":
    main()


