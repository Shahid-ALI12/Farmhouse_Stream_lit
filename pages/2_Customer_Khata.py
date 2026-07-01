"""
pages/2_Customer_Khata.py — running ledger per customer.
This is built automatically from sales AND goods-settlements (purchases
where a customer paid in product instead of cash) — nothing here is
hand-entered, so it can never drift out of sync with daily entries.
"""
import streamlit as st
import pandas as pd
import db
import ui
from pdf_bill import generate_customer_bill_pdf, CREDIT_LIMIT

ui.page_header("📖 Customer Khata", "Running ledger and credit balance for every customer.")

customers = db.get_customers()

if not customers:
    st.info("No customers yet. Add a sale on the Daily Entry page first.")
    st.stop()

# Build a quick balance summary for every customer first.
# Uses db.get_customer_balance, the single source of truth that already
# accounts for cash payments AND goods-as-payment settlements.
summary_rows = []
for c in customers:
    bal = db.get_customer_balance(c["id"])
    summary_rows.append({
        "Customer": c["name"],
        "Type": c["type"],
        "Total Billed": bal["total_bill"],
        "Cash Paid": bal["total_cash_paid"],
        "Paid in Goods": bal["total_goods_value"],
        "Balance Due": bal["balance_due"],
    })

summary_df = pd.DataFrame(summary_rows).sort_values("Balance Due", ascending=False)

st.subheader("📊 All Customers — Balance Overview")
st.caption(
    f"Rows highlighted in red have crossed the credit limit of Rs. {CREDIT_LIMIT:,.0f}."
)


def highlight_over_limit(row):
    if row["Balance Due"] >= CREDIT_LIMIT:
        return ["background-color: #fde2e1; color: #c0392b; font-weight: bold"] * len(row)
    return [""] * len(row)


st.dataframe(
    summary_df.style
        .apply(highlight_over_limit, axis=1)
        .format({
            "Total Billed": "Rs. {:,.0f}",
            "Cash Paid": "Rs. {:,.0f}",
            "Paid in Goods": "Rs. {:,.0f}",
            "Balance Due": "Rs. {:,.0f}",
        }),
    use_container_width=True,
    hide_index=True,
)

total_outstanding = summary_df["Balance Due"].sum()
st.metric("💰 Total Outstanding Across All Customers", f"Rs. {total_outstanding:,.0f}")

st.divider()

# Drill into one customer's full history
st.subheader("🔍 Individual Customer History")
customer_names = [c["name"] for c in customers]
selected_name = st.selectbox("Select a customer", customer_names)
selected_customer = next(c for c in customers if c["name"] == selected_name)

detail_sales = db.get_sales_for_customer(selected_customer["id"])
detail_settlements = db.get_purchases_settled_by_customer(selected_customer["id"])
bal = db.get_customer_balance(selected_customer["id"])

if not detail_sales and not detail_settlements:
    st.caption("No transactions yet for this customer.")
else:
    st.markdown("**Sales (charges added to their tab)**")
    if detail_sales:
        # Number bills in chronological order, grouped by
        # transaction_group_id, so multi-item bills are visibly tied
        # together instead of looking like unrelated single sales.
        group_numbers = {}
        next_group_num = 1
        rows = []
        for s in detail_sales:
            group_id = s.get("transaction_group_id")
            if group_id:
                if group_id not in group_numbers:
                    group_numbers[group_id] = next_group_num
                    next_group_num += 1
                bill_label = f"#{group_numbers[group_id]}"
            else:
                bill_label = "—"

            bill = s["quantity"] * s["rate_per_bag"] + s["rickshaw_fare"]
            rows.append({
                "Bill": bill_label,
                "Date": s["sale_date"],
                "Product": s["products"]["name"],
                "Qty": s["quantity"],
                "Rate": s["rate_per_bag"],
                "Rickshaw": s["rickshaw_fare"],
                "Bill Amount": bill,
                "Cash Paid": s["cash_received"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption("Rows sharing the same Bill number were one transaction (one customer visit).")
    else:
        st.caption("No sales recorded.")

    st.markdown("**Paid in Goods (reduces their tab, no cash involved)**")
    if detail_settlements:
        rows = []
        for p in detail_settlements:
            rows.append({
                "Date": p["purchase_date"],
                "Product Given": p["products"]["name"],
                "Qty": p["quantity"],
                "Rate": p["rate_per_bag"],
                "Value Credited": p["quantity"] * p["rate_per_bag"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No goods settlements recorded.")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Total Billed", f"Rs. {bal['total_bill']:,.0f}")
    d2.metric("Cash Paid", f"Rs. {bal['total_cash_paid']:,.0f}")
    d3.metric("Paid in Goods", f"Rs. {bal['total_goods_value']:,.0f}")
    d4.metric("Balance Due", f"Rs. {bal['balance_due']:,.0f}")

    if bal["balance_due"] >= CREDIT_LIMIT:
        st.error(
            f"⚠️ {selected_customer['name']} has crossed the credit limit "
            f"of Rs. {CREDIT_LIMIT:,.0f}.",
            icon="⚠️",
        )

    st.divider()
    st.subheader("🧾 Download Bill")
    st.caption("Generates a printable statement you can send to the customer.")

    statement_lines = db.get_customer_statement(selected_customer["id"])
    if statement_lines:
        pdf_bytes = generate_customer_bill_pdf(
            business_name="Danish Cattle Feed",
            customer_name=selected_customer["name"],
            statement_lines=statement_lines,
            balance_due=bal["balance_due"],
            customer_phone=selected_customer.get("phone"),
        )
        st.download_button(
            label="📥 Download Bill (PDF)",
            data=pdf_bytes,
            file_name=f"{selected_customer['name'].replace(' ', '_')}_bill.pdf",
            mime="application/pdf",
            type="primary",
        )
    else:
        st.caption("No transactions to put on a bill yet.")
