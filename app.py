"""
app.py — entry point. Sets up the page, theme, and grouped sidebar
navigation. Run with: streamlit run app.py
"""
import streamlit as st
import ui

st.set_page_config(
    page_title="Danish Cattle Feed — Daily Register",
    page_icon="🐄",
    layout="wide",
    initial_sidebar_state="expanded",
)

ui.inject_css()

nav_sections = {
    "Overview": [
        st.Page("pages/0_Dashboard.py", title="Dashboard", icon="📊"),
    ],
    "Daily Operations": [
        st.Page("pages/1_Daily_Entry.py", title="Daily Entry", icon="🧾"),
        st.Page("pages/6_Custom_Mix_Order.py", title="Custom Mix Order", icon="🧪"),
        st.Page("pages/3_Day_Reconciliation.py", title="Day Reconciliation", icon="🏁"),
    ],
    "Customers": [
        st.Page("pages/2_Customer_Khata.py", title="Customer Khata", icon="📖"),
    ],
    "Inventory": [
        st.Page("pages/5_Purchases_and_Stock.py", title="Purchases & Stock", icon="📦"),
        st.Page("pages/4_Manage_Products.py", title="Manage Products", icon="⚙️"),
    ],
}

all_pages = [p for group in nav_sections.values() for p in group]
selected_page = st.navigation(all_pages, position="hidden")

ui.render_sidebar(nav_sections)

selected_page.run()
