import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client

st.title("🌤️ 彩云计 · 云南之旅分账")

# ---------- 连接 Supabase ----------
@st.cache_resource
def get_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_client()

# ---------- 读取数据函数 ----------
def load_members():
    res = supabase.table("members").select("*").order("id").execute()
    return res.data

def load_expenses():
    res = supabase.table("expenses").select("*").order("id").execute()
    return res.data

def load_repayments():
    res = supabase.table("repayments").select("*").order("id").execute()
    return res.data

# ---------- 成员管理 ----------
st.header("👥 成员管理 (Members)")

new_member = st.text_input("输入昵称，添加新成员")

members = load_members()
member_names = [m["name"] for m in members]

if st.button("添加成员 (Add Member)"):
    if new_member.strip() == "":
        st.warning("昵称不能是空的！")
    elif new_member in member_names:
        st.warning("这个昵称已经存在了！")
    else:
        supabase.table("members").insert({"name": new_member}).execute()
        st.success(f"已添加成员：{new_member}")
        st.rerun()

st.subheader("目前的成员：")
if member_names:
    for m in member_names:
        st.write(f"- {m}")
else:
    st.write("还没有添加任何成员，请先添加成员再记录支出")

st.divider()

# ---------- 支出记录 ----------
st.header("💰 记录支出 (Add Expense)")

if not member_names:
    st.info("请先添加至少一个成员，才能记录支出")
else:
    expense_name = st.text_input("项目名称 (例如：午餐)")
    category = st.selectbox("类别 (Category)", ["交通", "住宿", "餐饮", "娱乐", "其他"])
    expense_date = st.date_input("日期 (Date)", value=date.today())

    currency = st.selectbox("币种 (Currency)", ["马币 (MYR)", "人民币 (CNY)"])
    amount = st.number_input("金额 (Amount，原始币种)", min_value=0.0, step=1.0)

    if currency == "人民币 (CNY)":
        rate = st.number_input("汇率 (1 人民币 = 多少马币)", min_value=0.0, value=0.62, step=0.01)
        amount_myr = round(amount * rate, 2)
        st.caption(f"换算成马币约：{amount_myr} MYR")
    else:
        amount_myr = amount

    payer = st.selectbox("谁先垫付的？(Payer)", member_names)
    expense_type = st.radio("类型 (Type)", ["个人开销", "团体开销"])

    if expense_type == "团体开销":
        split_members = st.multiselect(
            "这笔钱由谁平摊？(Split Among)",
            member_names,
            default=member_names
        )
    else:
        split_members = [payer]

    if st.button("添加支出 (Add Expense)"):
        if expense_name.strip() == "":
            st.warning("请填写项目名称！")
        elif amount <= 0:
            st.warning("金额必须大于 0！")
        elif expense_type == "团体开销" and not split_members:
            st.warning("请至少勾选一个分摊对象！")
        else:
            supabase.table("expenses").insert({
                "item": expense_name,
                "category": category,
                "expense_date": str(expense_date),
                "currency": currency,
                "original_amount": amount,
                "amount": amount_myr,
                "payer": payer,
                "expense_type": expense_type,
                "split_members": split_members,
            }).execute()
            st.success(f"已添加：{expense_name} - {amount_myr} MYR（{payer} 垫付）")
            st.rerun()

expenses = load_expenses()

st.subheader("📋 支出记录列表")
if expenses:
    for e in expenses:
        col1, col2 = st.columns([5, 1])
        with col1:
            st.write(f"**{e['item']}** ({e['category']}, {e['expense_date']}) - {e['amount']} MYR | 付款人: {e['payer']} | 类型: {e['expense_type']} | 分摊: {', '.join(e['split_members'])}")
        with col2:
            if st.button("🗑️ 删除", key=f"delete_exp_{e['id']}"):
                supabase.table("expenses").delete().eq("id", e["id"]).execute()
                st.rerun()
else:
    st.write("还没有任何支出记录")

st.divider()

# ---------- 图表统计 ----------
st.header("📊 花费统计 (Charts)")

if expenses:
    df = pd.DataFrame(expenses)

    st.subheader("按类别统计")
    by_category = df.groupby("category")["amount"].sum()
    st.bar_chart(by_category)

    st.subheader("按日期统计")
    by_date = df.groupby("expense_date")["amount"].sum()
    st.bar_chart(by_date)
else:
    st.write("还没有支出记录，暂时无法显示图表")

st.divider()

# ---------- 结算 ----------
st.header("🧮 结算 (Settlement)")

repayments = load_repayments()

if member_names and expenses:
    should_pay = {m: 0.0 for m in member_names}
    already_paid = {m: 0.0 for m in member_names}

    for e in expenses:
        already_paid[e["payer"]] += e["amount"]
        share = e["amount"] / len(e["split_members"])
        for person in e["split_members"]:
            if person in should_pay:
                should_pay[person] += share

    balance = {m: already_paid[m] - should_pay[m] for m in member_names}

    for r in repayments:
        if r["from_person"] in balance:
            balance[r["from_person"]] += r["amount"]
        if r["to_person"] in balance:
            balance[r["to_person"]] -= r["amount"]

    balance = {m: round(b, 2) for m, b in balance.items()}

    st.subheader("每人余额（已扣除还款记录）")
    for m in member_names:
        if balance[m] > 0.01:
            st.write(f"✅ **{m}**：应收回 {balance[m]} 元")
        elif balance[m] < -0.01:
            st.write(f"❌ **{m}**：需支付 {abs(balance[m])} 元")
        else:
            st.write(f"⚖️ **{m}**：不欠不收，刚好打平")

    st.subheader("💸 具体转账建议")

    creditors = sorted([(m, b) for m, b in balance.items() if b > 0.01], key=lambda x: -x[1])
    debtors = sorted([(m, -b) for m, b in balance.items() if b < -0.01], key=lambda x: -x[1])

    transactions = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor, debt = debtors[i]
        creditor, credit = creditors[j]
        pay_amount = round(min(debt, credit), 2)

        if pay_amount > 0:
            transactions.append((debtor, creditor, pay_amount))

        debtors[i] = (debtor, debt - pay_amount)
        creditors[j] = (creditor, credit - pay_amount)

        if debtors[i][1] <= 0.01:
            i += 1
        if creditors[j][1] <= 0.01:
            j += 1

    if transactions:
        for debtor, creditor, amt in transactions:
            st.write(f"👉 {debtor} → {creditor}：{amt} 元")
    else:
        st.write("大家都打平了，不用转账！")

    st.divider()

    # ---------- 标记还款 ----------
    st.subheader("✅ 标记还款 (Mark as Paid)")

    col1, col2, col3 = st.columns(3)
    with col1:
        pay_from = st.selectbox("谁还钱 (From)", member_names, key="pay_from")
    with col2:
        pay_to = st.selectbox("还给谁 (To)", member_names, key="pay_to")
    with col3:
        pay_amount_input = st.number_input("金额", min_value=0.0, step=1.0, key="pay_amount")

    if st.button("标记为已还款"):
        if pay_from == pay_to:
            st.warning("还款人和收款人不能是同一个人！")
        elif pay_amount_input <= 0:
            st.warning("金额必须大于 0！")
        else:
            supabase.table("repayments").insert({
                "from_person": pay_from,
                "to_person": pay_to,
                "amount": pay_amount_input,
            }).execute()
            st.success(f"已记录：{pay_from} 还给 {pay_to} {pay_amount_input} 元")
            st.rerun()

    st.subheader("📜 还款记录")
    if repayments:
        for r in repayments:
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(f"{r['from_person']} → {r['to_person']}：{r['amount']} 元")
            with col2:
                if st.button("🗑️ 删除", key=f"delete_repay_{r['id']}"):
                    supabase.table("repayments").delete().eq("id", r["id"]).execute()
                    st.rerun()
    else:
        st.write("还没有还款记录")

else:
    st.info("请先添加成员和支出记录，才能计算结算")
