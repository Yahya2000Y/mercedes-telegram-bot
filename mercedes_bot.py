#!/usr/bin/env python3
"""
Mercedes Owners Club Telegram Bot - 100% FREE Arabic Version
Specifically designed for Saudi Arabia Mercedes groups
Uses only free services: Railway.app, SQLite, No external APIs
"""

import os
import re
import json
import logging
import asyncio
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import threading
import time
from urllib.parse import urlparse

# Telegram Bot API (free)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    filters, ContextTypes, CallbackQueryHandler
)

# Free web framework for admin dashboard
from flask import Flask, render_template, jsonify
from flask_cors import CORS

# Configure logging with Arabic support
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('mercedes_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 100% FREE Configuration
class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN', 'احصل_عليه_من_BotFather')
    PORT = int(os.getenv('PORT', 8080))
    DATABASE_URL = 'mercedes_saudi_bot.db'  # Local SQLite - FREE
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'mercedes2024')

@dataclass
class UserWarning:
    user_id: int
    username: str
    warning_count: int
    last_warning: datetime
    violations: List[str]

@dataclass
class GroupSettings:
    group_id: int
    welcome_message: str
    max_warnings: int
    auto_delete_spam: bool
    topic_enforcement: bool
    banned_words: List[str]
    admin_notifications: bool

class ArabicContentFilter:
    """100% Free Arabic content filtering for Saudi Mercedes groups"""
    
    def __init__(self):
        # Arabic suspicious patterns
        self.suspicious_patterns = [
            # English suspicious patterns
            r'bit\.ly', r'tinyurl', r'shortlink', r't\.co', r'goo\.gl',
            r'free.*download', r'hack.*tool', r'generator', r'unlimited.*money',
            
            # Arabic suspicious patterns
            r'تحميل.*مجاني', r'هاك.*أداة', r'أموال.*سهلة', r'ربح.*سريع',
            r'مولد.*أرقام', r'حساب.*مجاني', r'فيزا.*وهمية', r'بطاقة.*ائتمان',
            r'كسب.*فلوس', r'شغل.*من.*البيت', r'استثمار.*مضمون',
            r'تداول.*عملات', r'فوركس.*مجاني', r'بيتكوين.*مجاني'
        ]
        
        # Arabic spam detection patterns
        self.spam_patterns = [
            (r'(.)\1{4,}', 'أحرف متكررة'),  # ااااا، !!!!
            (r'[A-Z]{10,}', 'أحرف كبيرة زائدة'),
            (r'(أموال.*مجانية|ربح.*سهل|كسب.*\d+.*ريال)', 'رسائل مالية مشبوهة'),
            (r'(اشتري.*الآن|تخفيض.*اليوم|خصم.*\d+%)', 'رسائل تجارية'),
            (r'(اضغط.*هنا.*الآن|عاجل.*اتصل|تحرك.*الآن)', 'رسائل استعجال'),
            (r'(محتوى.*بالغين|xxx|إباحي)', 'محتوى للكبار'),
            (r'(قمار|كازينو|مراهنة|بوكر)', 'قمار'),
            (r'(أدوية.*رخيصة|حبوب.*للبيع)', 'مواد غير قانونية'),
            (r'(🔥){5,}', 'رموز مفرطة'),
            (r'(💰){3,}', 'رموز مالية مفرطة')
        ]
        
        # Mercedes keywords in Arabic and English
        self.mercedes_keywords = {
            'models_arabic': [
                'مرسيدس', 'بنز', 'مرسيدس بنز', 'أم بي', 'دايملر',
                'سي كلاس', 'إي كلاس', 'إس كلاس', 'أيه كلاس', 'جي كلاس',
                'سي ال إس', 'سي ال كيه', 'جي ال إي', 'جي ال إس', 'جي ال كيه',
                'أيه أم جي', 'مايباخ', 'جي واجن', 'كابريو', 'كوبيه'
            ],
            'models_english': [
                'w123', 'w124', 'w126', 'w140', 'w202', 'w203', 'w204', 'w205', 'w206',
                'w210', 'w211', 'w212', 'w213', 'w214', 'w220', 'w221', 'w222', 'w223',
                'c-class', 'e-class', 's-class', 'a-class', 'g-class', 'cls', 'clk',
                'gle', 'gls', 'glk', 'gla', 'glb', 'glc', 'cla', 'amg', 'maybach'
            ],
            'parts_arabic': [
                'محرك', 'ناقل حركة', 'جير', 'فرامل', 'إطارات', 'جنوط', 'كفرات',
                'تعليق', 'مكيف', 'كهرباء', 'بطارية', 'دينمو', 'سلف',
                'زيت', 'فلتر', 'شمعات', 'رديتر', 'مروحة', 'حساسات',
                'مساعدات', 'كراسي', 'جلد', 'تابلو', 'مقود', 'فتحة سقف'
            ],
            'parts_english': [
                'engine', 'transmission', 'gearbox', '7g-tronic', '9g-tronic',
                'suspension', 'airmatic', 'abc', 'brakes', 'wheels', 'tires',
                'leather', 'interior', 'exterior', 'headlights', 'battery'
            ],
            'maintenance_arabic': [
                'صيانة', 'سيرفس', 'تغيير زيت', 'فحص', 'إصلاح', 'ورشة',
                'قطع غيار', 'كشف', 'تشخيص', 'كمبيوتر', 'سكانر',
                'لمبة تحذير', 'عطل', 'مشكلة', 'صوت غريب', 'اهتزاز'
            ],
            'maintenance_english': [
                'service', 'maintenance', 'oil change', 'repair', 'diagnostic',
                'scanner', 'fault', 'code', 'warning', 'check engine'
            ]
        }
        
        # Common Arabic non-Mercedes topics to filter
        self.off_topic_patterns_arabic = [
            r'(بي إم دبليو|أودي|لكزس|جاكوار|فولفو|بورش)(?!.*مقابل.*مرسيدس)',
            r'(تويوتا|هوندا|فورد|شيفروليه|نيسان|هيونداي)',
            r'(سياسة|انتخابات|حكومة)(?!.*سيارة)',
            r'(عملات|بيتكوين|تداول|فوركس)(?!.*سيارة)',
            r'(زواج|علاقات|حب)(?!.*سيارة)',
            r'(طبخ|وصفات|أكل)(?!.*سيارة)',
            r'(رياضة|كرة|هلال|نصر|اتحاد)(?!.*سيارة)'
        ]
        
        # Saudi-specific banned content
        self.saudi_banned_patterns = [
            r'(حرام|مخالف.*شرع)(?!.*سؤال)',  # Religious content (unless asking)
            r'(بنات|شباب.*يتعارف)',  # Dating/relationships
            r'(قروض.*ربوية|فوائد.*بنكية)',  # Usury/interest
            r'(خمر|كحول|مشروبات.*كحولية)',  # Alcohol
            r'(قمار|مراهنة|يانصيب)',  # Gambling
        ]
    
    def is_suspicious_link(self, text: str) -> tuple[bool, str]:
        """FREE Arabic link analysis"""
        # Extract URLs
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)
        
        if not urls:
            return False, ""
        
        for url in urls:
            try:
                domain = urlparse(url).netloc.lower()
                
                # Check against suspicious patterns
                for pattern in self.suspicious_patterns:
                    if re.search(pattern, url, re.IGNORECASE):
                        return True, f"رابط مشبوه: {pattern}"
                
                # Known suspicious domains
                suspicious_domains = [
                    'bit.ly', 'tinyurl.com', 'shortlink.com', 't.co',
                    'goo.gl', 'ow.ly', 'buff.ly', 'dlvr.it'
                ]
                
                if any(sus_domain in domain for sus_domain in suspicious_domains):
                    return True, f"خدمة روابط مختصرة: {domain}"
                
                # Suspicious TLDs
                suspicious_tlds = ['.tk', '.ml', '.ga', '.cf', '.pw', '.top']
                if any(url.endswith(tld) for tld in suspicious_tlds):
                    return True, "امتداد نطاق مشبوه"
                
            except Exception as e:
                logger.warning(f"URL parsing error: {e}")
                return True, "رابط غير صحيح"
        
        return False, ""
    
    def contains_banned_words(self, text: str, banned_words: List[str]) -> tuple[bool, str]:
        """Check for banned words in Arabic and English"""
        text_lower = text.lower()
        for word in banned_words:
            if word.lower() in text_lower:
                return True, f"كلمة محظورة: {word}"
        return False, ""
    
    def is_spam_content(self, text: str) -> tuple[bool, str]:
        """FREE spam detection for Arabic content"""
        for pattern, reason in self.spam_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True, reason
        
        # Check Saudi-specific banned content
        for pattern in self.saudi_banned_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True, "محتوى غير مناسب للمجموعة"
        
        # Check for excessive Arabic diacritics
        diacritics = len(re.findall(r'[ًٌٍَُِّْ]', text))
        if diacritics > 20:
            return True, "تشكيل مفرط"
        
        # Check for excessive emoji/symbols
        emoji_count = len(re.findall(r'[😀-🿿]|[⚀-⛿]|[✀-➿]', text))
        if emoji_count > 8:
            return True, "رموز تعبيرية مفرطة"
        
        return False, ""
    
    def is_mercedes_related(self, text: str) -> bool:
        """Removed - now allows all car discussions"""
        # Always return True to allow all topics
        return True

class ArabicDatabaseManager:
    """100% FREE SQLite database with Arabic support"""
    
    def __init__(self, db_path: str = 'mercedes_saudi_bot.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database with Arabic support"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Enable UTF-8 support
        cursor.execute('PRAGMA encoding="UTF-8"')
        
        # Users table with Arabic names support
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                warning_count INTEGER DEFAULT 0,
                last_warning TIMESTAMP,
                violations TEXT DEFAULT '[]',
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_banned BOOLEAN DEFAULT 0,
                language_preference TEXT DEFAULT 'ar'
            )
        ''')
        
        # Group settings with Arabic defaults
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_settings (
                group_id INTEGER PRIMARY KEY,
                group_title TEXT,
                welcome_message TEXT DEFAULT 'أهلاً وسهلاً بك في نادي مالكي مرسيدس 🚗\nيرجى الالتزام بقوانين المجموعة ومناقشة السيارات بشكل عام',
                max_warnings INTEGER DEFAULT 3,
                auto_delete_spam BOOLEAN DEFAULT 1,
                topic_enforcement BOOLEAN DEFAULT 0,
                banned_words TEXT DEFAULT '["سبام", "نصب", "هاك", "غش", "شراء متابعين", "عملات رقمية"]',
                admin_notifications BOOLEAN DEFAULT 1,
                welcome_enabled BOOLEAN DEFAULT 1,
                arabic_mode BOOLEAN DEFAULT 1,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Activity log with Arabic actions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                group_id INTEGER,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                admin_id INTEGER
            )
        ''')
        
        # Arabic Mercedes FAQ
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mercedes_faq_arabic (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_ar TEXT,
                question_en TEXT,
                answer_ar TEXT,
                answer_en TEXT,
                keywords_ar TEXT,
                keywords_en TEXT,
                category TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Saudi-specific data
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS saudi_dealers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name_ar TEXT,
                name_en TEXT,
                city TEXT,
                phone TEXT,
                services TEXT,
                rating REAL DEFAULT 0.0
            )
        ''')
        
        conn.commit()
        conn.close()
        self.populate_arabic_data()
    
    def populate_arabic_data(self):
        """Add Arabic Mercedes FAQ and Saudi dealer data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if Arabic FAQ exists
        cursor.execute('SELECT COUNT(*) FROM mercedes_faq_arabic')
        if cursor.fetchone()[0] == 0:
            arabic_faq = [
                (
                    "ما نوع الزيت المناسب لمرسيدس؟",
                    "What oil should I use for Mercedes?",
                    "مرسيدس توصي بزيوت معتمدة MB 229.5. الماركات الجيدة: موبيل 1، كاسترول، ليكوي مولي. دائماً راجع دليل المالك للمواصفات الدقيقة.",
                    "Mercedes recommends MB 229.5 approved oils. Good brands: Mobil 1, Castrol, Liqui Moly. Always check owner's manual.",
                    "زيت,محرك,صيانة",
                    "oil,engine,maintenance",
                    "صيانة"
                ),
                (
                    "كم مرة أسوي سيرفس للمرسيدس؟",
                    "How often should I service Mercedes?",
                    "اتبع نظام FSS: سيرفس A كل 10,000 كم أو سنة، سيرفس B كل 20,000 كم أو سنتين. المرسيدس الحديثة فيها مؤشر صيانة - لا تتجاهله!",
                    "Follow FSS system: Service A every 10,000km/year, Service B every 20,000km/2 years. Modern Mercedes have maintenance indicator.",
                    "سيرفس,صيانة,جدولة",
                    "service,maintenance,schedule",
                    "صيانة"
                ),
                (
                    "لمبة المحرك تشتغل - إيش السبب؟",
                    "Check engine light is on - what's wrong?",
                    "لمبة المحرك تدل على مشاكل العادم. أسباب شائعة: حساس الأكسجين، الكتلايزر، حساس الهواء، أو غطاء البنزين مفكوك. استخدم جهاز التشخيص.",
                    "Check engine light indicates emissions issues. Common: O2 sensor, catalytic converter, MAF sensor, loose gas cap. Use diagnostic scanner.",
                    "لمبة المحرك,تحذير,تشخيص",
                    "check engine,warning,diagnostic",
                    "مشاكل"
                ),
                (
                    "وين أشتري قطع غيار مرسيدس أصلية؟",
                    "Where to buy genuine Mercedes parts?",
                    "قطع أصلية: وكالات مرسيدس، مركز مرسيدس الكلاسيكية. بدائل جيدة: FCP Euro، بليكان بارتس، يورو كار بارتس.",
                    "Genuine parts: Mercedes dealers, Mercedes Classic Center. Good alternatives: FCP Euro, Pelican Parts, Euro Car Parts.",
                    "قطع غيار,أصلية,وكالة",
                    "parts,genuine,dealer",
                    "قطع غيار"
                ),
                (
                    "المرسيدس ما تشتغل - إيش أفحص؟",
                    "Mercedes won't start - what to check?",
                    "افحص: البطارية (12.6 فولت)، مستوى البنزين، دواسة الفرامل مضغوطة كامل، الجير على P أو N. مشاكل شائعة: بطارية فاضية، سلف خربان، طرمبة بنزين.",
                    "Check: battery (12.6V), fuel level, brake pedal fully pressed, gear in P/N. Common issues: dead battery, bad starter, fuel pump.",
                    "ما تشتغل,بطارية,سلف",
                    "won't start,battery,starter",
                    "مشاكل"
                ),
                (
                    "إيش الفرق بين 4Matic والدفع الخلفي؟",
                    "What's difference between 4Matic and RWD?",
                    "4Matic = دفع رباعي لجر أفضل في المطر والطين. الدفع الخلفي = أكثر رياضية وأداء. 4Matic يزيد الوزن لكن أكثر أمان في الطقس السيء.",
                    "4Matic = AWD for better traction in rain/mud. RWD = more sporty performance. 4Matic adds weight but safer in bad weather.",
                    "4matic,دفع رباعي,دفع خلفي",
                    "4matic,AWD,RWD",
                    "تقني"
                ),
                (
                    "كيف أحافظ على جلد المرسيدس؟",
                    "How to maintain Mercedes leather?",
                    "نظف شهرياً بمنظف جلد متعادل، رطب كل 3 شهور. تجنب المواد الكيميائية القوية. للـ MB-Tex (صناعي) استخدم صابون لطيف وماء.",
                    "Clean monthly with pH-neutral leather cleaner, condition every 3 months. Avoid harsh chemicals. For MB-Tex use mild soap and water.",
                    "جلد,مقاعد,تنظيف",
                    "leather,seats,cleaning",
                    "صيانة"
                ),
                (
                    "ليش لمبة ABC تشتغل؟",
                    "Why is ABC suspension light on?",
                    "مشاكل ABC: نقص سائل هيدروليك، مراكم خربان، مشاكل المضخة، أو حساسات معطلة. إصلاح مكلف - توقع 8000-20000 ريال.",
                    "ABC issues: low hydraulic fluid, failed accumulator, pump problems, sensor faults. Expensive repair - expect 8000-20000 SAR.",
                    "ABC,تعليق,هيدروليك",
                    "ABC,suspension,hydraulic",
                    "مشاكل"
                ),
                (
                    "أفضل كفرات للمرسيدس؟",
                    "Best tires for Mercedes?",
                    "مقاسات أصلية موصى بها. ممتازة: ميشلان بايلوت سبورت، كونتيننتال. اقتصادية: فالكن، كومهو. غير دائماً بالأزواج. تفقد المقاس على باب السيارة.",
                    "OEM sizes recommended. Premium: Michelin Pilot Sport, Continental. Budget: Falken, Kumho. Always replace in pairs. Check door jamb for specs.",
                    "كفرات,إطارات,تغيير",
                    "tires,replacement,wheels",
                    "صيانة"
                ),
                (
                    "كيف أصفر مؤشر الصيانة؟",
                    "How to reset service indicator?",
                    "الطريقة تختلف حسب السنة. عموماً: المفتاح على وضع 2، اضغط واستمر على زر الرحلة أثناء تشغيل المحرك، اتركه عند ظهور قائمة الصيانة. يوتيوب فيه شروحات مفصلة.",
                    "Method varies by year. Generally: key to position 2, hold trip reset while starting engine, release when service menu appears. YouTube has detailed tutorials.",
                    "صفر الصيانة,مؤشر,إعاد ضبط",
                    "service reset,indicator,reset",
                    "صيانة"
                )
            ]
            
            cursor.executemany('''
                INSERT INTO mercedes_faq_arabic 
                (question_ar, question_en, answer_ar, answer_en, keywords_ar, keywords_en, category)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', arabic_faq)
        
        # Add Saudi Mercedes dealers
        cursor.execute('SELECT COUNT(*) FROM saudi_dealers')
        if cursor.fetchone()[0] == 0:
            saudi_dealers = [
                ("شركة الجزيرة للسيارات", "Al Jazirah Vehicles", "الرياض", "011-123-4567", "مبيعات,صيانة,قطع غيار", 4.5),
                ("مجموعة محمد يوسف ناغي", "Mohammad Yousuf Naghi Group", "جدة", "012-123-4567", "مبيعات,صيانة,AMG", 4.3),
                ("مؤسسة الأهلي للسيارات", "Al Ahli Motors", "الدمام", "013-123-4567", "مبيعات,صيانة", 4.2),
                ("شركة ساسكو", "SASCO", "المدينة المنورة", "014-123-4567", "صيانة,قطع غيار", 4.0),
                ("الجميح للسيارات", "Al Jomaih Automotive", "الخبر", "013-987-6543", "مبيعات,صيانة,تأمين", 4.4)
            ]
            
            cursor.executemany('''
                INSERT INTO saudi_dealers (name_ar, name_en, city, phone, services, rating)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', saudi_dealers)
        
        conn.commit()
        conn.close()

class MercedesSaudiBotManager:
    """Main Saudi Mercedes bot manager with Arabic support"""
    
    def __init__(self):
        self.db = ArabicDatabaseManager()
        self.content_filter = ArabicContentFilter()
        self.user_warnings: Dict[int, UserWarning] = {}
        self.group_settings: Dict[int, GroupSettings] = {}
        
        # Arabic responses
        self.arabic_responses = {
            'welcome': "🚗 أهلاً وسهلاً بك في نادي مالكي مرسيدس!\n\nيرجى الالتزام بقوانين المجموعة:\n• مناقشة السيارات والمواضيع ذات الصلة\n• عدم إرسال روابط مشبوهة\n• الاحترام المتبادل\n\nاستمتع بوقتك معنا! 🌟",
            'warning': "⚠️ تحذير رقم {count} للعضو @{username}\nالسبب: {reason}\nالحد الأقصى للتحذيرات قبل الحظر: {max_warnings}",
            'banned': "🚫 تم حظر العضو @{username} بسبب التحذيرات المتكررة",
            'spam_deleted': "🗑️ تم حذف رسالة مخالفة لقوانين المجموعة",
            'off_topic': "📝 يرجى الالتزام بمواضيع السيارات في المجموعة",
            'admin_alert': "🚨 تنبيه للإدارة\nالعضو: @{username}\nالمخالفة: {violation}\nعدد التحذيرات: {count}"
        }
        
        self.load_group_settings()
    
    def load_group_settings(self):
        """Load group settings with Arabic defaults"""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM group_settings')
        
        for row in cursor.fetchall():
            group_id = row[0]
            self.group_settings[group_id] = GroupSettings(
                group_id=group_id,
                welcome_message=row[1],
                max_warnings=row[2],
                auto_delete_spam=bool(row[3]),
                topic_enforcement=bool(row[4]),
                banned_words=json.loads(row[5]),
                admin_notifications=bool(row[6])
            )
        
        conn.close()
    
    def get_group_settings(self, group_id: int) -> GroupSettings:
        """Get Arabic group settings"""
        if group_id not in self.group_settings:
            self.group_settings[group_id] = GroupSettings(
                group_id=group_id,
                welcome_message=self.arabic_responses['welcome'],
                max_warnings=3,
                auto_delete_spam=True,
                topic_enforcement=True,
                banned_words=['سبام', 'نصب', 'هاك', 'غش', 'شراء متابعين', 'عملات رقمية'],
                admin_notifications=True
            )
            self.save_group_settings(group_id)
        
        return self.group_settings[group_id]
    
    def save_group_settings(self, group_id: int):
        """Save Arabic group settings"""
        settings = self.group_settings[group_id]
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO group_settings 
            (group_id, welcome_message, max_warnings, auto_delete_spam, 
             topic_enforcement, banned_words, admin_notifications)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            group_id, settings.welcome_message, settings.max_warnings,
            settings.auto_delete_spam, settings.topic_enforcement,
            json.dumps(settings.banned_words, ensure_ascii=False), 
            settings.admin_notifications
        ))
        
        conn.commit()
        conn.close()
    
    def add_user_warning(self, user_id: int, username: str, violation: str, group_id: int):
        """Add warning with Arabic logging"""
        if user_id not in self.user_warnings:
            self.user_warnings[user_id] = UserWarning(
                user_id=user_id,
                username=username,
                warning_count=0,
                last_warning=datetime.now(),
                violations=[]
            )
        
        warning = self.user_warnings[user_id]
        warning.warning_count += 1
        warning.last_warning = datetime.now()
        warning.violations.append(violation)
        
        # Save to database with Arabic support
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, username, warning_count, last_warning, violations)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, username, warning.warning_count, warning.last_warning,
              json.dumps(warning.violations, ensure_ascii=False)))
        
        # Log activity in Arabic
        cursor.execute('''
            INSERT INTO activity_log (group_id, user_id, action, details)
            VALUES (?, ?, ?, ?)
        ''', (group_id, user_id, 'تحذير', violation))
        
        conn.commit()
        conn.close()
        
        return warning.warning_count
    
    async def moderate_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main Arabic message moderation"""
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
        
        settings = self.get_group_settings(chat.id)
        violations = []
        should_delete = False
        
        # Check for suspicious links
        is_suspicious, reason = self.content_filter.is_suspicious_link(message.text)
        if is_suspicious:
            violations.append(f"رابط مشبوه: {reason}")
            should_delete = True
        
        # Check for banned words
        has_banned_words, word = self.content_filter.contains_banned_words(
            message.text, settings.banned_words
        )
        if has_banned_words:
            violations.append(f"كلمة محظورة: {word}")
            should_delete = True
        
        # Check for spam
        is_spam, spam_reason = self.content_filter.is_spam_content(message.text)
        if is_spam:
            violations.append(f"رسالة مشبوهة: {spam_reason}")
            should_delete = True
        
        # Topic enforcement removed - allow all car discussions
        # Members can discuss any car topics freely
        
        # Take action if violations found
        if violations:
            if should_delete and settings.auto_delete_spam:
                try:
                    await message.delete()
                except:
                    pass
            
            # Add warning
            warning_count = self.add_user_warning(
                user.id, user.username or user.first_name, 
                "; ".join(violations), chat.id
            )
            
            # Send Arabic warning message
            warning_msg = self.arabic_responses['warning'].format(
                count=warning_count,
                username=user.username or user.first_name,
                reason=violations[0],
                max_warnings=settings.max_warnings
            )
            
            warning_message = await context.bot.send_message(
                chat.id, warning_msg, reply_to_message_id=message.message_id
            )
            
            # Auto-delete warning after 30 seconds
            context.job_queue.run_once(
                lambda context: asyncio.create_task(self.delete_message_safely(warning_message)),
                30
            )
            
            # Check if user should be banned
            if warning_count >= settings.max_warnings:
                try:
                    await context.bot.ban_chat_member(chat.id, user.id)
                    ban_msg = self.arabic_responses['banned'].format(
                        username=user.username or user.first_name
                    )
                    await context.bot.send_message(chat.id, ban_msg)
                    
                    # Log ban action
                    conn = sqlite3.connect(self.db.db_path)
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO activity_log (group_id, user_id, action, details)
                        VALUES (?, ?, ?, ?)
                    ''', (chat.id, user.id, 'حظر', 'تجاوز الحد الأقصى للتحذيرات'))
                    conn.commit()
                    conn.close()
                    
                except Exception as e:
                    logger.error(f"Failed to ban user {user.id}: {e}")
            
            # Notify admins in Arabic
            if settings.admin_notifications:
                await self.notify_admins_arabic(context, chat.id, user, violations, warning_count)
    
    async def delete_message_safely(self, message):
        """Safely delete message"""
        try:
            await message.delete()
        except:
            pass
    
    async def notify_admins_arabic(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, 
                                 user, violations: List[str], warning_count: int):
        """Notify admins in Arabic"""
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            notification = self.arabic_responses['admin_alert'].format(
                username=user.username or user.first_name,
                violation=', '.join(violations),
                count=warning_count
            )
            
            for admin in admins:
                if not admin.user.is_bot:
                    try:
                        await context.bot.send_message(admin.user.id, notification)
                    except:
                        pass
        except Exception as e:
            logger.error(f"Failed to notify admins: {e}")

# Bot Commands in Arabic
class ArabicBotCommands:
    """Arabic bot commands for Saudi Mercedes group"""
    
    def __init__(self, bot_manager):
        self.bot_manager = bot_manager
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command in Arabic"""
        welcome_text = """
🚗 أهلاً بك في بوت نادي مالكي مرسيدس

🤖 أنا هنا لمساعدتك في:
• الإجابة على أسئلة السيارات
• إدارة المجموعة
• منع الرسائل المشبوهة
• تقديم نصائح الصيانة

📝 الأوامر المتاحة:
/help - قائمة الأوامر
/faq - أسئلة شائعة عن مرسيدس
/dealers - وكلاء مرسيدس في السعودية
/settings - إعدادات المجموعة (للإدارة فقط)

🔧 للمساعدة التقنية، أرسل رسالة تحتوي على مشكلتك مع سيارتك
        """
        await update.message.reply_text(welcome_text)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Help command in Arabic"""
        help_text = """
📋 قائمة الأوامر - بوت مرسيدس

👥 للأعضاء:
/start - بدء استخدام البوت
/help - هذه الرسالة
/faq - أسئلة شائعة عن مرسيدس
/dealers - قائمة وكلاء مرسيدس في السعودية
/oil - معلومات عن زيت المحرك
/service - معلومات عن الصيانة
/parts - أماكن شراء قطع الغيار

🛠️ للإدارة فقط:
/settings - إعدادات المجموعة
/stats - إحصائيات المجموعة
/warnings @username - عرض تحذيرات عضو
/ban @username - حظر عضو
/unban @username - إلغاء حظر عضو
/add_faq - إضافة سؤال جديد للأسئلة الشائعة

💡 نصيحة: يمكنك كتابة مشكلتك مع أي سيارة وسأحاول مساعدتك!
        """
        await update.message.reply_text(help_text)
    
    async def faq_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Arabic FAQ command"""
        keyboard = [
            [InlineKeyboardButton("🔧 صيانة", callback_data="faq_maintenance")],
            [InlineKeyboardButton("⚙️ قطع غيار", callback_data="faq_parts")],
            [InlineKeyboardButton("🚨 مشاكل", callback_data="faq_problems")],
            [InlineKeyboardButton("🏪 وكلاء", callback_data="faq_dealers")],
            [InlineKeyboardButton("📋 عرض الكل", callback_data="faq_all")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🤔 اختر نوع السؤال الذي تريد معرفة إجابته:",
            reply_markup=reply_markup
        )
    
    async def dealers_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Saudi dealers command"""
        conn = sqlite3.connect(self.bot_manager.db.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT name_ar, city, phone, rating FROM saudi_dealers ORDER BY rating DESC')
        dealers = cursor.fetchall()
        conn.close()
        
        if dealers:
            dealers_text = "🏪 وكلاء مرسيدس في السعودية:\n\n"
            for dealer in dealers:
                dealers_text += f"🚗 **{dealer[0]}**\n"
                dealers_text += f"📍 المدينة: {dealer[1]}\n"
                dealers_text += f"📞 الهاتف: {dealer[2]}\n"
                dealers_text += f"⭐ التقييم: {dealer[3]}/5\n\n"
        else:
            dealers_text = "لا توجد بيانات وكلاء متاحة حالياً."
        
        await update.message.reply_text(dealers_text, parse_mode='Markdown')
    
    async def oil_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Oil information in Arabic"""
        oil_info = """
🛢️ معلومات زيت محرك مرسيدس

📋 المواصفات المطلوبة:
• MB 229.5 - للمحركات الحديثة
• MB 229.3 - للمحركات الأقدم
• MB 229.1 - للمحركات القديمة جداً

🏷️ الماركات الموصى بها:
• موبيل 1 (Mobil 1) 0W-40
• كاسترول (Castrol) 0W-40
• ليكوي مولي (Liqui Moly) 5W-40
• شل (Shell) 5W-40

📏 الكميات حسب المحرك:
• 4 سلندر: 6-7 لتر
• 6 سلندر: 7-8 لتر  
• 8 سلندر: 8-9 لتر

⚠️ مهم: دائماً راجع دليل المالك للمواصفات الدقيقة لسيارتك!
        """
        await update.message.reply_text(oil_info)
    
    async def service_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Service information in Arabic"""
        service_info = """
🔧 معلومات صيانة مرسيدس

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

💡 نصيحة: لا تتجاهل مؤشر الصيانة في التابلو!

🏪 أماكن الصيانة:
• الوكالة الرسمية (أغلى لكن أضمن)
• ورش متخصصة في مرسيدس
• تجنب الورش العامة للصيانة الدورية
        """
        await update.message.reply_text(service_info)
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle FAQ callback queries"""
        query = update.callback_query
        await query.answer()
        
        conn = sqlite3.connect(self.bot_manager.db.db_path)
        cursor = conn.cursor()
        
        if query.data == "faq_all":
            cursor.execute('SELECT question_ar, answer_ar FROM mercedes_faq_arabic ORDER BY category')
            faqs = cursor.fetchall()
            
            faq_text = "📋 جميع الأسئلة الشائعة:\n\n"
            for i, (question, answer) in enumerate(faqs, 1):
                faq_text += f"❓ **{question}**\n✅ {answer}\n\n"
                if i >= 5:  # Limit to avoid long messages
                    faq_text += "... والمزيد متاح عبر الأوامر المتخصصة"
                    break
        
        elif query.data == "faq_maintenance":
            cursor.execute('''SELECT question_ar, answer_ar FROM mercedes_faq_arabic 
                            WHERE category = 'صيانة' ORDER BY id''')
            faqs = cursor.fetchall()
            
            faq_text = "🔧 أسئلة الصيانة:\n\n"
            for question, answer in faqs:
                faq_text += f"❓ **{question}**\n✅ {answer}\n\n"
        
        elif query.data == "faq_problems":
            cursor.execute('''SELECT question_ar, answer_ar FROM mercedes_faq_arabic 
                            WHERE category = 'مشاكل' ORDER BY id''')
            faqs = cursor.fetchall()
            
            faq_text = "🚨 مشاكل شائعة:\n\n"
            for question, answer in faqs:
                faq_text += f"❓ **{question}**\n✅ {answer}\n\n"
        
        else:
            faq_text = "معذرة، لم أجد معلومات لهذا القسم."
        
        conn.close()
        
        await query.edit_message_text(text=faq_text, parse_mode='Markdown')
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Settings command for admins only"""
        if update.message.chat.type == 'private':
            await update.message.reply_text("هذا الأمر يعمل في المجموعات فقط.")
            return
        
        # Check if user is admin
        try:
            chat_member = await context.bot.get_chat_member(
                update.message.chat.id, update.message.from_user.id
            )
            if chat_member.status not in ['administrator', 'creator']:
                await update.message.reply_text("هذا الأمر للإدارة فقط.")
                return
        except:
            await update.message.reply_text("خطأ في التحقق من الصلاحيات.")
            return
        
        settings = self.bot_manager.get_group_settings(update.message.chat.id)
        
        keyboard = [
            [InlineKeyboardButton(
                f"🔄 حذف الرسائل المشبوهة: {'✅' if settings.auto_delete_spam else '❌'}", 
                callback_data="toggle_auto_delete"
            )],
            [InlineKeyboardButton(
                f"📝 مناقشة جميع السيارات: ✅ مسموح", 
                callback_data="topic_info"
            )],
            [InlineKeyboardButton(
                f"🔔 تنبيه الإدارة: {'✅' if settings.admin_notifications else '❌'}", 
                callback_data="toggle_admin_notifications"
            )],
            [InlineKeyboardButton("📝 تعديل رسالة الترحيب", callback_data="edit_welcome")],
            [InlineKeyboardButton("🚫 إدارة الكلمات المحظورة", callback_data="manage_banned_words")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        settings_text = f"""
⚙️ إعدادات مجموعة مرسيدس

📊 الإعدادات الحالية:
• الحد الأقصى للتحذيرات: {settings.max_warnings}
• حذف الرسائل المشبوهة: {'✅ مفعل' if settings.auto_delete_spam else '❌ معطل'}
• مناقشة جميع السيارات: ✅ مسموح
• تنبيه الإدارة: {'✅ مفعل' if settings.admin_notifications else '❌ معطل'}

🚫 الكلمات المحظورة: {len(settings.banned_words)} كلمة
        """
        
        await update.message.reply_text(settings_text, reply_markup=reply_markup)

# Main Flask app for admin dashboard
app = Flask(__name__)
CORS(app)

@app.route('/')
def dashboard():
    """Simple Arabic admin dashboard"""
    return '''
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>لوحة تحكم بوت مرسيدس</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px; }
        .card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .stat-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; text-align: center; }
        .stat-number { font-size: 2em; font-weight: bold; }
        .stat-label { opacity: 0.9; }
        .btn { background: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; text-decoration: none; display: inline-block; }
        .btn:hover { background: #2980b9; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚗 لوحة تحكم بوت نادي مالكي مرسيدس</h1>
            <p>إدارة شاملة للمجموعة مجاناً 100%</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number" id="total-members">-</div>
                <div class="stat-label">إجمالي الأعضاء</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="warnings-today">-</div>
                <div class="stat-label">تحذيرات اليوم</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="spam-blocked">-</div>
                <div class="stat-label">رسائل محذوفة</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="active-groups">1</div>
                <div class="stat-label">المجموعات النشطة</div>
            </div>
        </div>
        
        <div class="card">
            <h2>📊 إحصائيات سريعة</h2>
            <p>✅ البوت: نشط ويعمل بكفاءة</p>
            <p>🔒 الخصوصية: جميع البيانات محفوظة محلياً</p>
            <p>💰 التكلفة: مجاني 100% - لا توجد رسوم</p>
            <p>🌐 اللغة: دعم كامل للعربية والإنجليزية</p>
        </div>
        
        <div class="card">
            <h2>🛠️ أدوات الإدارة</h2>
            <a href="#" class="btn">عرض السجلات</a>
            <a href="#" class="btn">إدارة الأعضاء</a>
            <a href="#" class="btn">الأسئلة الشائعة</a>
            <a href="#" class="btn">إعدادات المجموعة</a>
        </div>
        
        <div class="card">
            <h2>📱 معلومات الاتصال</h2>
            <p>🤖 نوع البوت: مجاني 100% - مفتوح المصدر</p>
            <p>🏢 الاستضافة: Railway.app (مجاني)</p>
            <p>💾 قاعدة البيانات: SQLite (محلي ومجاني)</p>
            <p>🔧 حالة الخدمة: متاح 24/7</p>
        </div>
    </div>
    
    <script>
        // Load stats (placeholder - connect to real data)
        document.getElementById('total-members').textContent = '0';
        document.getElementById('warnings-today').textContent = '0';
        document.getElementById('spam-blocked').textContent = '0';
    </script>
</body>
</html>
    '''

# Main bot setup and runner
def create_mercedes_bot():
    """Create and configure the Mercedes bot"""
    bot_manager = MercedesSaudiBotManager()
    commands = ArabicBotCommands(bot_manager)
    
    # Create application
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", commands.start_command))
    application.add_handler(CommandHandler("help", commands.help_command))
    application.add_handler(CommandHandler("faq", commands.faq_command))
    application.add_handler(CommandHandler("dealers", commands.dealers_command))
    application.add_handler(CommandHandler("oil", commands.oil_command))
    application.add_handler(CommandHandler("service", commands.service_command))
    application.add_handler(CommandHandler("settings", commands.settings_command))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(commands.handle_callback_query))
    
    # Add message handler for moderation
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        bot_manager.moderate_message
    ))
    
    # Add new member handler
    async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome new members in Arabic"""
        for member in update.message.new_chat_members:
            if not member.is_bot:
                settings = bot_manager.get_group_settings(update.message.chat.id)
                welcome_msg = settings.welcome_message.replace('{name}', member.first_name)
                await context.bot.send_message(update.message.chat.id, welcome_msg)
    
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    
    return application

def run_flask_app():
    """Run Flask dashboard in background"""
    app.run(host='0.0.0.0', port=Config.PORT, debug=False)

def main():
    """Main function to run the bot"""
    print("🚗 بدء تشغيل بوت نادي مالكي مرسيدس...")
    print("💰 النسخة: مجانية 100%")
    print("🇸🇦 اللغة: العربية - السعودية")
    
    # Start Flask app in background thread
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    
    # Create and run bot
    application = create_mercedes_bot()
    
    print("✅ البوت جاهز ويعمل!")
    print("🌐 لوحة التحكم متاحة على المنفذ", Config.PORT)
    
    # Run bot
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
