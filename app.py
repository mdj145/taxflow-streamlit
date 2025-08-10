# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import yaml
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime

st.set_page_config(page_title="TaxFlow AI – MVP", page_icon="💰", layout="centered")

st.title("💰 TaxFlow AI – MVP")
st.write("העלה קובץ CSV/Excel עם עמודות: date, description, amount. נקבל תזרים חודשי, חזוי 30 יום, ואומדן מס (ע"פ קובץ חוקים).")

# ----- Helpers -----
def load_df(uploaded, name: str) -> pd.DataFrame:
    if name.lower().endswith('.csv'):
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_excel(uploaded)
    cols_lower = [c.lower().strip() for c in df.columns]
    need = ['date', 'description', 'amount']
    for col in need:
        if col not in cols_lower:
            raise ValueError(f"Missing required column: {col}")
    # normalize to standard names
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
    """
    מחשב מס הכנסה ישראלי שנתי לפי קובץ YAML של מדרגות.
    לא כולל נקודות זיכוי/ב"ל/בריאות. דמו לשלב MVP.
    """
    brackets = rules.get('brackets', [])
    surtax_threshold = rules.get('surtax_threshold', None)
    surtax_rate = rules.get('surtax_rate', 0.0)
    tax = 0.0
    last_cap = 0.0
    for b in brackets:
        cap = float(b['up_to'])
        rate = float(b['rate'])
        if annual_taxable_income > cap:
            taxable = cap - last_cap
            tax += taxable * rate
            last_cap = cap
        else:
            taxable = max(0.0, annual_taxable_income - last_cap)
            tax += taxable * rate
            return round(tax, 2)
    # מעבר למדרגה האחרונה: נניח שיעור אחרון + סר-טקס
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
    c.setFont('Helvetica-Bold', 16)
    c.drawString(40, y, 'דו"ח תזרים ותחזית מס – TaxFlow AI (MVP)')
    y -= 30
    c.setFont('Helvetica-Bold', 12)
    c.drawString(40, y, 'תזרים חודשי:')
    y -= 20
    c.setFont('Helvetica', 11)
    for k, v in monthly.items():
        c.drawString(60, y, f"{k}: ₪{v:,.2f}")
        y -= 16
    y -= 8
    c.setFont('Helvetica-Bold', 12)
    c.drawString(40, y, 'חזוי 30 ימים:')
    y -= 18
    c.setFont('Helvetica', 11)
    c.drawString(60, y, f"₪{forecast:,.2f}")
    y -= 24
    c.setFont('Helvetica-Bold', 12)
    c.drawString(40, y, 'אומדן מס שנתי (ע"פ כללים):')
    y -= 18
    c.setFont('Helvetica', 11)
    c.drawString(60, y, f"₪{est_tax:,.2f}")
    y -= 40
    c.setFont('Helvetica', 9)
    c.drawString(40, y, 'הערה: דמו חינוכי. אינו ייעוץ מס/פיננסי. בדקו מול רו"ח/רשויות.')
    c.showPage()
    c.save()
    buf.seek(0)
    return buf

# ----- UI -----
with st.expander('📥 הורד קובץ דוגמה (CSV)'):
    SAMPLE = """date,description,amount
2025-06-01,Salary,12000
2025-06-02,Rent,-5000
2025-06-03,Groceries,-600
2025-06-10,Consulting,3500
2025-06-15,Utilities,-450
2025-07-01,Salary,12000
2025-07-02,Rent,-5000
2025-07-05,Equipment,-1200
2025-07-12,Consulting,2200
2025-07-20,Restaurants,-700
2025-08-01,Salary,12000
2025-08-02,Rent,-5000
2025-08-05,Tax Prepayment,-2000
2025-08-12,Consulting,3000
2025-08-20,Insurance,-900
"""
    st.download_button('הורד sample_transactions.csv', data=SAMPLE, file_name='sample_transactions.csv')

uploaded = st.file_uploader('בחר קובץ CSV/Excel', type=['csv', 'xls', 'xlsx'])

st.divider()
st.subheader('הגדרות חישוב מס')
st.caption('יחס הכנסה חייבת מתוך התזרים (אם יש ערבוב פרטי/עסקי).')
taxable_ratio = st.slider('יחס הכנסה חייבת (דמו):', 0.10, 1.00, 0.70, 0.05)

# ----- Main Flow -----
try:
    TAX_RULES = load_tax_rules('tax_rules_il_2025.yaml')
except Exception as e:
    st.error("קובץ החוקים 'tax_rules_il_2025.yaml' חסר או פגום. צור אותו לפי ההוראות מטה.")
    TAX_RULES = None

if uploaded and TAX_RULES:
    try:
        df = load_df(uploaded, uploaded.name)
        monthly = monthly_cashflow(df)
        last_month_net = list(monthly.values())[-1] if monthly else 0.0
        forecast = naive_forecast_30d(df)
        annual_taxable = max(0.0, last_month_net * 12 * taxable_ratio)
        est_tax = compute_tax_il(annual_taxable, TAX_RULES)

        st.success('הניתוח הושלם.')
        st.subheader('תזרים חודשי')
        st.table(pd.DataFrame.from_dict(monthly, orient='index', columns=['נטו (₪)']))

        c1, c2 = st.columns(2)
        with c1:
            st.metric('חזוי 30 ימים', f'₪{forecast:,.2f}')
        with c2:
            st.metric('אומדן מס שנתי', f'₪{est_tax:,.2f}')

        pdf = build_pdf(monthly, forecast, est_tax)
        st.download_button('⬇ הורד PDF', data=pdf,
                           file_name=f'taxflow_report_{datetime.now().date()}.pdf',
                           mime='application/pdf')
    except Exception as e:
        st.error(f'שגיאה בקובץ: {e}')

st.divider()
with st.expander('איך מעדכנים את כללי המס (בלי קוד)'):
    st.markdown("""1. פתחו את הקובץ **`tax_rules_il_2025.yaml`** ברפו של GitHub.  
2. עדכנו שם את המדרגות (up_to, rate), ואת `surtax_threshold`/`surtax_rate` אם יש שינוי.  
3. לחצו **Commit**. ב-Streamlit לחצו Restart – והחישוב יתעדכן אוטומטית.
""")
st.caption('דיסקליימר: זו גרסת MVP הדגמתית. לפני שימוש אמיתי—לעבור הקשחה מקצועית.')
