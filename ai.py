import json
import os
from datetime import date

import requests
from dotenv import load_dotenv
from db import get_absentees, get_presentees, get_weekly_report, is_attendance_marked

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "openai/gpt-4o-mini"  # OpenRouter'dagi model nomi

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_absentees",
            "description": "Berilgan sanada kelmagan (sababli yoki sababsiz) o'quvchilar ro'yxatini qaytaradi",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "YYYY-MM-DD formatida sana"}
                },
                "required": ["date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_presentees",
            "description": "Berilgan sanada kelgan o'quvchilar ro'yxatini qaytaradi",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "YYYY-MM-DD formatida sana"}
                },
                "required": ["date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weekly_report",
            "description": "So'nggi 7 kun ichida kelmagan o'quvchilarning to'liq ro'yxatini (har bir sana va sababi bilan) qaytaradi. 'shu hafta', 'bu haftaning davomati' kabi so'rovlar uchun ishlatiladi.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "is_attendance_marked",
            "description": "Berilgan sanada davomat umuman belgilangan-belgilanmaganini tekshiradi. Har doim get_absentees yoki get_presentees'dan OLDIN shu funksiyani chaqir.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "YYYY-MM-DD formatida sana"}
                },
                "required": ["date"]
            }
        }
    }
]

FUNCTIONS = {
    "get_absentees": get_absentees,
    "get_presentees": get_presentees,
    "get_weekly_report": get_weekly_report,
    "is_attendance_marked": is_attendance_marked,
}



def _call_ai(messages, use_tools=True):
    payload = {"model": MODEL, "messages": messages}
    if use_tools:
        payload["tools"] = TOOLS
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
        json=payload
    ).json()
    if "choices" not in resp:
        # OpenRouter xato qaytardi (masalan rate limit yoki noto'g'ri kalit)
        print("OPENROUTER XATOSI:", resp)
        raise RuntimeError(resp.get("error", {}).get("message", "Noma'lum xato"))
    return resp["choices"][0]["message"]


def ask_ai(user_question: str) -> str:
    today = str(date.today())
    messages = [
        {
            "role": "system",
            "content": f"Bugungi sana: {today}. Foydalanuvchi 'bugun', 'kecha', 'ertaga' "
                       f"kabi so'zlar ishlatsa, shu sanaga nisbatan hisobla va funksiyaga "
                       f"aniq YYYY-MM-DD formatida sana ber. Javob berishdan oldin albatta "
                       f"tegishli funksiyani chaqir — ma'lumotni o'zing to'qib yozma. "
                       f"'Shu hafta', 'bu hafta' kabi so'rovlar uchun get_weekly_report "
                       f"funksiyasini ishlat. Javobni o'zbek tilida, qisqa va aniq yoz. "
                       f"Diqqat: get_absentees bo'sh natija qaytarsa, bu 'hech kim kelmagan' "
                       f"degani — barcha o'quvchilar kelgan hisoblanadi. Avval is_attendance_marked "
                       f"funksiyasini chaqir; agar u False qaytarsa (davomat belgilanmagan), "
                       f"foydalanuvchiga xuddi hamma kelgandek javob ber: 'kelmagan o'quvchi yo'q, "
                       f"hammasi keldi' deb ayt. Agar u True qaytarsa, albatta get_absentees yoki "
                       f"get_presentees funksiyasini ham chaqirib, haqiqiy natijaga qarab javob ber."
        },
        {"role": "user", "content": user_question}
    ]

    try:
        for _ in range(5):  # ortiqcha cheksiz aylanishning oldini olish uchun limit
            msg = _call_ai(messages)

            if not msg.get("tool_calls"):
                return msg["content"]

            messages.append(msg)

            for call in msg["tool_calls"]:
                func_name = call["function"]["name"]
                args = json.loads(call["function"]["arguments"] or "{}")
                print(f"AI chaqirdi: {func_name}({args})")  # debug uchun

                func = FUNCTIONS[func_name]
                data = func(args["date"]) if "date" in args else func()
                print(f"Bazadan natija: {data}")  # debug uchun

                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(data, ensure_ascii=False)
                })

        # 5 aylanishdan keyin ham tugamasa, oxirgi javobni tools'siz olamiz
        final = _call_ai(messages, use_tools=False)
        return final["content"]

    except Exception as e:
        print("ask_ai XATOSI:", repr(e))
        return "Kechirasiz, javob berishda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring."