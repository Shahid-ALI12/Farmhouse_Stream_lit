"""
pages/5_Purchases_and_Stock.py
Three things happen here:
  1. Audit/correct current stock levels per location, in EITHER bags
     or total KG — editing one recalculates the other live, using
     that row's own bag weight.
  2. Record purchases — either from a supplier (you pay cash) or
     from a credit customer paying you in goods instead of cash.
     Every purchase names a location, and only that location's stock
     changes.
  3. See today's purchase log.
"""
import streamlit as st
from datetime import date
import pandas as pd
import db
import ui

ui.page_header("📦 Purchases & Stock", "Correct stock counts, record purchases, and review today's purchase log.")

products = db.get_products()
product_names = [p["name"] for p in products]
product_lookup = {p["name"]: p for p in products}

locations = db.get_locations()
location_lookup = {l["name"]: l for l in locations}

selected_date = st.date_input("Date", value=date.today())
date_str = selected_date.isoformat()

st.divider()

# ================== CURRENT STOCK LEVELS — DUAL-UNIT EDITOR ==================
st.subheader("📊 Current Stock Levels — Physical Count Correction")
st.caption(
    "Farm and Shop stock are tracked *completely separately* — nothing here is "
    "added together. Edit a cell in *either* Bags or Total KG — the other "
    "column recalculates automatically using that row's bag weight, then click "
    "Save to write it to the database."
)

location_icons = {"Farm": "🏞️", "Shop": "🏬"}
stock_tabs = st.tabs([f"{location_icons.get(l['name'], '📍')} {l['name']}" for l in locations])

for tab, loc in zip(stock_tabs, locations):
    with tab:
        stock_rows = db.get_stock_for_location(loc["id"])

        base_df = pd.DataFrame([
            {
                "product_id": r["products"]["id"],
                "Product": r["products"]["name"],
                "Bag Weight (kg)": float(r.get("last_bag_weight_kg") or 50),
                "Bags": float(r["stock_quantity"]),
                "Total KG": float(r["stock_quantity"]) * float(r.get("last_bag_weight_kg") or 50),
            }
            for r in stock_rows
        ])

        editor_key = f"stock_editor_{loc['id']}"

        edited_df = st.data_editor(
            base_df,
            column_order=["Product", "Bag Weight (kg)", "Bags", "Total KG"],
            column_config={
                "Product": st.column_config.TextColumn(disabled=True),
                "Bag Weight (kg)": st.column_config.NumberColumn(disabled=True, format="%.0f"),
                "Bags": st.column_config.NumberColumn(format="%.1f"),
                "Total KG": st.column_config.NumberColumn(format="%.0f"),
            },
            hide_index=True,
            use_container_width=True,
            key=editor_key,
        )

        # Streamlit records exactly which cells the user touched in
        # st.session_state[editor_key]["edited_rows"], keyed by row
        # position -> {column_name: new_value}. We only act on cells
        # that were actually edited, so e.g. editing "Bags" doesn't
        # require the unrelated "Total KG" cell to also change first.
        edited_rows = st.session_state.get(editor_key, {}).get("edited_rows", {})

        if edited_rows:
            preview_lines = []
            pending_updates = {}  # row_idx -> final bag quantity to save

            for row_idx, changes in edited_rows.items():
                row = base_df.iloc[row_idx]
                bag_weight = row["Bag Weight (kg)"] or 50

                if "Bags" in changes:
                    new_bags = float(changes["Bags"])
                elif "Total KG" in changes:
                    new_kg = float(changes["Total KG"])
                    new_bags = new_kg / bag_weight if bag_weight else new_kg
                else:
                    continue

                pending_updates[row_idx] = new_bags
                preview_lines.append(
                    f"- *{row['Product']}*: {new_bags:,.1f} bags "
                    f"(≈ {new_bags * bag_weight:,.0f} kg)"
                )

            if preview_lines:
                st.info("Pending changes:\n" + "\n".join(preview_lines))

            if st.button(f"💾 Save {loc['name']} Stock Changes", key=f"save_{loc['id']}", type="primary"):
                for row_idx, new_bags in pending_updates.items():
                    product_id = int(base_df.iloc[row_idx]["product_id"])
                    db.set_stock(product_id, loc["id"], new_bags)
                st.success(f"Updated {len(pending_updates)} product(s) at {loc['name']}.")
                del st.session_state[editor_key]
                st.rerun()

        low_stock = base_df[base_df["Bags"] < 0]
        if not low_stock.empty:
            st.warning(
                f"⚠️ These products show *negative* stock at {loc['name']} — "
                "meaning more has gone out than was recorded coming in. "
                "Do a physical count and correct it above.",
                icon="⚠️",
            )

st.divider()

# ================== ADD A PURCHASE ==================
st.subheader("➕ Record a Purchase")

purchase_type = st.radio(
    "Purchase Type",
    ["From a supplier (I pay cash)", "From a credit customer (paid in goods, reduces their debt)"],
    horizontal=False,
)

# --- Everything needed for the live value preview lives OUTSIDE the
# st.form below, same fix as on the Daily Entry page: widgets inside a
# form freeze until submit, so a "this reduces their debt by Rs. X"
# preview would otherwise sit at Rs. 0 the whole time the operator is
# typing. Location + unit pickers were already outside; now product,
# quantity, bag weight and rate join them.
col_loc, col_unit = st.columns(2)
with col_loc:
    location_choice = st.radio(
        "Receiving at", list(location_lookup.keys()), horizontal=True,
        key="purchase_location_choice",
        help="This stock will be added to this location only.",
    )
with col_unit:
    unit_choice = st.radio(
        "Receiving in", ["Bags", "KG (loose)"], horizontal=True, key="purchase_unit_choice"
    )

selected_location = location_lookup[location_choice]
unit_type = "bags" if unit_choice == "Bags" else "kg"

if purchase_type == "From a supplier (I pay cash)":
    calc_col1, calc_col2, calc_col3 = st.columns(3)
    with calc_col1:
        supplier_name = st.text_input("Supplier Name", placeholder="Type name", key="sup_name")
        product_name = st.selectbox("Product", product_names, key="sup_product")
    with calc_col2:
        selected_product = product_lookup[product_name] if product_name else {}
        stock_here = (
            db.get_product_stock(selected_product["id"], selected_location["id"])
            if selected_product else {}
        )
        if unit_type == "bags":
            quantity = st.number_input("Quantity (bags)", min_value=0.0, step=1.0, key="sup_qty")
            bag_weight = st.number_input(
                "Bag Weight (kg)", min_value=0.0, step=5.0, key="sup_bag_weight",
                value=float(stock_here.get("last_bag_weight_kg") or 50),
            )
            rate = st.number_input("Rate per Bag (Rs.)", min_value=0.0, step=10.0, key="sup_rate")
        else:
            quantity = st.number_input("Quantity (kg)", min_value=0.0, step=5.0, key="sup_qty_kg")
            bag_weight = None
            rate = st.number_input("Rate per KG (Rs.)", min_value=0.0, step=10.0, key="sup_rate_kg")
    with calc_col3:
        cash_paid = st.number_input("Cash Paid (Rs.)", min_value=0.0, step=100.0, key="sup_cash")
        live_value = quantity * rate
        st.metric("Goods Value", f"Rs. {live_value:,.0f}")

    with st.form("supplier_purchase_form", clear_on_submit=True):
        notes = st.text_input("Notes (optional)", key="sup_notes")
        if st.form_submit_button("Add Purchase", type="primary", use_container_width=True):
            if not supplier_name.strip():
                st.error("Please enter a supplier name.")
            elif quantity <= 0:
                st.error("Quantity must be greater than 0.")
            elif unit_type == "bags" and bag_weight <= 0:
                st.error("Please enter a valid bag weight.")
            else:
                supplier = db.get_or_create_supplier(supplier_name)
                db.add_purchase_from_supplier(
                    supplier_id=supplier["id"],
                    product_id=product_lookup[product_name]["id"],
                    quantity=quantity,
                    rate_per_bag=rate,
                    cash_paid=cash_paid,
                    purchase_date=date_str,
                    location_id=selected_location["id"],
                    notes=notes,
                    unit_type=unit_type,
                    bag_weight_kg=bag_weight,
                )
                unit_label = "bag(s)" if unit_type == "bags" else "kg"
                st.success(
                    f"Purchased {quantity:,.0f} {unit_label} of {product_name} from {supplier_name} "
                    f"— {location_choice} stock increased, Rs. {cash_paid:,.0f} paid."
                )
                st.rerun()

else:
    st.caption(
        "Use this when a credit customer gives you product instead of cash "
        "to pay down what they owe. Their balance drops by the value of the "
        "goods, and that stock is added to whichever location you pick above."
    )
    credit_customers = db.get_customers(customer_type="credit")
    customer_names = [c["name"] for c in credit_customers]

    if not credit_customers:
        st.info("No credit customers yet. Add one first via the Daily Entry page.")
    else:
        calc_col1, calc_col2, calc_col3 = st.columns(3)
        with calc_col1:
            sel_customer_name = st.selectbox("Credit Customer", customer_names, key="cust_sel")
            product_name = st.selectbox("Product Received", product_names, key="cust_product")
        with calc_col2:
            selected_product = product_lookup[product_name] if product_name else {}
            stock_here = (
                db.get_product_stock(selected_product["id"], selected_location["id"])
                if selected_product else {}
            )
            if unit_type == "bags":
                quantity = st.number_input("Quantity (bags)", min_value=0.0, step=1.0, key="cust_qty")
                bag_weight = st.number_input(
                    "Bag Weight (kg)", min_value=0.0, step=5.0, key="cust_bag_weight",
                    value=float(stock_here.get("last_bag_weight_kg") or 50),
                )
                rate = st.number_input("Value per Bag (Rs.)", min_value=0.0, step=10.0, key="cust_rate")
            else:
                quantity = st.number_input("Quantity (kg)", min_value=0.0, step=5.0, key="cust_qty_kg")
                bag_weight = None
                rate = st.number_input("Value per KG (Rs.)", min_value=0.0, step=10.0, key="cust_rate_kg")
        with calc_col3:
            # This is the exact metric that used to be frozen at Rs. 0
            # inside the form until submit — now it updates live as
            # the operator types, since quantity/rate are widgets
            # outside any st.form.
            goods_value = quantity * rate
            st.metric("This reduces their debt by", f"Rs. {goods_value:,.0f}")

        with st.form("customer_settlement_form", clear_on_submit=True):
            notes = st.text_input("Notes (optional)", key="cust_notes")
            if st.form_submit_button("Record Settlement", type="primary", use_container_width=True):
                if quantity <= 0:
                    st.error("Quantity must be greater than 0.")
                elif unit_type == "bags" and bag_weight <= 0:
                    st.error("Please enter a valid bag weight.")
                else:
                    sel_customer = next(c for c in credit_customers if c["name"] == sel_customer_name)
                    db.add_purchase_settled_by_customer(
                        customer_id=sel_customer["id"],
                        product_id=product_lookup[product_name]["id"],
                        quantity=quantity,
                        rate_per_bag=rate,
                        purchase_date=date_str,
                        location_id=selected_location["id"],
                        notes=notes,
                        unit_type=unit_type,
                        bag_weight_kg=bag_weight,
                    )
                    unit_label = "bag(s)" if unit_type == "bags" else "kg"
                    st.success(
                        f"{sel_customer_name}'s debt reduced by Rs. {goods_value:,.0f} "
                        f"({quantity:,.0f} {unit_label} of {product_name} received into {location_choice} stock)."
                    )
                    st.rerun()

st.divider()

# ================== TODAY'S PURCHASES LIST ==================
st.subheader(f"📋 Purchases on {selected_date.strftime('%d %b %Y')}")

purchases = db.get_purchases_for_date(date_str)

if not purchases:
    st.caption("No purchases recorded yet for this date.")
else:
    h = st.columns([1.8, 1.3, 0.9, 0.8, 0.8, 1, 1, 0.8])
    for col, label in zip(h, ["Source", "Product", "Location", "Qty", "Rate", "Value", "Cash Paid", ""]):
        col.markdown(f"*{label}*")

    total_cash_out = 0
    for p in purchases:
        source = p["suppliers"]["name"] if p["suppliers"] else f"{p['customers']['name']} (goods settlement)"
        value = p["quantity"] * p["rate_per_bag"]
        total_cash_out += p["cash_paid"]
        unit_suffix = "kg" if p.get("unit_type") == "kg" else ""
        location_label = p["locations"]["name"] if p.get("locations") else "—"

        row = st.columns([1.8, 1.3, 0.9, 0.8, 0.8, 1, 1, 0.8])
        row[0].write(source)
        row[1].write(p["products"]["name"])
        row[2].write(location_label)
        row[3].write(f"{p['quantity']:,.0f}{unit_suffix}")
        row[4].write(f"{p['rate_per_bag']:,.0f}")
        row[5].write(f"{value:,.0f}")
        row[6].write(f"{p['cash_paid']:,.0f}")
        if row[7].button("🗑️", key=f"del_purchase_{p['id']}", help="Delete this purchase"):
            db.delete_purchase(p["id"])
            st.success("Purchase deleted and stock adjusted back.")
            st.rerun()

    st.metric("Total Cash Paid for Purchases Today", f"Rs. {total_cash_out:,.0f}")