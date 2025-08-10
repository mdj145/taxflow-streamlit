
import streamlit as st

st.set_page_config(page_title="TaxFlow MVP", page_icon="💰", layout="centered")

st.title("💰 TaxFlow - מחשבון מס פשוט")
st.write("ברוך הבא! הכנס את ההכנסה שלך וחישוב המס יופיע מייד.")

income = st.number_input("הכנס הכנסה שנתית:", min_value=0, step=1000)

if income:
    if income <= 75600:
        tax = income * 0.1
    elif income <= 108600:
        tax = (75600 * 0.1) + ((income - 75600) * 0.14)
    else:
        tax = (75600 * 0.1) + ((108600 - 75600) * 0.14) + ((income - 108600) * 0.2)

    st.success(f"סכום המס שלך הוא: {tax:,.0f} ש"ח")
