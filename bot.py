import os
import re
import warnings
from typing import List, Literal, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from database import (
    get_all_courts,
    reserve_court_slot,
    cancel_court_reservation,
    search_policies
)

warnings.filterwarnings("ignore", category=UserWarning)

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

AVAILABLE_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-flash-latest"
]

def get_llm(model_name: str):
    kwargs = {"model": model_name, "max_retries": 1, "timeout": 8, "google_api_key": api_key}
    if "lite" not in model_name:
        kwargs["temperature"] = 0
    return ChatGoogleGenerativeAI(**kwargs)

def clean_llm_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = [
            item.get("text", "") 
            for item in content 
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        return "\n".join(texts)
    return str(content)

class CourtSearchQuery(BaseModel):
    intent: Literal["search", "book", "cancel", "faq", "chat"] = Field(
        description="هدف کاربر: 'search' جستجو، 'book' رزرو سالن، 'cancel' لغو رزرو، 'faq' سوال درباره قوانین، 'chat' گفتگوی عادی."
    )
    sport_types: List[str] = Field(default_factory=list, description="لیست ورزش‌ها (فوتسال، پدل، تنیس، والیبال، بسکتبال).")
    region: str = Field(default="نامشخص", description="منطقه یا محله. اگر نامشخص بود 'نامشخص'")
    days: List[str] = Field(default_factory=list, description="روزهای هفته (شنبه تا جمعه).")
    max_price: int = Field(default=0, description="حداکثر قیمت به تومان. اگر نگفته بود 0")
    facilities: List[str] = Field(default_factory=list, description="امکانات فیزیکی (سرپوشیده، روباز، پارکینگ، دوش، کافه).")
    selected_court_name: Optional[str] = Field(default=None, description="نام سالن در حالت book یا cancel.")
    selected_slot: Optional[str] = Field(default=None, description="روز و ساعت سانس در حالت book یا cancel.")
    invoice_id: Optional[str] = Field(default=None, description="کد فاکتور مثل INV-XXXXXX")

# ۱. موتور Fast-Path (پردازش آنی در ۰.۰۱ ثانیه برای اکشن‌های مشخص)

def fast_path_extractor(user_text: str) -> Optional[CourtSearchQuery]:
    text = user_text.strip()

    # ۱. تشخیص آنی دکمه رزرو: "رزرو {نام سالن} برای {سانس}"
    book_match = re.match(r"^رزرو\s+(.+?)\s+برای\s+(.+)$", text)
    if book_match:
        return CourtSearchQuery(
            intent="book",
            selected_court_name=book_match.group(1).strip(),
            selected_slot=book_match.group(2).strip()
        )

    # ۲. تشخیص آنی لغو رزرو
    inv_match = re.search(r"(INV-[A-Z0-9]+)", text, re.IGNORECASE)
    if "لغو" in text or "کنسل کنم" in text:
        if "قوانین" not in text and "شرایط" not in text:
            return CourtSearchQuery(
                intent="cancel",
                invoice_id=inv_match.group(1).upper() if inv_match else None
            )

    # ۳. تشخیص آنی سوالات قوانین (FAQ) بدون اشاره به جستجوی سالن
    faq_keywords = ["قوانین کنسلی", "شرایط بارندگی", "بازپرداخت", "توپ و راکت", "تعداد نفرات", "جریمه کنسلی"]
    sport_names = ["فوتسال", "فوتبال", "پدل", "تنیس", "والیبال", "بسکتبال"]
    if any(k in text for k in faq_keywords) and not any(s in text for s in sport_names):
        return CourtSearchQuery(intent="faq")

    return None

def local_fallback_extractor(user_text: str) -> CourtSearchQuery:
    """استخراج‌کننده محلی در صورتی که اینترنت یا سرورهای گوگل در دسترس نباشند (حذف ۱۰۰٪ خطای 500)"""
    sports = [s for s in ["فوتسال", "پدل", "تنیس", "والیبال", "بسکتبال"] if s in user_text]
    if "فوتبال" in user_text or "چمن" in user_text:
        sports.append("فوتسال")
    
    days = [d for d in ["شنبه", "یکشنبه", "دوشنبه", "سه شنبه", "چهارشنبه", "پنجشنبه", "جمعه"] if d in user_text]
    
    region = "نامشخص"
    for r in ["غرب تهران", "شمال تهران", "شرق تهران", "جنوب تهران", "مرکز تهران", "ولنجک", "سعادت‌آباد", "شهرک غرب", "اکباتان", "نارمک", "میرداماد", "سئول", "بعثت"]:
        if r in user_text:
            region = r
            break

    facilities = [f for f in ["سرپوشیده", "روباز", "پارکینگ", "دوش", "کافه"] if f in user_text]
    
    max_price = 0
    if "۵۰۰" in user_text or "500" in user_text or "پونصد" in user_text:
        max_price = 500000
    elif "۴۰۰" in user_text or "400" in user_text or "چهارصد" in user_text:
        max_price = 400000
    elif "۳۰۰" in user_text or "300" in user_text or "سیصد" in user_text or "ارزان" in user_text:
        max_price = 350000

    intent = "search" if (sports or region != "نامشخص" or days or facilities or max_price > 0) else "chat"
    return CourtSearchQuery(
        intent=intent,
        sport_types=sports,
        region=region,
        days=days,
        max_price=max_price,
        facilities=facilities
    )

def extract_filters(user_text: str, chat_history: list) -> CourtSearchQuery:
    # بررسی مسیر سریع (Fast-Path)
    fast_result = fast_path_extractor(user_text)
    if fast_result:
        return fast_result

    history_str = "\n".join([f"{role}: {msg}" for role, msg in chat_history[-4:]])
    prompt_text = f"تاریخچه مکالمه اخیر:\n{history_str}\n\nپیام جدید کاربر: {user_text}"
    
    for model_name in AVAILABLE_MODELS:
        try:
            llm = get_llm(model_name)
            structured_llm = llm.with_structured_output(CourtSearchQuery)
            result = structured_llm.invoke(prompt_text)
            if result.intent == "faq":
                result.facilities = []
            return result
        except Exception:
            continue

    # اگر تمام مدل‌های گوگل شلوغ بودند، به جای خطای 500 از پارسر محلی استفاده کن
    return local_fallback_extractor(user_text)

IGNORED_FACILITY_KEYWORDS = {"توپ", "لباس", "کفش", "وسایل", "تجهیزات", "نامشخص"}

def search_database(filters: CourtSearchQuery) -> dict:
    all_courts = get_all_courts()
    exact_matches = []

    normalized_sports = []
    for sp in filters.sport_types:
        sp_clean = sp.strip()
        if sp_clean and sp_clean != "نامشخص":
            normalized_sports.append("فوتسال" if "فوتبال" in sp_clean or "چمن" in sp_clean else sp_clean)

    valid_days = [d.strip() for d in filters.days if d.strip() and d.strip() != "نامشخص"]

    for court in all_courts:
        if normalized_sports and not any(sp in court["sport_type"] for sp in normalized_sports):
            continue
        
        if filters.region != "نامشخص" and filters.region != "تهران":
            if (filters.region not in court["region"]) and (filters.region not in court["neighborhood"]):
                continue
            
        if filters.max_price > 0 and court["price_per_hour"] > filters.max_price:
            continue
            
        if valid_days:
            if not any(any(day in slot for slot in court["available_slots"]) for day in valid_days):
                continue

        facility_failed = False
        searchable_text = " ".join(court["facilities"]) + " " + court["description"]
        for kw in filters.facilities:
            kw_clean = kw.strip()
            if not kw_clean or kw_clean in IGNORED_FACILITY_KEYWORDS:
                continue
            if kw_clean == "سرپوشیده" and not court["is_indoor"]:
                facility_failed = True
                break
            elif kw_clean == "روباز" and court["is_indoor"]:
                facility_failed = True
                break
            elif kw_clean not in ["سرپوشیده", "روباز"] and kw_clean not in searchable_text:
                facility_failed = True
                break
                
        if facility_failed:
            continue

        exact_matches.append(court)

    if exact_matches:
        return {"match_type": "exact", "courts": exact_matches}

    scored_alternatives = []
    for court in all_courts:
        score = 0
        if normalized_sports and any(sp in court["sport_type"] for sp in normalized_sports):
            score += 5
        if filters.region != "نامشخص" and (filters.region in court["region"] or filters.region in court["neighborhood"]):
            score += 3
        if valid_days and any(any(d in slot for slot in court["available_slots"]) for d in valid_days):
            score += 2
        if filters.max_price > 0 and court["price_per_hour"] <= filters.max_price + 150000:
            score += 1

        if score >= 5:
            scored_alternatives.append((score, court))

    scored_alternatives.sort(key=lambda x: x[0], reverse=True)
    best_alternatives = [item[1] for item in scored_alternatives[:2]]

    return {"match_type": "alternative", "courts": best_alternatives}

def generate_quick_replies(user_query: str, chat_history: list, filters: CourtSearchQuery, search_result: dict, booking_result: dict) -> List[str]:
    intent = filters.intent
    courts = search_result.get("courts", [])
    buttons = []
    all_user_msgs = " ".join([msg for role, msg in chat_history if role == "کاربر"]) + " " + user_query

    if intent == "search":
        if courts:
            first_court = courts[0]
            if first_court["available_slots"]:
                buttons.append(f"رزرو {first_court['name']} برای {first_court['available_slots'][0]}")
            if len(courts) > 1 and courts[1]["available_slots"]:
                buttons.append(f"رزرو {courts[1]['name']} برای {courts[1]['available_slots'][0]}")
            buttons.append("فقط سالن‌های سرپوشیده")
            if "کنسل" not in all_user_msgs:
                buttons.append("قوانین کنسلی و بازپرداخت")
        else:
            buttons = ["سالن فوتسال غرب تهران", "کورت پدل شمال تهران", "ارزان‌ترین سالن‌ها"]

    elif intent == "book":
        b_status = booking_result.get("status")
        target_court = booking_result.get("court")
        if b_status == "booked":
            buttons = ["لغو همین رزرو", "جستجوی یک سالن دیگر", "قوانین کنسلی و بازپرداخت"]
        elif b_status in ["missing_slot", "slot_unavailable"] and target_court:
            for s in target_court["available_slots"]:
                buttons.append(f"رزرو {target_court['name']} برای {s}")
            buttons.append("جستجوی سالن دیگر")
        else:
            buttons = ["سالن فوتسال غرب تهران", "کورت پدل شمال تهران"]

    elif intent == "cancel":
        buttons = ["یکشنبه سالن فوتسال غرب تهران", "کورت پدل سرپوشیده ولنجک", "سالن والیبال غرب تهران"]

    elif intent == "faq":
        candidate_faqs = [
            ("باران", "شرایط بارندگی در زمین روباز چیه؟"),
            ("راکت", "توپ و راکت رو خودمون باید بیاریم؟"),
            ("کنسل", "قوانین کنسلی و بازپرداخت چیه؟"),
            ("تاخیر", "قوانین تاخیر و تعداد نفرات چطوره؟")
        ]
        for kw, btn_text in candidate_faqs:
            if kw not in all_user_msgs and len(buttons) < 2:
                buttons.append(btn_text)
        buttons.append("یکشنبه سالن فوتسال غرب تهران")
        buttons.append("کورت پدل سرپوشیده ولنجک")

    else:
        buttons = [
            "یکشنبه سالن فوتسال غرب تهران",
            "کورت پدل سرپوشیده ولنجک",
            "قوانین کنسلی و بازپرداخت"
        ]

    return buttons[:4]

def build_instant_response(intent: str, search_result: dict, booking_result: dict, cancel_result: dict, policy_context: str) -> str:
    """تولید پاسخ آنی و بدون تاخیر برای عملیات‌های رزرو، لغو، قوانین و پشتیبان جستجو"""
    if intent == "book":
        status = booking_result.get("status")
        inv = booking_result.get("invoice")
        court = booking_result.get("court")
        if status == "booked" and inv:
            return f"سانس **{inv['reserved_slot']}** در **{inv['court_name']}** با موفقیت برای شما قفل شد. مشخصات فاکتور رسمی و لینک درگاه پرداخت در کارت زیر درج شده است."
        elif status == "slot_unavailable" and court:
            return f"متأسفانه این سانس در **{court['name']}** پر شده است. سایر سانس‌های آزاد این مجموعه را می‌توانید در کارت زیر مشاهده و انتخاب کنید."
        elif status == "missing_slot" and court:
            return f"لطفاً یکی از سانس‌های آزاد **{court['name']}** را از روی کارت زیر انتخاب فرمایید."
        return "لطفاً نام مجموعه ورزشی و ساعت مورد نظر خود را مشخص فرمایید."

    if intent == "cancel":
        if cancel_result.get("status") == "cancelled":
            inv = cancel_result.get("cancelled_invoice")
            return f"فاکتور شماره **{inv['invoice_id']}** مربوط به **{inv['court_name']}** با موفقیت باطل شد و ظرفیت سانس مجدداً آزاد گردید."
        return "رزرو فعالی برای لغو یافت نشد."

    if intent == "faq" and policy_context:
        return f"بر اساس مقررات سامانه هوشمند آرنا:\n\n{policy_context}"

    if intent == "search":
        courts = search_result.get("courts", [])
        if not courts:
            return "مجموعه‌ای با این مشخصات یافت نشد. پیشنهاد می‌کنم فیلتر روز یا محدوده را تغییر دهید."
        names = "، ".join([f"**{c['name']}**" for c in courts])
        if search_result.get("match_type") == "exact":
            return f"بر اساس درخواست شما، {len(courts)} مجموعه منطبق ({names}) یافت شد. جزئیات امکانات و دکمه‌های رزرو آنی در کارت‌های زیر قابل مشاهده است."
        else:
            return f"با تمامی شروط دقیق شما سانسی یافت نشد؛ اما نزدیک‌ترین گزینه‌های جایگزین ({names}) در کارت‌های زیر آماده بررسی و رزرو هستند."

    return "من «آرنا»، دستیار هوشمند رزرو مجموعه‌های ورزشی هستم. لطفاً رشته ورزشی، محدوده یا روز مورد نظر خود را بفرمایید."

def generate_response(
    user_text: str,
    intent: str,
    search_result: dict,
    booking_result: dict,
    cancel_result: dict,
    policy_context: str,
    chat_history: list
) -> str:
    # برای رزرو، لغو و سوالات قوانین، پاسخ آنی (۰.۰۱ ثانیه) برگردان تا کاربر اصلاً معطل نشود
    if intent in ["book", "cancel", "faq"]:
        return build_instant_response(intent, search_result, booking_result, cancel_result, policy_context)

    history_str = "\n".join([f"{role}: {msg}" for role, msg in chat_history[-4:]])
    is_first_turn = len(chat_history) == 0
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """تو «آرنا» (ARENA AI)، دستیار هوشمند و رسمی-مدرن سامانه رزرو مجموعه‌های ورزشی هستی.
قوانین:
- لحن تو باید مودب، دقیق، حرفه‌ای و بدون کلمات عامیانه باشد.
- اگر پیام اول نیست (پیام اول: {is_first_turn})، دوباره سلام نکن.
- از ایموجی استفاده نکن.
- چون کارت‌های گرافیکی سالن‌ها زیر پیام تو نمایش داده می‌شود، لیست قیمت و سانس‌ها را در متن تکرار نکن و فقط در ۲ جمله کوتاه نتیجه را معرفی کن.

تاریخچه: {history}
هدف کاربر: {intent}
نوع تطابق: {match_type}
سالن‌ها: {context}
قوانین تکمیلی: {policy_context}"""),
        ("human", "{query}")
    ])
    
    for model_name in AVAILABLE_MODELS[:2]:
        try:
            llm = get_llm(model_name)
            chain = prompt | llm
            response = chain.invoke({
                "history": history_str,
                "is_first_turn": "بله" if is_first_turn else "خیر",
                "intent": intent,
                "match_type": search_result.get("match_type", "none"),
                "context": str(search_result.get("courts", [])),
                "policy_context": policy_context if policy_context else "ندارد",
                "query": user_text
            })
            return clean_llm_text(response.content)
        except Exception:
            continue

    # اگر سرور گوگل شلوغ بود، بدون خطای 500 پاسخ فوری بساز
    return build_instant_response(intent, search_result, booking_result, cancel_result, policy_context)

def handle_chat_turn(user_query: str, chat_history: list) -> dict:
    filters = extract_filters(user_query, chat_history)
    
    search_result = {"match_type": "none", "courts": []}
    booking_result = {"status": "none", "court": None, "invoice": None}
    cancel_result = {"status": "none", "cancelled_invoice": None}
    
    policy_context = search_policies(user_query, force_all=(filters.intent == "faq"))

    if filters.intent == "search":
        search_result = search_database(filters)
    elif filters.intent == "book":
        booking_result = reserve_court_slot(filters.selected_court_name, filters.selected_slot)
        if booking_result["status"] in ["slot_unavailable", "missing_slot"] and booking_result["court"]:
            search_result = {"match_type": "alternative", "courts": [booking_result["court"]]}
    elif filters.intent == "cancel":
        cancel_result = cancel_court_reservation(
            filters.selected_court_name, filters.selected_slot, filters.invoice_id
        )
        
    final_answer = generate_response(
        user_query, filters.intent, search_result, booking_result, cancel_result, policy_context, chat_history
    )
    quick_replies = generate_quick_replies(user_query, chat_history, filters, search_result, booking_result)
    
    chat_history.append(("کاربر", user_query))
    chat_history.append(("چت‌بات", final_answer))
    
    return {
        "reply": final_answer,
        "intent": filters.intent,
        "match_type": search_result["match_type"],
        "extracted_filters": filters.model_dump(),
        "matched_courts": search_result["courts"],
        "booking_status": booking_result["status"],
        "invoice": booking_result["invoice"] or cancel_result["cancelled_invoice"],
        "quick_replies": quick_replies
    }