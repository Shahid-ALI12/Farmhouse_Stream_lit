"""
app.py — entry point. Sets up the page and sidebar navigation.
Run with: streamlit run app.py
"""
import streamlit as st

st.set_page_config(
    page_title="Danish Cattle Feed — Daily Register",
    page_icon="📋",
    layout="wide",
)

st.title("📋 Danish Cattle Feed — Daily Register")

st.markdown(
    """
    Use the menu on the left to move between sections:

    - **🧾 Daily Entry** — add today's sales and expenses
    - **📖 Customer Khata** — see what each customer owes / has paid
    - **🏁 Day Reconciliation** — today's full cash summary
    - **⚙️ Manage Products & Rates** — add new items, update today's rates

    All data is saved to the shared database immediately, so anyone
    entering data on any device sees the same up-to-date numbers.
    """
)

st.info(
    "👈 Pick a page from the sidebar to get started.",
    icon="👉",
)
