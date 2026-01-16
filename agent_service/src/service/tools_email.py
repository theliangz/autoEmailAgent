#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：autoEmailAgent 
@File    ：tools_email.py
@IDE     ：PyCharm 
@Author  ：liangz
@Date    ：2026/1/12 15:00 
'''
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import os
import zipfile
from typing import List, Dict, Optional, Literal, Annotated
from datetime import datetime, timedelta
import base64
from agents import function_tool
from config import CFG
from core.db import fetchall, fetchone, dumps_json
import ssl

def _get_imap_connection():
    """获取IMAP连接"""
    # context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    # # 163 的服务器不兼容 TLS1.3
    # context.options |= ssl.OP_NO_TLSv1_3
    # # 163 要求较老的 cipher
    # context.set_ciphers("DEFAULT@SECLEVEL=1")
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    # 允许不安全密码套件（解决某些网关握手失败）
    context.set_ciphers('DEFAULT@SECLEVEL=1')
    mail = imaplib.IMAP4_SSL(
        CFG.imap_host,
        CFG.imap_port,
        ssl_context=context
    )
    mail.login(CFG.email_user, CFG.email_password)
    mail.select(CFG.email_folder)
    return mail


def _decode_mime_words(s):
    """解码MIME编码的字符串"""
    if s is None:
        return ""
    decoded_parts = decode_header(s)
    decoded_str = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            if encoding:
                decoded_str += part.decode(encoding)
            else:
                decoded_str += part.decode('utf-8', errors='ignore')
        else:
            decoded_str += part
    return decoded_str

@function_tool
def list_reimbursement_emails(
    # days: Optional[int] = None,
    max_count: Optional[int] = None
) -> str:
    """
    列出指定天数内的未读、且与AI报销相关的邮件
    
    Args:
        days: 扫描天数，默认使用配置中的scan_days
        max_count: 最大返回数量，默认使用配置中的max_emails_per_run
    
    Returns:
        JSON字符串，包含邮件列表
    """
    days = CFG.scan_days
    max_count = max_count or CFG.max_emails_per_run

    mail = _get_imap_connection()

    # 1. 修改搜索条件：增加 UNSEEN (未读)
    # 计算日期范围
    since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")

    # 仅搜索未读邮件，且在日期范围内
    # 注意：Tencent Exmail 对多条件搜索支持较好，UNSEEN 通常不会导致断连
    search_query = f'(UNSEEN SINCE {since_date})'

    status, messages = mail.search(None, search_query)

    if status != 'OK':
        mail.close()
        mail.logout()
        return dumps_json({"error": "搜索邮件失败", "emails": []})

    email_ids = messages[0].split()
    email_ids.reverse()  # 最新邮件优先

    # 2. 获取已处理的邮件ID（保持原有逻辑，防止重复处理）
    processed_emails = set()
    if email_ids:
        # 限制检查范围，避免数据库查询压力
        check_ids = [msg_id.decode() for msg_id in email_ids[:max_count * 3]]
        placeholders = ','.join(['%s'] * len(check_ids))
        existing = fetchall(
            f"SELECT email_id FROM reimbursements WHERE email_id IN ({placeholders})",
            tuple(check_ids)
        )
        processed_emails = {row['email_id'] for row in existing}

    # AI 报销关键词
    search_keywords = ['报销', 'reimbursement', 'AI工具', 'Cursor', 'ChatGPT', 'Claude', 'Gemini', 'OpenAI']

    result_emails = []
    count = 0

    for email_id in email_ids:
        if count >= max_count:
            break

        email_id_str = email_id.decode()

        # 逻辑：如果已处理且状态不是 NEW/NEED_INFO，直接跳过
        if email_id_str in processed_emails:
            existing_record = fetchone("SELECT status FROM reimbursements WHERE email_id = %s", (email_id_str,))
            if existing_record and existing_record['status'] not in ('NEW', 'NEED_INFO'):
                continue

        try:
            # 只获取 Header (Subject/From) 以提高速度
            status, msg_data = mail.fetch(email_id, '(BODY[HEADER.FIELDS (SUBJECT FROM DATE)])')
            if status != 'OK':
                continue

            msg = email.message_from_bytes(msg_data[0][1])
            subject = _decode_mime_words(msg['Subject'])
            from_addr = _decode_mime_words(msg['From'])

            # 3. 严格判定逻辑：必须是报销相关 且 未被正式处理过
            subject_lower = subject.lower()
            from_lower = from_addr.lower()

            is_ai_related = any(kw.lower() in subject_lower or kw.lower() in from_lower
                                for kw in search_keywords)

            if is_ai_related:
                email_date_str = msg['Date']
                email_date = parsedate_to_datetime(email_date_str) if email_date_str else None

                result_emails.append({
                    "email_id": email_id_str,
                    "subject": subject,
                    "from": from_addr,
                    "date": email_date.isoformat() if email_date else None,
                })
                count += 1

        except Exception as e:
            print(f"解析邮件 {email_id_str} 出错: {e}")
            continue

    # 注意：这里不执行 mail.close()，如果后续需要读取附件，可以保持连接或由外部控制
    # 建议在 Runner 结束后统一 logout
    return dumps_json({"emails": result_emails, "count": len(result_emails)})


@function_tool
def get_email(email_id: str) -> str:
    """
    获取指定邮件的详细内容
    
    Args:
        email_id: 邮件ID
    
    Returns:
        JSON字符串，包含邮件详细信息
    """
    mail = _get_imap_connection()
    
    try:
        status, msg_data = mail.fetch(email_id.encode(), '(RFC822)')
        if status != 'OK':
            return dumps_json({"error": "获取邮件失败", "email_id": email_id})
        
        msg = email.message_from_bytes(msg_data[0][1])
        
        # 解析邮件头
        subject = _decode_mime_words(msg['Subject'])
        from_addr = _decode_mime_words(msg['From'])
        to_addr = _decode_mime_words(msg['To'])
        email_date_str = msg['Date']
        email_date = parsedate_to_datetime(email_date_str) if email_date_str else None
        
        # 解析邮件正文
        body_text = ""
        body_html = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if "attachment" not in content_disposition:
                    if content_type == "text/plain":
                        try:
                            body_text = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        except:
                            pass
                    elif content_type == "text/html":
                        try:
                            body_html = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        except:
                            pass
        else:
            content_type = msg.get_content_type()
            if content_type == "text/plain":
                try:
                    body_text = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    pass
            elif content_type == "text/html":
                try:
                    body_html = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    pass
        
        # 获取附件列表
        attachments = []
        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition"))
                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        filename = _decode_mime_words(filename)
                        attachments.append({
                            "filename": filename,
                            "content_type": part.get_content_type(),
                            "size": len(part.get_payload(decode=True)) if part.get_payload(decode=True) else 0
                        })
        
        result = {
            "email_id": email_id,
            "subject": subject,
            "from": from_addr,
            "to": to_addr,
            "date": email_date.isoformat() if email_date else None,
            "body_text": body_text,
            "body_html": body_html,
            "attachments": attachments,
            "attachment_count": len(attachments)
        }
        
        return dumps_json(result)
    
    except Exception as e:
        return dumps_json({"error": f"解析邮件失败: {str(e)}", "email_id": email_id})
    finally:
        mail.close()
        mail.logout()

@function_tool
def download_attachments(
    email_id: str,
    attachment_names: Optional[List[str]] = None
) -> str:
    """
    下载邮件的附件
    
    Args:
        email_id: 邮件ID
        attachment_names: 要下载的附件名称列表，如果为None则下载所有附件
    
    Returns:
        JSON字符串，包含下载结果
    """
    mail = _get_imap_connection()
    
    # 确保附件目录存在
    os.makedirs(CFG.attachments_dir, exist_ok=True)
    email_attach_dir = os.path.join(CFG.attachments_dir, email_id)
    os.makedirs(email_attach_dir, exist_ok=True)
    
    downloaded_files = []
    
    try:
        status, msg_data = mail.fetch(email_id.encode(), '(RFC822)')
        if status != 'OK':
            return dumps_json({"error": "获取邮件失败", "email_id": email_id, "files": []})
        
        msg = email.message_from_bytes(msg_data[0][1])
        
        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition"))
                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        filename = _decode_mime_words(filename)
                        
                        # 如果指定了附件名称列表，只下载匹配的
                        if attachment_names and filename not in attachment_names:
                            continue
                        
                        file_path = os.path.join(email_attach_dir, filename)
                        
                        # 如果文件已存在，跳过
                        if os.path.exists(file_path):
                            downloaded_files.append({
                                "filename": filename,
                                "path": file_path,
                                "status": "exists"
                            })
                            continue
                        
                        # 下载附件
                        try:
                            payload = part.get_payload(decode=True)
                            if payload:
                                with open(file_path, 'wb') as f:
                                    f.write(payload)
                                downloaded_files.append({
                                    "filename": filename,
                                    "path": file_path,
                                    "size": len(payload),
                                    "status": "downloaded"
                                })
                        except Exception as e:
                            downloaded_files.append({
                                "filename": filename,
                                "path": file_path,
                                "status": "failed",
                                "error": str(e)
                            })
        
        return dumps_json({
            "email_id": email_id,
            "files": downloaded_files,
            "count": len(downloaded_files)
        })
    
    except Exception as e:
        return dumps_json({"error": f"下载附件失败: {str(e)}", "email_id": email_id, "files": []})
    finally:
        mail.close()
        mail.logout()


@function_tool
def extract_zip(
    zip_path: str,
    extract_to: Optional[str] = None
) -> str:
    """
    解压ZIP文件
    
    Args:
        zip_path: ZIP文件路径
        extract_to: 解压目标目录，如果为None则解压到ZIP文件所在目录
    
    Returns:
        JSON字符串，包含解压结果
    """
    if not os.path.exists(zip_path):
        return dumps_json({"error": "ZIP文件不存在", "zip_path": zip_path, "files": []})
    
    if extract_to is None:
        extract_to = os.path.dirname(zip_path)
    
    extract_dir = os.path.join(extract_to, os.path.splitext(os.path.basename(zip_path))[0])
    os.makedirs(extract_dir, exist_ok=True)
    
    extracted_files = []
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            file_list = zip_ref.namelist()
            
            for filename in file_list:
                file_path = os.path.join(extract_dir, filename)
                if os.path.isfile(file_path):
                    extracted_files.append({
                        "filename": filename,
                        "path": file_path,
                        "size": os.path.getsize(file_path)
                    })
        
        return dumps_json({
            "zip_path": zip_path,
            "extract_dir": extract_dir,
            "files": extracted_files,
            "count": len(extracted_files)
        })
    
    except Exception as e:
        return dumps_json({"error": f"解压失败: {str(e)}", "zip_path": zip_path, "files": []})


