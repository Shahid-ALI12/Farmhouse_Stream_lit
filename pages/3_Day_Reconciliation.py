"""
pages/3_Day_Reconciliation.py — end-of-day and historical cash summary.
This matches the bottom block of your handwritten page 2:
آمد (income) - اخراجات (expenses) = کیش (cash in hand)
"""
import streamlit as st
from datetime import date, timedelta
import pandas as pd
import db
import ui

ui.page_header("🏁 Day Reconciliation", "End-of-day cash summary — single day or a date range.")

mode = st.radio("View", ["Single Day", "Date Range"], horizontal=True)

if mode == "Single Day":
    selected_date = st.date_input("Date", value=date.today())
    start_date = end_date = selected_date
else:
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From", value=date.today() - timedelta(days=6))
    with col2:
        end_date = st.date_input("To", value=date.today())

if start_date > end_date:
    st.error("Start date must be before end date.")
    st.stop()

# Gather all sales & expenses across the selected range in ONE query
# each (using gte/lte date-range filters), instead of looping day by
# day and firing a separate network request per day. A 30-day report
# used to mean ~60 sequential round-trips; now it's 2, regardless of
# how many days are in the range.
all_sales = db.get_sales_for_date_range(start_date.isoformat(), end_date.isoformat())
all_expenses = db.get_expenses_for_date_range(start_date.isoformat(), end_date.isoformat())

st.divider()

if not all_sales and not all_expenses:
    st.info("No entries found for this period.")
    st.stop()

# ---- Sales summary ----
total_bags = sum(s["quantity"] for s in all_sales)
total_billed = sum(s["quantity"] * s["rate_per_bag"] + s["rickshaw_fare"] for s in all_sales)
total_cash_received = sum(s["cash_received"] for s in all_sales)
total_outstanding_change = total_billed - total_cash_received

credit_sales = [s for s in all_sales if s["customers"]["type"] == "credit"]
cash_sales = [s for s in all_sales if s["customers"]["type"] == "cash"]

st.subheader("💵 Income Summary")
i1, i2, i3 = st.columns(3)
i1.metric("Total Bags Sold", f"{total_bags:,.0f}")
i2.metric("Total Billed", f"Rs. {total_billed:,.0f}")
i3.metric("Cash Actually Received", f"Rs. {total_cash_received:,.0f}")

c1, c2 = st.columns(2)
c1.metric("From Credit Customers", f"Rs. {sum(s['cash_received'] for s in credit_sales):,.0f}")
c2.metric("From Cash Customers", f"Rs. {sum(s['cash_received'] for s in cash_sales):,.0f}")

st.divider()

# ---- Expenses summary ----
st.subheader("➖ Expenses Summary")
total_expenses = sum(e["amount"] for e in all_expenses)
st.metric("Total Expenses", f"Rs. {total_expenses:,.0f}")

if all_expenses:
    exp_df = pd.DataFrame([
        {"Date": e["expense_date"], "Description": e["description"], "Amount": e["amount"]}
        for e in all_expenses
    ])
    st.dataframe(exp_df, use_container_width=True, hide_index=True)

st.divider()

# ---- Final reconciliation ----
st.subheader("🏁 Net Cash Position")
expected_cash = total_cash_received - total_expenses

f1, f2, f3 = st.columns(3)
f1.metric("Total Cash In", f"Rs. {total_cash_received:,.0f}")
f2.metric("Total Cash Out (Expenses)", f"Rs. {total_expenses:,.0f}")
f3.metric("Expected Cash in Hand", f"Rs. {expected_cash:,.0f}")

st.caption(
    "Note: 'Cash Received' only counts money actually collected. Credit sales "
    "not yet paid stay on the customer's Khata balance and are not counted as cash."
)
