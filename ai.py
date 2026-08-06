import json
import os
from datetime import date

import requests
from dotenv import load_dotenv
from db import get_absentees, get_presentees, get_weekly_report

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
    }
]

FUNCTIONS = {
    "get_absentees": get_absentees,
    "get_presentees": get_presentees,
    "get_weekly_report": get_weekly_report,
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
                       f"funksiyasini ishlat. Javobni o'zbek tilida, qisqa va aniq yoz."
        },
        {"role": "user", "content": user_question}
    ]

    try:
        msg = _call_ai(messages)

        if msg.get("tool_calls"):
            messages.append(msg)

            # AI bir nechta funksiyani birdan chaqirishi mumkin —
            # har biriga alohida javob qaytarish shart, aks holda API xato beradi
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

            final = _call_ai(messages, use_tools=False)
            return final["content"]

        return msg["content"]

    except Exception as e:
        print("ask_ai XATOSI:", repr(e))
        return "Kechirasiz, javob berishda xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring."