"""
pages/7_Cash_Management.py
Tracks the two places cash physically lives: a small amount kept
"in Hand" for day-to-day small expenses, and the bulk kept "in
Locker" upstairs for safety. Total Cash is always Hand + Locker —
moving money between them doesn't create or destroy cash, it just
shifts which bucket it's sitting in.

Every movement (a sale's cash landing in Locker, an expense paid out
of Locker, or a manual Hand<->Locker transfer) is one row in the
shared cash_ledger table — these two balances are never stored
numbers, they are always SUMS of that ledger, so they can never
silently drift from what's actually been recorded.
"""
import streamlit as st
from datetime import date
import pandas as pd
import db
import ui

ui.page_header(
    "🏦 Cash Management",
    "Track cash in Hand vs cash in the Locker, and move money between them.",
)

accounts = db.get_cash_accounts()
account_lookup = {a["name"]: a for a in accounts}
hand_account = account_lookup.get("Cash In Hand")
locker_account = account_lookup.get("Cash In Locker")

if not hand_account or not locker_account:
    st.error(
        "Cash accounts not found. Make sure migration_4_cash_ledger.sql "
        "has been run in Supabase."
    )
    st.stop()

balances = db.get_all_account_balances()
hand_balance = balances.get("Cash In Hand", 0)
locker_balance = balances.get("Cash In Locker", 0)
total_cash = hand_balance + locker_balance

# ================== BALANCE OVERVIEW ==================
c1, c2, c3 = st.columns(3)
c1.metric("💵 Cash In Hand", f"Rs. {hand_balance:,.0f}")
c2.metric("🔒 Cash In Locker", f"Rs. {locker_balance:,.0f}")
c3.metric("📊 Total Cash", f"Rs. {total_cash:,.0f}")

st.caption(
    "Total Cash is always Hand + Locker. Moving money between them with a "
    "transfer below changes how it's split, never the total."
)

st.divider()

# ================== TRANSFER CASH ==================
st.subheader("🔁 Transfer Cash")
st.caption(
    "Use this whenever cash physically moves between Hand and Locker — "
    "e.g. taking cash from the Locker to pay a supplier, or moving the "
    "day's earnings from Hand into the Locker for safekeeping."
)

with st.form("transfer_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        direction = st.radio(
            "Direction",
            ["Locker ➜ Hand", "Hand ➜ Locker"],
            horizontal=True,
            help="Pick which way the cash is physically moving.",
        )
        transfer_date = st.date_input("Date", value=date.today())
    with col2:
        amount = st.number_input("Amount (Rs.)", min_value=0.0, step=100.0)
        notes = st.text_input("Notes (optional)", placeholder="e.g. Paying Choker supplier")

    submitted = st.form_submit_button("Record Transfer", type="primary", use_container_width=True)

    if submitted:
        if amount <= 0:
            st.error("Amount must be greater than 0.")
        else:
            if direction == "Locker ➜ Hand":
                from_id, to_id = locker_account["id"], hand_account["id"]
            else:
                from_id, to_id = hand_account["id"], locker_account["id"]

            if direction == "Locker ➜ Hand" and amount > locker_balance:
                st.warning(
                    f"⚠️ This is more than what's currently in the Locker "
                    f"(Rs. {locker_balance:,.0f}) — recording it anyway, but "
                    f"double check this is correct."
                )
            elif direction == "Hand ➜ Locker" and amount > hand_balance:
                st.warning(
                    f"⚠️ This is more than what's currently in Hand "
                    f"(Rs. {hand_balance:,.0f}) — recording it anyway, but "
                    f"double check this is correct."
                )

            db.transfer_cash(
                from_account_id=from_id,
                to_account_id=to_id,
                amount=amount,
                transfer_date=transfer_date.isoformat(),
                notes=notes,
            )
            st.success(f"Recorded: Rs. {amount:,.0f} moved {direction}.")
            st.rerun()

st.divider()

# ================== TRANSFER HISTORY ==================
st.subheader("📋 Recent Transfers")

view_date = st.date_input("View transfers for", value=date.today(), key="transfer_view_date")
transfers = db.get_cash_transfers_for_date(view_date.isoformat())

if not transfers:
    st.caption("No transfers recorded for this date.")
else:
    rows = []
    for t in transfers:
        from_name = next((a["name"] for a in accounts if a["id"] == t["from_account_id"]), "—")
        to_name = next((a["name"] for a in accounts if a["id"] == t["to_account_id"]), "—")
        rows.append({
            "From": from_name,
            "To": to_name,
            "Amount": t["amount"],
            "Notes": t.get("notes") or "",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.divider()

# ================== MANUAL CORRECTION ==================
with st.expander("✏️ Correct a balance after a physical cash count"):
    st.caption(
        "If the real cash on hand doesn't match what's shown above (e.g. "
        "after starting this system for the first time, or finding a "
        "mismatch), set the correct amount here. This writes one ledger "
        "entry for the difference — it never edits history, only adds "
        "an explanatory adjustment."
    )
    correct_col1, correct_col2, correct_col3 = st.columns(3)
    with correct_col1:
        account_to_fix = st.selectbox("Account", ["Cash In Hand", "Cash In Locker"])
    with correct_col2:
        current_val = hand_balance if account_to_fix == "Cash In Hand" else locker_balance
        target_balance = st.number_input(
            "Actual amount counted (Rs.)", min_value=0.0, value=float(current_val), step=100.0
        )
    with correct_col3:
        st.write("")
        st.write("")
        if st.button("Apply Correction", use_container_width=True):
            account_id = account_lookup[account_to_fix]["id"]
            db.adjust_account_balance_manually(
                account_id, target_balance, date.today().isoformat(),
                notes="Manual correction after physical count",
            )
            st.success(f"{account_to_fix} set to Rs. {target_balance:,.0f}")
            st.rerun()
