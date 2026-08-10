import telebot
from datetime import date
from telebot import types
from db import (add_student, get_all_students, mark_attendance,
                 get_attendance_summary, delete_student, get_weekly_report)
from ai import ask_ai, OPENROUTER_API_KEY

from dotenv import load_dotenv
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import io
from db import (add_student, get_all_students, mark_attendance,
                 get_attendance_summary, delete_student, get_weekly_report,
                 add_user, get_all_users, get_attendance_percentage)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")


bot = telebot.TeleBot(BOT_TOKEN)

def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ O'quvchi qo'shish", callback_data="addstudent"),
        types.InlineKeyboardButton("📋 O'quvchilar ro'yxati", callback_data="students"),
        types.InlineKeyboardButton("✅ Davomat belgilash", callback_data="mark"),
        types.InlineKeyboardButton("🗑 O'quvchini o'chirish", callback_data="deletestudent"),
        types.InlineKeyboardButton("📊 Haftalik hisobot", callback_data="weeklyreport"),
        types.InlineKeyboardButton("🤖 AI'dan so'rash", callback_data="ask"),
        types.InlineKeyboardButton("📈 Statistika grafigi", callback_data="chart"),
    )
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Salom! Men davomat botiman. Kerakli bo'limni tanlang:", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: True)
def callback_router(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id

    if call.data == "addstudent":
        msg = bot.send_message(chat_id, "Har birini yangi qatorda yozing:\nAziz Karimov\nBotir Yusupov")
        bot.register_next_step_handler(msg, add_student_step)

    elif call.data == "students":
        students = get_all_students()
        if not students:
            bot.send_message(chat_id, "O'quvchilar hali qo'shilmagan.")
        else:
            text = "\n".join(f"{s[0]}. {s[1]}" for s in students)
            bot.send_message(chat_id, text)

    elif call.data == "mark":
        students = get_all_students()
        if not students:
            bot.send_message(chat_id, "O'quvchilar hali qo'shilmagan.")
            return
        text = "Kim kelmadi? Ismini yozing (har birini yangi qatorda). Hech kim kelmagan bo'lsa 'yo'q' deb yozing:\n\n"
        text += "\n".join(s[1] for s in students)
        msg = bot.send_message(chat_id, text)
        bot.register_next_step_handler(msg, process_absent, students)

    elif call.data == "deletestudent":
        students = get_all_students()
        if not students:
            bot.send_message(chat_id, "O'quvchilar hali qo'shilmagan.")
            return
        text = "O'chirmoqchi bo'lgan o'quvchi ID'sini yozing:\n\n"
        text += "\n".join(f"{s[0]}. {s[1]}" for s in students)
        msg = bot.send_message(chat_id, text)
        bot.register_next_step_handler(msg, delete_student_step)


    elif call.data == "weeklyreport":

        report = get_weekly_report()

        if not report:
            bot.send_message(chat_id, "📊 Bu hafta hamma qatnashgan, kelmagan o'quvchi yo'q ✅")

            return

        absences = {}

        for name, d, reason in report:
            absences.setdefault(name, []).append((d, reason))

        text = "📊 <b>Haftalik hisobot — kelmaganlar</b>\n\n"

        for name, days in absences.items():

            text += f"🔴 <b>{name}</b>\n"

            for d, reason in days:
                text += f"  {d} — {reason}\n"

            text += "\n"

        bot.send_message(chat_id, text, parse_mode="HTML")

    elif call.data == "ask":
        msg = bot.send_message(chat_id, "Savolingizni yozing:")
        bot.register_next_step_handler(msg, ask_step)

    elif call.data == "chart":
        data = get_attendance_percentage()
        if not data:
            bot.send_message(chat_id, "Hali davomat ma'lumoti yo'q.")
            return

        names = [row[0] for row in data]
        percentages = [round(row[1] / row[2] * 100, 1) if row[2] > 0 else 0 for row in data]

        plt.figure(figsize=(8, max(4, len(names) * 0.4)))
        plt.barh(names, percentages, color="#4CAF50")
        plt.xlabel("Davomat foizi (%)")
        plt.xlim(0, 100)
        plt.title("O'quvchilar davomati")
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png")
        plt.close()
        buf.seek(0)

        bot.send_photo(chat_id, buf, reply_markup=main_menu())

def add_student_step(message):
    names = [n.strip() for n in message.text.split('\n') if n.strip()]
    for name in names:
        add_student(name)
    bot.send_message(message.chat.id, "Qo'shildi ✅:\n" + "\n".join(names), reply_markup=main_menu())

def delete_student_step(message):
    if not message.text.strip().isdigit():
        bot.send_message(message.chat.id, "Faqat ID raqamini yuboring.")
        return
    student_id = int(message.text.strip())
    delete_student(student_id)
    bot.send_message(message.chat.id, f"ID {student_id} o'chirildi ✅", reply_markup=main_menu())

def process_absent(message, students):
    if message.text.strip().lower() == "yo'q":
        absent_names = []
    else:
        absent_names = [n.strip() for n in message.text.split('\n') if n.strip()]

    name_to_student = {s[1].lower(): s for s in students}
    absent_students = []
    not_found = []
    for name in absent_names:
        student = name_to_student.get(name.lower())
        if student:
            absent_students.append(student)
        else:
            not_found.append(name)

    if not_found:
        bot.send_message(message.chat.id, "Topilmadi (ro'yxatdagidek aniq yozing):\n" + "\n".join(not_found))
        return

    if not absent_students:
        today = str(date.today())
        for student_id, full_name in students:
            mark_attendance(student_id, today, "present")
        bot.send_message(message.chat.id, f"{today} — hamma keldi ✅", reply_markup=main_menu())
        return

    text = "Kelmaganlardan qaysilari sababli? Ismini yozing (bo'sh qoldirsangiz — hammasi sababsiz):\n\n"
    text += "\n".join(s[1] for s in absent_students)
    msg = bot.send_message(message.chat.id, text)
    bot.register_next_step_handler(msg, process_absent_reason, students, absent_students)

def process_absent_reason(message, students, absent_students):
    excused_names = [n.strip().lower() for n in message.text.split('\n') if n.strip()]
    absent_ids = {s[0] for s in absent_students}
    excused_ids = {s[0] for s in absent_students if s[1].lower() in excused_names}

    today = str(date.today())
    for student_id, full_name in students:
        if student_id not in absent_ids:
            mark_attendance(student_id, today, "present")
        else:
            reason = "sababli" if student_id in excused_ids else "sababsiz"
            mark_attendance(student_id, today, "absent", reason)

    bot.send_message(message.chat.id, f"{today} sanasi uchun davomat saqlandi ✅", reply_markup=main_menu())

def ask_step(message):
    question = message.text.strip()
    answer = ask_ai(question)
    bot.send_message(message.chat.id, answer, reply_markup=main_menu())

bot.infinity_polling()