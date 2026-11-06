"""Reusable Streamlit components."""
from __future__ import annotations
from html import escape

import streamlit as st

VERDICT_STYLE = {
    "ALLERGY_ALERT": ("alert", "🚫 ALLERGY ALERT", True),
    "REGULATORY_CONCERN": ("alert", "⚖️ POTENTIAL REGULATORY CONCERN", True),
    "CAUTION": ("caution", "⚠️ CAUTION", True),
    "UNCERTAIN": ("caution", "❓ UNCERTAIN - INCOMPLETE INFORMATION", False),
    "NO_CONCERNS_FOUND": ("safe", "✅ NO CONCERNS FOUND", False),
    "INSUFFICIENT_DATA": ("neutral", "ℹ️ INSUFFICIENT DATA", False),
}
STATUS_BADGE = {"reportable": "🔴 reportable", "confirmed": "🟠 confirmed", "possible": "🟣 possible"}


def verdict_banner(result):
    style, label, has_spines = VERDICT_STYLE.get(
        result.verdict, ("neutral", result.verdict, False)
    )
    cactus_color = "#b5473c" if has_spines else "#347a51"
    spine_lines = """
        <path d="M39 45l-6-3m6 15l-6-3m6 15l-6-3m6 15l-6-3m6 15l-6-3
                 M61 45l6-3m-6 15l6-3m-6 15l6-3m-6 15l6-3m-6 15l6-3
                 M29 55l-5-3m5 11l-5-3m36 2l5-3m-5 11l5-3"
              fill="none" stroke="#b5473c" stroke-width="2.5" stroke-linecap="round"/>
    """ if has_spines else ""
    cactus_label = "Cactus with warning spines" if has_spines else "Healthy cactus"
    confidence = escape(str(result.confidence))
    verdict_text = escape(str(result.verdict_text))
    st.markdown(
        f"""
        <section class="verdict-banner verdict-banner--{style}" aria-label="Assessment verdict">
          <svg class="verdict-cactus" viewBox="0 0 90 120" role="img"
               aria-label="{cactus_label}" xmlns="http://www.w3.org/2000/svg">
            <path d="M45 110V30M45 67H29V50M45 82H62V64"
                  fill="none" stroke="{cactus_color}" stroke-width="15"
                  stroke-linecap="round" stroke-linejoin="round"/>
            {spine_lines}
          </svg>
          <div class="verdict-copy">
            <div class="verdict-heading">{escape(label)}</div>
            <div>{verdict_text}</div>
            <div class="verdict-confidence">Confidence in this assessment: <b>{confidence}</b></div>
          </div>
        </section>
        <style>
          .verdict-banner {{
            display: flex; align-items: center; gap: 1rem;
            padding: 1rem 1.25rem; margin: 0.75rem 0 1.25rem;
            border: 1px solid #e4dfcd; border-left: 7px solid #71806f;
            border-radius: 0.9rem; background: #fffdf7; color: #29392e;
          }}
          .verdict-banner--safe {{ border-left-color: #347a51; }}
          .verdict-banner--alert {{ border-left-color: #b5473c; }}
          .verdict-banner--caution {{ border-left-color: #a56816; }}
          .verdict-banner--neutral {{ border-left-color: #71806f; }}
          .verdict-cactus {{ flex: 0 0 3.5rem; width: 3.5rem; height: 4.5rem; }}
          .verdict-heading {{ font-size: 1.2rem; font-weight: 750; margin-bottom: 0.2rem; }}
          .verdict-confidence {{ color: #536256; font-size: 0.86rem; margin-top: 0.35rem; }}
          @media (max-width: 480px) {{
            .verdict-banner {{ gap: 0.5rem; padding: 0.75rem; }}
            .verdict-cactus {{ flex-basis: 2.8rem; width: 2.8rem; height: 3.8rem; }}
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def kb_banner(kb):
    if kb.is_demo:
        st.caption("Demo knowledge base active: illustrative data, not verified regulatory content. "
                   "Add official, versioned data to `data/knowledge_base/` to use it instead.")


def finding_card(f, explainer):
    with st.container(border=True):
        st.markdown(f"**{f.headline}**  \n{STATUS_BADGE[f.status]} · severity **{f.severity}**"
                    + (" · ✔ verified by backward chaining" if f.verified_backward else ""))
        st.write(f.explanation)
        if f.regulations:
            st.caption("Regulation(s): " + ", ".join(f.regulations))
        with st.expander("Why? (proof tree)"):
            for p in f.proofs[:3]:
                st.code(explainer.proof_text(p), language=None)
            for p in f.regulation_proofs[:1]:
                st.caption("Link to regulation:")
                st.code(explainer.proof_text(p), language=None)
