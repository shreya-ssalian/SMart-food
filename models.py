"""Shared data structures."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Finding:
    kind: str
    subject: str
    details: list = field(default_factory=list)      # e.g. ingredients responsible
    sources: list = field(default_factory=list)
    severity: str = "low"
    confirmed: bool = True                            # False => "possible" (needs verification)
    reportable: bool = False
    regulations: list = field(default_factory=list)   # regulation ids
    headline: str = ""
    explanation: str = ""
    proofs: list = field(default_factory=list)        # backward-chaining ProofNodes
    forward_proofs: list = field(default_factory=list)
    verified_backward: bool = False
    regulation_proofs: list = field(default_factory=list)
    module: str = ""

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.subject}"

    @property
    def status(self) -> str:
        if self.reportable and self.confirmed: return "reportable"
        return "confirmed" if self.confirmed else "possible"


@dataclass
class Gap:
    kind: str
    subject: str
    message: str
    impact: str = "medium"        # high | medium | low


@dataclass
class AnalysisContext:
    kb: Any
    product: dict
    pid: str
    label: Any                    # ParsedLabel
    nutrition: Any                # NutritionParse
    claims: list
    allergy_profile: list
    category: Optional[str]
    forward: Any
    backward: Any
    notes: list = field(default_factory=list)


@dataclass
class AnalysisResult:
    product: dict
    pid: str
    verdict: str
    verdict_text: str
    findings: list
    gaps: list
    confidence: str
    label: Any
    nutrition: Any
    claims: list
    allergy_profile: list
    category: Optional[str]
    forward_trace: list
    forward_stats: dict
    overrides: list
    kb_summary: dict
    kb_issues: list
    ctx: Any = None

    def by_status(self, status: str):
        return [f for f in self.findings if f.status == status]

    @property
    def reportable(self):
        return [f for f in self.findings if f.reportable and f.confirmed]
