"""
pages/4_Manage_Products.py — add new products and update today's rates.
This is where the "occasional new item" gets added in a few seconds.
"""
import streamlit as st
import pandas as pd
import db
import ui

ui.page_header("⚙️ Manage Products & Rates", "Add new items and update today's suggested rates.")

st.caption(
    "Rates here are just the **starting suggestion** shown when entering a sale — "
    "you can always override the rate for any individual sale. Past sales never change. "
    "Stock shown below is for reference only — manage it on the Purchases & Stock page."
)

products = db.get_products()
locations = db.get_locations()

st.subheader("📦 Current Products")

for p in products:
    col1, col2, col3, col4 = st.columns([2.2, 1, 1, 1])
    col1.write(p["name"])
    new_rate = col2.number_input(
        "Rate", min_value=0.0, value=float(p["default_rate"]),
        step=10.0, key=f"rate_{p['id']}", label_visibility="collapsed"
    )

    # Quick read-only glance at stock per location — Farm and Shop
    # numbers are independent, shown side by side, never summed.
    stock_bits = []
    for loc in locations:
        stock_row = db.get_product_stock(p["id"], loc["id"])
        stock_bits.append(f"{loc['name']}: {stock_row['stock_quantity']:,.0f}")
    col3.caption(" · ".join(stock_bits))

    if col4.button("Update", key=f"update_{p['id']}", use_container_width=True):
        db.update_product_rate(p["id"], new_rate)
        st.success(f"Updated {p['name']} rate to Rs. {new_rate:,.0f}")
        st.rerun()

st.divider()

st.subheader("➕ Add a New Product")
st.caption("New products start at 0 stock at both Farm and Shop — set real counts on the Purchases & Stock page.")
with st.form("add_product_form", clear_on_submit=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        new_name = st.text_input("Product Name", placeholder="e.g. Wheat Bran")
    with col2:
        new_rate_input = st.number_input("Starting Rate (Rs.)", min_value=0.0, step=10.0)

    if st.form_submit_button("Add Product", type="primary"):
        if not new_name.strip():
            st.error("Please enter a product name.")
        elif new_name.strip() in [p["name"] for p in products]:
            st.error("This product already exists.")
        else:
            db.add_product(new_name, new_rate_input)
            st.success(f"Added new product: {new_name}")
            st.rerun()
