"""
pages/1_Daily_Entry.py — the main screen used every day.
Add sales (credit or cash) and expenses, see today's running list,
and a live cash summary at the bottom.
"""
import streamlit as st
from datetime import date
import pandas as pd
import db

st.set_page_config(page_title="Daily Entry", page_icon="🧾", layout="wide")
st.title("🧾 Daily Entry")

selected_date = st.date_input("Date", value=date.today())
date_str = selected_date.isoformat()

st.divider()

# ================== ADD A SALE ==================
st.subheader("➕ Add a Sale")

products = db.get_products()
product_names = [p["name"] for p in products]
product_lookup = {p["name"]: p for p in products}

locations = db.get_locations()
location_names = [l["name"] for l in locations]
location_lookup = {l["name"]: l for l in locations}

# --- Everything that feeds the bill calculation lives OUTSIDE the
# st.form below. Streamlit only re-runs the script (and recalculates
# things like a live bill preview) when a widget OUTSIDE a form
# changes; widgets INSIDE a form stay frozen until the form is
# submitted. Putting location/unit/product/quantity/rate/rickshaw out
# here means the bill preview updates on every keystroke, instead of
# showing Rs. 0 until the operator hits "Add Sale".
col_a, col_b = st.columns(2)
with col_a:
    location_choice = st.radio(
        "Location (this sale's stock comes from)", location_names,
        horizontal=True, key="sale_location_choice",
        help="Farm and Shop stock are tracked completely separately.",
    )
with col_b:
    unit_choice = st.radio(
        "Selling in", ["Bags", "KG (loose)"], horizontal=True, key="sale_unit_choice"
    )

selected_location = location_lookup[location_choice]
unit_type = "bags" if unit_choice == "Bags" else "kg"

calc_col1, calc_col2, calc_col3 = st.columns([1.3, 1, 1])

with calc_col1:
    product_name = st.selectbox("Product", product_names, key="sale_product")
    selected_product = product_lookup[product_name] if product_name else {}
    stock_here = (
        db.get_product_stock(selected_product["id"], selected_location["id"])
        if selected_product else {}
    )
    st.caption(f"📍 Stock at {location_choice}: **{stock_here.get('stock_quantity', 0):,.0f} bags**")

with calc_col2:
    if unit_type == "bags":
        quantity = st.number_input("Quantity (bags)", min_value=0.0, step=1.0, key="sale_qty")
        bag_weight = st.number_input(
            "Bag Weight (kg)", min_value=0.0, step=5.0, key="sale_bag_weight",
            value=float(stock_here.get("last_bag_weight_kg") or 50),
            help="Weight of each bag in this batch — can differ from last time.",
        )
    else:
        quantity = st.number_input("Quantity (kg)", min_value=0.0, step=5.0, key="sale_qty_kg")
        bag_weight = None

with calc_col3:
    default_rate = selected_product.get("default_rate", 0)
    rate_label = "Rate per Bag (Rs.)" if unit_type == "bags" else "Rate per KG (Rs.)"
    rate = st.number_input(rate_label, min_value=0.0, value=float(default_rate),
                            step=10.0, key="sale_rate")
    rickshaw = st.number_input("Rickshaw Freight (Rs.)", min_value=0.0, step=50.0, key="sale_rickshaw")

# --- Live preview, recalculated on every keystroke above ---
live_bill = quantity * rate + rickshaw
st.info(f"💰 **Bill so far: Rs. {live_bill:,.0f}**  ({quantity:,.0f} x Rs.{rate:,.0f} + Rs.{rickshaw:,.0f} freight)")

with st.form("add_sale_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        customer_type = st.radio(
            "Customer Type", ["credit", "cash"], horizontal=True,
            help="Credit = ادھار کھاتہ (goes on their running tab). Cash = نقد (paid now)."
        )
        customer_name = st.text_input(
            "Customer Name",
            placeholder="Type name — existing customer is matched automatically",
        )
    with col2:
        cash_received = st.number_input(
            "Cash Received Now (Rs.)", min_value=0.0, step=100.0,
            help="For cash customers, this is usually the full bill amount.",
        )
        st.metric("Bill Total", f"Rs. {live_bill:,.0f}")

    submitted = st.form_submit_button("Add Sale", use_container_width=True, type="primary")

    if submitted:
        if not customer_name.strip():
            st.error("Please enter a customer name.")
        elif quantity <= 0:
            st.error("Quantity must be greater than 0.")
        elif unit_type == "bags" and bag_weight <= 0:
            st.error("Please enter a valid bag weight.")
        else:
            customer = db.get_or_create_customer(customer_name, customer_type)
            db.add_sale(
                customer_id=customer["id"],
                product_id=selected_product["id"],
                quantity=quantity,
                rate_per_bag=rate,
                rickshaw_fare=rickshaw,
                cash_received=cash_received,
                sale_date=date_str,
                location_id=selected_location["id"],
                unit_type=unit_type,
                bag_weight_kg=bag_weight,
            )
            unit_label = "bag(s)" if unit_type == "bags" else "kg"
            st.success(
                f"Added: {customer_name} — {quantity:,.0f} {unit_label} of {product_name} "
                f"@ Rs.{rate:,.0f} = Rs.{live_bill:,.0f} bill  (from {location_choice})"
            )
            st.rerun()

st.divider()

# ================== TODAY'S SALES LIST ==================
st.subheader(f"📋 Sales on {selected_date.strftime('%d %b %Y')}")

sales = db.get_sales_for_date(date_str)

if not sales:
    st.caption("No sales entered yet for this date.")
else:
    # Header row
    h = st.columns([1.3, 0.9, 1.3, 0.9, 0.8, 0.8, 0.8, 1, 1, 1, 0.8])
    headers = ["Customer", "Type", "Product", "Location", "Qty", "Rate", "Rickshaw",
               "Bill", "Cash Recv.", "Remaining", ""]
    for col, label in zip(h, headers):
        col.markdown(f"**{label}**")

    total_bags = 0
    total_bill = 0
    total_cash_from_sales = 0

    for s in sales:
        bill = s["quantity"] * s["rate_per_bag"] + s["rickshaw_fare"]
        remaining = bill - s["cash_received"]
        total_bags += s["quantity"] if s.get("unit_type", "bags") == "bags" else 0
        total_bill += bill
        total_cash_from_sales += s["cash_received"]

        unit_suffix = "kg" if s.get("unit_type") == "kg" else ""
        location_label = s["locations"]["name"] if s.get("locations") else "—"
        row = st.columns([1.3, 0.9, 1.3, 0.9, 0.8, 0.8, 0.8, 1, 1, 1, 0.8])
        row[0].write(s["customers"]["name"])
        row[1].write(s["customers"]["type"])
        row[2].write(s["products"]["name"])
        row[3].write(location_label)
        row[4].write(f"{s['quantity']:,.0f}{unit_suffix}")
        row[5].write(f"{s['rate_per_bag']:,.0f}")
        row[6].write(f"{s['rickshaw_fare']:,.0f}")
        row[7].write(f"{bill:,.0f}")
        row[8].write(f"{s['cash_received']:,.0f}")
        row[9].write(f"{remaining:,.0f}")
        if row[10].button("🗑️", key=f"del_sale_{s['id']}", help="Delete this sale"):
            db.delete_sale(s["id"])
            st.success("Sale deleted and stock adjusted back.")
            st.rerun()

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Bags Sold", f"{total_bags:,.0f}")
    c2.metric("Total Billed", f"Rs. {total_bill:,.0f}")
    c3.metric("Cash Collected from Sales", f"Rs. {total_cash_from_sales:,.0f}")

st.divider()

# ================== ADD AN EXPENSE ==================
st.subheader("➖ Add an Expense")

with st.form("add_expense_form", clear_on_submit=True):
    e1, e2 = st.columns([3, 1])
    with e1:
        expense_desc = st.text_input("Description", placeholder="e.g. Rickshaw, Tea, Labour")
    with e2:
        expense_amount = st.number_input("Amount (Rs.)", min_value=0.0, step=50.0)

    expense_submitted = st.form_submit_button("Add Expense", use_container_width=True)

    if expense_submitted:
        if not expense_desc.strip():
            st.error("Please enter a description.")
        elif expense_amount <= 0:
            st.error("Amount must be greater than 0.")
        else:
            db.add_expense(expense_desc, expense_amount, date_str)
            st.success(f"Added expense: {expense_desc} — Rs. {expense_amount:,.0f}")
            st.rerun()

# ================== TODAY'S EXPENSES LIST ==================
expenses = db.get_expenses_for_date(date_str)

total_expenses = 0
if expenses:
    h = st.columns([3, 1.5, 0.8])
    h[0].markdown("**Description**")
    h[1].markdown("**Amount**")
    h[2].markdown("**​**")

    for e in expenses:
        total_expenses += e["amount"]
        row = st.columns([3, 1.5, 0.8])
        row[0].write(e["description"])
        row[1].write(f"Rs. {e['amount']:,.0f}")
        if row[2].button("🗑️", key=f"del_exp_{e['id']}", help="Delete this expense"):
            db.delete_expense(e["id"])
            st.success("Expense deleted.")
            st.rerun()

    st.metric("Total Expenses Today", f"Rs. {total_expenses:,.0f}")
else:
    st.caption("No expenses entered yet for this date.")

st.divider()

# ================== LIVE CASH SUMMARY ==================
st.subheader("🏁 Live Cash Summary")

total_cash_in = sum(s["cash_received"] for s in sales) if sales else 0
expected_cash = total_cash_in - total_expenses

s1, s2, s3 = st.columns(3)
s1.metric("Cash Received Today", f"Rs. {total_cash_in:,.0f}")
s2.metric("Expenses Today", f"Rs. {total_expenses:,.0f}")
s3.metric("Expected Cash in Hand", f"Rs. {expected_cash:,.0f}")
