"""
db.py — single place that talks to Supabase.
Every other file imports from here instead of calling Supabase directly.
This keeps things easy to change later (e.g. swap database) without
touching every page.
"""
import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_client() -> Client:
    """
    Creates one shared Supabase connection for the whole app session.
    Reads credentials from Streamlit secrets (see .streamlit/secrets.toml).
    """
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


# ---------- CASH LEDGER ----------
# Single source of truth for all cash movement. "Cash In Hand" and
# "Cash In Locker" are never stored as raw numbers — they are always
# computed by summing this table. Every function that moves cash
# (sales, purchases, expenses, salaries, utility bills, transfers)
# writes one row here so the business stays fully auditable.

DEFAULT_CASH_ACCOUNT = "Cash In Locker"  # confirmed default holding place


def get_cash_accounts():
    client = get_client()
    return client.table("cash_accounts").select("*").order("name").execute().data


def get_cash_account_by_name(name: str):
    client = get_client()
    result = client.table("cash_accounts").select("*").eq("name", name).execute().data
    return result[0] if result else None


def add_ledger_entry(account_id: int, direction: str, amount: float,
                      source_type: str, source_id: int = None,
                      description: str = None, entry_date: str = None,
                      entered_by: str = None):
    """
    The one function that actually writes a cash movement. Every
    other "cash touches this" function in this file should call this
    instead of updating a balance directly — there is no other path
    to changing cash totals.
    """
    if amount is None or amount <= 0:
        return None  # nothing to record — keeps callers simple, no need to check first
    client = get_client()
    return client.table("cash_ledger").insert({
        "entry_date": entry_date,
        "account_id": account_id,
        "direction": direction,
        "amount": amount,
        "source_type": source_type,
        "source_id": source_id,
        "description": description,
        "entered_by": entered_by,
    }).execute()


def get_account_balance(account_id: int) -> float:
    """Sums every ledger row for one account: all 'in' minus all 'out'."""
    client = get_client()
    rows = (
        client.table("cash_ledger").select("direction, amount")
        .eq("account_id", account_id).execute().data
    )
    total = 0.0
    for r in rows:
        total += r["amount"] if r["direction"] == "in" else -r["amount"]
    return total


def get_all_account_balances():
    """Returns {account_name: balance} for every cash account — this is
    what the Cash Management page and Dashboard should display."""
    accounts = get_cash_accounts()
    return {a["name"]: get_account_balance(a["id"]) for a in accounts}


def delete_ledger_entries_for_source(source_type: str, source_id: int):
    """Removes ledger rows tied to a deleted sale/purchase/expense/etc,
    so deleting the original transaction also removes its cash trace."""
    client = get_client()
    return (
        client.table("cash_ledger").delete()
        .eq("source_type", source_type).eq("source_id", source_id).execute()
    )


def transfer_cash(from_account_id: int, to_account_id: int, amount: float,
                   transfer_date: str, notes: str = None, entered_by: str = None):
    """
    Moves cash between two accounts (e.g. Hand -> Locker). Records the
    human-readable transfer AND the two matching ledger rows (an 'out'
    from one account, an 'in' to the other) that make the balances
    actually move.
    """
    client = get_client()
    transfer = client.table("cash_transfers").insert({
        "transfer_date": transfer_date,
        "from_account_id": from_account_id,
        "to_account_id": to_account_id,
        "amount": amount,
        "notes": notes,
        "entered_by": entered_by,
    }).execute()
    transfer_id = transfer.data[0]["id"]

    add_ledger_entry(from_account_id, "out", amount, "transfer", transfer_id,
                      description=notes, entry_date=transfer_date, entered_by=entered_by)
    add_ledger_entry(to_account_id, "in", amount, "transfer", transfer_id,
                      description=notes, entry_date=transfer_date, entered_by=entered_by)
    return transfer


def get_cash_transfers_for_date(transfer_date: str):
    client = get_client()
    return (
        client.table("cash_transfers")
        .select("*")
        .eq("transfer_date", transfer_date)
        .order("created_at")
        .execute()
        .data
    )


def adjust_account_balance_manually(account_id: int, target_balance: float,
                                     adjustment_date: str, notes: str = None):
    """
    Correction tool — same pattern as set_stock() for products. Reads
    the current computed balance, then writes one ledger entry for the
    difference so the balance becomes exactly target_balance. Never
    edits a stored number directly, since there isn't one — this keeps
    the ledger as the only source of truth even for manual fixes.
    """
    current = get_account_balance(account_id)
    diff = target_balance - current
    if diff == 0:
        return None
    direction = "in" if diff > 0 else "out"
    return add_ledger_entry(
        account_id, direction, abs(diff), "manual_adjustment",
        description=notes or "Manual balance correction",
        entry_date=adjustment_date,
    )


# ---------- LOCATIONS ----------

def get_locations():
    client = get_client()
    return client.table("locations").select("*").order("name").execute().data


def get_location_by_name(name: str):
    client = get_client()
    result = client.table("locations").select("*").eq("name", name).execute().data
    return result[0] if result else None


# ---------- PRODUCTS ----------

def get_products(active_only: bool = True):
    client = get_client()
    query = client.table("products").select("*").order("name")
    if active_only:
        query = query.eq("is_active", True)
    return query.execute().data


def add_product(name: str, default_rate: float = 0):
    """
    Adds a new product, and creates a product_stock row (starting at 0)
    for every existing location, so the stock editor always has a row
    to show for this product at every location right away.
    """
    client = get_client()
    result = client.table("products").insert(
        {"name": name.strip(), "default_rate": default_rate}
    ).execute()
    product_id = result.data[0]["id"]
    locations = get_locations()
    for loc in locations:
        client.table("product_stock").insert({
            "product_id": product_id,
            "location_id": loc["id"],
            "stock_quantity": 0,
        }).execute()
    return result


def update_product_rate(product_id: int, new_rate: float):
    client = get_client()
    return client.table("products").update(
        {"default_rate": new_rate}
    ).eq("id", product_id).execute()


def get_product(product_id: int):
    client = get_client()
    return (
        client.table("products").select("*").eq("id", product_id)
        .single().execute().data
    )


# ---------- PER-LOCATION STOCK ----------
# Stock is tracked separately per (product, location) — Farm and Shop
# never share or sum their numbers. Every function below operates on
# exactly one location at a time, matching how the pages call them.

def get_product_stock(product_id: int, location_id: int):
    """One product's stock row at one location. Creates it on the fly
    (starting at 0) if it doesn't exist yet, so callers never have to
    handle a missing row as a special case."""
    client = get_client()
    result = (
        client.table("product_stock").select("*")
        .eq("product_id", product_id).eq("location_id", location_id)
        .execute().data
    )
    if result:
        return result[0]
    created = client.table("product_stock").insert({
        "product_id": product_id, "location_id": location_id, "stock_quantity": 0,
    }).execute()
    return created.data[0]


def get_stock_for_location(location_id: int):
    """Every product's stock row at one location, joined with product
    name — this is exactly what the per-location stock editor displays."""
    client = get_client()
    return (
        client.table("product_stock")
        .select("*, products(id, name)")
        .eq("location_id", location_id)
        .order("id")
        .execute()
        .data
    )


def adjust_stock(product_id: int, location_id: int, delta: float):
    """
    Changes one product's stock at one location by delta (positive to
    add, negative to remove). Reads-then-writes, fine for a small
    single-shop team; a true race condition is an edge case for later.
    """
    client = get_client()
    current = get_product_stock(product_id, location_id)
    new_qty = current["stock_quantity"] + delta
    return client.table("product_stock").update(
        {"stock_quantity": new_qty}
    ).eq("id", current["id"]).execute()


def set_stock(product_id: int, location_id: int, new_quantity: float):
    """Direct override — used by the manual stock-count correction tool,
    for one product at one specific location."""
    current = get_product_stock(product_id, location_id)
    client = get_client()
    return client.table("product_stock").update(
        {"stock_quantity": new_quantity}
    ).eq("id", current["id"]).execute()


def update_last_bag_weight(product_id: int, location_id: int, bag_weight_kg: float):
    """Remembers the most recently used bag weight for a product AT THIS
    LOCATION, so the entry form can pre-fill it next time."""
    current = get_product_stock(product_id, location_id)
    client = get_client()
    return client.table("product_stock").update(
        {"last_bag_weight_kg": bag_weight_kg}
    ).eq("id", current["id"]).execute()


def bags_equivalent(quantity: float, unit_type: str, bag_weight_kg: float) -> float:
    """
    Converts any entry into bag-count, since stock is always stored in
    bags underneath. 'bags' entries pass through unchanged. 'kg' entries
    get divided by the bag weight for that product/transaction.
    """
    if unit_type == "kg":
        if not bag_weight_kg or bag_weight_kg <= 0:
            bag_weight_kg = 50  # safe fallback, should rarely be hit
        return quantity / bag_weight_kg
    return quantity


# ---------- CUSTOMERS ----------

def get_customers(customer_type: str = None, active_only: bool = True):
    client = get_client()
    query = client.table("customers").select("*").order("name")
    if customer_type:
        query = query.eq("type", customer_type)
    if active_only:
        query = query.eq("is_active", True)
    return query.execute().data


def add_customer(name: str, customer_type: str, phone: str = None):
    client = get_client()
    return client.table("customers").insert(
        {"name": name.strip(), "type": customer_type, "phone": phone}
    ).execute()


def get_or_create_customer(name: str, customer_type: str):
    """
    Looks up a customer by name+type (case-insensitive).
    Creates them if they don't exist yet.
    This is the key trick that prevents typo'd duplicate customers
    while still letting staff type a new name on the fly.
    """
    client = get_client()
    name = name.strip()
    existing = (
        client.table("customers")
        .select("*")
        .ilike("name", name)
        .eq("type", customer_type)
        .execute()
        .data
    )
    if existing:
        return existing[0]
    result = add_customer(name, customer_type)
    return result.data[0]


# ---------- SALES ----------

def add_sale(customer_id: int, product_id: int, quantity: float,
             rate_per_bag: float, rickshaw_fare: float,
             cash_received: float, sale_date: str, location_id: int,
             entered_by: str = None, unit_type: str = "bags",
             bag_weight_kg: float = None, mix_order_id: str = None,
             transaction_group_id: str = None, rickshaw_driver_name: str = None):
    client = get_client()
    result = client.table("sales").insert({
        "customer_id": customer_id,
        "product_id": product_id,
        "quantity": quantity,
        "rate_per_bag": rate_per_bag,
        "rickshaw_fare": rickshaw_fare,
        "cash_received": cash_received,
        "sale_date": sale_date,
        "location_id": location_id,
        "entered_by": entered_by,
        "unit_type": unit_type,
        "bag_weight_kg": bag_weight_kg,
        "mix_order_id": mix_order_id,
        "transaction_group_id": transaction_group_id,
        "rickshaw_driver_name": rickshaw_driver_name.strip() if rickshaw_driver_name else None,
    }).execute()
    sale_id = result.data[0]["id"]
    # A sale takes stock OUT of the specific location it was sold from
    stock_change = bags_equivalent(quantity, unit_type, bag_weight_kg)
    adjust_stock(product_id, location_id, -stock_change)
    if unit_type == "bags" and bag_weight_kg:
        update_last_bag_weight(product_id, location_id, bag_weight_kg)
    # Cash received lands in the default account (Cash In Locker)
    if cash_received and cash_received > 0:
        locker = get_cash_account_by_name(DEFAULT_CASH_ACCOUNT)
        add_ledger_entry(locker["id"], "in", cash_received, "sale", sale_id,
                          description="Cash from sale", entry_date=sale_date,
                          entered_by=entered_by)
    return result


def get_sales_for_date(sale_date: str):
    """Returns sales joined with customer, product, and location names."""
    client = get_client()
    return (
        client.table("sales")
        .select("*, customers(name, type), products(name), locations(name)")
        .eq("sale_date", sale_date)
        .order("created_at")
        .execute()
        .data
    )


def get_sales_for_customer(customer_id: int):
    client = get_client()
    return (
        client.table("sales")
        .select("*, products(name)")
        .eq("customer_id", customer_id)
        .order("sale_date")
        .execute()
        .data
    )


def get_sales_for_date_range(start_date: str, end_date: str):
    """All sales between two dates (inclusive) in ONE query, instead of
    looping day by day and firing a separate request per day."""
    client = get_client()
    return (
        client.table("sales")
        .select("*, customers(name, type), products(name), locations(name)")
        .gte("sale_date", start_date).lte("sale_date", end_date)
        .order("sale_date")
        .execute()
        .data
    )


def get_mix_order_lines(mix_order_id: str):
    """All ingredient lines belonging to one custom-mix order, used to
    rebuild the combined bill (and re-display it later if needed)."""
    client = get_client()
    return (
        client.table("sales")
        .select("*, products(name), customers(name, type, phone)")
        .eq("mix_order_id", mix_order_id)
        .order("created_at")
        .execute()
        .data
    )


def get_transaction_group_lines(transaction_group_id: str):
    """All product lines belonging to one cart-style multi-item sale
    (one customer, several different products, billed together)."""
    client = get_client()
    return (
        client.table("sales")
        .select("*, products(name), customers(name, type, phone), locations(name)")
        .eq("transaction_group_id", transaction_group_id)
        .order("created_at")
        .execute()
        .data
    )


def delete_sale(sale_id: int):
    client = get_client()
    # Reverse the stock effect before deleting, so stock stays correct
    sale = client.table("sales").select("*").eq("id", sale_id).single().execute().data
    if sale and sale.get("location_id"):
        stock_change = bags_equivalent(
            sale["quantity"], sale.get("unit_type", "bags"), sale.get("bag_weight_kg")
        )
        adjust_stock(sale["product_id"], sale["location_id"], stock_change)  # give the stock back
    delete_ledger_entries_for_source("sale", sale_id)
    return client.table("sales").delete().eq("id", sale_id).execute()


# ---------- EXPENSES ----------

def add_expense(description: str, amount: float, expense_date: str,
                 entered_by: str = None):
    client = get_client()
    result = client.table("expenses").insert({
        "description": description.strip(),
        "amount": amount,
        "expense_date": expense_date,
        "entered_by": entered_by,
    }).execute()
    expense_id = result.data[0]["id"]
    locker = get_cash_account_by_name(DEFAULT_CASH_ACCOUNT)
    add_ledger_entry(locker["id"], "out", amount, "expense", expense_id,
                      description=description, entry_date=expense_date,
                      entered_by=entered_by)
    return result


def get_expenses_for_date(expense_date: str):
    client = get_client()
    return (
        client.table("expenses")
        .select("*")
        .eq("expense_date", expense_date)
        .order("created_at")
        .execute()
        .data
    )


def get_expenses_for_date_range(start_date: str, end_date: str):
    """All expenses between two dates (inclusive) in ONE query."""
    client = get_client()
    return (
        client.table("expenses")
        .select("*")
        .gte("expense_date", start_date).lte("expense_date", end_date)
        .order("expense_date")
        .execute()
        .data
    )


def delete_expense(expense_id: int):
    client = get_client()
    delete_ledger_entries_for_source("expense", expense_id)
    return client.table("expenses").delete().eq("id", expense_id).execute()


# ---------- SUPPLIERS ----------

def get_suppliers(active_only: bool = True):
    client = get_client()
    query = client.table("suppliers").select("*").order("name")
    if active_only:
        query = query.eq("is_active", True)
    return query.execute().data


def get_or_create_supplier(name: str):
    """Same matching trick as get_or_create_customer — case-insensitive,
    creates on first use, so typing a new supplier name just works."""
    client = get_client()
    name = name.strip()
    existing = (
        client.table("suppliers").select("*").ilike("name", name).execute().data
    )
    if existing:
        return existing[0]
    result = client.table("suppliers").insert({"name": name}).execute()
    return result.data[0]


# ---------- PURCHASES ----------

def add_purchase_from_supplier(supplier_id: int, product_id: int, quantity: float,
                                rate_per_bag: float, cash_paid: float,
                                purchase_date: str, location_id: int,
                                notes: str = None, entered_by: str = None,
                                unit_type: str = "bags", bag_weight_kg: float = None):
    """
    Normal purchase: you buy stock from a supplier and pay cash.
    Stock goes UP at the specified location. This does not touch any
    customer's balance.
    """
    client = get_client()
    result = client.table("purchases").insert({
        "purchase_date": purchase_date,
        "product_id": product_id,
        "quantity": quantity,
        "rate_per_bag": rate_per_bag,
        "supplier_id": supplier_id,
        "cash_paid": cash_paid,
        "location_id": location_id,
        "notes": notes,
        "entered_by": entered_by,
        "unit_type": unit_type,
        "bag_weight_kg": bag_weight_kg,
    }).execute()
    purchase_id = result.data[0]["id"]
    stock_change = bags_equivalent(quantity, unit_type, bag_weight_kg)
    adjust_stock(product_id, location_id, stock_change)  # stock IN
    if unit_type == "bags" and bag_weight_kg:
        update_last_bag_weight(product_id, location_id, bag_weight_kg)
    if cash_paid and cash_paid > 0:
        locker = get_cash_account_by_name(DEFAULT_CASH_ACCOUNT)
        add_ledger_entry(locker["id"], "out", cash_paid, "purchase", purchase_id,
                          description=notes or "Cash paid for purchase",
                          entry_date=purchase_date, entered_by=entered_by)
    return result


def add_purchase_settled_by_customer(customer_id: int, product_id: int,
                                      quantity: float, rate_per_bag: float,
                                      purchase_date: str, location_id: int,
                                      notes: str = None, entered_by: str = None,
                                      unit_type: str = "bags", bag_weight_kg: float = None):
    """
    Goods-as-payment: a credit customer hands you product instead of cash
    to reduce what they owe you. Stock goes UP at the chosen location, no
    cash changes hands, and the customer's outstanding balance goes DOWN
    by quantity * rate (this happens automatically wherever balance is
    calculated, since the Khata pages always recompute balance fresh
    from sales AND purchases settled by that customer).
    """
    client = get_client()
    result = client.table("purchases").insert({
        "purchase_date": purchase_date,
        "product_id": product_id,
        "quantity": quantity,
        "rate_per_bag": rate_per_bag,
        "settled_by_customer_id": customer_id,
        "cash_paid": 0,
        "location_id": location_id,
        "notes": notes,
        "entered_by": entered_by,
        "unit_type": unit_type,
        "bag_weight_kg": bag_weight_kg,
    }).execute()
    stock_change = bags_equivalent(quantity, unit_type, bag_weight_kg)
    adjust_stock(product_id, location_id, stock_change)  # stock IN
    if unit_type == "bags" and bag_weight_kg:
        update_last_bag_weight(product_id, location_id, bag_weight_kg)
    return result


def get_purchases_for_date(purchase_date: str):
    client = get_client()
    return (
        client.table("purchases")
        .select("*, products(name), suppliers(name), customers(name), locations(name)")
        .eq("purchase_date", purchase_date)
        .order("created_at")
        .execute()
        .data
    )


def get_purchases_settled_by_customer(customer_id: int):
    """All goods-as-payment purchases tied to one credit customer —
    used to correctly compute their real outstanding balance."""
    client = get_client()
    return (
        client.table("purchases")
        .select("*, products(name)")
        .eq("settled_by_customer_id", customer_id)
        .order("purchase_date")
        .execute()
        .data
    )


def delete_purchase(purchase_id: int):
    client = get_client()
    purchase = (
        client.table("purchases").select("*").eq("id", purchase_id)
        .single().execute().data
    )
    if purchase and purchase.get("location_id"):
        stock_change = bags_equivalent(
            purchase["quantity"], purchase.get("unit_type", "bags"),
            purchase.get("bag_weight_kg")
        )
        adjust_stock(purchase["product_id"], purchase["location_id"], -stock_change)  # reverse stock
    delete_ledger_entries_for_source("purchase", purchase_id)
    return client.table("purchases").delete().eq("id", purchase_id).execute()


def get_customer_balance(customer_id: int):
    """
    The REAL outstanding balance for a credit customer:
    total billed from sales, minus cash they've paid, minus the value
    of any goods they've given you to settle their debt.
    This is the single source of truth — use this everywhere instead of
    recomputing the math inline, so it can't drift between pages.
    """
    sales = get_sales_for_customer(customer_id)
    total_bill = sum(s["quantity"] * s["rate_per_bag"] + s["rickshaw_fare"] for s in sales)
    total_cash_paid = sum(s["cash_received"] for s in sales)

    goods_settlements = get_purchases_settled_by_customer(customer_id)
    total_goods_value = sum(p["quantity"] * p["rate_per_bag"] for p in goods_settlements)

    return {
        "total_bill": total_bill,
        "total_cash_paid": total_cash_paid,
        "total_goods_value": total_goods_value,
        "balance_due": total_bill - total_cash_paid - total_goods_value,
    }


def get_customer_statement(customer_id: int):
    """
    Builds one chronological list of every transaction affecting this
    customer's balance — sales (charges) and goods settlements (credits)
    interleaved by date — plus a running balance after each line.
    Keeps product/qty/rate as separate fields (not flattened into one
    description string) so the PDF can render proper itemized columns.
    """
    sales = get_sales_for_customer(customer_id)
    settlements = get_purchases_settled_by_customer(customer_id)

    lines = []
    for s in sales:
        bill = s["quantity"] * s["rate_per_bag"] + s["rickshaw_fare"]
        unit_label = "kg" if s.get("unit_type") == "kg" else "bag(s)"
        lines.append({
            "date": s["sale_date"],
            "type": "sale",
            "product": s["products"]["name"],
            "quantity": s["quantity"],
            "unit_label": unit_label,
            "rate": s["rate_per_bag"],
            "rickshaw_fare": s["rickshaw_fare"],
            "charge": bill,
            "payment": s["cash_received"],
        })
    for p in settlements:
        unit_label = "kg" if p.get("unit_type") == "kg" else "bag(s)"
        lines.append({
            "date": p["purchase_date"],
            "type": "goods_settlement",
            "product": p["products"]["name"],
            "quantity": p["quantity"],
            "unit_label": unit_label,
            "rate": p["rate_per_bag"],
            "rickshaw_fare": 0,
            "charge": 0,
            "payment": p["quantity"] * p["rate_per_bag"],
        })

    lines.sort(key=lambda l: l["date"])

    running = 0
    for line in lines:
        running += line["charge"] - line["payment"]
        line["running_balance"] = running

    return lines


# ---------- EMPLOYEES ----------

def get_employees(active_only: bool = True):
    client = get_client()
    query = client.table("employees").select("*").order("name")
    if active_only:
        query = query.eq("is_active", True)
    return query.execute().data


def add_employee(name: str, phone: str = None, designation: str = None,
                  joining_date: str = None):
    client = get_client()
    return client.table("employees").insert({
        "name": name.strip(),
        "phone": phone,
        "designation": designation,
        "joining_date": joining_date,
    }).execute()


def set_employee_active(employee_id: int, is_active: bool):
    client = get_client()
    return client.table("employees").update(
        {"is_active": is_active}
    ).eq("id", employee_id).execute()


# ---------- EMPLOYEE SALARIES ----------

def add_salary_payment(employee_id: int, amount: float, payment_date: str,
                        notes: str = None, entered_by: str = None):
    client = get_client()
    result = client.table("employee_salaries").insert({
        "employee_id": employee_id,
        "amount": amount,
        "payment_date": payment_date,
        "notes": notes,
        "entered_by": entered_by,
    }).execute()
    salary_id = result.data[0]["id"]
    locker = get_cash_account_by_name(DEFAULT_CASH_ACCOUNT)
    add_ledger_entry(locker["id"], "out", amount, "salary", salary_id,
                      description=notes or "Salary payment", entry_date=payment_date,
                      entered_by=entered_by)
    return result


def get_salary_payments_for_date(payment_date: str):
    client = get_client()
    return (
        client.table("employee_salaries")
        .select("*, employees(name)")
        .eq("payment_date", payment_date)
        .order("created_at")
        .execute()
        .data
    )


def get_salary_payments_for_employee(employee_id: int):
    client = get_client()
    return (
        client.table("employee_salaries")
        .select("*")
        .eq("employee_id", employee_id)
        .order("payment_date")
        .execute()
        .data
    )


def delete_salary_payment(salary_id: int):
    client = get_client()
    delete_ledger_entries_for_source("salary", salary_id)
    return client.table("employee_salaries").delete().eq("id", salary_id).execute()


# ---------- UTILITY BILLS ----------

UTILITY_BILL_TYPES = ["Electricity", "Gas", "Internet", "Water", "Rent", "Labour", "Other"]


def add_utility_bill(bill_type: str, amount: float, bill_date: str,
                      notes: str = None, entered_by: str = None):
    client = get_client()
    result = client.table("utility_bills").insert({
        "bill_type": bill_type,
        "amount": amount,
        "bill_date": bill_date,
        "notes": notes,
        "entered_by": entered_by,
    }).execute()
    bill_id = result.data[0]["id"]
    locker = get_cash_account_by_name(DEFAULT_CASH_ACCOUNT)
    add_ledger_entry(locker["id"], "out", amount, "utility_bill", bill_id,
                      description=f"{bill_type} bill" + (f" — {notes}" if notes else ""),
                      entry_date=bill_date, entered_by=entered_by)
    return result


def get_utility_bills_for_date(bill_date: str):
    client = get_client()
    return (
        client.table("utility_bills")
        .select("*")
        .eq("bill_date", bill_date)
        .order("created_at")
        .execute()
        .data
    )


def get_utility_bills_for_range(start_date: str, end_date: str, bill_type: str = None):
    client = get_client()
    query = (
        client.table("utility_bills").select("*")
        .gte("bill_date", start_date).lte("bill_date", end_date)
    )
    if bill_type:
        query = query.eq("bill_type", bill_type)
    return query.order("bill_date").execute().data


def delete_utility_bill(bill_id: int):
    client = get_client()
    delete_ledger_entries_for_source("utility_bill", bill_id)
    return client.table("utility_bills").delete().eq("id", bill_id).execute()
