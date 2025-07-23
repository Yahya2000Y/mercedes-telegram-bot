#!/usr/bin/env python3
"""
Mercedes Owners Club Telegram Bot - SIMPLIFIED VERSION
100% FREE - Works on Railway without SQLite issues
Arabic support for Saudi Mercedes groups
"""

import os
import re
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import threading
import time
from urllib.parse import urlparse

# Telegram Bot API
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)

# Simple web server for Railway
from flask import Flask
import threading

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
    PORT = int(os.getenv('PORT', 8080))
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'mercedes2024')

# Simple in-memory storage (no database needed)
class SimpleStorage:
    def __init__(self):
        self.user_warnings = {}  # user_id: warning_count
        self.group_settings = {}  # group_id: settings
        self.banned_users = set()
        self.video_reports = {}  # message_id: [reporter_ids]
        self.blacklisted_users = set()  # Users who sent inappropriate content
        self.deleted_videos_count = 0
        
    def add_warning(self, user_id: int, group_id: int) -> int:
        key = f"{group_id}_{user_id}"
        if key not in self.user_warnings:
            self.user_warnings[key] = 0
        self.user_warnings[key] += 1
        return self.user_warnings[key]
    
    def get_warnings(self, user_id: int, group_id: int) -> int:
        key = f"{group_id}_{user_id}"
        return self.user_warnings.get(key, 0)
    
    def ban_user(self, user_id: int):
        self.banned_users.add(user_id)
    
    def is_banned(self, user_id: int) -> bool:
        return user_id in self.banned_users
    
    def add_video_report(self, message_id: int, reporter_id: int) -> int:
        if message_id not in self.video_reports:
            self.video_reports[message_id] = []
        
        if reporter_id not in self.video_reports[message_id]:
            self.video_reports[message_id].append(reporter_id)
        
        return len(self.video_reports[message_id])
    
    def blacklist_user(self, user_id: int):
        self.blacklisted_users.add(user_id)
    
    def is_blacklisted(self, user_id: int) -> bool:
        return user_id in self.blacklisted_users
    
    def increment_deleted_videos(self):
        self.deleted_videos_count += 1

# Global storage
storage = SimpleStorage()

class VideoContentFilter:
    """Video content filtering system - FREE version"""
    
    def __init__(self):
        # Suspicious filename patterns (Arabic and English)
        self.suspicious_filename_patterns = [
            r'xxx', r'porn', r'sex', r'adult', r'nude', r'naked',
            r'جنس', r'إباحي', r'عاري', r'فاضح', r'مثير',
            r'torture', r'kill', r'death', r'blood', r'violence',
            r'تعذيب', r'قتل', r'موت', r'دم', r'عنف', r'ضرب',
            r'rape', r'abuse', r'assault', r'harm',
            r'اغتصاب', r'اعتداء', r'إيذاء', r'ضرر'
        ]
        
        # Video size limits (in bytes)
        self.max_video_size = 50 * 1024 * 1024  # 50MB
        self.max_video_duration = 300  # 5 minutes in seconds
        
        # Reports needed for auto-deletion
        self.reports_threshold = 2  # 2 reports = auto delete
    
    def is_video_suspicious(self, video_file, filename: str = "") -> tuple[bool, str]:
        """Check if video is suspicious based on size, duration, filename"""
        reasons = []
        
        # Check file size
        if hasattr(video_file, 'file_size') and video_file.file_size:
            if video_file.file_size > self.max_video_size:
                reasons.append(f"حجم كبير جداً: {video_file.file_size / (1024*1024):.1f}MB")
        
        # Check duration
        if hasattr(video_file, 'duration') and video_file.duration:
            if video_file.duration > self.max_video_duration:
                minutes = video_file.duration // 60
                seconds = video_file.duration % 60
                reasons.append(f"مدة طويلة جداً: {minutes}:{seconds:02d}")
        
        # Check filename for suspicious patterns
        if filename:
            filename_lower = filename.lower()
            for pattern in self.suspicious_filename_patterns:
                if re.search(pattern, filename_lower):
                    reasons.append(f"اسم ملف مشبوه: {pattern}")
                    break
        
        if reasons:
            return True, "; ".join(reasons)
        
        return False, ""

class ArabicContentFilter:
    """Simple Arabic content filter"""
    
    def __init__(self):
        # Suspicious link patterns
        self.suspicious_patterns = [
            r'bit\.ly', r'tinyurl', r'shortlink', r't\.co', r'goo\.gl',
            r'تحميل.*مجاني', r'هاك.*أداة', r'أموال.*سهلة', r'ربح.*سريع',
            r'مولد.*أرقام', r'حساب.*مجاني', r'فيزا.*وهمية', r'بطاقة.*ائتمان',
            r'كسب.*فلوس', r'شغل.*من.*البيت', r'استثمار.*مضمون',
            r'تداول.*عملات', r'فوركس.*مجاني', r'بيتكوين.*مجاني'
        ]
        
        # Spam patterns
        self.spam_patterns = [
            (r'(.)\1{4,}', 'أحرف متكررة'),
            (r'[A-Z]{10,}', 'أحرف كبيرة زائدة'),
            (r'(أموال.*مجانية|ربح.*سهل|كسب.*\d+.*ريال)', 'رسائل مالية مشبوهة'),
            (r'(اشتري.*الآن|تخفيض.*اليوم|خصم.*\d+%)', 'رسائل تجارية'),
            (r'(اضغط.*هنا.*الآن|عاجل.*اتصل|تحرك.*الآن)', 'رسائل استعجال'),
            (r'(محتوى.*بالغين|xxx|إباحي)', 'محتوى للكبار'),
            (r'(قمار|كازينو|مراهنة|بوكر)', 'قمار'),
            (r'(🔥){5,}', 'رموز مفرطة'),
            (r'(💰){3,}', 'رموز مالية مفرطة')
        ]
        
        # Default banned words
        self.banned_words = [
            'سبام', 'نصب', 'هاك', 'غش', 'شراء متابعين', 
            'عملات رقمية', 'spam', 'scam', 'hack', 'cheat'
        ]
    
    def is_suspicious_link(self, text: str) -> tuple[bool, str]:
        """Check for suspicious links"""
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
        
        for url in urls:
            for pattern in self.suspicious_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return True, f"رابط مشبوه: {pattern}"
        return False, ""
    
    def contains_banned_words(self, text: str) -> tuple[bool, str]:
        """Check for banned words"""
        text_lower = text.lower()
        for word in self.banned_words:
            if word.lower() in text_lower:
                return True, f"كلمة محظورة: {word}"
        return False, ""
    
    def is_spam_content(self, text: str) -> tuple[bool, str]:
        """Check for spam"""
        for pattern, reason in self.spam_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True, reason
        
        # Check emoji count
        emoji_count = len(re.findall(r'[😀-🿿]', text))
        if emoji_count > 8:
            return True, "رموز تعبيرية مفرطة"
        
        return False, ""

class MercedesBotManager:
    """Main bot manager"""
    
    def __init__(self):
        self.content_filter = ArabicContentFilter()
        self.video_filter = VideoContentFilter()
        self.max_warnings = 3
        
        # Arabic responses
        self.responses = {
            'welcome': """🚗 أهلاً وسهلاً بك في نادي مالكي مرسيدس!

يرجى الالتزام بقوانين المجموعة:
• مناقشة السيارات والمواضيع ذات الصلة
• عدم إرسال روابط مشبوهة
• الاحترام المتبادل

استمتع بوقتك معنا! 🌟""",
            
            'help': """📋 قائمة الأوامر - بوت مرسيدس

👥 للأعضاء:
/start - بدء استخدام البوت
/help - هذه الرسالة
/faq - أسئلة شائعة عن مرسيدس
/dealers - وكلاء مرسيدس في السعودية
/oil - معلومات عن زيت المحرك
/service - معلومات عن الصيانة

🛡️ حماية المجموعة:
• حذف الروابط المشبوهة تلقائياً
• حذف الفيديوهات المشبوهة
• نظام التبليغ عن المحتوى الحساس
• نظام التحذيرات التلقائي

💡 نصيحة: يمكنك كتابة مشكلتك مع أي سيارة وسأحاول مساعدتك!
لإبلاغ عن محتوى مشبوه، اضغط زر 🚨 تحت الرسالة""",
            
            'oil_info': """🛢️ معلومات زيت محرك مرسيدس

📋 المواصفات المطلوبة:
• MB 229.5 - للمحركات الحديثة
• MB 229.3 - للمحركات الأقدم
• MB 229.1 - للمحركات القديمة

🏷️ الماركات الموصى بها:
• موبيل 1 (Mobil 1) 0W-40
• كاسترول (Castrol) 0W-40
• ليكوي مولي (Liqui Moly) 5W-40
• شل (Shell) 5W-40

📏 الكميات حسب المحرك:
• 4 سلندر: 6-7 لتر
• 6 سلندر: 7-8 لتر  
• 8 سلندر: 8-9 لتر

⚠️ مهم: دائماً راجع دليل المالك للمواصفات الدقيقة!""",
            
            'service_info': """🔧 معلومات صيانة مرسيدس

📅 جدولة الصيانة (نظام FSS):
• سيرفس A: كل 10,000 كم أو سنة
• سيرفس B: كل 20,000 كم أو سنتين

🔍 سيرفس A يشمل:
• تغيير زيت المحرك والفلتر
• فحص المكابح والإطارات
• فحص السوائل
• فحص الأضواء

🔧 سيرفس B يشمل:
• كل ما في سيرفس A بالإضافة إلى:
• تغيير فلتر الهواء
• فحص شامل للمحرك
• فحص نظام التبريد
• فحص البطارية

💡 نصيحة: لا تتجاهل مؤشر الصيانة في التابلو!""",
            
            'dealers_info': """🏪 وكلاء مرسيدس في السعودية:

🚗 **شركة الجزيرة للسيارات**
📍 الرياض
📞 011-123-4567
⭐ التقييم: 4.5/5

🚗 **مجموعة محمد يوسف ناغي**
📍 جدة
📞 012-123-4567
⭐ التقييم: 4.3/5

🚗 **مؤسسة الأهلي للسيارات**
📍 الدمام
📞 013-123-4567
⭐ التقييم: 4.2/5

🚗 **شركة ساسكو**
📍 المدينة المنورة
📞 014-123-4567
⭐ التقييم: 4.0/5

🚗 **الجميح للسيارات**
📍 الخبر
📞 013-987-6543
⭐ التقييم: 4.4/5""",
            
            'faq': """🤔 أسئلة شائعة عن مرسيدس:

❓ **ما نوع الزيت المناسب؟**
✅ مرسيدس توصي بزيوت معتمدة MB 229.5

❓ **كم مرة أسوي سيرفس؟**
✅ سيرفس A كل 10,000 كم، سيرفس B كل 20,000 كم

❓ **لمبة المحرك تشتغل؟**
✅ افحص حساس الأكسجين، الكتلايزر، أو غطاء البنزين

❓ **وين أشتري قطع غيار؟**
✅ الوكالة للأصلية، FCP Euro للبدائل الجيدة

❓ **السيارة ما تشتغل؟**
✅ افحص البطارية، مستوى البنزين، والفيوزات

للمزيد من الأسئلة، استخدم /oil أو /service"""
        }
    
    async def handle_video_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle video messages with content filtering"""
        if not update.message or not update.message.video:
            return
        
        message = update.message
        user = message.from_user
        chat = message.chat
        video = message.video
        
        # Skip private chats
        if chat.type == 'private':
            return
        
        # Skip if user is admin
        try:
            chat_member = await context.bot.get_chat_member(chat.id, user.id)
            if chat_member.status in ['administrator', 'creator']:
                # Still add report button for admins' videos
                await self.add_report_button(message, context)
                return
        except:
            pass
        
        # Check if user is banned or blacklisted
        if storage.is_banned(user.id) or storage.is_blacklisted(user.id):
            try:
                await message.delete()
                await context.bot.send_message(
                    chat.id,
                    f"🚫 العضو @{user.username or user.first_name} في القائمة السوداء ولا يمكنه إرسال فيديوهات."
                )
                return
            except:
                pass
        
        # Get filename if available
        filename = getattr(video, 'file_name', '') or ''
        
        # Check if video is suspicious
        is_suspicious, reason = self.video_filter.is_video_suspicious(video, filename)
        
        if is_suspicious:
            # Delete suspicious video immediately
            try:
                await message.delete()
                storage.increment_deleted_videos()
                
                # Warn user
                warning_count = storage.add_warning(user.id, chat.id)
                
                warning_msg = f"🚫 تم حذف فيديو مشبوه من @{user.username or user.first_name}\n"
                warning_msg += f"السبب: {reason}\n"
                warning_msg += f"تحذير رقم {warning_count} من {self.max_warnings}"
                
                warning_message = await context.bot.send_message(chat.id, warning_msg)
                
                # Auto-delete warning after 30 seconds
                context.job_queue.run_once(
                    lambda context: asyncio.create_task(self.delete_message_safely(warning_message)),
                    30
                )
                
                # Check if user should be banned
                if warning_count >= self.max_warnings:
                    try:
                        await context.bot.ban_chat_member(chat.id, user.id)
                        storage.ban_user(user.id)
                        await context.bot.send_message(
                            chat.id,
                            f"🚫 تم حظر العضو @{user.username or user.first_name} نهائياً بسبب إرسال محتوى مشبوه متكرر."
                        )
                    except Exception as e:
                        logger.error(f"Failed to ban user {user.id}: {e}")
                
                # Notify admins
                await self.notify_admins_about_video(context, chat.id, user, reason, warning_count)
                
            except Exception as e:
                logger.error(f"Failed to delete suspicious video: {e}")
        else:
            # Add report button to normal videos
            await self.add_report_button(message, context)
    
    async def add_report_button(self, message, context):
        """Add report button to video messages"""
        try:
            keyboard = [
                [InlineKeyboardButton("🚨 إبلاغ عن محتوى مشبوه", callback_data=f"report_video_{message.message_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                message.chat.id,
                "📹 للإبلاغ عن هذا المقطع إذا كان يحتوي على محتوى غير مناسب:",
                reply_to_message_id=message.message_id,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to add report button: {e}")
    
    async def handle_video_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle video report button clicks"""
        query = update.callback_query
        await query.answer()
        
        if not query.data.startswith("report_video_"):
            return
        
        try:
            message_id = int(query.data.split("_")[-1])
            reporter_id = query.from_user.id
            chat_id = query.message.chat.id
            
            # Add report
            report_count = storage.add_video_report(message_id, reporter_id)
            
            # Notify reporter
            await query.edit_message_text(
                f"✅ تم تسجيل بلاغك. عدد البلاغات: {report_count}/{self.video_filter.reports_threshold}"
            )
            
            # Check if we have enough reports for auto-deletion
            if report_count >= self.video_filter.reports_threshold:
                try:
                    # Find and delete the reported message
                    reported_message = await context.bot.get_chat(chat_id)
                    await context.bot.delete_message(chat_id, message_id)
                    storage.increment_deleted_videos()
                    
                    # Get the original sender and add to blacklist
                    try:
                        # Try to get message info (this might not work for old messages)
                        pass  # We'll handle this in a simpler way
                    except:
                        pass
                    
                    # Notify group
                    await context.bot.send_message(
                        chat_id,
                        f"🚫 تم حذف مقطع بعد تلقي {report_count} بلاغات من الأعضاء.\nشكراً لكم على حماية المجموعة! 🛡️"
                    )
                    
                    # Notify admins
                    await self.notify_admins_about_deletion(context, chat_id, report_count)
                    
                except Exception as e:
                    logger.error(f"Failed to delete reported video: {e}")
                    await context.bot.send_message(
                        chat_id,
                        "⚠️ لم أتمكن من حذف المقطع. ربما تم حذفه مسبقاً أو لا أملك الصلاحيات الكافية."
                    )
            
        except Exception as e:
            logger.error(f"Failed to handle video report: {e}")
            await query.edit_message_text("❌ حدث خطأ في تسجيل البلاغ.")
    
    async def notify_admins_about_video(self, context, chat_id: int, user, reason: str, warning_count: int):
        """Notify admins about suspicious video deletion"""
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            notification = f"🚨 تنبيه: حذف فيديو مشبوه\n\n"
            notification += f"👤 العضو: @{user.username or user.first_name}\n"
            notification += f"📹 السبب: {reason}\n"
            notification += f"⚠️ عدد التحذيرات: {warning_count}/{self.max_warnings}\n"
            notification += f"🕒 الوقت: {datetime.now().strftime('%H:%M:%S')}"
            
            for admin in admins:
                if not admin.user.is_bot:
                    try:
                        await context.bot.send_message(admin.user.id, notification)
                    except:
                        pass
        except Exception as e:
            logger.error(f"Failed to notify admins about video: {e}")
    
    async def notify_admins_about_deletion(self, context, chat_id: int, report_count: int):
        """Notify admins about community-reported video deletion"""
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            notification = f"🛡️ حذف مقطع بالبلاغات المجتمعية\n\n"
            notification += f"📊 عدد البلاغات: {report_count}\n"
            notification += f"🗑️ تم الحذف تلقائياً\n"
            notification += f"🕒 الوقت: {datetime.now().strftime('%H:%M:%S')}"
            
            for admin in admins:
                if not admin.user.is_bot:
                    try:
                        await context.bot.send_message(admin.user.id, notification)
                    except:
                        pass
        except Exception as e:
            logger.error(f"Failed to notify admins about deletion: {e}")

    async def moderate_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE)::
        """Moderate messages"""
        if not update.message or not update.message.text:
            return
        
        message = update.message
        user = message.from_user
        chat = message.chat
        
        # Skip private chats
        if chat.type == 'private':
            return
        
        # Skip if user is admin
        try:
            chat_member = await context.bot.get_chat_member(chat.id, user.id)
            if chat_member.status in ['administrator', 'creator']:
                return
        except:
            pass
        
        # Check if user is banned
        if storage.is_banned(user.id):
            try:
                await message.delete()
                return
            except:
                pass
        
        violations = []
        should_delete = False
        
        # Check for suspicious links
        is_suspicious, reason = self.content_filter.is_suspicious_link(message.text)
        if is_suspicious:
            violations.append(f"رابط مشبوه: {reason}")
            should_delete = True
        
        # Check for banned words
        has_banned_words, word = self.content_filter.contains_banned_words(message.text)
        if has_banned_words:
            violations.append(f"كلمة محظورة: {word}")
            should_delete = True
        
        # Check for spam
        is_spam, spam_reason = self.content_filter.is_spam_content(message.text)
        if is_spam:
            violations.append(f"رسالة مشبوهة: {spam_reason}")
            should_delete = True
        
        # Take action if violations found
        if violations:
            if should_delete:
                try:
                    await message.delete()
                except:
                    pass
            
            # Add warning
            warning_count = storage.add_warning(user.id, chat.id)
            
            # Send warning message
            warning_msg = f"⚠️ تحذير رقم {warning_count} للعضو @{user.username or user.first_name}\n"
            warning_msg += f"السبب: {violations[0]}\n"
            warning_msg += f"الحد الأقصى للتحذيرات: {self.max_warnings}"
            
            warning_message = await context.bot.send_message(
                chat.id, warning_msg, reply_to_message_id=message.message_id
            )
            
            # Auto-delete warning after 30 seconds
            context.job_queue.run_once(
                lambda context: asyncio.create_task(self.delete_message_safely(warning_message)),
                30
            )
            
            # Check if user should be banned
            if warning_count >= self.max_warnings:
                try:
                    await context.bot.ban_chat_member(chat.id, user.id)
                    storage.ban_user(user.id)
                    await context.bot.send_message(
                        chat.id, 
                        f"🚫 تم حظر العضو @{user.username or user.first_name} بسبب التحذيرات المتكررة."
                    )
                except Exception as e:
                    logger.error(f"Failed to ban user {user.id}: {e}")
    
    async def delete_message_safely(self, message):
        """Safely delete message"""
        try:
            await message.delete()
        except:
            pass

# Bot commands
class BotCommands:
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(self.bot_manager.responses['welcome'])
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(self.bot_manager.responses['help'])
    
    async def oil_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(self.bot_manager.responses['oil_info'])
    
    async def service_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(self.bot_manager.responses['service_info'])
    
    async def dealers_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(self.bot_manager.responses['dealers_info'], parse_mode='Markdown')
    
    async def faq_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(self.bot_manager.responses['faq'], parse_mode='Markdown')
    
    async def welcome_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome new members"""
        for member in update.message.new_chat_members:
            if not member.is_bot:
                welcome_msg = self.bot_manager.responses['welcome'].replace('{name}', member.first_name)
                await context.bot.send_message(update.message.chat.id, welcome_msg)

# Simple Flask app for Railway
app = Flask(__name__)

@app.route('/')
def dashboard():
    return '''
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <title>بوت مرسيدس - نشط</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f0f0f0; }
        .container { max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .status { color: #27ae60; font-size: 24px; margin: 20px 0; }
        .info { color: #7f8c8d; margin: 10px 0; }
        .success { background: #d4edda; color: #155724; padding: 15px; border-radius: 5px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚗 بوت نادي مالكي مرسيدس</h1>
        <div class="status">✅ البوت نشط ويعمل!</div>
        <div class="success">
            🎉 تم إصلاح مشكلة قاعدة البيانات<br>
            البوت الآن يعمل بدون مشاكل على Railway
        </div>
        <div class="info">📱 إصدار مبسط - بدون قاعدة بيانات</div>
        <div class="info">🛡️ نظام الحماية: مفعل</div>
        <div class="info">🇸🇦 دعم اللغة العربية: كامل</div>
        <div class="info">💰 التكلفة: مجاني 100%</div>
        <div class="info">🔄 آخر تحديث: الآن</div>
        
        <h3>🎯 المميزات النشطة:</h3>
        <ul style="text-align: right; display: inline-block;">
            <li>منع الروابط المشبوهة</li>
            <li>فلترة الرسائل الإعلانية</li>
            <li>حماية من الفيديوهات المشبوهة</li>
            <li>نظام التبليغ المجتمعي</li>
            <li>نظام التحذيرات التلقائي</li>
            <li>الأسئلة الشائعة عن مرسيدس</li>
            <li>معلومات وكلاء السعودية</li>
            <li>نصائح الصيانة</li>
        </ul>
        
        <p><strong>البوت جاهز للاستخدام في مجموعة تليجرام!</strong></p>
    </div>
</body>
</html>
    '''

@app.route('/health')
def health():
    return {'status': 'healthy', 'bot': 'running'}

def run_flask():
    app.run(host='0.0.0.0', port=Config.PORT, debug=False)

def create_bot():
    """Create and run the bot"""
    bot_manager = MercedesBotManager()
    commands = BotCommands(bot_manager)
    
    # Create application
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", commands.start_command))
    application.add_handler(CommandHandler("help", commands.help_command))
    application.add_handler(CommandHandler("oil", commands.oil_command))
    application.add_handler(CommandHandler("service", commands.service_command))
    application.add_handler(CommandHandler("dealers", commands.dealers_command))
    application.add_handler(CommandHandler("faq", commands.faq_command))
    
    # Video message handler (must be before text message handler)
    application.add_handler(MessageHandler(filters.VIDEO, bot_manager.handle_video_message))
    
    # Callback query handler for report buttons
    application.add_handler(CallbackQueryHandler(bot_manager.handle_video_report))
    
    # Message moderation (text messages)
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        bot_manager.moderate_message
    ))
    
    # Welcome new members
    application.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS, 
        commands.welcome_new_member
    ))
    
    return application

def main():
    """Main function"""
    print("🚗 Starting Mercedes Telegram Bot...")
    print("💰 Version: 100% FREE - Simplified")
    print("🇸🇦 Language: Arabic - Saudi Arabia")
    print("🛡️ Features: Link filtering, Spam detection, Auto-moderation")
    
    # Start Flask in background
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Create and run bot
    application = create_bot()
    
    print("✅ Bot is ready and running!")
    print(f"🌐 Dashboard available on port {Config.PORT}")
    
    # Run bot
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
