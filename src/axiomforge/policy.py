from __future__ import annotations

from dataclasses import dataclass


CLAIM_TYPES = {"measured", "replicated", "hypothesis", "estimate", "speculation"}


@dataclass(frozen=True)
class GateResult:
    ok: bool
    reasons: tuple[str, ...]


def validate_claim_type(claim_type: str) -> GateResult:
    if claim_type in CLAIM_TYPES:
        return GateResult(True, ())
    return GateResult(False, (f"unknown claim type: {claim_type}",))


def validate_lab_note(*, title: str, claim_type: str, body: str, evidence: str) -> GateResult:
    reasons: list[str] = []
    if not title.strip():
        reasons.append("title is required")
    if not body.strip():
        reasons.append("body is required")
    if not evidence.strip():
        reasons.append("evidence path or explanation is required")
    claim = validate_claim_type(claim_type)
    reasons.extend(claim.reasons)
    if "autonomous" not in body.lower():
        reasons.append("body must disclose autonomous generation")
    if "limitation" not in body.lower():
        reasons.append("body must include limitations")
    return GateResult(not reasons, tuple(reasons))

