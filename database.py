# database.py
import threading
import uuid
from datetime import datetime

booking_lock = threading.Lock()
active_invoices = {}

def normalize_text(text: str) -> str:
    """تبدیل اعداد انگلیسی و عربی به فارسی و حذف کلمات اضافه برای تطابق ۱۰۰٪ دقیق ساعت و نام سالن"""
    if not text:
        return ""
    en_to_fa = str.maketrans("0123456789٠١٢٣٤٥٦٧٨٩", "۰۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹")
    cleaned = text.translate(en_to_fa)
    for word in ["ساعت", "سانس", "روز", "برای", "در", "‌", "\u200c"]:
        cleaned = cleaned.replace(word, " ")
    return " ".join(cleaned.split())

mock_courts = [
    {
        "id": "1",
        "name": "سالن فوتسال چمران",
        "sport_type": "فوتسال",
        "region": "غرب تهران",
        "neighborhood": "شهرک غرب",
        "is_indoor": True,
        "rating": 4.8,
        "price_per_hour": 400000,
        "available_slots": ["یکشنبه ۱۷:۰۰", "دوشنبه ۱۹:۰۰", "پنجشنبه ۲۱:۰۰"],
        "facilities": ["دوش", "پارکینگ", "تهویه مطبوع", "کفپوش پارکت"],
        "description": "سالن سرپوشیده استاندارد با کفپوش عالی و جای پارک راحت در شهرک غرب"
    },
    {
        "id": "2",
        "name": "مجموعه ورزشی انقلاب - کورت پدل",
        "sport_type": "پدل",
        "region": "شمال تهران",
        "neighborhood": "سئول",
        "is_indoor": False,
        "rating": 4.9,
        "price_per_hour": 800000,
        "available_slots": ["یکشنبه ۱۷:۰۰", "چهارشنبه ۲۰:۰۰", "جمعه ۱۰:۰۰"],
        "facilities": ["کافه", "پارکینگ", "اجاره راکت", "رختکن VIP"],
        "description": "کورت استاندارد جهانی پدل در فضای باز با امکان اجاره راکت و توپ"
    },
    {
        "id": "3",
        "name": "زمین تنیس استقلال",
        "sport_type": "تنیس",
        "region": "مرکز تهران",
        "neighborhood": "میرداماد",
        "is_indoor": False,
        "rating": 4.6,
        "price_per_hour": 600000,
        "available_slots": ["شنبه ۱۶:۰۰", "سه شنبه ۱۸:۰۰", "پنجشنبه ۱۶:۰۰"],
        "facilities": ["دوش", "فروشگاه لوازم ورزشی", "مربی خصوصی"],
        "description": "زمین تنیس خاک رس با نورپردازی حرفه‌ای برای بازی در شب"
    },
    {
        "id": "4",
        "name": "سالن چندمنظوره آزادی",
        "sport_type": "والیبال",
        "region": "غرب تهران",
        "neighborhood": "اکباتان",
        "is_indoor": True,
        "rating": 4.5,
        "price_per_hour": 350000,
        "available_slots": ["یکشنبه ۱۹:۰۰", "پنجشنبه ۱۸:۰۰", "جمعه ۱۶:۰۰"],
        "facilities": ["سرویس بهداشتی", "جایگاه تماشاچی", "بوفه"],
        "description": "سالن سقف بلند مناسب والیبال و تمرینات تیمی در محدوده اکباتان"
    },
    {
        "id": "5",
        "name": "سالن بسکتبال شهید حیدری",
        "sport_type": "بسکتبال",
        "region": "شرق تهران",
        "neighborhood": "نارمک",
        "is_indoor": True,
        "rating": 4.7,
        "price_per_hour": 450000,
        "available_slots": ["یکشنبه ۱۵:۰۰", "پنجشنبه ۲۰:۰۰"],
        "facilities": ["تهویه مطبوع", "دوش", "کفپوش استاندارد", "اسکوربورد دیجیتال"],
        "description": "سالن تخصصی بسکتبال در شرق تهران با اسکوربورد و حلقه حرفه‌ای"
    },
    {
        "id": "6",
        "name": "زمین چمن مصنوعی درفشی‌فر",
        "sport_type": "فوتسال",
        "region": "غرب تهران",
        "neighborhood": "سعادت‌آباد",
        "is_indoor": False,
        "rating": 4.9,
        "price_per_hour": 650000,
        "available_slots": ["شنبه ۲۱:۰۰", "یکشنبه ۲۲:۰۰", "جمعه ۲۰:۰۰"],
        "facilities": ["چمن مصنوعی درجه یک", "پارکینگ", "کافه", "دوش"],
        "description": "زمین چمن مصنوعی روباز مناسب فوتبال ۶ نفره و فوتسال در سعادت‌آباد"
    },
    {
        "id": "7",
        "name": "آکادمی پدل ولنجک",
        "sport_type": "پدل",
        "region": "شمال تهران",
        "neighborhood": "ولنجک",
        "is_indoor": True,
        "rating": 4.8,
        "price_per_hour": 950000,
        "available_slots": ["دوشنبه ۱۸:۰۰", "پنجشنبه ۲۱:۰۰", "جمعه ۱۸:۰۰"],
        "facilities": ["سرپوشیده", "پارکینگ", "اجاره راکت", "کافه رستوران"],
        "description": "کورت پدل سرپوشیده چهارفصل در ولنجک بدون نگرانی از بارندگی"
    },
    {
        "id": "8",
        "name": "سالن اقتصادی بعثت",
        "sport_type": "فوتسال",
        "region": "جنوب تهران",
        "neighborhood": "بعثت",
        "is_indoor": True,
        "rating": 4.2,
        "price_per_hour": 250000,
        "available_slots": ["یکشنبه ۱۶:۰۰", "سه شنبه ۲۰:۰۰", "جمعه ۱۴:۰۰"],
        "facilities": ["سرویس بهداشتی", "پارکینگ"],
        "description": "سالن فوتسال ارزان و اقتصادی مناسب بازی‌های دوستانه دانشجویی"
    }
]

policy_documents = [
    {
        "topic": "قوانین کنسلی، لغو رزرو و بازپرداخت وجه",
        "keywords": ["کنسل", "لغو", "بازپرداخت", "پول", "جریمه", "استرداد", "پس گرفتن"],
        "content": (
            "۱. لغو رزرو تا ۲۴ ساعت قبل از شروع سانس کاملاً رایگان است و ۱۰۰٪ مبلغ بازگردانده می‌شود.\n"
            "۲. لغو رزرو بین ۱۲ تا ۲۴ ساعت مانده به سانس، شامل ۲۰٪ جریمه کنسلی است و ۸۰٪ مبلغ مسترد می‌گردد.\n"
            "۳. در صورت لغو رزرو در کمتر از ۱۲ ساعت مانده به شروع بازی، وجهی مسترد نخواهد شد."
        )
    },
    {
        "topic": "شرایط آب و هوایی و بارندگی (زمین‌های روباز)",
        "keywords": ["باران", "بارون", "برف", "آب و هوا", "طوفان", "خیس"],
        "content": (
            "در زمین‌های روباز، در صورت بارندگی شدید و عدم امکان بازی، "
            "کاربر می‌تواند بدون جریمه سانس خود را جابه‌جا کند یا ۱۰۰٪ مبلغ پرداختی را دریافت نماید."
        )
    },
    {
        "topic": "تجهیزات ورزشی، توپ، راکت و لباس",
        "keywords": ["راکت", "توپ", "کفش", "لباس", "وسایل", "تجهیزات"],
        "content": (
            "در سالن‌های فوتسال، والیبال و بسکتبال، یک عدد توپ استاندارد به صورت امانی تحویل داده می‌شود. "
            "در کورت‌های پدل، امکان اجاره راکت و توپ در محل فراهم است. همراه داشتن کفش ورزشی استاندارد الزامی است."
        )
    },
    {
        "topic": "قوانین حضور، تاخیر و تعداد نفرات",
        "keywords": ["تاخیر", "دیر", "نفرات", "تعداد", "چند نفر", "ورود", "قوانین", "مقررات"],
        "content": (
            "حضور بازیکنان ۱۵ دقیقه قبل از شروع سانس الزامی است و زمان تاخیر قابل جبران نیست. "
            "حداکثر نفرات مجاز برای فوتسال ۱۲ نفر، پدل ۴ نفر، تنیس ۴ نفر و والیبال/بسکتبال ۱۴ نفر است."
        )
    }
]

def get_all_courts():
    return mock_courts

def search_policies(user_query: str, force_all: bool = False) -> str:
    matched_docs = []
    for doc in policy_documents:
        if any(kw in user_query for kw in doc["keywords"]):
            matched_docs.append(f"• {doc['topic']}:\n{doc['content']}")
    
    if not matched_docs and force_all:
        matched_docs = [f"• {doc['topic']}:\n{doc['content']}" for doc in policy_documents]
        
    return "\n\n".join(matched_docs)

def reserve_court_slot(court_name: str, requested_slot: str) -> dict:
    with booking_lock:
        target_court = None
        norm_court_name = normalize_text(court_name)
        
        for court in mock_courts:
            norm_db_name = normalize_text(court["name"])
            if norm_court_name and (norm_court_name in norm_db_name or norm_db_name in norm_court_name):
                target_court = court
                break
        
        if not target_court:
            return {"status": "court_not_found", "court": None, "invoice": None}

        if not requested_slot or requested_slot == "نامشخص":
            return {"status": "missing_slot", "court": target_court, "invoice": None}

        norm_req_slot = normalize_text(requested_slot)
        matched_slot = None
        
        for slot in target_court["available_slots"]:
            norm_db_slot = normalize_text(slot)
            # تطابق دقیق پس از یکسان‌سازی اعداد فارسی و انگلیسی
            if norm_req_slot in norm_db_slot or norm_db_slot in norm_req_slot:
                matched_slot = slot
                break
            # بررسی تطابق روز و عدد ساعت به صورت مجزا (مثلاً "پنجشنبه 20" با "پنجشنبه ۲۰:۰۰")
            parts = norm_req_slot.split()
            if len(parts) >= 2 and all(p in norm_db_slot for p in parts):
                matched_slot = slot
                break

        if not matched_slot:
            return {"status": "slot_unavailable", "court": target_court, "invoice": None}

        target_court["available_slots"].remove(matched_slot)

        invoice_code = f"INV-{uuid.uuid4().hex[:6].upper()}"
        invoice = {
            "invoice_id": invoice_code,
            "court_id": target_court["id"],
            "court_name": target_court["name"],
            "sport_type": target_court["sport_type"],
            "neighborhood": target_court["neighborhood"],
            "reserved_slot": matched_slot,
            "amount_toman": target_court["price_per_hour"],
            "status": "PENDING_PAYMENT",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "payment_url": f"https://shaparak.ir/pay/{invoice_code}"
        }
        active_invoices[invoice_code] = invoice
        return {"status": "booked", "court": target_court, "invoice": invoice}

def cancel_court_reservation(court_name: str = None, slot: str = None, invoice_id: str = None) -> dict:
    with booking_lock:
        target_inv = None
        if invoice_id and invoice_id in active_invoices:
            target_inv = active_invoices[invoice_id]
        else:
            norm_name = normalize_text(court_name) if court_name else ""
            for inv_id, inv in reversed(list(active_invoices.items())):
                if inv["status"] != "CANCELLED":
                    norm_inv_name = normalize_text(inv["court_name"])
                    if not norm_name or (norm_name in norm_inv_name or norm_inv_name in norm_name):
                        target_inv = inv
                        break

        if not target_inv:
            return {"status": "not_found", "cancelled_invoice": None}

        for court in mock_courts:
            if court["id"] == target_inv["court_id"]:
                if target_inv["reserved_slot"] not in court["available_slots"]:
                    court["available_slots"].insert(0, target_inv["reserved_slot"])
                break

        target_inv["status"] = "CANCELLED"
        return {"status": "cancelled", "cancelled_invoice": target_inv}