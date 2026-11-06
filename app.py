"""SmartFood AI - Streamlit front-end.   Run:  streamlit run app.py"""
import datetime

import pandas as pd
import streamlit as st

import config
from analyzer import SmartFoodAnalyzer
from knowledge.kb_loader import load_kb, read_csv
from modules import additive_checker, allergen_checker, nutrition_checker
from modules.regulation_checker import regulation_details
from reports.complaint_generator import generate_pdf, generate_text
from ui import components as ui

st.set_page_config(page_title="SmartFood AI", page_icon="🌵", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --cactus-green: #347a51;
        --cactus-deep: #234b37;
        --cactus-sage: #e8efe5;
        --desert-sand: #f7f4e8;
        --alert-red: #b5473c;
        --caution-amber: #a56816;
    }
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stSidebar"] {
        color: #29392e;
    }
    [data-testid="stAppViewContainer"] { background: var(--desert-sand); }
    [data-testid="stHeader"] { background: rgba(247, 244, 232, 0.92); }
    [data-testid="stSidebar"] { background: var(--cactus-sage); }
    .stMarkdown, .stMarkdown p,
    [data-testid="stWidgetLabel"],
    [data-testid="stWidgetLabel"] p,
    [data-testid="stCaptionContainer"],
    [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"],
    [data-testid="stRadio"] label {
        color: #29392e !important;
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stMain"] h1,
    [data-testid="stMain"] h2,
    [data-testid="stMain"] h3 { color: var(--cactus-deep); }
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea,
    [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
        background-color: #fffdf7;
        color: #29392e;
        border-color: #bdcdbb;
        border-radius: 0.65rem;
    }
    [data-testid="stTextInput"] input:focus,
    [data-testid="stTextArea"] textarea:focus {
        border-color: var(--cactus-green);
        box-shadow: 0 0 0 1px var(--cactus-green);
    }
    [data-testid="stBaseButton-primary"] {
        background: var(--cactus-green);
        border-color: var(--cactus-green);
        border-radius: 0.65rem;
    }
    [data-testid="stBaseButton-primary"]:hover {
        background: var(--cactus-deep);
        border-color: var(--cactus-deep);
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        color: var(--cactus-deep);
        border-bottom-color: var(--cactus-green);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_analyzer(mode: str):
    return SmartFoodAnalyzer(load_kb(mode))


def sample_products():
    d = config.TEST_DIR if read_csv(config.TEST_DIR / "test_products.csv") else config.DEMO_TEST_DIR
    return {f"{r['test_id']} - {r['product_id']}": r for r in read_csv(d / "test_products.csv")}


# ------------------------------------------------------------------ sidebar --
with st.sidebar:
    st.title("🌵 SmartFood AI")
    st.caption("Knowledge representation · First-order logic · Forward & backward chaining. No ML/DL.")
    mode = st.radio("Knowledge base", ["auto", "demo", "real"], horizontal=True,
                    help="auto = your data/knowledge_base if filled, else the illustrative demo")
    analyzer = get_analyzer(mode)
    kb = analyzer.kb
    st.markdown(f"**Using:** `{kb.dir.relative_to(config.BASE_DIR)}`")
    ui.kb_banner(kb)
    st.metric("Facts loaded", kb.facts.count())
    st.metric("Inference rules", len(analyzer.rules))
    samples = sample_products()
    choice = st.selectbox("Load a sample product", ["(none)"] + list(samples))

sample = samples.get(choice, {}) if choice != "(none)" else {}
st.header("Food label safety assessment")

# -------------------------------------------------------------------- input --
c1, c2 = st.columns(2)
with c1:
    name = st.text_input("Product name / ID", sample.get("product_id", ""))
    cats = [""] + sorted(kb.categories)
    cur = sample.get("category_id", "")
    category = st.selectbox("Category", cats, index=cats.index(cur) if cur in cats else 0,
                            format_func=lambda c: kb.display(c) if c else "(unknown)")
    ingredients = st.text_area("Ingredients (as printed on the label)", sample.get("ingredients_text", ""), height=130)
with c2:
    nutrition = st.text_area("Nutrition information", sample.get("nutrition_text", ""), height=90,
                             help="e.g. Per 100 g: Energy 450 kcal, Sugars 20 g, Sodium 300 mg")
    claims = st.text_input("Claims on pack (comma separated)", sample.get("claims", ""),
                           help="e.g. sugar free, high fibre, no preservatives")
    allergy_opts = sorted(kb.allergens)
    default_alg = [a for a in [x.strip() for x in sample.get("allergy_profile", "").replace(",", ";").split(";")] if a in allergy_opts]
    profile = st.multiselect("Your allergy profile", allergy_opts, default=default_alg,
                             format_func=kb.display)

if st.button("Analyse", type="primary"):
    st.session_state["product"] = {"product_id": name or "product", "ingredients_text": ingredients,
                                   "category_id": category, "nutrition_text": nutrition,
                                   "claims": claims, "allergy_profile": ";".join(profile)}
    st.session_state["result"] = analyzer.analyze(st.session_state["product"])
    st.session_state["mode"] = mode

res = st.session_state.get("result")
if res is None:
    st.info("Enter a label (or load a sample) and press **Analyse**.")
    st.stop()
if st.session_state.get("mode") != mode:
    st.warning("Knowledge base changed - press Analyse again to refresh.")

ui.verdict_banner(res)
ex = analyzer.explainer
tabs = st.tabs(["Findings", "Parsed label", "Reasoning", "Ask the system", "Complaint report", "Knowledge base"])

# ----------------------------------------------------------------- findings --
with tabs[0]:
    if not res.findings:
        st.success("No findings from the rules in the knowledge base.")
    for f in res.findings:
        ui.finding_card(f, ex)
    real_gaps = [g for g in res.gaps if g.kind != "parse_note"]
    if real_gaps:
        st.subheader("Data gaps (unknown ≠ safe)")
        for g in real_gaps:
            st.markdown(f"- {g.message}")
    notes = [g.message for g in res.gaps if g.kind == "parse_note"]
    if notes:
        with st.expander("Parsing notes"):
            for n in notes: st.markdown(f"- {n}")
    ctx = res.ctx
    inv = allergen_checker.inventory(ctx)
    if inv:
        st.subheader("Allergen inventory")
        st.dataframe(pd.DataFrame([{"allergen": kb.display(a), "contains via": ", ".join(kb.display(i) for i in d["contains"]),
                                    "may contain via": ", ".join(kb.display(i) for i in d["may_contain"]),
                                    "declared on label": "yes" if d["declared"] else "NO"} for a, d in inv.items()]),
                     hide_index=True)
    rep = additive_checker.report(ctx)
    if rep:
        st.subheader("Additives")
        st.dataframe(pd.DataFrame(rep).drop(columns=["id"]), hide_index=True)
    nt = nutrition_checker.table(ctx)
    if nt:
        st.subheader("Nutrition (per 100 g / ml)")
        st.dataframe(pd.DataFrame(nt).drop(columns=["id"]), hide_index=True)

# ------------------------------------------------------------------- parsed --
with tabs[1]:
    st.dataframe(pd.DataFrame([{"#": i.position, "level": i.depth, "as written": i.raw, "interpreted as": i.display,
                                "id": i.canonical, "match": i.match, "function": i.function or "",
                                "%": i.percent or "", "mg/kg": i.quantity_mg_kg or "", "part of": i.parent or ""}
                               for i in res.label.items]), hide_index=True)
    st.write({"declared allergens": sorted(res.label.declared_allergens),
              "'may contain' advisory": sorted(res.label.advisory_allergens),
              "claims": res.claims, "category": res.category, "nutrition basis": res.nutrition.basis})

# ---------------------------------------------------------------- reasoning --
with tabs[2]:
    st.markdown(f"**Forward chaining** reached a fixpoint after {res.forward_stats['iterations']} passes, "
                f"deriving **{res.forward_stats['derived']}** new facts from "
                f"{res.forward_stats['total_facts'] - res.forward_stats['derived']} base facts. "
                "Each finding was then **re-proved by backward chaining** from the goal "
                "(✔ marks on the Findings tab).")
    if res.overrides:
        st.subheader("Rule-conflict resolution")
        for o in res.overrides:
            st.markdown(f"- {kb.display(o['additive'])}: general rule for **{kb.display(o['overridden_category'])}** "
                        f"({o['overridden_permitted']}) was overridden by the more specific rule for "
                        f"**{kb.display(o['winning_category'])}** ({o['winning_permitted']}).")
    st.subheader("Forward-chaining trace (concerns & gaps only)")
    st.dataframe(pd.DataFrame([{"step": t.step, "stratum": t.stratum, "rule": t.rule_id, "derived fact": t.fact}
                               for t in res.forward_trace if t.fact.split("(")[0] in
                               ("concern", "possible_concern", "gap", "reportable", "effective_limit")]),
                 hide_index=True)
    with st.expander("All derived facts"):
        st.dataframe(pd.DataFrame([{"step": t.step, "rule": t.rule_id, "fact": t.fact} for t in res.forward_trace]),
                     hide_index=True)
    with st.expander("Rule base"):
        for r in analyzer.rules:
            st.markdown(f"**{r.id}** - {r.description}")
        st.caption("Source: knowledge/rules.pl (standard Prolog syntax)")

# ---------------------------------------------------------------------- ask --
with tabs[3]:
    st.markdown("Query the knowledge base by **backward chaining**. Variables start with a capital letter.")
    pid = res.pid
    presets = {
        "Which allergens are present?": f"allergen_present({pid}, A, I, S)",
        "Which concerns exist?": f"concern({pid}, Kind, Subject, Detail, Source)",
        "What is reportable and under which regulation?": f"reportable({pid}, Reg, Kind, Subject)",
        "Which additives are in the product?": f"additive_in({pid}, A)",
        "Which categories does it belong to?": f"in_category({pid}, C)",
        "What data is missing?": f"gap({pid}, Kind, Subject)",
    }
    pick = st.selectbox("Example questions", list(presets))
    goal = st.text_input("Goal", presets[pick], key=f"goal_{pick}")
    if st.button("Prove"):
        try:
            sols = analyzer.ask(res, goal, 25)
            if not sols: st.error("Not provable from the knowledge base (closed-world: treated as false).")
            for s in sols:
                st.markdown(f"**✔ {ex.describe_fact(s.goal.pred, s.goal.args) or s.goal}**  `{s.goal}`")
                with st.expander("proof"):
                    st.code(ex.proof_text(s.proof), language=None)
        except Exception as e:
            st.error(f"Could not run query: {e}")

# ---------------------------------------------------------------- complaint --
with tabs[4]:
    if not res.reportable:
        st.info("No reportable regulatory concerns - nothing to file. (Advisory findings are not complaints.)")
    else:
        st.markdown(f"**{len(res.reportable)}** potential regulatory concern(s) can be put into a structured report.")
        a, b = st.columns(2)
        who = {"name": a.text_input("Your name"), "contact": a.text_input("Contact (phone/email)"),
               "brand": b.text_input("Brand / manufacturer"), "batch": b.text_input("Batch / lot number"),
               "best_before": b.text_input("Best before"), "purchase_info": a.text_input("Shop and date of purchase")}
        who = {k: v for k, v in who.items() if v}
        text = generate_text(res, analyzer, who)
        st.text_area("Draft", text, height=420)
        st.download_button("Download .txt", text, file_name=f"complaint_{res.pid}.txt")
        import tempfile, os
        tmp = os.path.join(tempfile.gettempdir(), f"complaint_{res.pid}.pdf")
        if generate_pdf(text, tmp):
            st.download_button("Download .pdf", open(tmp, "rb").read(), file_name=f"complaint_{res.pid}.pdf")
        if kb.is_demo:
            st.error("Generated from DEMO data - not suitable for submission.")

# ----------------------------------------------------------------------- KB --
with tabs[5]:
    st.subheader("Validation")
    for i in res.kb_issues:
        {"error": st.error, "warning": st.warning, "info": st.info}[i.level](i.message)
    st.subheader("Table sizes")
    st.dataframe(pd.DataFrame([{"table": t, "rows": n} for t, n in res.kb_summary["rows"].items()]),
                 hide_index=True)
    tbl = st.selectbox("Browse a table", list(kb.tables))
    st.dataframe(pd.DataFrame(kb.tables[tbl]), hide_index=True)
