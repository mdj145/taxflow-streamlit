# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import yaml
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime
import matplotlib.pyplot as plt

st.set_page_config(page_title='TaxFlow AI – MVP', page_icon='💰', layout='wide')

# ---------- CSS (simple polish + RTL) ----------
st.markdown(
    """
    <style>
    html, body, [data-testid="stApp"] { direction: rtl; }
    .hero {display:flex; align-items:center; gap:16px; margin: 8px 0 24px 0;}
    .hero img {width:48px; height:48px}
    .card {background:#fff; border:1px solid #E6EAF0; border-radius:12px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,0.04);}
    .muted {color:#6b7280; font-size:14px}
    .metrics {display:flex; gap:16px; flex-wrap:wrap}
    .metrics .card {min-width:220px; text-align:center}
    .divider {height:1px; background:#E6EAF0; margin:24px 0}
    .footer-note {font-size:12px; color:#6b7280}
    </style>
    """,
    unsafe_allow_html=True
)

# ---------- Header ----------
col_logo, col_title = st.columns([1, 8])
with col_logo:
    st.image('assets/logo.png')
with col_title:
    st.markdown("<div class='hero'><h1>TaxFlow AI – MVP</h1></div>", unsafe_allow_html=True)
    st.markdown(
        "האפליקציה מחשבת תזרים חודשי, חזוי 30 יום, ואומדן מס על בסיס קובץ כללים (YAML). "
        "העלו קובץ CSV או Excel עם העמודות: `date, description, amount`.",
        help="מבנה עמודות חובה: date, description, amount"
    )

# ---------- Sidebar settings ----------
with st.sidebar:
    st.header("הגדרות")
    st.caption("יחס הכנסה חייבת מתוך התזרים (אם יש ערבוב פרטי/עסקי).")
    taxable_ratio = st.slider('יחס הכנסה חייבת (דמו):', 0.10, 1.00, 0.70, 0.05)
    st.divider()
    st.caption("עדכון כללי מס: עריכת הקובץ tax_rules_il_2025.yaml בריפו (בלי קוד).")

# ---------- Helpers ----------
def load_df(uploaded, name: str) -> pd.DataFrame:
    if name.lower().endswith('.csv'):
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_excel(uploaded)
    cols_lower = [c.lower().strip() for c in df.columns]
    need = ['date', 'description', 'amount']
    for col in need:
        if col not in cols_lower:
            raise ValueError(f'חסרה עמודה נדרשת: {col}')
    mapper = {orig: orig for orig in df.columns}
    for col in df.columns:
        cl = col.lower().strip()
        if cl == 'date': mapper[col] = 'date'
        if cl == 'description': mapper[col] = 'description'
        if cl == 'amount': mapper[col] = 'amount'
    df = df.rename(columns=mapper)
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
    df = df.dropna(subset=['date']).sort_values('date')
    return df

def monthly_cashflow(df: pd.DataFrame) -> dict:
    grouped = df.groupby(df['date'].dt.to_period('M'))['amount'].sum().astype(float)
    return {str(k): round(v, 2) for k, v in grouped.items()}

def naive_forecast_30d(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    daily = df.groupby(df['date'].dt.date)['amount'].sum()
    window = daily.tail(90) if len(daily) > 90 else daily
    avg = window.mean() if len(window) else 0.0
    return round(float(avg * 30.0), 2)

def load_tax_rules(path: str = 'tax_rules_il_2025.yaml') -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def compute_tax_il(annual_taxable_income: float, rules: dict) -> float:
    brackets = rules.get('brackets', [])
    surtax_threshold = rules.get('surtax_threshold', None)
    surtax_rate = rules.get('surtax_rate', 0.0)
    tax = 0.0
    last_cap = 0.0
    for b in brackets:
        cap = float(b['up_to']); rate = float(b['rate'])
        if annual_taxable_income > cap:
            taxable = cap - last_cap
            tax += taxable * rate
            last_cap = cap
        else:
            taxable = max(0.0, annual_taxable_income - last_cap)
            tax += taxable * rate
            return round(tax, 2)
    if annual_taxable_income > last_cap:
        last_rate = float(brackets[-1]['rate']) if brackets else 0.47
        tax += (annual_taxable_income - last_cap) * last_rate
    if surtax_threshold is not None and annual_taxable_income > surtax_threshold:
        excess = annual_taxable_income - float(surtax_threshold)
        tax += excess * float(surtax_rate)
    return round(tax, 2)

def build_pdf(monthly: dict, forecast: float, est_tax: float) -> BytesIO:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 50
    c.setFont('Helvetica-Bold', 16); c.drawString(40, y, 'דו״ח תזרים ותחזית מס – TaxFlow AI (MVP)'); y -= 30
    c.setFont('Helvetica-Bold', 12); c.drawString(40, y, 'תזרים חודשי:'); y -= 20
    c.setFont('Helvetica', 11)
    for k, v in monthly.items():
        c.drawString(60, y, f'{k}: ₪{v:,.2f}'); y -= 16
    y -= 8; c.setFont('Helvetica-Bold', 12); c.drawString(40, y, 'חזוי 30 ימים:'); y -= 18
    c.setFont('Helvetica', 11); c.drawString(60, y, f'₪{forecast:,.2f}'); y -= 24
    c.setFont('Helvetica-Bold', 12); c.drawString(40, y, 'אומדן מס שנתי (לפי כללים):'); y -= 18
    c.setFont('Helvetica', 11); c.drawString(60, y, f'₪{est_tax:,.2f}'); y -= 40
    c.setFont('Helvetica', 9); c.drawString(40, y, 'הערה: דמו חינוכי. אינו ייעוץ מס/פיננסי. בדקו מול רו״ח/רשויות.')
    c.showPage(); c.save(); buf.seek(0); return buf

# ---------- Sample + Upload ----------
with st.expander('📥 הורד קובץ דוגמה (CSV)'):
    SAMPLE = (
        'date,description,amount
'
        '2025-06-01,Salary,12000
'
        '2025-06-02,Rent,-5000
'
        '2025-06-03,Groceries,-600
'
        '2025-06-10,Consulting,3500
'
        '2025-06-15,Utilities,-450
'
        '2025-07-01,Salary,12000
'
        '2025-07-02,Rent,-5000
'
        '2025-07-05,Equipment,-1200
'
        '2025-07-12,Consulting,2200
'
        '2025-07-20,Restaurants,-700
'
        '2025-08-01,Salary,12000
'
        '2025-08-02,Rent,-5000
'
        '2025-08-05,Tax Prepayment,-2000
'
        '2025-08-12,Consulting,3000
'
        '2025-08-20,Insurance,-900
'
    )
    st.download_button('הורד sample_transactions.csv', data=SAMPLE, file_name='sample_transactions.csv')

uploaded = st.file_uploader('בחר קובץ CSV/Excel', type=['csv', 'xls', 'xlsx'])

# ---------- Main ----------
rules_ok = True
try:
    TAX_RULES = load_tax_rules('tax_rules_il_2025.yaml')
except Exception:
    rules_ok = False
    st.error("קובץ הכללים 'tax_rules_il_2025.yaml' חסר/פגום. ודא שהוא קיים בשורש הפרויקט.")

if uploaded and rules_ok:
    with st.spinner('מעבד נתונים...'):
        try:
            df = load_df(uploaded, uploaded.name)
            monthly = monthly_cashflow(df)
            last_month_net = list(monthly.values())[-1] if monthly else 0.0
            forecast = naive_forecast_30d(df)
            annual_taxable = max(0.0, last_month_net * 12 * taxable_ratio)
            est_tax = compute_tax_il(annual_taxable, TAX_RULES)
        except Exception as e:
            st.error(f'שגיאה בקובץ: {e}')
            st.stop()

    # Metrics
    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    st.subheader('סיכום מהיר')
    mcol1, mcol2 = st.columns(2)
    with mcol1:
        st.metric('חזוי 30 ימים', f'₪{forecast:,.2f}')
    with mcol2:
        st.metric('אומדן מס שנתי', f'₪{est_tax:,.2f}')

    # Chart
    st.subheader('תזרים חודשי (גרף)')
    fig, ax = plt.subplots()
    months = list(monthly.keys()); values = list(monthly.values())
    ax.bar(months, values)  # default colors
    ax.set_xlabel('חודש'); ax.set_ylabel('נטו (₪)'); ax.set_title('תזרים חודשי')
    plt.xticks(rotation=45, ha='right')
    st.pyplot(fig, clear_figure=True)

    # Table
    st.subheader('טבלה')
    st.table(pd.DataFrame.from_dict(monthly, orient='index', columns=['נטו (₪)']))

    # PDF
    pdf = build_pdf(monthly, forecast, est_tax)
    st.download_button('⬇ הורד PDF', data=pdf, file_name=f'taxflow_report_{datetime.now().date()}.pdf', mime='application/pdf')

st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.markdown("<p class='footer-note'>דיסקליימר: גרסת MVP הדגמתית. לפני שימוש אמיתי יש לבצע הקשחה מקצועית.</p>", unsafe_allow_html=True)
