"""
pages/0_Dashboard.py — landing page shown when the app first opens.
A quick at-a-glance summary of today's activity, with shortcuts into
the rest of the app. Nothing here is editable — it's a read-only
overview built entirely from the same data the other pages already use.
"""
import streamlit as st
from datetime import date
import db
import ui

ui.page_header(
    f"{ui.BRAND_ICON} {ui.BRAND_NAME}",
    f"Daily Register · {date.today().strftime('%A, %d %B %Y')}",
)

try:
    today_str = date.today().isoformat()
    sales = db.get_sales_for_date(today_str)
    expenses = db.get_expenses_for_date(today_str)
    customers = db.get_customers()

    total_bill = sum(s["quantity"] * s["rate_per_bag"] + s["rickshaw_fare"] for s in sales) if sales else 0
    total_cash_in = sum(s["cash_received"] for s in sales) if sales else 0
    total_expenses = sum(e["amount"] for e in expenses) if expenses else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sales Today", f"{len(sales)}", "transactions")
    c2.metric("Billed Today", f"Rs. {total_bill:,.0f}")
    c3.metric("Cash Collected", f"Rs. {total_cash_in:,.0f}")
    c4.metric("Expenses Today", f"Rs. {total_expenses:,.0f}")

    st.divider()

    outstanding_total = 0
    over_limit_count = 0
    from pdf_bill import CREDIT_LIMIT
    for c in customers:
        bal = db.get_customer_balance(c["id"])
        outstanding_total += bal["balance_due"]
        if bal["balance_due"] >= CREDIT_LIMIT:
            over_limit_count += 1

    d1, d2, d3 = st.columns(3)
    d1.metric("Customers", f"{len(customers)}")
    d2.metric("Total Outstanding (Khata)", f"Rs. {outstanding_total:,.0f}")
    d3.metric("Over Credit Limit", f"{over_limit_count}")

except Exception:
    st.info("No data to summarize yet — start by adding a sale on the **Daily Entry** page.")

st.divider()
st.markdown("##### Quick links")
q1, q2, q3 = st.columns(3)
with q1:
    st.page_link("pages/1_Daily_Entry.py", label="Add a Sale / Expense", icon="🧾")
    st.page_link("pages/6_Custom_Mix_Order.py", label="Build a Custom Mix Bill", icon="🧪")
with q2:
    st.page_link("pages/2_Customer_Khata.py", label="Check a Customer's Khata", icon="📖")
    st.page_link("pages/3_Day_Reconciliation.py", label="Reconcile the Day", icon="🏁")
with q3:
    st.page_link("pages/5_Purchases_and_Stock.py", label="Record a Purchase", icon="📦")
    st.page_link("pages/4_Manage_Products.py", label="Manage Products & Rates", icon="⚙️")
