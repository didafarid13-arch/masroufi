"""
مصروفي Pro - إدارة المصاريف الشخصية (ملف واحد)
المتطلبات: kivy==2.3.0, kivymd==1.2.0, arabic-reshaper, python-bidi==0.4.2
ضع خطًا عربيًا بجانب الملف باسم arabic.ttf
"""
import csv
import os
import sqlite3
from datetime import datetime

from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.utils import platform

from kivymd.app import MDApp
from kivymd.toast import toast
from kivymd.uix.bottomnavigation import MDBottomNavigation, MDBottomNavigationItem
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import (MDFlatButton, MDFloatingActionButton,
                               MDIconButton, MDRaisedButton)
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import MDDialog
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.list import MDList, TwoLineListItem
from kivymd.uix.progressbar import MDProgressBar
from kivymd.uix.screen import MDScreen
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.textfield import MDTextField
from kivymd.uix.toolbar import MDTopAppBar

# ------------------------- العربية -------------------------
try:
    import arabic_reshaper
    from bidi.algorithm import get_display

    def ar(text):
        return get_display(arabic_reshaper.reshape(str(text)))
except Exception:
    def ar(text):
        return str(text)


HERE = os.path.dirname(os.path.abspath(__file__))
FONT_FILE = os.path.join(HERE, "arabic.ttf")
FONT_NAME = "Arabic" if os.path.exists(FONT_FILE) else None
if FONT_NAME:
    LabelBase.register(name=FONT_NAME, fn_regular=FONT_FILE)

if platform not in ("android", "ios"):
    Window.size = (400, 760)
Window.softinput_mode = "below_target"

GREEN = (0.13, 0.55, 0.35, 1)
RED = (0.8, 0.2, 0.2, 1)
ORANGE = (0.95, 0.6, 0.1, 1)
GREY = (0.6, 0.6, 0.6, 1)
MONTHS = ["جانفي", "فيفري", "مارس", "أفريل", "ماي", "جوان",
          "جويلية", "أوت", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]

STATE = {"month": datetime.now().strftime("%Y-%m")}
DB_NAME = "masroufi.db"


def today_str():
    return datetime.now().strftime("%Y-%m-%d")


def real_month():
    return datetime.now().strftime("%Y-%m")


def month_title(m):
    return f"{MONTHS[int(m[5:]) - 1]} {m[:4]}"


def shift_month(m, d):
    y, mo = int(m[:4]), int(m[5:]) + d
    while mo > 12:
        mo, y = mo - 12, y + 1
    while mo < 1:
        mo, y = mo + 12, y - 1
    return f"{y}-{mo:02d}"


def get_week_of_month(date_str):
    return min((int(date_str.split("-")[2]) - 1) // 7 + 1, 4)


def fmt(n):
    return f"{n:,.0f} دج"


# ======================================================================
#                           قاعدة البيانات
# ======================================================================
def db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def q(sql, params=(), one=False, write=False):
    conn = db()
    try:
        cur = conn.execute(sql, params)
        if write:
            conn.commit()
            return None
        return cur.fetchone() if one else cur.fetchall()
    finally:
        conn.close()


def init_db():
    conn = db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS income (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount REAL NOT NULL, source TEXT, date TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, icon TEXT, type TEXT DEFAULT 'expense');
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount REAL NOT NULL, category_id INTEGER, note TEXT,
        date TEXT NOT NULL, week_number INTEGER);
    CREATE TABLE IF NOT EXISTS budget (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER, weekly_limit REAL, month TEXT);
    CREATE TABLE IF NOT EXISTS prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product TEXT NOT NULL, price REAL NOT NULL,
        unit TEXT, market TEXT, date TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
    CREATE INDEX IF NOT EXISTS idx_exp_date ON expenses(date);
    CREATE INDEX IF NOT EXISTS idx_inc_date ON income(date);
    """)
    if c.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
        c.executemany("INSERT INTO categories (name, icon) VALUES (?, ?)", [
            ("خضروات", "🥬"), ("فواكه", "🍎"), ("مواد غذائية", "🛒"),
            ("مواد تنظيف", "🧴"), ("مصاريف العمل", "💼"), ("وقود", "⛽"),
            ("صيانة السيارة", "🔧"), ("المطعم", "🍔"), ("فواتير", "📄"),
            ("أخرى", "📦")])
    conn.commit()
    conn.close()


def get_setting(key, default=None):
    r = q("SELECT value FROM settings WHERE key=?", (key,), one=True)
    return r[0] if r else default


def set_setting(key, value):
    q("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
      (key, str(value)), write=True)


# --- الدخل والمصروفات ---
def add_income(amount, source, date=None):
    q("INSERT INTO income (amount, source, date) VALUES (?, ?, ?)",
      (amount, source, date or today_str()), write=True)


def add_expense(amount, cid, note="", date=None):
    date = date or today_str()
    q("INSERT INTO expenses (amount, category_id, note, date, week_number) "
      "VALUES (?, ?, ?, ?, ?)",
      (amount, cid, note, date, get_week_of_month(date)), write=True)


def update_expense(eid, amount, cid, note):
    q("UPDATE expenses SET amount=?, category_id=?, note=? WHERE id=?",
      (amount, cid, note, eid), write=True)


def update_income(iid, amount, note):
    q("UPDATE income SET amount=?, source=? WHERE id=?",
      (amount, note, iid), write=True)


def delete_tx(kind, tid):
    table = "expenses" if kind == "expense" else "income"
    q(f"DELETE FROM {table} WHERE id=?", (tid,), write=True)


def get_transactions(month):
    return q("""
        SELECT 'expense' AS kind, e.id, e.amount, e.note AS note, e.date,
               c.name AS cat, c.icon AS icon, e.category_id AS cid
        FROM expenses e LEFT JOIN categories c ON e.category_id = c.id
        WHERE e.date LIKE ?
        UNION ALL
        SELECT 'income', id, amount, source, date, NULL, '💰', NULL
        FROM income WHERE date LIKE ?
        ORDER BY date DESC, id DESC""", (f"{month}%", f"{month}%"))


def total(table, month, week=None):
    sql = f"SELECT COALESCE(SUM(amount),0) FROM {table} WHERE date LIKE ?"
    params = [f"{month}%"]
    if week:
        sql += " AND week_number = ?"
        params.append(week)
    return q(sql, params, one=True)[0]


def expenses_by_category(month):
    return q("""SELECT c.name, c.icon, SUM(e.amount) AS total
                FROM expenses e JOIN categories c ON e.category_id = c.id
                WHERE e.date LIKE ? GROUP BY c.id ORDER BY total DESC""",
             (f"{month}%",))


def expenses_by_week(month):
    return {r["w"]: r["t"] for r in q(
        """SELECT week_number AS w, SUM(amount) AS t FROM expenses
           WHERE date LIKE ? GROUP BY week_number""", (f"{month}%",))}


def category_week_spent(cid, month, week):
    return q("""SELECT COALESCE(SUM(amount),0) FROM expenses
                WHERE category_id=? AND date LIKE ? AND week_number=?""",
             (cid, f"{month}%", week), one=True)[0]


# --- التصنيفات والميزانية والأسعار ---
def get_categories():
    return q("SELECT * FROM categories")


def add_category(name, icon):
    q("INSERT INTO categories (name, icon) VALUES (?, ?)", (name, icon), write=True)


def set_weekly_budget(cid, limit, month):
    q("DELETE FROM budget WHERE category_id=? AND month=?", (cid, month), write=True)
    q("INSERT INTO budget (category_id, weekly_limit, month) VALUES (?, ?, ?)",
      (cid, limit, month), write=True)


def delete_budget(bid):
    q("DELETE FROM budget WHERE id=?", (bid,), write=True)


def get_weekly_budgets(month):
    return q("""SELECT b.*, c.name, c.icon FROM budget b
                LEFT JOIN categories c ON b.category_id = c.id
                WHERE b.month=?""", (month,))


def add_price(product, price, unit):
    q("INSERT INTO prices (product, price, unit, market, date) VALUES (?, ?, ?, '', ?)",
      (product, price, unit, today_str()), write=True)


def get_prices(limit=5):
    return q("SELECT * FROM prices ORDER BY date DESC, id DESC LIMIT ?", (limit,))


def get_summary(month):
    income, spent = total("income", month), total("expenses", month)
    is_now = month == real_month()
    week = get_week_of_month(today_str()) if is_now else None
    budgets = get_weekly_budgets(real_month()) if is_now else []
    wb = sum(b["weekly_limit"] or 0 for b in budgets)
    we = total("expenses", month, week) if week else 0
    return dict(income=income, spent=spent, balance=income - spent,
                week=week, week_spent=we, week_budget=wb, week_left=wb - we)


def auto_split_budget(income, fixed, weeks=4):
    left = income - fixed
    return left / weeks if left > 0 else 0


def export_csv():
    """يصدّر العمليات إلى CSV ويرجع المسار."""
    folder = MDApp.get_running_app().user_data_dir
    if platform == "android":
        try:
            from android.storage import primary_external_storage_path
            d = os.path.join(primary_external_storage_path(), "Download")
            if os.path.isdir(d):
                folder = d
        except Exception:
            pass
    path = os.path.join(folder, f"masroufi_{datetime.now():%Y%m%d_%H%M}.csv")
    try:
        f = open(path, "w", newline="", encoding="utf-8-sig")
    except OSError:
        path = os.path.join(MDApp.get_running_app().user_data_dir,
                            os.path.basename(path))
        f = open(path, "w", newline="", encoding="utf-8-sig")
    with f:
        w = csv.writer(f)
        w.writerow(["النوع", "التاريخ", "المبلغ", "التصنيف", "ملاحظة"])
        for r in get_transactions(""):
            w.writerow(["مصروف" if r["kind"] == "expense" else "دخل",
                        r["date"], r["amount"], r["cat"] or "", r["note"] or ""])
    return path


# ======================================================================
#                           أدوات الواجهة
# ======================================================================
def label(text, style="Body1", height=None, halign="center", **kw):
    kw.setdefault("size_hint", (1, None) if height else (1, 1))
    lb = MDLabel(text=ar(text), halign=halign, font_style=style, **kw)
    if height:
        lb.height = dp(height)
    return lb


def field(hint, numeric=False):
    f = MDTextField(hint_text=ar(hint), mode="rectangle")
    if numeric:
        f.input_filter = "float"
    if FONT_NAME:
        f.font_name = FONT_NAME
    return f


def button(text, on_release, flat=False):
    cls = MDFlatButton if flat else MDRaisedButton
    return cls(text=ar(text), size_hint=(1, None), height=dp(46),
               on_release=on_release)


def item(title, subtitle, on_release=None):
    it = TwoLineListItem(text=ar(title), secondary_text=ar(subtitle))
    if on_release:
        it.bind(on_release=on_release)
    return it


def scroll_box(spacing=10, padding=15):
    sv = ScrollView()
    box = MDBoxLayout(orientation="vertical", spacing=dp(spacing),
                      padding=dp(padding), adaptive_height=True)
    sv.add_widget(box)
    return sv, box


def bar_row(title, subtitle, pct, color=GREEN, on_release=None):
    card = MDCard(orientation="vertical", padding=dp(10), spacing=dp(4),
                  size_hint=(1, None), height=dp(68), radius=[10],
                  elevation=1, on_release=on_release or (lambda x: None))
    top = MDBoxLayout(size_hint=(1, None), height=dp(26))
    top.add_widget(label(subtitle, "Caption", halign="left"))
    top.add_widget(label(title, "Subtitle1", halign="right"))
    bar = MDProgressBar(value=max(0, min(pct, 100)), size_hint=(1, None),
                        height=dp(6))
    bar.color = color
    card.add_widget(top)
    card.add_widget(bar)
    return card


def ask(title, text, actions):
    """حوار بأزرار: actions = [(نص, دالة أو None)]."""
    dlg = None

    def mk(fn):
        def handler(*a):
            dlg.dismiss()
            if fn:
                fn()
        return handler

    dlg = MDDialog(title=ar(title), text=ar(text), buttons=[
        MDFlatButton(text=ar(t), on_release=mk(f)) for t, f in actions])
    dlg.open()


def app():
    return MDApp.get_running_app()


# ======================================================================
#                           التبويبات
# ======================================================================
class HomeTab(MDFloatLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        main = MDBoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))

        nav = MDBoxLayout(size_hint=(1, None), height=dp(44))
        nav.add_widget(MDIconButton(icon="chevron-left",
                                    on_release=lambda x: self.move(1)))
        self.month_lbl = label("", "H6")
        nav.add_widget(self.month_lbl)
        nav.add_widget(MDIconButton(icon="chevron-right",
                                    on_release=lambda x: self.move(-1)))
        main.add_widget(nav)

        self.card = MDCard(orientation="vertical", padding=dp(16),
                           size_hint=(1, None), height=dp(150), radius=[20],
                           md_bg_color=GREEN)
        white = dict(theme_text_color="Custom", text_color=(1, 1, 1, 1))
        self.card.add_widget(label("الرصيد المتبقي", "Subtitle1", **white))
        self.balance = label("", "H4", **white)
        self.card.add_widget(self.balance)
        self.sub = label("", "Caption", theme_text_color="Custom",
                         text_color=(1, 1, 1, 0.9))
        self.card.add_widget(self.sub)
        main.add_widget(self.card)

        row = MDBoxLayout(size_hint=(1, None), height=dp(64), spacing=dp(8))
        self.inc_card, self.inc = self.mini("الدخل")
        self.exp_card, self.exp = self.mini("المصروفات")
        row.add_widget(self.inc_card)
        row.add_widget(self.exp_card)
        main.add_widget(row)

        main.add_widget(label("العمليات (اضغط للتعديل أو الحذف)", "Caption",
                              height=24, halign="right"))
        sv = ScrollView()
        self.list = MDList()
        sv.add_widget(self.list)
        main.add_widget(sv)
        self.add_widget(main)

        self.add_widget(MDFloatingActionButton(
            icon="plus", pos_hint={"right": 0.95, "y": 0.03},
            on_release=lambda x: app().open_add()))

    def mini(self, title):
        card = MDCard(orientation="vertical", padding=dp(8), radius=[12],
                      elevation=1)
        card.add_widget(label(title, "Caption"))
        val = label("", "Subtitle1")
        card.add_widget(val)
        return card, val

    def move(self, d):
        STATE["month"] = shift_month(STATE["month"], d)
        app().refresh_all()

    def refresh(self):
        m = STATE["month"]
        s = get_summary(m)
        self.month_lbl.text = ar(month_title(m))
        self.balance.text = ar(fmt(s["balance"]))
        self.card.md_bg_color = RED if s["balance"] < 0 else GREEN
        if s["week"]:
            extra = f" | متبقي من ميزانية الأسبوع: {fmt(s['week_left'])}" \
                if s["week_budget"] else ""
            self.sub.text = ar(f"الأسبوع {s['week']} | مصروف: "
                               f"{fmt(s['week_spent'])}{extra}")
        else:
            self.sub.text = ar("ملخص الشهر")
        self.inc.text = ar(fmt(s["income"]))
        self.exp.text = ar(fmt(s["spent"]))

        self.list.clear_widgets()
        rows = get_transactions(m)
        if not rows:
            self.list.add_widget(label("لا توجد عمليات في هذا الشهر", height=60))
        for r in rows[:60]:
            sign = "-" if r["kind"] == "expense" else "+"
            name = r["cat"] or ("غير مصنف" if r["kind"] == "expense"
                                else (r["note"] or "دخل"))
            note = f" • {r['note']}" if r["kind"] == "expense" and r["note"] else ""
            self.list.add_widget(item(
                f"{r['icon'] or '📌'} {name}",
                f"{sign}{fmt(r['amount'])}  •  {r['date']}{note}",
                on_release=lambda x, row=r: self.on_tx(row)))

    def on_tx(self, row):
        def edit():
            app().open_add(row)

        def delete():
            delete_tx(row["kind"], row["id"])
            toast(ar("تم الحذف"))
            app().refresh_all()

        ask("العملية", f"{fmt(row['amount'])} - {row['date']}",
            [("تعديل", edit), ("حذف", delete), ("إلغاء", None)])


class ReportsTab(MDBoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", **kw)
        self.sv, self.box = scroll_box()
        self.add_widget(self.sv)

    def refresh(self):
        m = STATE["month"]
        b = self.box
        b.clear_widgets()
        b.add_widget(label(f"تقرير {month_title(m)}", "H5", height=44))
        spent, inc = total("expenses", m), total("income", m)
        b.add_widget(label(f"الدخل: {fmt(inc)}", "Subtitle1", height=28))
        b.add_widget(label(f"المصروفات: {fmt(spent)}", "Subtitle1", height=28))
        if inc > 0:
            b.add_widget(label(f"نسبة الإنفاق من الدخل: {spent / inc * 100:.0f}%",
                               "Subtitle1", height=28))

        b.add_widget(label("حسب الأسبوع", "H6", height=40, halign="right"))
        weeks = expenses_by_week(m)
        top = max(weeks.values()) if weeks else 1
        for w in range(1, 5):
            v = weeks.get(w, 0)
            b.add_widget(bar_row(f"الأسبوع {w}", fmt(v), v / top * 100))

        b.add_widget(label("حسب التصنيف", "H6", height=40, halign="right"))
        rows = expenses_by_category(m)
        if not rows:
            b.add_widget(label("لا توجد بيانات بعد", height=50))
        grand = sum(r["total"] for r in rows) or 1
        for r in rows:
            pct = r["total"] / grand * 100
            b.add_widget(bar_row(f"{r['icon'] or '📌'} {r['name']}",
                                 f"{fmt(r['total'])}  ({pct:.0f}%)", pct))


class BudgetTab(MDBoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", **kw)
        self.cat_ids = {}
        sv, b = scroll_box(spacing=8)
        self.add_widget(sv)

        b.add_widget(label("الميزانية الأسبوعية", "H5", height=44))
        b.add_widget(label("حاسبة التقسيم التلقائي", "H6", height=32,
                           halign="right"))
        self.income_f = field("الدخل الشهري", True)
        self.fixed_f = field("الالتزامات الثابتة (إيجار، فواتير...)", True)
        b.add_widget(self.income_f)
        b.add_widget(self.fixed_f)
        b.add_widget(button("احسب الميزانية الأسبوعية", self.calc))
        self.result = label("", "H6", height=36)
        b.add_widget(self.result)

        b.add_widget(label("تحديد ميزانية لتصنيف", "H6", height=32,
                           halign="right"))
        row = MDBoxLayout(size_hint=(1, None), height=dp(56), spacing=dp(8))
        self.spinner = Spinner(text=ar("اختر تصنيفًا"), size_hint=(0.5, 1))
        if FONT_NAME:
            self.spinner.font_name = FONT_NAME
        self.limit_f = field("الحد الأسبوعي", True)
        self.limit_f.size_hint = (0.5, 1)
        row.add_widget(self.spinner)
        row.add_widget(self.limit_f)
        b.add_widget(row)
        b.add_widget(button("حفظ الميزانية", self.save))

        b.add_widget(label("الميزانيات الحالية (اضغط للحذف)", "H6", height=36,
                           halign="right"))
        self.list_box = MDBoxLayout(orientation="vertical", spacing=dp(8),
                                    adaptive_height=True)
        b.add_widget(self.list_box)

    def calc(self, *a):
        try:
            w = auto_split_budget(float(self.income_f.text or 0),
                                  float(self.fixed_f.text or 0))
        except ValueError:
            return toast(ar("أدخل أرقامًا صحيحة"))
        self.result.text = ar(f"الميزانية الأسبوعية: {fmt(w)}")

    def save(self, *a):
        cid = self.cat_ids.get(self.spinner.text)
        if cid is None:
            return toast(ar("اختر تصنيفًا"))
        try:
            limit = float(self.limit_f.text)
        except ValueError:
            return toast(ar("أدخل مبلغًا صحيحًا"))
        set_weekly_budget(cid, limit, real_month())
        self.limit_f.text = ""
        toast(ar("تم حفظ الميزانية ✅"))
        app().refresh_all()

    def refresh(self):
        self.cat_ids = {ar(c["name"]): c["id"] for c in get_categories()}
        self.spinner.values = list(self.cat_ids)
        self.list_box.clear_widgets()
        week = get_week_of_month(today_str())
        budgets = get_weekly_budgets(real_month())
        if not budgets:
            self.list_box.add_widget(label("لم تحدد ميزانية بعد", height=44))
        for bd in budgets:
            lim = bd["weekly_limit"] or 0
            spent = category_week_spent(bd["category_id"], real_month(), week)
            pct = spent / lim * 100 if lim else 0
            color = RED if pct >= 100 else ORANGE if pct >= 80 else GREEN
            self.list_box.add_widget(bar_row(
                f"{bd['icon'] or '📌'} {bd['name']}",
                f"{fmt(spent)} / {fmt(lim)}", pct, color,
                on_release=lambda x, i=bd["id"]: self.drop(i)))

    def drop(self, bid):
        def go():
            delete_budget(bid)
            app().refresh_all()
        ask("حذف الميزانية", "هل تريد حذف هذه الميزانية؟",
            [("حذف", go), ("إلغاء", None)])


class SettingsTab(MDBoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", **kw)
        sv, b = scroll_box(spacing=8)
        self.add_widget(sv)
        b.add_widget(label("الإعدادات", "H5", height=44))

        row = MDBoxLayout(size_hint=(1, None), height=dp(48))
        self.dark = MDSwitch(active=get_setting("dark", "0") == "1",
                             pos_hint={"center_y": 0.5})
        self.dark.bind(active=self.toggle_dark)
        row.add_widget(self.dark)
        row.add_widget(label("الوضع الداكن", halign="right"))
        b.add_widget(row)

        b.add_widget(label("إضافة تصنيف جديد", "H6", height=34, halign="right"))
        self.cat_name = field("اسم التصنيف")
        self.cat_icon = field("أيقونة (Emoji)")
        b.add_widget(self.cat_name)
        b.add_widget(self.cat_icon)
        b.add_widget(button("إضافة التصنيف", self.add_cat))

        b.add_widget(label("تسجيل سعر سوق", "H6", height=34, halign="right"))
        self.p_name = field("المنتج (طماطم...)")
        self.p_price = field("السعر", True)
        self.p_unit = field("الوحدة (كغ/لتر)")
        for w in (self.p_name, self.p_price, self.p_unit):
            b.add_widget(w)
        b.add_widget(button("حفظ السعر", self.add_price))
        self.prices = MDBoxLayout(orientation="vertical", adaptive_height=True)
        b.add_widget(self.prices)

        b.add_widget(label("النسخ الاحتياطي", "H6", height=34, halign="right"))
        b.add_widget(button("تصدير العمليات إلى CSV", self.export))

    def toggle_dark(self, sw, value):
        app().theme_cls.theme_style = "Dark" if value else "Light"
        set_setting("dark", "1" if value else "0")

    def add_cat(self, *a):
        name = self.cat_name.text.strip()
        if not name:
            return toast(ar("أدخل اسم التصنيف"))
        add_category(name, self.cat_icon.text.strip() or "📌")
        self.cat_name.text = self.cat_icon.text = ""
        toast(ar("تمت إضافة التصنيف ✅"))

    def add_price(self, *a):
        name = self.p_name.text.strip()
        if not name:
            return toast(ar("أدخل اسم المنتج"))
        try:
            price = float(self.p_price.text)
        except ValueError:
            return toast(ar("أدخل سعرًا صحيحًا"))
        add_price(name, price, self.p_unit.text.strip() or "كغ")
        self.p_name.text = self.p_price.text = self.p_unit.text = ""
        toast(ar("تم حفظ السعر ✅"))
        self.refresh()

    def export(self, *a):
        try:
            path = export_csv()
            ask("تم التصدير", path, [("حسنًا", None)])
        except Exception as e:
            toast(ar(f"فشل التصدير: {e}"))

    def refresh(self):
        self.prices.clear_widgets()
        for p in get_prices():
            self.prices.add_widget(item(
                p["product"], f"{p['price']:,.0f} دج / {p['unit']}  •  {p['date']}"))


# ======================================================================
#                           الشاشات
# ======================================================================
class MainScreen(MDScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        box = MDBoxLayout(orientation="vertical")
        box.add_widget(MDTopAppBar(title=ar("مصروفي"), elevation=2))
        nav = MDBottomNavigation()
        self.tabs = {}
        for name, text, icon, cls in (
                ("home", "الرئيسية", "home", HomeTab),
                ("reports", "التقارير", "chart-bar", ReportsTab),
                ("budget", "الميزانية", "wallet", BudgetTab),
                ("settings", "الإعدادات", "cog", SettingsTab)):
            tab = MDBottomNavigationItem(name=name, text=ar(text), icon=icon)
            content = cls()
            tab.add_widget(content)
            tab.bind(on_tab_press=lambda *a, c=content: c.refresh())
            nav.add_widget(tab)
            self.tabs[name] = content
        box.add_widget(nav)
        self.add_widget(box)

    def refresh_all(self):
        for t in self.tabs.values():
            t.refresh()

    def on_pre_enter(self, *a):
        self.refresh_all()


class AddScreen(MDScreen):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.mode, self.cid, self.edit = "expense", None, None
        self.cards = {}

        box = MDBoxLayout(orientation="vertical")
        self.bar = MDTopAppBar(
            title=ar("إضافة عملية"), elevation=2,
            left_action_items=[["arrow-left", lambda x: app().go("main")]])
        box.add_widget(self.bar)

        body = MDBoxLayout(orientation="vertical", padding=dp(15),
                           spacing=dp(10))
        toggle = MDBoxLayout(size_hint=(1, None), height=dp(46), spacing=dp(10))
        self.b_exp = MDRaisedButton(text=ar("مصروف"), size_hint=(1, 1),
                                    on_release=lambda x: self.set_mode("expense"))
        self.b_inc = MDRaisedButton(text=ar("دخل"), size_hint=(1, 1),
                                    on_release=lambda x: self.set_mode("income"))
        toggle.add_widget(self.b_exp)
        toggle.add_widget(self.b_inc)
        body.add_widget(toggle)

        self.amount = field("المبلغ (دج)", True)
        body.add_widget(self.amount)
        self.cat_title = label("التصنيف:", height=26, halign="right")
        body.add_widget(self.cat_title)
        sv = ScrollView()
        self.grid = MDGridLayout(cols=3, spacing=dp(8), adaptive_height=True)
        sv.add_widget(self.grid)
        body.add_widget(sv)
        self.note = field("ملاحظة (اختياري)")
        body.add_widget(self.note)
        body.add_widget(button("حفظ", self.save))
        box.add_widget(body)
        self.add_widget(box)

    def start(self, row=None):
        """يفتح الشاشة لإضافة عملية جديدة أو لتعديل row."""
        self.edit = (row["kind"], row["id"]) if row else None
        self.bar.title = ar("تعديل عملية" if row else "إضافة عملية")
        self.amount.text = f"{row['amount']:g}" if row else ""
        self.note.text = (row["note"] or "") if row else ""
        self.load_categories()
        self.cid = None
        self.set_mode(row["kind"] if row else "expense")
        if row and row["cid"]:
            self.pick(row["cid"])
        for b in (self.b_exp, self.b_inc):
            b.disabled = bool(row)

    def load_categories(self):
        self.grid.clear_widgets()
        self.cards = {}
        for c in get_categories():
            card = MDCard(orientation="vertical", padding=dp(4),
                          size_hint=(1, None), height=dp(76), radius=[12],
                          md_bg_color=app().theme_cls.bg_light,
                          on_release=lambda x, i=c["id"]: self.pick(i))
            card.add_widget(label(c["icon"] or "📌", "H5"))
            card.add_widget(label(c["name"], "Caption"))
            self.grid.add_widget(card)
            self.cards[c["id"]] = card

    def pick(self, cid):
        self.cid = cid
        for i, card in self.cards.items():
            card.md_bg_color = ((0.6, 0.85, 0.7, 1) if i == cid
                                else app().theme_cls.bg_light)

    def set_mode(self, mode):
        self.mode = mode
        self.b_exp.md_bg_color = GREEN if mode == "expense" else GREY
        self.b_inc.md_bg_color = GREEN if mode == "income" else GREY
        self.cat_title.opacity = self.grid.opacity = 1 if mode == "expense" else 0
        self.grid.disabled = mode != "expense"

    def save(self, *a):
        try:
            amount = float(self.amount.text.strip())
        except ValueError:
            return toast(ar("أدخل مبلغًا صحيحًا"))
        if amount <= 0:
            return toast(ar("المبلغ يجب أن يكون أكبر من صفر"))
        note = self.note.text.strip()

        if self.mode == "expense" and not self.cid:
            return toast(ar("اختر تصنيفًا"))

        if self.edit:
            kind, tid = self.edit
            if kind == "expense":
                update_expense(tid, amount, self.cid, note)
            else:
                update_income(tid, amount, note or "دخل")
            toast(ar("تم التعديل ✅"))
        elif self.mode == "expense":
            add_expense(amount, self.cid, note)
            toast(ar("تم حفظ المصروف ✅"))
        else:
            add_income(amount, note or "دخل")
            toast(ar("تم حفظ الدخل ✅"))

        STATE["month"] = real_month() if not self.edit else STATE["month"]
        app().go("main")


# ======================================================================
#                           التطبيق
# ======================================================================
class MasroufiApp(MDApp):
    def build(self):
        global DB_NAME
        DB_NAME = os.path.join(self.user_data_dir, "masroufi.db")
        init_db()

        self.title = "مصروفي"
        self.theme_cls.primary_palette = "Green"
        self.theme_cls.theme_style = ("Dark" if get_setting("dark", "0") == "1"
                                      else "Light")
        if FONT_NAME:
            for style in self.theme_cls.font_styles:
                self.theme_cls.font_styles[style][0] = FONT_NAME

        self.sm = ScreenManager(transition=SlideTransition())
        self.main = MainScreen(name="main")
        self.add_screen = AddScreen(name="add")
        self.sm.add_widget(self.main)
        self.sm.add_widget(self.add_screen)

        Window.bind(on_keyboard=self.on_back)
        return self.sm

    def go(self, name):
        self.sm.transition.direction = "right" if name == "main" else "left"
        self.sm.current = name

    def open_add(self, row=None):
        self.add_screen.start(row)
        self.go("add")

    def refresh_all(self):
        self.main.refresh_all()

    def on_back(self, window, key, *a):
        if key == 27 and self.sm.current != "main":  # زر الرجوع في أندرويد
            self.go("main")
            return True
        return False


if __name__ == "__main__":
    MasroufiApp().run()