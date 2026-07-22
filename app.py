%%writefile app.py
import streamlit as st
import json
import os
import pandas as pd
from datetime import date

st.title("🌤️ 彩云计 · 云南之旅分账")

SAVE_PATH = "/content/drive/MyDrive/travel_expense_data.json"

def load_data():
    if os.path.exists(SAVE_PATH):
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"members": [], "expenses": [], "repayments": []}

def save_data():
    data = {
        "members": st.session_state.members,
        "expenses": st.session_state.expenses,
        "repayments": st.session_state.repayments,
    }
    with open(SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if "members" not in st.session_state:
    loaded = load_data()
    st.session_state.members = loaded["members"]
    st.session_state.expenses = loaded["expenses"]
    st.session_state.repayments = loaded.get("repayments", [])

# ---------- 成员管理 ----------
st.header("👥 成员管理 (Members)")

new_member = st.text_input("输入昵称，添加新成员")

if st.button("添加成员 (Add Member)"):
    if new_member.strip() == "":
        st.warning("昵称不能是空的！")
    elif new_member in st.session_state.members:
        st.warning("这个昵称已经存在了！")
    else:
        st.session_state.members.append(new_member)
        save_data()
        st.success(f"已添加成员：{new_member}")

st.subheader("目前的成员：")
if st.session_state.members:
    for m in st.session_state.members:
        st.write(f"- {m}")
else:
    st.write("还没有添加任何成员，请先添加成员再记录支出")

st.divider()

# ---------- 支出记录 ----------
st.header("💰 记录支出 (Add Expense)")

if not st.session_state.members:
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

    payer = st.selectbox("谁先垫付的？(Payer)", st.session_state.members)
    expense_type = st.radio("类型 (Type)", ["个人开销", "团体开销"])

    if expense_type == "团体开销":
        split_members = st.multiselect(
            "这笔钱由谁平摊？(Split Among)",
            st.session_state.members,
            default=st.session_state.members
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
            st.session_state.expenses.append({
                "项目": expense_name,
                "类别": category,
                "日期": str(expense_date),
                "币种": currency,
                "原始金额": amount,
                "金额": amount_myr,  # 统一用马币计算
                "付款人": payer,
                "类型": expense_type,
                "分摊对象": split_members,
            })
            save_data()
            st.success(f"已添加：{expense_name} - {amount_myr} MYR（{payer} 垫付）")

st.subheader("📋 支出记录列表")
if st.session_state.expenses:
    for i, e in enumerate(st.session_state.expenses):
        col1, col2 = st.columns([5, 1])
        with col1:
            st.write(f"{i+1}. **{e['项目']}** ({e['类别']}, {e['日期']}) - {e['金额']} MYR | 付款人: {e['付款人']} | 类型: {e['类型']} | 分摊: {', '.join(e['分摊对象'])}")
        with col2:
            if st.button("🗑️ 删除", key=f"delete_{i}"):
                st.session_state.expenses.pop(i)
                save_data()
                st.rerun()
else:
    st.write("还没有任何支出记录")

st.divider()

# ---------- 图表统计 ----------
st.header("📊 花费统计 (Charts)")

if st.session_state.expenses:
    df = pd.DataFrame(st.session_state.expenses)

    st.subheader("按类别统计")
    by_category = df.groupby("类别")["金额"].sum()
    st.bar_chart(by_category)

    st.subheader("按日期统计")
    by_date = df.groupby("日期")["金额"].sum()
    st.bar_chart(by_date)
else:
    st.write("还没有支出记录，暂时无法显示图表")

st.divider()

# ---------- 结算 ----------
st.header("🧮 结算 (Settlement)")

if st.session_state.members and st.session_state.expenses:
    should_pay = {m: 0.0 for m in st.session_state.members}
    already_paid = {m: 0.0 for m in st.session_state.members}

    for e in st.session_state.expenses:
        already_paid[e["付款人"]] += e["金额"]
        share = e["金额"] / len(e["分摊对象"])
        for person in e["分摊对象"]:
            should_pay[person] += share

    balance = {m: already_paid[m] - should_pay[m] for m in st.session_state.members}

    # 扣除已还款的部分
    for r in st.session_state.repayments:
        balance[r["from"]] += r["amount"]
        balance[r["to"]] -= r["amount"]

    balance = {m: round(b, 2) for m, b in balance.items()}

    st.subheader("每人余额（已扣除还款记录）")
    for m in st.session_state.members:
        if balance[m] > 0.01:
            st.write(f"✅ **{m}**：应收回 {balance[m]} 元")
        elif balance[m] < -0.01:
            st.write(f"❌ **{m}**：需支付 {abs(balance[m])} 元")
        else:
            st.write(f"⚖️ **{m}**：不欠不收，刚好打平")

    st.subheader("💸 具体转账建议")

    creditors = [(m, b) for m, b in balance.items() if b > 0.01]
    debtors = [(m, -b) for m, b in balance.items() if b < -0.01]

    transactions = []
    i, j = 0, 0
    creditors = sorted(creditors, key=lambda x: -x[1])
    debtors = sorted(debtors, key=lambda x: -x[1])

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
        pay_from = st.selectbox("谁还钱 (From)", st.session_state.members, key="pay_from")
    with col2:
        pay_to = st.selectbox("还给谁 (To)", st.session_state.members, key="pay_to")
    with col3:
        pay_amount_input = st.number_input("金额", min_value=0.0, step=1.0, key="pay_amount")

    if st.button("标记为已还款"):
        if pay_from == pay_to:
            st.warning("还款人和收款人不能是同一个人！")
        elif pay_amount_input <= 0:
            st.warning("金额必须大于 0！")
        else:
            st.session_state.repayments.append({
                "from": pay_from,
                "to": pay_to,
                "amount": pay_amount_input,
            })
            save_data()
            st.success(f"已记录：{pay_from} 还给 {pay_to} {pay_amount_input} 元")
            st.rerun()

    st.subheader("📜 还款记录")
    if st.session_state.repayments:
        for i, r in enumerate(st.session_state.repayments):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(f"{i+1}. {r['from']} → {r['to']}：{r['amount']} 元")
            with col2:
                if st.button("🗑️ 删除", key=f"delete_repay_{i}"):
                    st.session_state.repayments.pop(i)
                    save_data()
                    st.rerun()
    else:
        st.write("还没有还款记录")

else:
    st.info("请先添加成员和支出记录，才能计算结算")
