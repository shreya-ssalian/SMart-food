"""Additive reasoning: permission by category (most specific rule wins) and max levels."""
from models import Finding
from modules._base import collect

KINDS = {"additive_not_permitted", "additive_exceeds_limit"}


def check(ctx) -> list[Finding]:
    return collect(ctx, KINDS, "additive", "concern")


def report(ctx) -> list[dict]:
    kb, rows = ctx.kb, []
    eff = {r[1]: r for r in ctx.forward.query("effective_limit", ctx.pid)}
    gaps = {r[2] for r in ctx.forward.query("gap", ctx.pid, "additive_no_limit_data")}
    seen = set()
    for _, a in ctx.forward.query("additive_in", ctx.pid):
        if a in seen: continue
        seen.add(a)
        info = kb.additive_info.get(a, {})
        if a in eff:
            _, _, cat, perm, mx, src = eff[a]
            status = "not permitted" if perm == "no" else "permitted"
            lim = f"max {mx:g} mg/kg" if isinstance(mx, (int, float)) else "no numeric limit"
            basis = f"{kb.display(cat)} ({src})"
        else:
            status, lim, basis = "unverified (no data)", "-", "-"
        rows.append({"additive": kb.display(a), "id": a, "ins": info.get("ins_code", ""),
                     "function": info.get("function", ""), "status": status,
                     "limit": lim, "rule basis": basis})
    return rows
