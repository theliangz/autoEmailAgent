#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：autoEmailAgent 
@File    ：tools_email_unified.py
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
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from agents import function_tool
from config import CFG
from core.db import fetchall, fetchone, dumps_json
from utils.logger import get_logger, log_step, log_tool_call
import ssl


def _get_imap_connection():
    """获取IMAP连接"""
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
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
def process_reimbursement_email(
    email_id: Optional[str] = None,
    max_count: Optional[int] = None,
    download_attachments: bool = True,
    extract_zips: bool = True
) -> str:
    """
    处理报销邮件：列出邮件、获取内容、下载附件、解压ZIP文件
    
    如果提供email_id，则处理指定邮件；否则列出并处理未处理的报销邮件。
    
    Args:
        email_id: 邮件ID（可选），如果提供则处理指定邮件，否则列出未处理的邮件
        max_count: 最大处理邮件数量（仅在email_id为None时有效），默认使用配置中的max_emails_per_run
        download_attachments: 是否下载附件，默认True
        extract_zips: 是否自动解压ZIP文件，默认True
    
    Returns:
        JSON字符串，包含邮件信息和处理结果
    """
    logger = get_logger()
    log_tool_call("process_reimbursement_email", {
        "email_id": email_id,
        "max_count": max_count,
        "download_attachments": download_attachments,
        "extract_zips": extract_zips
    })
    
    mail = _get_imap_connection()
    
    try:
        if email_id:
            # 处理指定邮件
            log_step("邮件处理", f"开始处理邮件: {email_id}")
            result = _process_single_email(mail, email_id, download_attachments, extract_zips)
            log_step("邮件处理完成", f"邮件 {email_id} 处理完成")
            log_step(f"邮件 {email_id} 处理结果：{result}")
            return result
        else:
            # 列出并处理未处理的邮件
            log_step("邮件列表", "开始列出未处理的报销邮件")
            result = _list_and_process_emails(mail, max_count, download_attachments, extract_zips)
            log_step("邮件列表完成", "邮件列表获取完成")
            log_step(f"待处理邮件列表：{result}")
            return result
    finally:
        mail.close()
        mail.logout()


def _process_single_email(mail, email_id: str, download_attachments: bool, extract_zips: bool) -> str:
    """处理单个邮件"""
    try:
        # 获取邮件完整内容
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
        
        # 获取邮件Message-ID等信息（用于回复邮件）
        message_id = msg.get('Message-ID', '')
        references = msg.get('References', '')
        
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
        
        # 获取附件信息并下载
        attachments_info = []
        downloaded_files = []
        extracted_files = []
        
        if download_attachments:
            # 确保附件目录存在
            os.makedirs(CFG.attachments_dir, exist_ok=True)
            email_attach_dir = os.path.join(CFG.attachments_dir, email_id)
            os.makedirs(email_attach_dir, exist_ok=True)
            
            if msg.is_multipart():
                for part in msg.walk():
                    content_disposition = str(part.get("Content-Disposition"))
                    if "attachment" in content_disposition:
                        filename = part.get_filename()
                        if filename:
                            filename = _decode_mime_words(filename)
                            content_type = part.get_content_type()
                            payload = part.get_payload(decode=True)
                            size = len(payload) if payload else 0
                            
                            attachments_info.append({
                                "filename": filename,
                                "content_type": content_type,
                                "size": size
                            })
                            
                            # 下载附件
                            file_path = os.path.join(email_attach_dir, filename)
                            
                            if os.path.exists(file_path):
                                downloaded_files.append({
                                    "filename": filename,
                                    "path": file_path,
                                    "status": "exists"
                                })
                            else:
                                try:
                                    if payload:
                                        with open(file_path, 'wb') as f:
                                            f.write(payload)
                                        downloaded_files.append({
                                            "filename": filename,
                                            "path": file_path,
                                            "size": size,
                                            "status": "downloaded"
                                        })
                                        
                                        # 如果是ZIP文件且需要解压
                                        if extract_zips and filename.lower().endswith('.zip'):
                                            extracted = _extract_zip_file(file_path)
                                            if extracted:
                                                extracted_files.extend(extracted)
                                except Exception as e:
                                    downloaded_files.append({
                                        "filename": filename,
                                        "path": file_path,
                                        "status": "failed",
                                        "error": str(e)
                                    })
        
        result = {
            "email_id": email_id,
            "subject": subject,
            "from": from_addr,
            "to": to_addr,
            "date": email_date.isoformat() if email_date else None,
            "body_text": body_text,
            #"body_html": body_html,
            "attachments": attachments_info,
            "attachment_count": len(attachments_info),
            "downloaded_files": downloaded_files,
            "extracted_files": extracted_files,
            "message_id": message_id,  # 用于回复邮件
            "references": references   # 用于回复邮件
        }
        
        return dumps_json(result)
    
    except Exception as e:
        return dumps_json({"error": f"处理邮件失败: {str(e)}", "email_id": email_id})


def _list_and_process_emails(mail, max_count: Optional[int], download_attachments: bool, extract_zips: bool) -> str:
    """列出并处理未处理的邮件"""
    days = CFG.scan_days
    max_count = max_count or CFG.max_emails_per_run
    
    # 计算日期范围
    since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
    
    # 搜索未读邮件
    search_query = f'(UNSEEN SINCE {since_date})'
    status, messages = mail.search(None, search_query)
    
    if status != 'OK':
        return dumps_json({"error": "搜索邮件失败", "emails": []})
    
    email_ids = messages[0].split()
    email_ids.reverse()  # 最新邮件优先
    
    # 获取已处理的邮件ID
    processed_emails = set()
    if email_ids:
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
        
        # 数据库查询 跳过已处理且状态不是NEW/NEED_INFO的邮件
        if email_id_str in processed_emails:
            existing_record = fetchone("SELECT status FROM reimbursements WHERE email_id = %s", (email_id_str,))
            if existing_record and existing_record['status'] not in ('NEW', 'NEED_INFO'):
                continue
        
        try:
            # 只获取Header进行初步筛选
            status, msg_data = mail.fetch(email_id, '(BODY[HEADER.FIELDS (SUBJECT FROM DATE)])')
            if status != 'OK':
                continue
            
            msg = email.message_from_bytes(msg_data[0][1])
            subject = _decode_mime_words(msg['Subject'])
            from_addr = _decode_mime_words(msg['From'])
            
            # 检查是否与AI报销相关
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
    
    return dumps_json({"emails": result_emails, "count": len(result_emails)})


def _extract_zip_file(zip_path: str) -> List[Dict]:
    """解压ZIP文件，返回解压的文件列表"""
    if not os.path.exists(zip_path):
        return []
    
    extract_dir = os.path.join(os.path.dirname(zip_path), os.path.splitext(os.path.basename(zip_path))[0])
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
    except Exception as e:
        logger = get_logger()
        logger.warning(f"解压ZIP文件失败: {e}")
        return []
    
    return extracted_files

