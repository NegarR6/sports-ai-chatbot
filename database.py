# database.py
import re
import threading
import uuid
from datetime import datetime

booking_lock = threading.Lock()
active_invoices = {}

def normalize_text(text: str) -> str:
    """تبدیل اعداد انگلیسی و عربی به فارسی و یکسان‌سازی نیم‌فاصله‌ها و افعال محاوره‌ای"""
    if not text:
        return ""
    en_to_fa = str.maketrans("0123456789٠١٢٣٤٥٦٧٨٩", "۰۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹")
    cleaned = text.translate(en_to_fa)
    cleaned = cleaned.replace("‌", " ").replace("\u200c", " ")
    cleaned = re.sub(r"\bنمی\s+", "نمی", cleaned)
    cleaned = re.sub(r"\bمی\s+", "می", cleaned)
    for word in ["ساعت", "سانس", "روز", "برای", "در"]:
        cleaned = re.sub(rf"\b{word}\b", " ", cleaned)
    return " ".join(cleaned.split())

def extract_weekdays(text: str) -> list:
    """استخراج دقیق روزهای هفته بدون تداخل کلمه «شنبه» با «یکشنبه/دوشنبه/پنجشنبه»"""
    if not text:
        return []
    t = text.replace("‌", " ").replace("\u200c", " ")
    t = re.sub(r"یک\s+شنبه", "یکشنبه", t)
    t = re.sub(r"دو\s+شنبه", "دوشنبه", t)
    t = re.sub(r"سه\s*شنبه", "سه شنبه", t)
    t = re.sub(r"چهار\s+شنبه", "چهارشنبه", t)
    t = re.sub(r"پنج\s+شنبه", "پنجشنبه", t)

    compound_days = ["یکشنبه", "دوشنبه", "سه شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
    found = []
    temp = t
    for d in compound_days:
        if d in temp:
            found.append(d)
            temp = temp.replace(d, " ")

    if "شنبه" in temp:
        found.insert(0, "شنبه")

    return found

SUPPORTED_SPORTS = ["فوتسال", "پدل", "تنیس", "والیبال", "بسکتبال"]

UNSUPPORTED_SPORTS_MAP = {
    "شنا": "شنا و استخر",
    "استخر": "شنا و استخر",
    "جکوزی": "شنا و استخر",
    "سونا": "شنا و استخر",
    "ماساژ": "ماساژ و اسپا",
    "اسپا": "ماساژ و اسپا",
    "واترپلو": "واترپلو",
    "شیرجه": "شیرجه و استخر",
    "اسب سواری": "اسب‌سواری و سوارکاری",
    "سوارکاری": "اسب‌سواری و سوارکاری",
    "چوگان": "چوگان و سوارکاری",
    "بدمینتون": "بدمینتون",
    "پینگ پنگ": "تنیس روی میز (پینگ‌پنگ)",
    "تنیس روی میز": "تنیس روی میز (پینگ‌پنگ)",
    "اسکواش": "اسکواش",
    "بولینگ": "بولینگ",
    "بیلیارد": "بیلیارد و اسنوکر",
    "اسنوکر": "بیلیارد و اسنوکر",
    "کشتی": "کشتی",
    "کاراته": "ورزش‌های رزمی",
    "تکواندو": "ورزش‌های رزمی",
    "بوکس": "بوکس",
    "کیک بوکسینگ": "بوکس و رزمی",
    "جودو": "ورزش‌های رزمی",
    "ووشو": "ورزش‌های رزمی",
    "شمشیربازی": "شمشیربازی",
    "بدنسازی": "باشگاه بدنسازی و فیتنس",
    "فیتنس": "باشگاه بدنسازی و فیتنس",
    "کراس فیت": "کراس‌فیت و بدنسازی",
    "یوگا": "یوگا و پیلاتس",
    "پیلاتس": "یوگا و پیلاتس",
    "ایروبیک": "ایروبیک و فیتنس",
    "ژیمناستیک": "ژیمناستیک",
    "اسکی": "اسکی",
    "پینت بال": "پینت‌بال",
    "کارتینگ": "کارتینگ",
    "تیراندازی": "تیراندازی",
    "کمان": "تیراندازی با کمان",
    "هندبال": "هندبال",
    "گلف": "گلف",
    "هاکی": "هاکی",
    "اسکیت": "اسکیت",
    "صخره نوردی": "صخره‌نوردی",
    "سنگ نوردی": "سنگ‌نوردی",
    "دوچرخه": "دوچرخه‌سواری",
    "شطرنج": "شطرنج",
    "دارت": "دارت",
    "فوتبال دستی": "فوتبال‌دستی"
}

INITIAL_SLOTS_BACKUP = {
    "1": ["یکشنبه ۱۷:۰۰", "دوشنبه ۱۹:۰۰", "پنجشنبه ۲۱:۰۰"],
    "2": ["یکشنبه ۱۷:۰۰", "چهارشنبه ۲۰:۰۰", "جمعه ۱۰:۰۰"],
    "3": ["شنبه ۱۶:۰۰", "سه شنبه ۱۸:۰۰", "پنجشنبه ۱۶:۰۰"],
    "4": ["یکشنبه ۱۹:۰۰", "پنجشنبه ۱۸:۰۰", "جمعه ۱۶:۰۰"],
    "5": ["یکشنبه ۱۵:۰۰", "پنجشنبه ۲۰:۰۰"],
    "6": ["شنبه ۲۱:۰۰", "یکشنبه ۲۲:۰۰", "جمعه ۲۰:۰۰"],
    "7": ["دوشنبه ۱۸:۰۰", "پنجشنبه ۲۱:۰۰", "جمعه ۱۸:۰۰"],
    "8": ["یکشنبه ۱۶:۰۰", "سه شنبه ۲۰:۰۰", "جمعه ۱۴:۰۰"]
}

mock_courts = [
    {
        "id": "1",
        "name": "سالن فوتسال چمران",
        "keywords": ["چمران", "شهرک غرب"],
        "sport_type": "فوتسال",
        "region": "غرب تهران",
        "neighborhood": "شهرک غرب",
        "is_indoor": True,
        "rating": 4.8,
        "price_per_hour": 400000,
        "recommended_players": 10,
        "available_slots": list(INITIAL_SLOTS_BACKUP["1"]),
        "facilities": ["دوش", "پارکینگ", "تهویه مطبوع", "کفپوش پارکت"],
        "description": "سالن سرپوشیده استاندارد با کفپوش عالی و جای پارک راحت در شهرک غرب"
    },
    {
        "id": "2",
        "name": "مجموعه ورزشی انقلاب - کورت پدل",
        "keywords": ["انقلاب", "سئول"],
        "sport_type": "پدل",
        "region": "شمال تهران",
        "neighborhood": "سئول",
        "is_indoor": False,
        "rating": 4.9,
        "price_per_hour": 800000,
        "recommended_players": 4,
        "available_slots": list(INITIAL_SLOTS_BACKUP["2"]),
        "facilities": ["کافه", "پارکینگ", "اجاره راکت", "رختکن VIP"],
        "description": "کورت استاندارد جهانی پدل در فضای باز با امکان اجاره راکت و توپ و رختکن VIP"
    },
    {
        "id": "3",
        "name": "زمین تنیس استقلال",
        "keywords": ["استقلال", "میرداماد"],
        "sport_type": "تنیس",
        "region": "مرکز تهران",
        "neighborhood": "میرداماد",
        "is_indoor": False,
        "rating": 4.6,
        "price_per_hour": 600000,
        "recommended_players": 2,
        "available_slots": list(INITIAL_SLOTS_BACKUP["3"]),
        "facilities": ["دوش", "فروشگاه لوازم ورزشی", "مربی خصوصی"],
        "description": "زمین تنیس خاک رس با نورپردازی حرفه‌ای برای بازی در شب"
    },
    {
        "id": "4",
        "name": "سالن چندمنظوره آزادی",
        "keywords": ["آزادی", "ازادی", "اکباتان"],
        "sport_type": "والیبال",
        "region": "غرب تهران",
        "neighborhood": "اکباتان",
        "is_indoor": True,
        "rating": 4.5,
        "price_per_hour": 350000,
        "recommended_players": 12,
        "available_slots": list(INITIAL_SLOTS_BACKUP["4"]),
        "facilities": ["سرویس بهداشتی", "جایگاه تماشاچی", "بوفه"],
        "description": "سالن سقف بلند مناسب والیبال و تمرینات تیمی در محدوده اکباتان"
    },
    {
        "id": "5",
        "name": "سالن بسکتبال شهید حیدری",
        "keywords": ["حیدری", "نارمک"],
        "sport_type": "بسکتبال",
        "region": "شرق تهران",
        "neighborhood": "نارمک",
        "is_indoor": True,
        "rating": 4.7,
        "price_per_hour": 450000,
        "recommended_players": 10,
        "available_slots": list(INITIAL_SLOTS_BACKUP["5"]),
        "facilities": ["تهویه مطبوع", "دوش", "کفپوش استاندارد", "اسکوربورد دیجیتال"],
        "description": "سالن تخصصی بسکتبال در شرق تهران با اسکوربورد و حلقه حرفه‌ای"
    },
    {
        "id": "6",
        "name": "زمین چمن مصنوعی درفشی‌فر",
        "keywords": ["درفشی", "درفشی فر", "سعادت آباد"],
        "sport_type": "فوتسال",
        "region": "غرب تهران",
        "neighborhood": "سعادت‌آباد",
        "is_indoor": False,
        "rating": 4.9,
        "price_per_hour": 650000,
        "recommended_players": 12,
        "available_slots": list(INITIAL_SLOTS_BACKUP["6"]),
        "facilities": ["چمن مصنوعی درجه یک", "پارکینگ", "کافه", "دوش"],
        "description": "زمین چمن مصنوعی روباز مناسب فوتبال ۶ نفره و فوتسال در سعادت‌آباد"
    },
    {
        "id": "7",
        "name": "آکادمی پدل ولنجک",
        "keywords": ["ولنجک", "آکادمی پدل"],
        "sport_type": "پدل",
        "region": "شمال تهران",
        "neighborhood": "ولنجک",
        "is_indoor": True,
        "rating": 4.8,
        "price_per_hour": 950000,
        "recommended_players": 4,
        "available_slots": list(INITIAL_SLOTS_BACKUP["7"]),
        "facilities": ["سرپوشیده", "پارکینگ", "اجاره راکت", "کافه رستوران"],
        "description": "کورت پدل سرپوشیده چهارفصل در ولنجک بدون نگرانی از بارندگی"
    },
    {
        "id": "8",
        "name": "سالن اقتصادی بعثت",
        "keywords": ["بعثت", "اقتصادی"],
        "sport_type": "فوتسال",
        "region": "جنوب تهران",
        "neighborhood": "بعثت",
        "is_indoor": True,
        "rating": 4.2,
        "price_per_hour": 250000,
        "recommended_players": 10,
        "available_slots": list(INITIAL_SLOTS_BACKUP["8"]),
        "facilities": ["سرویس بهداشتی", "پارکینگ"],
        "description": "سالن فوتسال ارزان و اقتصادی مناسب بازی‌های دوستانه دانشجویی"
    }
]

def reset_database_state():
    """پاکسازی فاکتورهای قبلی و بازگرداندن ظرفیت اولیه سالن‌ها هنگام شروع نشست جدید"""
    with booking_lock:
        active_invoices.clear()
        for court in mock_courts:
            cid = court["id"]
            if cid in INITIAL_SLOTS_BACKUP:
                court["available_slots"] = list(INITIAL_SLOTS_BACKUP[cid])

policy_documents = [
    {
        "topic": "قوانین کنسلی، لغو رزرو و بازپرداخت وجه",
        "keywords": ["کنسلی", "کنسلیتون", "بازپرداخت", "جریمه", "استرداد", "پس گرفتن", "چند ساعت قبل"],
        "content": (
            "۱. لغو رزرو تا ۲۴ ساعت قبل از شروع سانس کاملاً رایگان است و ۱۰۰٪ مبلغ بازگردانده می‌شود.\n"
            "۲. لغو رزرو بین ۱۲ تا ۲۴ ساعت مانده به سانس، شامل ۲۰٪ جریمه کنسلی است و ۸۰٪ مبلغ مسترد می‌گردد.\n"
            "۳. در صورت لغو رزرو در کمتر از ۱۲ ساعت مانده به شروع بازی، وجهی مسترد نخواهد شد."
        )
    },
    {
        "topic": "شرایط آب و هوایی و بارندگی (زمین‌های روباز)",
        "keywords": ["باران", "بارون", "برف", "آب و هوا", "طوفان", "خیس", "بارندگی", "پولمون پس"],
        "content": (
            "در زمین‌های روباز (مانند چمن درفشی‌فر، پدل انقلاب و تنیس استقلال)، در صورت بارندگی شدید و عدم امکان بازی، "
            "کاربر می‌تواند بدون جریمه سانس خود را جابه‌جا کند یا ۱۰۰٪ مبلغ پرداختی را دریافت نماید."
        )
    },
    {
        "topic": "تجهیزات ورزشی، توپ، راکت و لباس",
        "keywords": ["راکت", "توپ", "کفش", "لباس", "وسایل", "تجهیزات", "اجاره راکت"],
        "content": (
            "در سالن‌های فوتسال، والیبال و بسکتبال، یک عدد توپ استاندارد به صورت امانی و رایگان تحویل داده می‌شود. "
            "در کورت‌های پدل (انقلاب و ولنجک)، امکان اجاره راکت (هر عدد ۱۰۰ هزار تومان) و توپ در محل فراهم است. همراه داشتن کفش ورزشی استاندارد الزامی است."
        )
    },
    {
        "topic": "قوانین حضور، تاخیر و تعداد نفرات",
        "keywords": ["تاخیر", "دیر برسن", "دیر برسیم", "دیر بشه", "دیر بیایم", "چند نفر", "ظرفیت مجاز", "مقررات حضور"],
        "content": (
            "حضور بازیکنان ۱۵ دقیقه قبل از شروع سانس الزامی است و زمان تاخیر کاربران قابل جبران یا تمدید نیست. "
            "حداکثر نفرات مجاز برای فوتسال ۱۲ نفر، پدل ۴ نفر، تنیس ۴ نفر و والیبال/بسکتبال ۱۴ نفر است."
        )
    },
    {
        "topic": "رزرو بلندمدت، قرارداد شرکتی و تخفیف دانشجویی",
        "keywords": ["تخفیف", "شرکتی", "قرارداد", "بلندمدت", "دانشجویی", "تورنمنت", "ماهیانه"],
        "content": (
            "برای رزروهای ماهانه (بیش از ۴ جلسه در ماه) یا قراردادهای سازمانی و دانشگاهی، ۱۰٪ تخفیف ویژه اعمال می‌شود. "
            "همچنین سالن اقتصادی بعثت با تعرفه ویژه دانشجویی (ساعتی ۲۵۰ هزار تومان) ارائه می‌گردد."
        )
    },
    {
        "topic": "ساعت کاری کافه، بوفه و خدمات رفاهی مجموعه‌ها",
        "keywords": ["کافش", "ساعت کاری", "تا چه ساعتی بازه", "کی بازه", "بوفه", "رستوران"],
        "content": (
            "کافه، کافه‌رستوران و بوفه مجموعه‌های ورزشی (از جمله آکادمی پدل ولنجک، پدل انقلاب و چمن درفشی‌فر) همه‌روزه از ساعت ۰۹:۰۰ صبح الی ۲۳:۰۰ شب (تا پایان آخرین سانس) فعال و آماده پذیرایی از ورزشکاران هستند."
        )
    },
    {
        "topic": "مربی خصوصی، داور و خدمات جانبی",
        "keywords": ["مربی", "آموزش", "کلاس", "داور", "فیلمبرداری", "کمد"],
        "content": (
            "در زمین تنیس استقلال امکان هماهنگی مربی خصوصی وجود دارد. تمامی مجموعه‌ها دارای رختکن مجزا و کمد قفل‌دار هستند "
            "و مجموعه پدل انقلاب مجهز به رختکن VIP می‌باشد."
        )
    }
]

def get_all_courts():
    return mock_courts

def find_courts_mentioned_in_text(text: str) -> list:
    norm_t = normalize_text(text)
    matched = []
    for c in mock_courts:
        if any(normalize_text(kw) in norm_t for kw in c.get("keywords", [])):
            matched.append(c)
    return matched

def detect_unsupported_sport(text: str) -> str:
    norm_t = normalize_text(text)
    for kw, title in UNSUPPORTED_SPORTS_MAP.items():
        if normalize_text(kw) in norm_t:
            return title

    known_words = (
        SUPPORTED_SPORTS
        + ["فوتبال", "چمن", "ورزشی", "خوب", "ارزان", "ارزون", "گران", "گرون", "سرپوشیده", "روباز", "تهران", "غرب", "شرق", "شمال", "جنوب", "مرکز"]
        + [kw for c in mock_courts for kw in c.get("keywords", [])]
    )
    if not any(normalize_text(k) in norm_t for k in known_words):
        m = re.search(r"(?:سالن|زمین|باشگاه|کورت|استخر|پیست|مرکز)\s+([آ-ی]+(?:\s+[آ-ی]+)?)", norm_t)
        if m:
            candidate = m.group(1).strip()
            stop_words = [
                "میخوام", "می خوام", "دارید", "داری", "چی", "کجاست", "چطوره", "چطورن",
                "خوبه", "در", "تو", "سمت", "این", "دو", "مکان", "ها", "هارو", "منظورم", "هست", "بود"
            ]
            cleaned_parts = [w for w in candidate.split() if w not in stop_words]
            if cleaned_parts:
                return " ".join(cleaned_parts)

    return ""

def search_policies(user_query: str, force_all: bool = False) -> str:
    norm_q = user_query.replace("‌", " ").replace("\u200c", " ")
    matched_docs = []
    for doc in policy_documents:
        if any(kw in norm_q for kw in doc["keywords"]):
            matched_docs.append(f"• {doc['topic']}:\n{doc['content']}")
        elif doc["topic"].startswith("قوانین حضور") and ("دیر" in norm_q or "تاخیر" in norm_q):
            matched_docs.append(f"• {doc['topic']}:\n{doc['content']}")
        elif doc["topic"].startswith("قوانین کنسلی") and ("قوانین" in norm_q or "شرایط" in norm_q) and ("کنسل" in norm_q or "لغو" in norm_q):
            matched_docs.append(f"• {doc['topic']}:\n{doc['content']}")
    
    if not matched_docs and force_all:
        matched_docs = [f"• {doc['topic']}:\n{doc['content']}" for doc in policy_documents[:4]]
        
    return "\n\n".join(matched_docs)

def _find_target_court(court_name: str):
    if not court_name:
        return None
    norm_court_name = normalize_text(court_name)
    for court in mock_courts:
        norm_db_name = normalize_text(court["name"])
        if norm_court_name and (norm_court_name in norm_db_name or norm_db_name in norm_court_name):
            return court
        if any(normalize_text(kw) in norm_court_name for kw in court.get("keywords", [])):
            return court
    return None

def _slot_matches_single_request(slot: str, req: str) -> bool:
    norm_slot = normalize_text(slot)
    norm_req = normalize_text(req)
    if norm_req == norm_slot:
        return True

    req_days = extract_weekdays(req)
    slot_days = extract_weekdays(slot)
    if req_days and slot_days:
        if not any(rd == sd for rd in req_days for sd in slot_days):
            return False
        req_nums = re.findall(r"[۰-۹]+", norm_req)
        if req_nums:
            slot_hour = re.findall(r"[۰-۹]+", norm_slot)
            if slot_hour:
                return req_nums[0] == slot_hour[0]
        return True

    req_nums = re.findall(r"[۰-۹]+", norm_req)
    if req_nums and not req_days:
        slot_hour = re.findall(r"[۰-۹]+", norm_slot)
        if slot_hour:
            return req_nums[0] == slot_hour[0]

    return False

def match_slots_in_court(target_court: dict, requested_slot: str) -> list:
    if not target_court or not target_court["available_slots"]:
        return []
    if requested_slot == "ALL":
        return list(target_court["available_slots"])
    if "،" in requested_slot:
        req_parts = [p.strip() for p in requested_slot.split("،") if p.strip()]
        return [
            s for s in target_court["available_slots"]
            if any(_slot_matches_single_request(s, rp) for rp in req_parts)
        ]

    for slot in target_court["available_slots"]:
        if _slot_matches_single_request(slot, requested_slot):
            return [slot]
    return []

def reserve_court_slot(court_name: str, requested_slot: str) -> dict:
    with booking_lock:
        target_court = _find_target_court(court_name)
        if not target_court:
            return {"status": "court_not_found", "court": None, "invoice": None}

        if not requested_slot or requested_slot == "نامشخص":
            return {"status": "missing_slot", "court": target_court, "invoice": None}

        slots_to_book = match_slots_in_court(target_court, requested_slot)
        if not slots_to_book:
            return {"status": "slot_unavailable", "court": target_court, "invoice": None}

        for s in slots_to_book:
            target_court["available_slots"].remove(s)

        invoice_code = f"INV-{uuid.uuid4().hex[:6].upper()}"
        combined_slots_str = " + ".join(slots_to_book)
        total_amount = target_court["price_per_hour"] * len(slots_to_book)
        invoice = {
            "invoice_id": invoice_code,
            "court_id": target_court["id"],
            "court_name": target_court["name"],
            "sport_type": target_court["sport_type"],
            "neighborhood": target_court["neighborhood"],
            "reserved_slot": combined_slots_str,
            "booked_slots_list": slots_to_book,
            "sub_items": [{"court_id": target_court["id"], "court_name": target_court["name"], "slots": slots_to_book, "subtotal": total_amount}],
            "amount_toman": total_amount,
            "status": "PENDING_PAYMENT",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "payment_url": f"https://shaparak.ir/pay/{invoice_code}"
        }
        active_invoices[invoice_code] = invoice
        return {"status": "booked", "court": target_court, "invoice": invoice}

def reserve_multiple_orders(orders: list) -> dict:
    with booking_lock:
        sub_items = []
        total_amount = 0
        court_names = []
        neighborhoods = []
        slot_summaries = []

        for item in orders:
            c_name = item.get("court_name")
            req_slot = item.get("slot")
            target_court = _find_target_court(c_name)
            if not target_court:
                continue
            matched_slots = match_slots_in_court(target_court, req_slot)
            if not matched_slots:
                continue

            for s in matched_slots:
                target_court["available_slots"].remove(s)

            subtotal = target_court["price_per_hour"] * len(matched_slots)
            total_amount += subtotal
            if target_court["name"] not in court_names:
                court_names.append(target_court["name"])
            if target_court["neighborhood"] not in neighborhoods:
                neighborhoods.append(target_court["neighborhood"])

            slot_summaries.append(f"{target_court['name']} ({' + '.join(matched_slots)})")
            sub_items.append({
                "court_id": target_court["id"],
                "court_name": target_court["name"],
                "slots": matched_slots,
                "subtotal": subtotal
            })

        if not sub_items:
            return {"status": "slot_unavailable", "court": None, "invoice": None}

        invoice_code = f"INV-{uuid.uuid4().hex[:6].upper()}"
        invoice = {
            "invoice_id": invoice_code,
            "court_id": sub_items[0]["court_id"],
            "court_name": " و ".join(court_names),
            "sport_type": "رزرو ترکیبی",
            "neighborhood": "، ".join(neighborhoods),
            "reserved_slot": " | ".join(slot_summaries),
            "booked_slots_list": [s for sub in sub_items for s in sub["slots"]],
            "sub_items": sub_items,
            "amount_toman": total_amount,
            "status": "PENDING_PAYMENT",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "payment_url": f"https://shaparak.ir/pay/{invoice_code}"
        }
        active_invoices[invoice_code] = invoice
        return {"status": "booked", "court": None, "invoice": invoice}

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
                    norm_inv_sport = normalize_text(inv.get("sport_type", ""))
                    name_match = (
                        not norm_name
                        or (norm_name in norm_inv_name or norm_inv_name in norm_name)
                        or (norm_name == norm_inv_sport)
                    )
                    slot_match = not slot or _slot_matches_single_request(inv["reserved_slot"], slot)
                    if name_match and slot_match:
                        target_inv = inv
                        break

        if not target_inv:
            return {"status": "not_found", "cancelled_invoice": None}

        if "sub_items" in target_inv:
            for sub in target_inv["sub_items"]:
                for court in mock_courts:
                    if court["id"] == sub["court_id"]:
                        for s in reversed(sub["slots"]):
                            if s not in court["available_slots"]:
                                court["available_slots"].insert(0, s)
                        break
        else:
            for court in mock_courts:
                if court["id"] == target_inv["court_id"]:
                    restored_slots = target_inv.get("booked_slots_list", [target_inv["reserved_slot"]])
                    for s in reversed(restored_slots):
                        if s not in court["available_slots"]:
                            court["available_slots"].insert(0, s)
                    break

        target_inv["status"] = "CANCELLED"
        return {"status": "cancelled", "cancelled_invoice": target_inv}

def get_active_bookings() -> list:
    return [
        inv for inv in active_invoices.values()
        if inv["status"] != "CANCELLED"
    ]