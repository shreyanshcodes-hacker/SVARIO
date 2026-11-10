"""Tool 3 & Phase 4D: `search_business_knowledge` — Controlled Business Knowledge Retrieval.

Requirements:
- Every query is strictly organization and business scoped via the verified `bundle`.
- Never returns information from another organization.
- Only active FAQs (`faq.is_active == True`) may be returned.
- Includes internal `SourceMetadata` provenance.
- Handles empty search results explicitly without inventing missing information.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Set
from app.agents.schemas import (
    KnowledgeMatchItem,
    SearchBusinessKnowledgeToolInput,
    SearchBusinessKnowledgeToolOutput,
    SourceMetadata,
)
from app.modules.onboarding.schemas import OnboardingBundleResponse

STOP_WORDS: Set[str] = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "what",
    "where",
    "when",
    "how",
    "do",
    "does",
    "can",
    "you",
    "your",
    "for",
    "in",
    "on",
    "at",
    "to",
    "of",
    "and",
    "or",
    "please",
    "tell",
    "me",
    "about",
    "kya",
    "hai",
    "hain",
    "ka",
    "ki",
    "ke",
    "mein",
}


def _tokenize(text: str) -> Set[str]:
    words = re.findall(r"[\w\u0900-\u097F]{2,}", text.lower())
    return {w for w in words if w not in STOP_WORDS}


def execute_search_business_knowledge(
    *,
    bundle: OnboardingBundleResponse,
    raw_arguments: Dict[str, Any],
) -> SearchBusinessKnowledgeToolOutput:
    """Search verified active FAQs and business profile/hours for the resolved business."""
    validated = SearchBusinessKnowledgeToolInput.model_validate(raw_arguments or {})
    query_text = validated.query
    query_lower = query_text.lower()
    query_tokens = _tokenize(query_text)
    category_filter = (
        validated.category.strip().lower() if validated.category else None
    )

    matches: List[KnowledgeMatchItem] = []

    # 1. Search ONLY active FAQs (`faq.is_active == True`) belonging to this organization & business
    for faq in bundle.faqs:
        if not faq.is_active:
            continue
        if (
            faq.organization_id != bundle.organization.id
            or faq.business_id != bundle.business_id
        ):
            continue
        if category_filter and faq.category.lower() != category_filter:
            continue

        combined_text = f"{faq.category} {faq.question} {faq.answer}"
        faq_tokens = _tokenize(combined_text)

        overlap = len(query_tokens.intersection(faq_tokens))
        substring_bonus = (
            0.35
            if (
                query_lower in faq.question.lower()
                or query_lower in faq.answer.lower()
            )
            else 0.0
        )

        if overlap > 0 or substring_bonus > 0:
            denom = max(1, min(len(query_tokens), 6))
            raw_score = (overlap / denom) * 0.75 + substring_bonus
            score = round(min(0.99, max(0.25, raw_score)), 2)
            matches.append(
                KnowledgeMatchItem(
                    source_type="business_faq",
                    record_id=str(faq.id),
                    category=faq.category,
                    question_or_topic=faq.question,
                    verified_answer=faq.answer,
                    relevance_score=score,
                )
            )

    # 2. Check verified business profile description/contact if relevant keywords appear
    profile = bundle.profile
    if profile.description:
        desc_tokens = _tokenize(f"{profile.display_name} {profile.description}")
        desc_overlap = len(query_tokens.intersection(desc_tokens))
        if desc_overlap > 0:
            score = round(min(0.85, 0.30 + desc_overlap * 0.18), 2)
            matches.append(
                KnowledgeMatchItem(
                    source_type="business_profile",
                    record_id=str(profile.id),
                    category="profile",
                    question_or_topic=f"Overview of {profile.display_name}",
                    verified_answer=profile.description,
                    relevance_score=score,
                )
            )

    matches.sort(key=lambda m: m.relevance_score, reverse=True)
    top_matches = matches[:5]
    top_confidence = top_matches[0].relevance_score if top_matches else 0.0

    fallback_directive = (
        None
        if top_matches
        else (
            "No verified answer matched this query in the business's active FAQs or profile. "
            "Do NOT invent or guess an answer; state clearly that this detail is not in the "
            "verified reception records and offer to escalate to human staff."
        )
    )

    return SearchBusinessKnowledgeToolOutput(
        query=query_text,
        matches=top_matches,
        total_matches=len(top_matches),
        has_verified_answer=len(top_matches) > 0,
        confidence=top_confidence,
        fallback_directive=fallback_directive,
        source_metadata=SourceMetadata(
            organization_id=bundle.organization.id,
            business_id=bundle.business_id,
            source_tables=["business_faqs", "business_profiles"],
            retrieved_at=datetime.now(timezone.utc),
        ),
    )
