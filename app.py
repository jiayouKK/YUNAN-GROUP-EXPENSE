import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client

st.title("🌤️ 彩云计 · 云南之旅の账")

@st.cache_resource
def get_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_client()

def load_members():
    res = supabase.table("members").select("*").order("id").execute()
    return res.data

def load_expenses():
    res = supabase.table("expenses").select("*").order("id").execute()
    return res.data

def load_debts():
    res = supabase.table("debts").select("*").order("id").execute()
    return res.data

def load_debt_repayments():
    res = supabase.table("debt_repayments").select("*").execute()
    return res.data

def load_prepayments():
    res = supabase.table("prepayments").select("*").order("id").execute()
    return res.data

def load_prepayment_usage():
    res = supabase.table("prepayment_usage").select("*").execute()
    return res.data

# ---------- 成员管理 ----------
st.header("👥 都有谁？ (Members)")

new_member = st.text_input("输入昵称，加人")

members = load_members()
member_names = [m["name"] for m in members]

if st.button("加人 (Add Member)"):
    if new_member.strip() == "":
        st.warning("不能空！")
    elif new_member in member_names:
        st.warning("有过了，重写！")
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
    expense_date_input = st.date_input("日期 (Date)", value=date.today())

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

    collector = None
    via_collector = []

    if expense_type == "团体开销":
        split_members = st.multiselect(
            "这笔钱由谁平摊？(Split Among)",
            member_names,
            default=member_names
        )

        has_collector = st.checkbox("是否有人需要把钱交给「代收人」，再统一转给垫付人？")

        if has_collector:
            collector_options = [m for m in member_names if m != payer]
            collector = st.selectbox("代收人是谁？", collector_options)

            via_options = [m for m in split_members if m != payer and m != collector]
            via_collector = st.multiselect(
                f"以下哪些人的钱，是交给「{collector}」的？（没勾选的人，直接还给垫付人）",
                via_options
            )
    else:
        split_members = [payer]

    if st.button("添加支出 (Add Expense)"):
        if expense_name.strip() == "":
            st.warning("花什么！")
        elif amount <= 0:
            st.warning("金额必须大于 0！")
        elif expense_type == "团体开销" and not split_members:
            st.warning("请至少勾选一个分摊对象！")
        else:
            res = supabase.table("expenses").insert({
                "item": expense_name,
                "category": category,
                "expense_date": str(expense_date_input),
                "currency": currency,
                "original_amount": amount,
                "amount": amount_myr,
                "payer": payer,
                "expense_type": expense_type,
                "split_members": split_members,
                "creditor": payer,
            }).execute()
            expense_id = res.data[0]["id"]

            if expense_type == "团体开销":
                share = round(amount_myr / len(split_members), 2)
                debt_rows = []
                collected_total = 0.0

                for person in split_members:
                    if person == payer:
                        continue
                    if collector and person in via_collector:
                        debt_rows.append({
                            "expense_id": expense_id,
                            "debtor": person,
                            "creditor": collector,
                            "amount": share,
                            "item": expense_name,
                            "category": category,
                            "expense_date": str(expense_date_input),
                        })
                        collected_total += share
                    else:
                        debt_rows.append({
                            "expense_id": expense_id,
                            "debtor": person,
                            "creditor": payer,
                            "amount": share,
                            "item": expense_name,
                            "category": category,
                            "expense_date": str(expense_date_input),
                        })

                if collector and collector in split_members:
                    collected_total += share

                if collector and collected_total > 0:
                    debt_rows.append({
                        "expense_id": expense_id,
                        "debtor": collector,
                        "creditor": payer,
                        "amount": round(collected_total, 2),
                        "item": f"{expense_name}（代收转交）",
                        "category": category,
                        "expense_date": str(expense_date_input),
                    })

                if debt_rows:
                    supabase.table("debts").insert(debt_rows).execute()

            st.success(f"已添加：{expense_name} - {amount_myr} MYR（{payer} 垫付）")
            st.rerun()

expenses = load_expenses()

st.subheader("📋 花销记录列表")
if expenses:
    for e in expenses:
        col1, col2 = st.columns([5, 1])
        with col1:
            note = f" | 最终收款: {e['creditor']}" if e.get("creditor") and e["creditor"] != e["payer"] else ""
            st.write(f"**{e['item']}** ({e['category']}, {e['expense_date']}) - {e['amount']} MYR | 付款人: {e['payer']} | 类型: {e['expense_type']} | 分摊: {', '.join(e['split_members'])}{note}")
        with col2:
            if st.button("🗑️ 删除", key=f"delete_exp_{e['id']}"):
                supabase.table("expenses").delete().eq("id", e["id"]).execute()
                st.rerun()
else:
    st.write("还没有任何花销")

st.divider()

# ---------- 图表统计 ----------
st.header("📊 花费统计 (Charts)")

if expenses:
    import plotly.express as px

    df = pd.DataFrame(expenses)

    st.subheader("按类别统计（占比）")
    by_category = df.groupby("category")["amount"].sum().reset_index()
    fig_pie = px.pie(
        by_category, names="category", values="amount",
        hole=0.4,
    )
    fig_pie.update_traces(textinfo="label+percent")
    st.plotly_chart(fig_pie, use_container_width=True)

    st.subheader("按日期统计（趋势）")
    by_date = df.groupby("expense_date")["amount"].sum().reset_index()
    fig_bar = px.bar(
        by_date, x="expense_date", y="amount",
        labels={"expense_date": "日期", "amount": "花费 (MYR)"},
        text_auto=True,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("按每人开销统计")

    person_rows = []
    for e in expenses:
        n = len(e["split_members"])
        share = round(e["amount"] / n, 2) if n > 0 else 0
        for person in e["split_members"]:
            person_rows.append({
                "person": person,
                "category": e["category"],
                "amount": share,
            })

    df_person = pd.DataFrame(person_rows)

    fig_person = px.bar(
        df_person.groupby(["person", "category"])["amount"].sum().reset_index(),
        x="person", y="amount", color="category",
        labels={"person": "成员", "amount": "花费 (MYR)", "category": "类别"},
        text_auto=True,
    )
    st.plotly_chart(fig_person, use_container_width=True)
else:
    st.write("还没有支出记录，暂时无法显示图表")

st.divider()

# ---------- 预付款管理 ----------
st.header("🎒 预付款管理 (Prepayments)")

if not member_names:
    st.info("请先添加成员，才能登记预付款")
else:
    st.subheader("➕ 登记新预付")
    col1, col2, col3 = st.columns(3)
    with col1:
        pre_from = st.selectbox("谁预付？(From)", member_names, key="pre_from")
    with col2:
        pre_to = st.selectbox("交给谁保管？(To)", member_names, key="pre_to")
    with col3:
        pre_amount = st.number_input("预付金额", min_value=0.0, step=1.0, key="pre_amount")
    pre_note = st.text_input("备注（可选）", key="pre_note")

    if st.button("登记预付款"):
        if pre_from == pre_to:
            st.warning("预付人和保管人不能是同一个人！")
        elif pre_amount <= 0:
            st.warning("金额必须大于 0！")
        else:
            supabase.table("prepayments").insert({
                "from_person": pre_from,
                "to_person": pre_to,
                "amount": pre_amount,
                "prepay_date": str(date.today()),
                "note": pre_note,
            }).execute()
            st.success(f"已登记：{pre_from} 预付 {pre_amount} 元给 {pre_to}")
            st.rerun()

    st.subheader("📜 预付款列表")
    prepayments = load_prepayments()
    usage_records = load_prepayment_usage()

    used_by_prepay = {}
    for u in usage_records:
        used_by_prepay[u["prepayment_id"]] = used_by_prepay.get(u["prepayment_id"], 0) + u["amount"]

    if prepayments:
        for p in prepayments:
            used = used_by_prepay.get(p["id"], 0)
            remaining_amt = round(p["amount"] - used, 2)
            note_str = f"（{p['note']}）" if p.get("note") else ""

            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(f"**{p['from_person']} → {p['to_person']}**：预付 {p['amount']} 元{note_str} | 已用 {used} | 剩余 **{remaining_amt}**")
            with col2:
                if st.button("🗑️ 删除整笔", key=f"delete_prepay_{p['id']}"):
                    supabase.table("prepayment_usage").delete().eq("prepayment_id", p["id"]).execute()
                    supabase.table("prepayments").delete().eq("id", p["id"]).execute()
                    st.rerun()

            with st.expander(f"查看/使用这笔预付款（剩余 {remaining_amt}）"):
                use_list = [u for u in usage_records if u["prepayment_id"] == p["id"]]
                if use_list:
                    for u in use_list:
                        ucol1, ucol2 = st.columns([4, 1])
                        with ucol1:
                            st.write(f"- 用了 {u['amount']} 元，{u['usage_date']}，备注：{u.get('note', '')}")
                        with ucol2:
                            if st.button("🗑️", key=f"delete_usage_{u['id']}"):
                                supabase.table("prepayment_usage").delete().eq("id", u["id"]).execute()
                                st.rerun()

                if remaining_amt > 0.01:
                    use_amount = st.number_input(
                        "本次使用/扣除金额", min_value=0.0, max_value=float(remaining_amt),
                        step=1.0, key=f"use_amt_{p['id']}"
                    )
                    use_note = st.text_input("用途备注（例如：车票）", key=f"use_note_{p['id']}")
                    if st.button("确认扣除", key=f"use_btn_{p['id']}"):
                        if use_amount <= 0:
                            st.warning("金额必须大于 0！")
                        else:
                            supabase.table("prepayment_usage").insert({
                                "prepayment_id": p["id"],
                                "amount": use_amount,
                                "usage_date": str(date.today()),
                                "note": use_note,
                            }).execute()
                            st.success(f"已扣除 {use_amount} 元")
                            st.rerun()

                    if st.button("剩余全部退还给预付人", key=f"refund_btn_{p['id']}"):
                        supabase.table("prepayment_usage").insert({
                            "prepayment_id": p["id"],
                            "amount": remaining_amt,
                            "usage_date": str(date.today()),
                            "note": "退还",
                        }).execute()
                        st.success(f"已退还 {remaining_amt} 元")
                        st.rerun()
                else:
                    st.write("✅ 这笔预付款已用完/已退还")
    else:
        st.write("还没有任何预付款记录")

st.divider()

# ---------- 债务明细与结算 ----------
st.header("🧮 债务明细与结算 (Debts & Settlement)")

debts = load_debts()
debt_repayments = load_debt_repayments()

paid_by_debt = {}
for r in debt_repayments:
    paid_by_debt[r["debt_id"]] = paid_by_debt.get(r["debt_id"], 0) + r["amount"]

def remaining(d):
    return round(d["amount"] - paid_by_debt.get(d["id"], 0), 2)

if member_names and debts:
    st.subheader("📜 每笔债务明细")
    for d in debts:
        rem = remaining(d)
        paid = paid_by_debt.get(d["id"], 0)
        if rem <= 0.01:
            status = "✅ 已还清"
        elif paid > 0:
            status = f"🟡 已还 {paid}，剩 {rem}"
        else:
            status = f"❌ 未还 {rem}"
        st.write(f"{d['debtor']} 欠 {d['creditor']} — {d['item']} ({d['category']}, {d['expense_date']}) 共 {d['amount']} 元 | {status}")

        this_debt_repayments = [r for r in debt_repayments if r["debt_id"] == d["id"]]
        if this_debt_repayments:
            with st.expander(f"查看/管理这笔的还款记录（{len(this_debt_repayments)} 笔）"):
                for r in this_debt_repayments:
                    rcol1, rcol2 = st.columns([4, 1])
                    with rcol1:
                        st.write(f"- {r['repay_date']}：还了 {r['amount']} 元")
                    with rcol2:
                        if st.button("🗑️ 删除", key=f"delete_repay_{r['id']}"):
                            supabase.table("debt_repayments").delete().eq("id", r["id"]).execute()
                            st.rerun()

    st.subheader("📊 还款进度（按类别）")
    df_debts = pd.DataFrame(debts)
    df_debts["paid"] = df_debts["id"].map(lambda i: paid_by_debt.get(i, 0))
    df_debts["remaining"] = df_debts["amount"] - df_debts["paid"]
    st.bar_chart(df_debts.groupby("category")[["paid", "remaining"]].sum())

    st.subheader("💰 净余额总览")
    net_balance = {m: 0.0 for m in member_names}
    for d in debts:
        rem = remaining(d)
        if d["debtor"] in net_balance:
            net_balance[d["debtor"]] -= rem
        if d["creditor"] in net_balance:
            net_balance[d["creditor"]] += rem

    for m in member_names:
        b = round(net_balance[m], 2)
        if b > 0.01:
            st.write(f"✅ **{m}**：应收回 {b} 元")
        elif b < -0.01:
            st.write(f"❌ **{m}**：还需支付 {abs(b)} 元")
        else:
            st.write(f"⚖️ **{m}**：没有欠款！")

    st.divider()

    st.subheader("✅ 标记还款 (Mark Repayment)")

    col1, col2 = st.columns(2)
    with col1:
        sel_debtor = st.selectbox("谁还钱 (欠款人)", member_names, key="sel_debtor")
    with col2:
        sel_creditor = st.selectbox("还给谁 (收款人)", member_names, key="sel_creditor")

    relevant_debts = [d for d in debts if d["debtor"] == sel_debtor and d["creditor"] == sel_creditor and remaining(d) > 0.01]

    if relevant_debts:
        options = {f"{d['item']} ({d['category']}, {d['expense_date']}) - 剩 {remaining(d)} 元": d for d in relevant_debts}
        chosen_label = st.selectbox("选择要还的债务", list(options.keys()))
        chosen_debt = options[chosen_label]

        repay_amount = st.number_input(
            "本次还款金额", min_value=0.0, max_value=float(remaining(chosen_debt)),
            step=1.0, value=float(remaining(chosen_debt))
        )

        if st.button("确认还款"):
            if repay_amount <= 0:
                st.warning("金额必须大于 0！")
            else:
                supabase.table("debt_repayments").insert({
                    "debt_id": chosen_debt["id"],
                    "amount": repay_amount,
                    "repay_date": str(date.today()),
                }).execute()
                st.success(f"已记录：{sel_debtor} 还给 {sel_creditor} {repay_amount} 元（{chosen_debt['item']}）")
                st.rerun()
    else:
        st.info(f"{sel_debtor} 目前没有欠 {sel_creditor} 钱！")
else:
    st.info("请先添加成员和团体支出，才能查看债务与结算")
