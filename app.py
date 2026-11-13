"""CreatorRights prototype UI. Run: streamlit run app.py"""
import hashlib
from datetime import date
import pandas as pd
import streamlit as st
import rules

st.set_page_config(page_title="CreatorRights", page_icon="©", layout="wide")
c = rules.connect()
st.title("CreatorRights")
st.caption("Content rights register and campaign clearance. Synthetic demo data. Nothing is 'verified' until a person confirms it.")
t1, t2, t3, t4, t5 = st.tabs(["Clearance check", "Asset register", "Expiry alerts", "Contract reader", "Audit log"])

with t1:
    assets = pd.read_sql("SELECT asset_id, name FROM assets ORDER BY asset_id", c)
    label = dict(zip(assets.asset_id, assets.asset_id + "  " + assets.name))
    a, b, d, e = st.columns(4)
    aid = a.selectbox("Asset", list(label), format_func=label.get)
    plat = b.selectbox("Platform", rules.PLATFORMS)
    reg = d.selectbox("Region", list(rules.REGIONS), format_func=lambda k: f"{k} ({rules.REGIONS[k]})")
    when = e.date_input("Use date", date.today())
    comm = st.checkbox("Commercial use (paid ad, brand campaign)", value=True)
    if st.button("Check clearance", type="primary"):
        status, why = rules.check_use(c, aid, plat, reg, when.isoformat(), comm)
        show = {"GREEN": st.success, "AMBER": st.warning, "RED": st.error, "UNVERIFIED": st.info}[status]
        show(f"**{status}**: {label[aid]} on {plat}, {reg}, {when}")
        for r in why:
            st.write("- " + r)
        st.caption("Result saved to the audit log.")

with t2:
    st.dataframe(pd.read_sql("SELECT * FROM assets ORDER BY asset_id", c), use_container_width=True, hide_index=True)

with t3:
    q = f"""SELECT asset_id, name, supplier, end_date, CAST(julianday(end_date)-julianday('now') AS INT) AS days_left
            FROM assets WHERE end_date <= date('now','+{rules.WARN_DAYS} day') ORDER BY end_date"""
    df = pd.read_sql(q, c)
    st.metric(f"Expired or expiring within {rules.WARN_DAYS} days", len(df))
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("In the full build, n8n sends these as reminders to the asset owner.")

with t4:
    st.write("Paste a contract. The AI reader proposes terms with the quoted clause; a person edits and confirms before they enter the register.")
    sample = ("Licence Agreement. BeatLib grants a non-exclusive licence to use the track 'Diwali Beat' on Instagram and "
              "YouTube in India and the UAE from 2026-10-01 to 2027-03-31. Commercial use is permitted. "
              "The track may not be modified or remixed.")
    text = st.text_area("Contract text", sample, height=140)
    up = st.file_uploader("Evidence file (optional, hashed with SHA-256)")
    if st.button("Extract terms"):
        st.session_state["ext"] = rules.extract_terms(text)
        st.session_state["ext"]["_id"] = abs(hash(text))
    ext = st.session_state.get("ext")
    if ext:
        st.caption("Method: " + ext["method"])
        k = ext["_id"]
        name = st.text_input("Asset name", "Diwali Beat track", key=f"n{k}")
        sup = st.text_input("Supplier", "BeatLib", key=f"s{k}")
        c1, c2, c3, c4 = st.columns(4)
        plats = c1.text_input("Platforms", ext["platforms"], key=f"p{k}")
        regs = c2.text_input("Regions", ext["regions"], key=f"r{k}")
        sd = c3.text_input("Start date", ext["start_date"], key=f"a{k}")
        ed = c4.text_input("End date", ext["end_date"], key=f"b{k}")
        cm = st.checkbox("Commercial use allowed", bool(ext["commercial_ok"]), key=f"c{k}")
        md = st.checkbox("Edits / remixes allowed", bool(ext["modification_ok"]), key=f"m{k}")
        ai = st.checkbox("AI-generated", bool(ext["ai_generated"]), key=f"i{k}")
        with st.expander("Quoted clauses (evidence for the reviewer)"):
            for key, clause in ext["clauses"].items():
                st.write(f"**{key}:** {clause or '(not found)'}")
        if st.button("Confirm and add to register"):
            h = hashlib.sha256(up.getvalue()).hexdigest() if up else ""
            new = rules.add_asset(c, dict(name=name, asset_type="Other", supplier=sup, licence_type="From contract",
                                          platforms=plats, regions=regs, start_date=sd, end_date=ed,
                                          commercial_ok=int(cm), modification_ok=int(md), ai_generated=int(ai),
                                          evidence_url=up.name if up else "pasted contract", evidence_hash=h, verified=1))
            st.success(f"Added {new}. Try it in the Clearance check tab.")

with t5:
    st.dataframe(pd.read_sql("SELECT * FROM usage_log ORDER BY id DESC", c), use_container_width=True, hide_index=True)
