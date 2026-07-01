"""
pages/6_Custom_Mix_Order.py
For when a customer wants a custom feed blend at a specific total
weight (e.g. 2000kg), built by adding ingredients one at a time —
each with its own weight and rate — until the target weight is hit.

Behind the scenes, each ingredient becomes a normal sale row (so
stock, the cash ledger, and the customer's Khata balance all work
exactly the way they already do everywhere else) — all sharing one
mix_order_id so they can be shown/printed together as one bill.
"""
import streamlit as st
from datetime import date
import uuid
import pandas as pd
import db
import ui
from pdf_bill import generate_custom_mix_bill_pdf, CREDIT_LIMIT

ui.page_header(
    "🧪 Custom Mix Order",
    "Build a custom feed blend to a target total weight, ingredient by ingredient.",
)

# ---------------- Session state setup ----------------
if "mix_target_weight" not in st.session_state:
    st.session_state.mix_target_weight = None
if "mix_ingredients" not in st.session_state:
    st.session_state.mix_ingredients = []  # list of dicts
if "mix_customer_name" not in st.session_state:
    st.session_state.mix_customer_name = ""
if "mix_customer_type" not in st.session_state:
    st.session_state.mix_customer_type = "credit"
if "mix_order_date" not in st.session_state:
    st.session_state.mix_order_date = date.today()
if "mix_location_id" not in st.session_state:
    st.session_state.mix_location_id = None

products = db.get_products()
product_names = [p["name"] for p in products]
product_lookup = {p["name"]: p for p in products}

locations = db.get_locations()
location_lookup = {l["name"]: l for l in locations}


def reset_order():
    st.session_state.mix_target_weight = None
    st.session_state.mix_ingredients = []
    st.session_state.mix_customer_name = ""
    st.session_state.mix_customer_type = "credit"
    st.session_state.mix_order_date = date.today()
    st.session_state.mix_location_id = None


# ================== STEP 1: Start a new order ==================
if st.session_state.mix_target_weight is None:
    st.subheader("1️⃣ Start a New Mix Order")

    with st.form("start_mix_form"):
        col1, col2 = st.columns(2)
        with col1:
            customer_name = st.text_input("Customer Name", placeholder="Type name")
            customer_type = st.radio("Customer Type", ["credit", "cash"], horizontal=True)
            location_choice = st.radio(
                "Mixing from", list(location_lookup.keys()), horizontal=True,
                help="Stock for every ingredient in this order comes from this location.",
            )
        with col2:
            order_date = st.date_input("Order Date", value=date.today())
            target_weight = st.number_input(
                "Target Total Weight (kg)", min_value=0.0, step=50.0,
                help="The total weight of feed the customer wants, e.g. 2000kg.",
            )

        if st.form_submit_button("Start Order", type="primary", use_container_width=True):
            if not customer_name.strip():
                st.error("Please enter a customer name.")
            elif target_weight <= 0:
                st.error("Target weight must be greater than 0.")
            else:
                st.session_state.mix_customer_name = customer_name.strip()
                st.session_state.mix_customer_type = customer_type
                st.session_state.mix_order_date = order_date
                st.session_state.mix_target_weight = target_weight
                st.session_state.mix_location_id = location_lookup[location_choice]["id"]
                st.session_state.mix_ingredients = []
                st.rerun()

else:
    # ================== STEP 2: Add ingredients ==================
    target = st.session_state.mix_target_weight
    used = sum(i["weight_kg"] for i in st.session_state.mix_ingredients)
    remaining = target - used

    st.subheader(f"2️⃣ Building Order for {st.session_state.mix_customer_name}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Target Weight", f"{target:,.0f} kg")
    c2.metric("Weight Used So Far", f"{used:,.1f} kg")
    c3.metric("Remaining to Fill", f"{remaining:,.1f} kg",
              delta=None if remaining >= 0 else "Over target!",
              delta_color="inverse")

    st.divider()

    st.markdown("**➕ Add an Ingredient**")
    with st.form("add_ingredient_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            ing_product = st.selectbox("Product", product_names)
        with col2:
            ing_weight = st.number_input("Weight (kg)", min_value=0.0, step=10.0)
        with col3:
            selected_product = product_lookup[ing_product] if ing_product else {}
            ing_rate = st.number_input(
                "Rate per KG (Rs.)", min_value=0.0, step=1.0,
                help="Rate is always per KG for custom mix orders.",
            )

        if st.form_submit_button("Add to Mix", type="primary", use_container_width=True):
            if ing_weight <= 0:
                st.error("Weight must be greater than 0.")
            else:
                amount = ing_weight * ing_rate
                st.session_state.mix_ingredients.append({
                    "product": ing_product,
                    "product_id": selected_product["id"],
                    "weight_kg": ing_weight,
                    "rate_per_kg": ing_rate,
                    "amount": amount,
                })
                st.success(
                    f"Added {ing_weight:,.0f}kg of {ing_product} @ Rs.{ing_rate:,.2f}/kg "
                    f"= Rs.{amount:,.0f}"
                )
                st.rerun()

    st.divider()

    # ================== Current mix table ==================
    st.markdown("**📋 Current Mix**")
    if not st.session_state.mix_ingredients:
        st.caption("No ingredients added yet.")
    else:
        h = st.columns([2, 1, 1, 1, 0.6])
        for col, label in zip(h, ["Product", "Weight (kg)", "Rate/kg", "Amount", ""]):
            col.markdown(f"**{label}**")

        for idx, ing in enumerate(st.session_state.mix_ingredients):
            row = st.columns([2, 1, 1, 1, 0.6])
            row[0].write(ing["product"])
            row[1].write(f"{ing['weight_kg']:,.1f}")
            row[2].write(f"{ing['rate_per_kg']:,.2f}")
            row[3].write(f"{ing['amount']:,.0f}")
            if row[4].button("🗑️", key=f"del_ing_{idx}"):
                st.session_state.mix_ingredients.pop(idx)
                st.rerun()

        total_amount = sum(i["amount"] for i in st.session_state.mix_ingredients)
        st.metric("💰 Bill So Far", f"Rs. {total_amount:,.0f}")

    st.divider()

    # ================== Cash received (only if relevant) ==================
    cash_received = 0.0
    if st.session_state.mix_customer_type == "cash":
        cash_received = st.number_input(
            "Cash Received (Rs.)", min_value=0.0, step=100.0,
            value=sum(i["amount"] for i in st.session_state.mix_ingredients),
        )

    # ================== Finish order ==================
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔄 Cancel / Start Over", use_container_width=True):
            reset_order()
            st.rerun()

    with col_b:
        finish_disabled = len(st.session_state.mix_ingredients) == 0
        if st.button("✅ Finish Order & Generate Bill", type="primary",
                      use_container_width=True, disabled=finish_disabled):
            mix_order_id = str(uuid.uuid4())
            customer = db.get_or_create_customer(
                st.session_state.mix_customer_name, st.session_state.mix_customer_type
            )
            order_date_str = st.session_state.mix_order_date.isoformat()
            total_amount = sum(i["amount"] for i in st.session_state.mix_ingredients)

            # Each ingredient becomes a normal sale row, sharing mix_order_id.
            # Only the FIRST line carries the cash_received amount (for cash
            # orders), so the total isn't double counted across lines.
            for i, ing in enumerate(st.session_state.mix_ingredients):
                db.add_sale(
                    customer_id=customer["id"],
                    product_id=ing["product_id"],
                    quantity=ing["weight_kg"],
                    rate_per_bag=ing["rate_per_kg"],
                    rickshaw_fare=0,
                    cash_received=cash_received if i == 0 else 0,
                    sale_date=order_date_str,
                    location_id=st.session_state.mix_location_id,
                    unit_type="kg",
                    mix_order_id=mix_order_id,
                )

            st.session_state.mix_last_order_id = mix_order_id
            st.session_state.mix_last_customer_id = customer["id"]
            st.success(
                f"Order saved! Rs. {total_amount:,.0f} billed to "
                f"{st.session_state.mix_customer_name}, stock updated."
            )
            reset_order()
            st.rerun()

# ================== Show download link for the most recent finished order ==================
if "mix_last_order_id" in st.session_state and st.session_state.mix_target_weight is None:
    st.divider()
    st.subheader("🧾 Download Last Order's Bill")

    lines = db.get_mix_order_lines(st.session_state.mix_last_order_id)
    if lines:
        customer_info = lines[0]["customers"]
        ingredient_lines = [{
            "product": l["products"]["name"],
            "weight_kg": l["quantity"],
            "rate_per_kg": l["rate_per_bag"],
            "amount": l["quantity"] * l["rate_per_bag"],
        } for l in lines]
        target_weight_used = sum(l["weight_kg"] for l in ingredient_lines)
        cash_received_total = sum(l["cash_received"] for l in lines)
        payment_type = customer_info["type"]

        bal = db.get_customer_balance(st.session_state.mix_last_customer_id)

        pdf_bytes = generate_custom_mix_bill_pdf(
            business_name="Danish Cattle Feed",
            customer_name=customer_info["name"],
            order_date=lines[0]["sale_date"],
            target_weight_kg=target_weight_used,
            ingredient_lines=ingredient_lines,
            customer_phone=customer_info.get("phone"),
            payment_type=payment_type,
            cash_received=cash_received_total,
            new_balance_due=bal["balance_due"] if payment_type == "credit" else None,
        )
        st.download_button(
            label="📥 Download Mix Order Bill (PDF)",
            data=pdf_bytes,
            file_name=f"{customer_info['name'].replace(' ', '_')}_mix_order.pdf",
            mime="application/pdf",
            type="primary",
        )
