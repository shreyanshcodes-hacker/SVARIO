"""Phase 4G — Controlled Agent Orchestrator & Tool Execution Pipeline.

Orchestration Flow:
1. Receive user conversation input (or Realtime tool invocation).
2. Resolve session and business context (`(organization_id, business_id, session_id)`).
3. Identify intent (`IntentClassifier`).
4. Determine whether a tool is needed.
5. Validate the tool request (schema, tenant isolation, per-turn limit, rate limit).
6. Execute through FastAPI with timeout protection.
7. Return structured tool result.
8. Generate natural-language response in `en`, `hi`, or `hinglish`.
9. Maintain session-scoped conversation context.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional
from uuid import UUID
from fastapi import HTTPException, status
from pydantic import ValidationError
from app.core.auth import AuthenticatedUser
from app.agents.context import (
    ConversationContextManager,
    get_conversation_context_manager,
)
from app.agents.industries import get_industry_agent
from app.agents.intent import IntentClassifier
from app.agents.schemas import (
    AgentIntent,
    AgentToolName,
    AgentTurnResponse,
    EscalationUrgency,
    ExecutedToolCallSummary,
    IntentClassificationResult,
    SafetyFlag,
    VoiceToolExecutionResponse,
)
from app.agents.tools import (
    execute_cancel_clinic_appointment,
    execute_cancel_salon_appointment,
    execute_check_clinic_availability,
    execute_check_salon_availability,
    execute_create_clinic_appointment,
    execute_create_salon_appointment,
    execute_get_business_hours,
    execute_get_business_profile,
    execute_get_clinic_consultation_types,
    execute_get_clinic_departments,
    execute_get_clinic_doctors,
    execute_get_clinic_information,
    execute_get_clinic_specialities,
    execute_get_salon_services,
    execute_get_salon_staff,
    execute_request_clinic_human_escalation,
    execute_request_human_escalation,
    execute_reschedule_clinic_appointment,
    execute_reschedule_salon_appointment,
    execute_save_conversation_summary,
    execute_search_business_knowledge,
)
from app.modules.clinics.service import ClinicWorkflowService, get_clinic_workflow_service
from app.modules.onboarding.schemas import LanguageCode, OnboardingBundleResponse
from app.modules.organizations.schemas import OrganizationIndustry
from app.modules.salons.service import (
    SalonWorkflowService,
    build_salon_workflow_service,
)
from app.modules.voice.rate_limit import VoiceSessionRateLimiter, get_voice_rate_limiter

WEEKDAY_NAMES = {
    0: "Sunday",
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
}

ModelResponseGeneratorCallable = Callable[
    [OnboardingBundleResponse, IntentClassificationResult, List[ExecutedToolCallSummary]],
    Coroutine[Any, Any, str],
]


logger = logging.getLogger("svario.voice.tools")

_PII_ARGUMENT_KEYS = {
    "customer_name",
    "customer_phone",
    "customer_email",
    "patient_display_name",
    "patient_contact",
    "patient_contact_verification",
    "notes",
}


def _sanitize_arguments_for_log(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Return a privacy-safe copy of tool arguments for structured observability logs."""
    safe: Dict[str, Any] = {}
    for key, val in (arguments or {}).items():
        if key in _PII_ARGUMENT_KEYS:
            safe[key] = "[REDACTED]"
        else:
            safe[key] = val
    return safe


class AgentOrchestrator:
    """Controlled Stage 4 conversational orchestrator and tool execution engine."""

    def __init__(
        self,
        *,
        context_manager: Optional[ConversationContextManager] = None,
        intent_classifier: Optional[IntentClassifier] = None,
        rate_limiter: Optional[VoiceSessionRateLimiter] = None,
        max_tool_calls_per_turn: int = 3,
        tool_timeout_seconds: float = 5.0,
        response_timeout_seconds: float = 8.0,
        persist_summaries_enabled: bool = True,
        model_response_generator: Optional[ModelResponseGeneratorCallable] = None,
        salon_service: Optional[SalonWorkflowService] = None,
        clinic_service: Optional[ClinicWorkflowService] = None,
    ) -> None:
        self._context_manager = context_manager or get_conversation_context_manager()
        self._intent_classifier = intent_classifier or IntentClassifier()
        self._rate_limiter = rate_limiter or get_voice_rate_limiter()
        self._max_tool_calls_per_turn = max_tool_calls_per_turn
        self._tool_timeout_seconds = tool_timeout_seconds
        self._response_timeout_seconds = response_timeout_seconds
        self._persist_summaries_enabled = persist_summaries_enabled
        self._model_response_generator = model_response_generator
        self._salon_service = salon_service or build_salon_workflow_service()
        self._clinic_service = clinic_service or get_clinic_workflow_service()

    @property
    def context_manager(self) -> ConversationContextManager:
        """Return the context manager bound to this orchestrator."""
        return self._context_manager

    @property
    def salon_service(self) -> SalonWorkflowService:
        """Return the salon workflow service bound to this orchestrator."""
        return self._salon_service

    @property
    def clinic_service(self) -> ClinicWorkflowService:
        """Return the clinic workflow service bound to this orchestrator."""
        return self._clinic_service

    def _dispatch_tool_sync(
        self,
        *,
        tool_name: AgentToolName,
        bundle: OnboardingBundleResponse,
        session_id: str,
        arguments: Dict[str, Any],
        actor: Optional[AuthenticatedUser] = None,
        actor_user_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Validate arguments and execute the specified tool synchronously."""
        # Security check: reject any attempt by the model to supply organization_id or business_id
        forbidden_identity_keys = {"organization_id", "business_id", "tenant_id"}
        if forbidden_identity_keys.intersection((arguments or {}).keys()):
            raise ValueError(
                "Tool arguments must not override backend-resolved organization_id or business_id."
            )

        if tool_name == AgentToolName.GET_BUSINESS_PROFILE:
            res = execute_get_business_profile(
                bundle=bundle, raw_arguments=arguments
            )
            return res.model_dump(mode="json")

        if tool_name == AgentToolName.GET_BUSINESS_HOURS:
            res = execute_get_business_hours(
                bundle=bundle, raw_arguments=arguments
            )
            return res.model_dump(mode="json")

        if tool_name == AgentToolName.SEARCH_BUSINESS_KNOWLEDGE:
            res = execute_search_business_knowledge(
                bundle=bundle, raw_arguments=arguments
            )
            return res.model_dump(mode="json")

        if tool_name == AgentToolName.SAVE_CONVERSATION_SUMMARY:
            res = execute_save_conversation_summary(
                bundle=bundle,
                session_id=session_id,
                raw_arguments=arguments,
                context_manager=self._context_manager,
                actor_user_id=actor_user_id,
                persist_enabled=self._persist_summaries_enabled,
            )
            return res.model_dump(mode="json")

        if tool_name == AgentToolName.REQUEST_HUMAN_ESCALATION:
            res = execute_request_human_escalation(
                bundle=bundle,
                session_id=session_id,
                raw_arguments=arguments,
                context_manager=self._context_manager,
                actor_user_id=actor_user_id,
            )
            return res.model_dump(mode="json")

        # Stage 5 Salon Workflow Tools
        if tool_name == AgentToolName.GET_SALON_SERVICES:
            salon_res = execute_get_salon_services(
                bundle=bundle,
                raw_arguments=arguments,
                salon_service=self._salon_service,
                actor=actor,
                actor_user_id=actor_user_id,
            )
            return salon_res.model_dump(mode="json")

        if tool_name == AgentToolName.GET_SALON_STAFF:
            salon_res = execute_get_salon_staff(
                bundle=bundle,
                raw_arguments=arguments,
                salon_service=self._salon_service,
                actor=actor,
                actor_user_id=actor_user_id,
            )
            return salon_res.model_dump(mode="json")

        if tool_name == AgentToolName.CHECK_SALON_AVAILABILITY:
            salon_res = execute_check_salon_availability(
                bundle=bundle,
                raw_arguments=arguments,
                salon_service=self._salon_service,
                actor=actor,
                actor_user_id=actor_user_id,
            )
            return salon_res.model_dump(mode="json")

        if tool_name == AgentToolName.CREATE_SALON_APPOINTMENT:
            salon_res = execute_create_salon_appointment(
                bundle=bundle,
                raw_arguments=arguments,
                salon_service=self._salon_service,
                actor=actor,
                actor_user_id=actor_user_id,
            )
            return salon_res.model_dump(mode="json")

        if tool_name == AgentToolName.RESCHEDULE_SALON_APPOINTMENT:
            salon_res = execute_reschedule_salon_appointment(
                bundle=bundle,
                raw_arguments=arguments,
                salon_service=self._salon_service,
                actor=actor,
                actor_user_id=actor_user_id,
            )
            return salon_res.model_dump(mode="json")

        if tool_name == AgentToolName.CANCEL_SALON_APPOINTMENT:
            salon_res = execute_cancel_salon_appointment(
                bundle=bundle,
                raw_arguments=arguments,
                salon_service=self._salon_service,
                actor=actor,
                actor_user_id=actor_user_id,
            )
            return salon_res.model_dump(mode="json")

        # Stage 6 Clinic Workflow Tools
        if tool_name == AgentToolName.GET_CLINIC_INFORMATION:
            clinic_res = execute_get_clinic_information(
                bundle=bundle,
                raw_arguments=arguments,
            )
            return clinic_res.model_dump(mode="json")

        if tool_name == AgentToolName.GET_CLINIC_DEPARTMENTS:
            clinic_res = execute_get_clinic_departments(
                bundle=bundle,
                raw_arguments=arguments,
                clinic_service=self._clinic_service,
                actor_user_id=actor_user_id,
            )
            return clinic_res.model_dump(mode="json")

        if tool_name == AgentToolName.GET_CLINIC_SPECIALITIES:
            clinic_res = execute_get_clinic_specialities(
                bundle=bundle,
                raw_arguments=arguments,
                clinic_service=self._clinic_service,
                actor_user_id=actor_user_id,
            )
            return clinic_res.model_dump(mode="json")

        if tool_name == AgentToolName.GET_CLINIC_DOCTORS:
            clinic_res = execute_get_clinic_doctors(
                bundle=bundle,
                raw_arguments=arguments,
                clinic_service=self._clinic_service,
                actor_user_id=actor_user_id,
            )
            return clinic_res.model_dump(mode="json")

        if tool_name == AgentToolName.GET_CLINIC_CONSULTATION_TYPES:
            clinic_res = execute_get_clinic_consultation_types(
                bundle=bundle,
                raw_arguments=arguments,
                clinic_service=self._clinic_service,
                actor_user_id=actor_user_id,
            )
            return clinic_res.model_dump(mode="json")

        if tool_name == AgentToolName.CHECK_CLINIC_AVAILABILITY:
            clinic_res = execute_check_clinic_availability(
                bundle=bundle,
                raw_arguments=arguments,
                clinic_service=self._clinic_service,
                actor_user_id=actor_user_id,
            )
            return clinic_res.model_dump(mode="json")

        if tool_name == AgentToolName.CREATE_CLINIC_APPOINTMENT:
            clinic_res = execute_create_clinic_appointment(
                bundle=bundle,
                raw_arguments=arguments,
                clinic_service=self._clinic_service,
                actor_user_id=actor_user_id,
            )
            return clinic_res.model_dump(mode="json")

        if tool_name == AgentToolName.RESCHEDULE_CLINIC_APPOINTMENT:
            clinic_res = execute_reschedule_clinic_appointment(
                bundle=bundle,
                raw_arguments=arguments,
                clinic_service=self._clinic_service,
                actor_user_id=actor_user_id,
            )
            return clinic_res.model_dump(mode="json")

        if tool_name == AgentToolName.CANCEL_CLINIC_APPOINTMENT:
            clinic_res = execute_cancel_clinic_appointment(
                bundle=bundle,
                raw_arguments=arguments,
                clinic_service=self._clinic_service,
                actor_user_id=actor_user_id,
            )
            return clinic_res.model_dump(mode="json")

        if tool_name == AgentToolName.REQUEST_CLINIC_HUMAN_ESCALATION:
            clinic_res = execute_request_clinic_human_escalation(
                bundle=bundle,
                session_id=session_id,
                raw_arguments=arguments,
                context_manager=self._context_manager,
                actor_user_id=actor_user_id,
            )
            return clinic_res.model_dump(mode="json")

        raise ValueError(f"Unsupported tool: {tool_name}")

    async def execute_realtime_tool(
        self,
        *,
        bundle: OnboardingBundleResponse,
        session_id: str,
        call_id: str,
        tool_name: AgentToolName,
        arguments: Dict[str, Any],
        actor: Optional[AuthenticatedUser] = None,
        actor_user_id: Optional[UUID] = None,
        rate_limit_key: str = "default",
        max_requests_per_minute: int = 30,
    ) -> VoiceToolExecutionResponse:
        """Validate and execute a Realtime voice function call with strict limits."""
        started_at = time.perf_counter()
        safe_args = _sanitize_arguments_for_log(arguments)
        logger.info(
            "voice_tool.started session_id=%s call_id=%s tool=%s industry=%s args=%s",
            session_id,
            call_id,
            tool_name.value,
            bundle.organization.industry.value,
            safe_args,
        )
        # 1. Verify session context exists (or initialize for this verified session) & check isolation
        ctx = self._context_manager.get_or_create_context(
            session_id=session_id,
            organization_id=bundle.organization.id,
            business_id=bundle.business_id,
            industry=bundle.organization.industry,
            initial_language=bundle.languages.primary_language,
        )

        # 2. Enforce rate limit
        self._rate_limiter.check_and_record(
            actor_key=f"tool:{rate_limit_key}:{session_id}",
            max_requests_per_window=max_requests_per_minute,
        )

        # 3. Verify tool is allowed for this industry agent
        industry_agent = get_industry_agent(bundle.organization.industry)
        if tool_name not in industry_agent.allowed_tools:
            return VoiceToolExecutionResponse(
                session_id=session_id,
                call_id=call_id,
                tool_name=tool_name,
                status="rejected",
                output={
                    "error": "tool_not_permitted",
                    "message": f"Tool '{tool_name.value}' is not permitted for this business.",
                },
                detected_language=ctx.detected_language,
            )

        # 4. Enforce per-turn tool-call limit (`max_tool_calls_per_turn`)
        try:
            self._context_manager.record_tool_call(
                session_id=session_id,
                organization_id=bundle.organization.id,
                business_id=bundle.business_id,
                max_tool_calls_per_turn=self._max_tool_calls_per_turn,
            )
        except HTTPException as exc:
            if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                return VoiceToolExecutionResponse(
                    session_id=session_id,
                    call_id=call_id,
                    tool_name=tool_name,
                    status="rejected",
                    output={
                        "error": "tool_call_limit_exceeded",
                        "message": str(exc.detail),
                    },
                    detected_language=ctx.detected_language,
                )
            raise

        # 5. Execute tool with timeout & validation error handling
        try:
            output = await asyncio.wait_for(
                asyncio.to_thread(
                    self._dispatch_tool_sync,
                    tool_name=tool_name,
                    bundle=bundle,
                    session_id=session_id,
                    arguments=arguments,
                    actor=actor,
                    actor_user_id=actor_user_id,
                ),
                timeout=self._tool_timeout_seconds,
            )
        except asyncio.TimeoutError:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
            logger.warning(
                "voice_tool.timeout session_id=%s call_id=%s tool=%s duration_ms=%s",
                session_id,
                call_id,
                tool_name.value,
                duration_ms,
            )
            self._context_manager.record_audit_log(
                organization_id=bundle.organization.id,
                business_id=bundle.business_id,
                session_id=session_id,
                actor_user_id=actor_user_id,
                action=f"agent.tool_timeout.{tool_name.value}",
                target_type="agent_tool",
                target_id=call_id,
                metadata={"tool_name": tool_name.value, "status": "error"},
            )
            return VoiceToolExecutionResponse(
                session_id=session_id,
                call_id=call_id,
                tool_name=tool_name,
                status="error",
                output={
                    "error": "tool_timeout",
                    "message": "Tool execution timed out. Do not invent an answer; inform the caller.",
                },
                detected_language=ctx.detected_language,
            )
        except (ValidationError, ValueError) as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
            logger.warning(
                "voice_tool.rejected session_id=%s call_id=%s tool=%s duration_ms=%s reason=%s",
                session_id,
                call_id,
                tool_name.value,
                duration_ms,
                str(exc)[:200],
            )
            self._context_manager.record_audit_log(
                organization_id=bundle.organization.id,
                business_id=bundle.business_id,
                session_id=session_id,
                actor_user_id=actor_user_id,
                action=f"agent.tool_rejected.{tool_name.value}",
                target_type="agent_tool",
                target_id=call_id,
                metadata={"tool_name": tool_name.value, "status": "rejected"},
            )
            return VoiceToolExecutionResponse(
                session_id=session_id,
                call_id=call_id,
                tool_name=tool_name,
                status="rejected",
                output={
                    "error": "invalid_tool_arguments",
                    "message": str(exc),
                },
                detected_language=ctx.detected_language,
            )
        except HTTPException as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
            is_client_rejection = 400 <= exc.status_code < 500
            tool_status = "rejected" if is_client_rejection else "error"
            detail_msg = str(exc.detail or "Backend rejected the tool request.")
            logger.warning(
                "voice_tool.http_error session_id=%s call_id=%s tool=%s http_status=%s status=%s duration_ms=%s detail=%s",
                session_id,
                call_id,
                tool_name.value,
                exc.status_code,
                tool_status,
                duration_ms,
                detail_msg[:240],
            )
            self._context_manager.record_audit_log(
                organization_id=bundle.organization.id,
                business_id=bundle.business_id,
                session_id=session_id,
                actor_user_id=actor_user_id,
                action=f"agent.tool_{tool_status}.{tool_name.value}",
                target_type="agent_tool",
                target_id=call_id,
                metadata={
                    "tool_name": tool_name.value,
                    "status": tool_status,
                    "http_status": exc.status_code,
                },
            )
            err_output: Dict[str, Any] = {
                "error": f"http_{exc.status_code}",
                "message": (
                    detail_msg
                    if is_client_rejection
                    else f"{detail_msg} Do not claim the action succeeded."
                ),
            }
            if not is_client_rejection and tool_name == AgentToolName.CHECK_SALON_AVAILABILITY:
                err_output["availability_status"] = "AVAILABILITY_DATA_ERROR"
            return VoiceToolExecutionResponse(
                session_id=session_id,
                call_id=call_id,
                tool_name=tool_name,
                status=tool_status,
                output=err_output,
                detected_language=ctx.detected_language,
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
            logger.exception(
                "voice_tool.exception session_id=%s call_id=%s tool=%s duration_ms=%s exc_type=%s",
                session_id,
                call_id,
                tool_name.value,
                duration_ms,
                type(exc).__name__,
            )
            self._context_manager.record_audit_log(
                organization_id=bundle.organization.id,
                business_id=bundle.business_id,
                session_id=session_id,
                actor_user_id=actor_user_id,
                action=f"agent.tool_error.{tool_name.value}",
                target_type="agent_tool",
                target_id=call_id,
                metadata={"tool_name": tool_name.value, "status": "error"},
            )
            exc_output: Dict[str, Any] = {
                "error": "tool_execution_failed",
                "message": "Tool execution encountered an internal error. Do not claim the action succeeded.",
            }
            if tool_name == AgentToolName.CHECK_SALON_AVAILABILITY:
                exc_output["availability_status"] = "AVAILABILITY_DATA_ERROR"
            return VoiceToolExecutionResponse(
                session_id=session_id,
                call_id=call_id,
                tool_name=tool_name,
                status="error",
                output=exc_output,
                detected_language=ctx.detected_language,
            )

        duration_ms = round((time.perf_counter() - started_at) * 1000, 1)
        logger.info(
            "voice_tool.succeeded session_id=%s call_id=%s tool=%s duration_ms=%s",
            session_id,
            call_id,
            tool_name.value,
            duration_ms,
        )

        if tool_name in {
            AgentToolName.GET_BUSINESS_PROFILE,
            AgentToolName.GET_BUSINESS_HOURS,
            AgentToolName.SEARCH_BUSINESS_KNOWLEDGE,
            AgentToolName.GET_SALON_SERVICES,
            AgentToolName.GET_SALON_STAFF,
            AgentToolName.CHECK_SALON_AVAILABILITY,
            AgentToolName.CREATE_SALON_APPOINTMENT,
            AgentToolName.RESCHEDULE_SALON_APPOINTMENT,
            AgentToolName.CANCEL_SALON_APPOINTMENT,
            AgentToolName.GET_CLINIC_INFORMATION,
            AgentToolName.GET_CLINIC_DEPARTMENTS,
            AgentToolName.GET_CLINIC_DOCTORS,
            AgentToolName.GET_CLINIC_SPECIALITIES,
            AgentToolName.GET_CLINIC_CONSULTATION_TYPES,
            AgentToolName.CHECK_CLINIC_AVAILABILITY,
            AgentToolName.CREATE_CLINIC_APPOINTMENT,
            AgentToolName.RESCHEDULE_CLINIC_APPOINTMENT,
            AgentToolName.CANCEL_CLINIC_APPOINTMENT,
        }:
            self._context_manager.record_audit_log(
                organization_id=bundle.organization.id,
                business_id=bundle.business_id,
                session_id=session_id,
                actor_user_id=actor_user_id,
                action=f"agent.tool_executed.{tool_name.value}",
                target_type="agent_tool",
                target_id=call_id,
                metadata={"tool_name": tool_name.value, "status": "succeeded"},
            )

        escalation_triggered = (
            tool_name
            in {
                AgentToolName.REQUEST_HUMAN_ESCALATION,
                AgentToolName.REQUEST_CLINIC_HUMAN_ESCALATION,
            }
            and bool(output.get("accepted"))
        )
        escalation_ref = (
            str(output["escalation_reference"])
            if escalation_triggered and output.get("escalation_reference")
            else None
        )

        return VoiceToolExecutionResponse(
            session_id=session_id,
            call_id=call_id,
            tool_name=tool_name,
            status="succeeded",
            output=output,
            escalation_triggered=escalation_triggered,
            escalation_reference=escalation_ref,
            detected_language=ctx.detected_language,
        )

    async def process_turn(
        self,
        *,
        bundle: OnboardingBundleResponse,
        session_id: str,
        user_input: str,
        preferred_language: Optional[LanguageCode] = None,
        actor: Optional[AuthenticatedUser] = None,
        actor_user_id: Optional[UUID] = None,
        rate_limit_key: str = "default",
    ) -> AgentTurnResponse:
        """Execute a complete 9-step Stage 4 conversational turn."""
        industry = bundle.organization.industry
        industry_agent = get_industry_agent(industry)

        # Check whether user repeated the exact same query before we append this turn
        existing_ctx = self._context_manager.get_or_create_context(
            session_id=session_id,
            organization_id=bundle.organization.id,
            business_id=bundle.business_id,
            industry=industry,
            initial_language=bundle.languages.primary_language,
        )
        normalized_query = user_input.strip().lower()[:200]
        is_repeated_query = (
            len(existing_ctx.recent_user_queries) > 0
            and existing_ctx.recent_user_queries[-1] == normalized_query
        )

        # Step 1 & 2: Start turn & resolve session context
        ctx = self._context_manager.start_new_turn(
            session_id=session_id,
            organization_id=bundle.organization.id,
            business_id=bundle.business_id,
            industry=industry,
            user_query=user_input,
        )

        # Step 3: Classify intent & safety flags
        intent_result = self._intent_classifier.classify(
            user_input=user_input,
            industry=industry,
            supported_languages=bundle.languages.supported_languages,
            preferred_language=preferred_language,
        )
        lang = intent_result.detected_language

        # Step 4: Immediate Emergency Short-Circuit (No delaying questions!)
        if intent_result.intent == AgentIntent.EMERGENCY_INTENT or (
            SafetyFlag.MEDICAL_EMERGENCY_DETECTED in intent_result.safety_flags
        ):
            emergency_msg = industry_agent.build_emergency_response(
                bundle, language_code=lang.value
            )
            updated_ctx = self._context_manager.update_from_intent(
                session_id=session_id,
                organization_id=bundle.organization.id,
                business_id=bundle.business_id,
                intent=AgentIntent.EMERGENCY_INTENT,
                confidence=intent_result.confidence,
                detected_language=lang,
                entities=intent_result.extracted_entities,
            )
            self._context_manager.record_audit_log(
                organization_id=bundle.organization.id,
                business_id=bundle.business_id,
                session_id=session_id,
                actor_user_id=actor_user_id,
                action="agent.emergency_intent_directed",
                target_type="voice_session",
                target_id=session_id,
                metadata={"industry": industry.value, "language": lang.value},
            )
            return AgentTurnResponse(
                session_id=session_id,
                organization_id=bundle.organization.id,
                business_id=bundle.business_id,
                industry=industry,
                intent_result=intent_result,
                tool_calls=[],
                spoken_response=emergency_msg,
                response_language=lang,
                clarification_question=None,
                escalated=False,
                escalation_reference=None,
                escalation_status="emergency_redirected",
                emergency_guidance_issued=True,
                booking_created=False,
                context_snapshot=updated_ctx,
            )

        # Step 5: Execute required tool(s) within `max_tool_calls_per_turn`
        executed_tools: List[ExecutedToolCallSummary] = []
        clarification_question: Optional[str] = None

        clinical_flags = {
            SafetyFlag.CLINICAL_DIAGNOSIS_REQUEST,
            SafetyFlag.PRESCRIPTION_OR_MEDICATION_REQUEST,
            SafetyFlag.TREATMENT_RECOMMENDATION_REQUEST,
        }
        has_clinical_safety_flag = bool(
            clinical_flags.intersection(intent_result.safety_flags)
        )

        if has_clinical_safety_flag:
            esc_call = await self.execute_realtime_tool(
                bundle=bundle,
                session_id=session_id,
                call_id=f"call_clinical_{ctx.turn_count}",
                tool_name=AgentToolName.REQUEST_HUMAN_ESCALATION,
                arguments={
                    "reason": "Clinical or medical question requiring qualified healthcare staff",
                    "summary": user_input[:300],
                    "urgency": EscalationUrgency.CLINICAL_STAFF.value,
                },
                actor_user_id=actor_user_id,
                rate_limit_key=rate_limit_key,
            )
            executed_tools.append(
                ExecutedToolCallSummary(
                    tool_name=esc_call.tool_name,
                    status=esc_call.status,
                    output=esc_call.output,
                )
            )
        elif intent_result.recommended_tool is not None:
            tool_args = self._build_tool_arguments_for_intent(
                intent_result=intent_result,
                user_input=user_input,
                ctx_entities=ctx.extracted_entities,
            )
            tool_res = await self.execute_realtime_tool(
                bundle=bundle,
                session_id=session_id,
                call_id=f"call_turn_{ctx.turn_count}_1",
                tool_name=intent_result.recommended_tool,
                arguments=tool_args,
                actor=actor,
                actor_user_id=actor_user_id,
                rate_limit_key=rate_limit_key,
            )
            executed_tools.append(
                ExecutedToolCallSummary(
                    tool_name=tool_res.tool_name,
                    status=tool_res.status,
                    output=tool_res.output,
                )
            )

            # If knowledge search returned 0 matches and question was repeated or caller needs help,
            # automatically trigger controlled human escalation if within tool budget
            if (
                tool_res.tool_name == AgentToolName.SEARCH_BUSINESS_KNOWLEDGE
                and tool_res.status == "succeeded"
                and not tool_res.output.get("has_verified_answer")
                and (is_repeated_query or ctx.consecutive_low_confidence_turns >= 1)
                and len(executed_tools) < self._max_tool_calls_per_turn
            ):
                esc_fallback = await self.execute_realtime_tool(
                    bundle=bundle,
                    session_id=session_id,
                    call_id=f"call_turn_{ctx.turn_count}_2",
                    tool_name=AgentToolName.REQUEST_HUMAN_ESCALATION,
                    arguments={
                        "reason": "Unanswered business question after knowledge lookup",
                        "summary": f"Caller asked about: {user_input[:250]}",
                        "urgency": EscalationUrgency.STANDARD.value,
                    },
                    actor_user_id=actor_user_id,
                    rate_limit_key=rate_limit_key,
                )
                executed_tools.append(
                    ExecutedToolCallSummary(
                        tool_name=esc_fallback.tool_name,
                        status=esc_fallback.status,
                        output=esc_fallback.output,
                    )
                )

        # Step 6: Compose natural-language response strictly grounded in tool outputs
        if intent_result.missing_information:
            clarification_question = self._build_clarification_question(
                intent_result=intent_result, language=lang, industry=industry
            )

        if self._model_response_generator is not None:
            try:
                spoken_response = await asyncio.wait_for(
                    self._model_response_generator(
                        bundle, intent_result, executed_tools
                    ),
                    timeout=self._response_timeout_seconds,
                )
            except Exception:
                spoken_response = self._compose_grounded_response(
                    bundle=bundle,
                    intent_result=intent_result,
                    executed_tools=executed_tools,
                    clarification_question=clarification_question,
                )
        else:
            spoken_response = self._compose_grounded_response(
                bundle=bundle,
                intent_result=intent_result,
                executed_tools=executed_tools,
                clarification_question=clarification_question,
            )

        # Step 7: Update session context
        updated_ctx = self._context_manager.update_from_intent(
            session_id=session_id,
            organization_id=bundle.organization.id,
            business_id=bundle.business_id,
            intent=intent_result.intent,
            confidence=intent_result.confidence,
            detected_language=lang,
            entities=intent_result.extracted_entities,
            clarification_question=clarification_question,
        )

        booking_created = any(
            t.tool_name == AgentToolName.CREATE_SALON_APPOINTMENT
            and t.status == "succeeded"
            for t in executed_tools
        )

        return AgentTurnResponse(
            session_id=session_id,
            organization_id=bundle.organization.id,
            business_id=bundle.business_id,
            industry=industry,
            intent_result=intent_result,
            tool_calls=executed_tools,
            spoken_response=spoken_response,
            response_language=lang,
            clarification_question=clarification_question,
            escalated=updated_ctx.escalated,
            escalation_reference=updated_ctx.escalation_reference,
            escalation_status=updated_ctx.escalation_status,
            emergency_guidance_issued=False,
            booking_created=booking_created,
            context_snapshot=updated_ctx,
        )

    def _build_tool_arguments_for_intent(
        self,
        *,
        intent_result: IntentClassificationResult,
        user_input: str,
        ctx_entities: Dict[str, Any],
    ) -> Dict[str, Any]:
        tool = intent_result.recommended_tool
        merged_entities = {**ctx_entities, **intent_result.extracted_entities}

        if tool == AgentToolName.GET_BUSINESS_PROFILE:
            return {}

        if tool == AgentToolName.GET_BUSINESS_HOURS:
            if "weekday" in merged_entities:
                return {"weekday": int(merged_entities["weekday"])}
            return {}

        if tool == AgentToolName.SEARCH_BUSINESS_KNOWLEDGE:
            return {"query": user_input[:250]}

        if tool == AgentToolName.SAVE_CONVERSATION_SUMMARY:
            prefs: Dict[str, str] = {}
            for key in ("topic", "preferred_date", "preferred_time", "weekday_name"):
                if key in merged_entities and merged_entities[key] is not None:
                    prefs[key] = str(merged_entities[key])
            return {
                "summary_text": f"Caller expressed {intent_result.intent.value}: {user_input[:250]}",
                "primary_intent": intent_result.intent.value,
                "detected_language": intent_result.detected_language.value,
                "booking_preferences": prefs,
            }

        if tool == AgentToolName.REQUEST_HUMAN_ESCALATION:
            return {
                "reason": f"Caller requested {intent_result.intent.value}",
                "summary": user_input[:300],
                "urgency": EscalationUrgency.STANDARD.value,
            }

        return {}

    def _build_clarification_question(
        self,
        *,
        intent_result: IntentClassificationResult,
        language: LanguageCode,
        industry: Optional[OrganizationIndustry] = None,
    ) -> str:
        missing = intent_result.missing_information
        if intent_result.intent == AgentIntent.BOOKING_INTENT:
            if industry == OrganizationIndustry.SALON:
                if language == LanguageCode.HINDI:
                    return "ज़रूर! क्या आपकी कोई पसंदीदा स्टाइलिस्ट या समय है?"
                if language == LanguageCode.HINGLISH:
                    return "Sure! Kya aapki koi preferred stylist ya time preference hai?"
                return "Sure! Do you have a preferred stylist or time?"
            if language == LanguageCode.HINDI:
                return "कृपया बताएं कि आप किस सेवा/विभाग और किस दिन व समय के लिए प्राथमिकता दर्ज कराना चाहते हैं?"
            if language == LanguageCode.HINGLISH:
                return "Kripya bataiye aap kis service/department aur kis preferred day aur time ke liye preference note karwana chahte hain?"
            return "Could you please share which service or department and what preferred day and time we should note for the reception team?"

        if "specific_service_or_consultation" in missing:
            if language == LanguageCode.HINDI:
                return "आप किस विशेष सेवा या परामर्श के शुल्क के बारे में जानना चाहते हैं?"
            if language == LanguageCode.HINGLISH:
                return "Aap kis specific service ya consultation ki fees ke baare mein jaanna chahte hain?"
            return "Which specific service or consultation fee would you like me to check in our verified records?"

        if language == LanguageCode.HINDI:
            return "क्या आप कृपया अपना प्रश्न थोड़ा और स्पष्ट कर सकते हैं?"
        if language == LanguageCode.HINGLISH:
            return "Kya aap apna question thoda aur clarify kar sakte hain?"
        return "Could you please clarify how I may help you today?"

    def _compose_grounded_response(
        self,
        *,
        bundle: OnboardingBundleResponse,
        intent_result: IntentClassificationResult,
        executed_tools: List[ExecutedToolCallSummary],
        clarification_question: Optional[str],
    ) -> str:
        lang = intent_result.detected_language
        biz_name = bundle.profile.display_name
        assistant_name = bundle.assistant.assistant_name

        # 1. Clinical safety refusal + escalation confirmation
        clinical_flags = {
            SafetyFlag.CLINICAL_DIAGNOSIS_REQUEST,
            SafetyFlag.PRESCRIPTION_OR_MEDICATION_REQUEST,
            SafetyFlag.TREATMENT_RECOMMENDATION_REQUEST,
        }
        if clinical_flags.intersection(intent_result.safety_flags):
            esc_tool = next(
                (
                    t
                    for t in executed_tools
                    if t.tool_name == AgentToolName.REQUEST_HUMAN_ESCALATION
                    and t.status == "succeeded"
                ),
                None,
            )
            ref = esc_tool.output.get("escalation_reference") if esc_tool else None
            if lang == LanguageCode.HINDI:
                ref_note = f" आपका एस्केलेशन संदर्भ {ref} दर्ज कर लिया गया है।" if ref else ""
                return (
                    f"मैं {biz_name} का प्रशासनिक रिसेप्शनिस्ट हूँ और चिकित्सा निदान, दवा या इलाज की सलाह नहीं दे सकता।"
                    f"{ref_note} हमारे योग्य चिकित्सा स्टाफ आपकी सहायता करेंगे।"
                )
            if lang == LanguageCode.HINGLISH:
                ref_note = f" Aapka escalation reference {ref} log kar liya gaya hai." if ref else ""
                return (
                    f"Main {biz_name} ka administrative receptionist hoon aur medical diagnosis, prescription, ya treatment advice nahi de sakta."
                    f"{ref_note} Qualified medical staff aapki madad karenge."
                )
            ref_note = (
                f" I have logged escalation request {ref} (pending human review) for our qualified clinical team."
                if ref
                else ""
            )
            return (
                f"I am an administrative receptionist for {biz_name} and cannot provide medical diagnosis, "
                f"prescriptions, or treatment recommendations.{ref_note}"
            )

        # 2. Prompt injection / policy bypass refusal
        if SafetyFlag.PROMPT_INJECTION_OR_POLICY_BYPASS in intent_result.safety_flags:
            return (
                f"I can only assist with verified administrative enquiries for {biz_name}."
            )

        # 3. Greeting
        if intent_result.intent == AgentIntent.GREETING:
            if lang == LanguageCode.HINDI:
                return f"नमस्ते! मैं {assistant_name} हूँ, {biz_name} से। मैं आज आपकी क्या सहायता कर सकता हूँ?"
            if lang == LanguageCode.HINGLISH:
                return f"Namaste! Main {assistant_name} bol raha hoon {biz_name} se. Aaj main aapki kaise help kar sakta hoon?"
            return f"{bundle.assistant.greeting} I am {assistant_name} from {biz_name}. How may I assist you today?"

        # 4. Check tool execution failures first (never claim success if tool failed)
        if executed_tools and any(
            t.status in {"error", "rejected"} for t in executed_tools
        ):
            return (
                f"I was unable to retrieve or confirm that action from {biz_name}'s system right now. "
                f"Please contact our reception desk directly at {bundle.profile.phone or bundle.profile.email or 'our main desk'}."
            )

        # 4b. Stage 5 Salon Workflow Tool Results
        create_appt_tool = next(
            (t for t in executed_tools if t.tool_name == AgentToolName.CREATE_SALON_APPOINTMENT and t.status == "succeeded"),
            None,
        )
        if create_appt_tool is not None:
            out = create_appt_tool.output
            b_ref = out.get("booking_reference")
            s_name = out.get("service_name")
            st_name = out.get("staff_name")
            a_date = out.get("appointment_date")
            s_time = out.get("start_time")
            if lang == LanguageCode.HINDI:
                return (
                    f"आपका {s_name} के लिए {a_date} को {s_time} बजे {st_name} के साथ अपॉइंटमेंट सफलतापूर्वक कन्फर्म हो गया है! "
                    f"बुकिंग संदर्भ संख्या {b_ref} है। हम {biz_name} में आपका स्वागत करने के लिए तत्पर हैं।"
                )
            if lang == LanguageCode.HINGLISH:
                return (
                    f"Aapka {s_name} ke liye {a_date} ko {s_time} par {st_name} ke saath appointment confirm ho gaya hai! "
                    f"Booking reference number {b_ref} hai. {biz_name} mein aapka swagat hai!"
                )
            return (
                f"Your appointment for {s_name} on {a_date} at {s_time} with {st_name} is confirmed! "
                f"Your booking reference is {b_ref}. We look forward to seeing you at {biz_name}!"
            )

        resched_tool = next(
            (t for t in executed_tools if t.tool_name == AgentToolName.RESCHEDULE_SALON_APPOINTMENT and t.status == "succeeded"),
            None,
        )
        if resched_tool is not None:
            out = resched_tool.output
            b_ref = out.get("booking_reference")
            n_date = out.get("new_date")
            n_time = out.get("new_start_time")
            st_name = out.get("staff_name")
            if lang == LanguageCode.HINDI:
                return f"अपॉइंटमेंट {b_ref} सफलतापूर्वक {n_date} को {n_time} बजे {st_name} के साथ रीशेड्यूल कर दिया गया है।"
            if lang == LanguageCode.HINGLISH:
                return f"Appointment {b_ref} successfully {n_date} ko {n_time} par {st_name} ke saath reschedule ho gaya hai."
            return f"Your appointment {b_ref} has been successfully rescheduled to {n_date} at {n_time} with {st_name}."

        cancel_tool = next(
            (t for t in executed_tools if t.tool_name == AgentToolName.CANCEL_SALON_APPOINTMENT and t.status == "succeeded"),
            None,
        )
        if cancel_tool is not None:
            out = cancel_tool.output
            b_ref = out.get("booking_reference")
            s_name = out.get("service_name")
            if lang == LanguageCode.HINDI:
                return f"आपका {s_name} का अपॉइंटमेंट (संदर्भ: {b_ref}) सफलतापूर्वक रद्द कर दिया गया है।"
            if lang == LanguageCode.HINGLISH:
                return f"Aapka {s_name} ka appointment (reference: {b_ref}) successfully cancel kar diya gaya hai."
            return f"Your appointment {b_ref} for {s_name} has been successfully cancelled."

        avail_tool = next(
            (t for t in executed_tools if t.tool_name == AgentToolName.CHECK_SALON_AVAILABILITY and t.status == "succeeded"),
            None,
        )
        if avail_tool is not None:
            out = avail_tool.output
            s_name = out.get("service_name")
            r_date = out.get("requested_date")
            slots = out.get("available_slots", [])
            is_closed = out.get("is_business_closed", False)
            closure_reason = out.get("closure_reason")
            if is_closed:
                return f"I checked our schedule, and {biz_name} is closed on {r_date} ({closure_reason or 'closed'}). Would you like to check another date?"
            if not slots:
                return f"I checked our availability for {s_name} on {r_date}, but there are currently no available openings. Would you like to try another date or check our operating hours?"
            slot_times = [s["start_time"] for s in slots[:4]]
            times_str = ", ".join(slot_times)
            if lang == LanguageCode.HINDI:
                return f"मुझे {r_date} को {s_name} के लिए निम्नलिखित समय उपलब्ध मिले हैं: {times_str}। क्या आप इनमें से कोई समय बुक करना चाहेंगे?"
            if lang == LanguageCode.HINGLISH:
                return f"Mujhe {r_date} ko {s_name} ke liye ye time slots available mile hain: {times_str}. Kya aap inme se koi slot book karna chahenge?"
            return f"We have slots available for {s_name} on {r_date} around {times_str}. Would you like me to book one of these for you?"

        services_tool = next(
            (t for t in executed_tools if t.tool_name == AgentToolName.GET_SALON_SERVICES and t.status == "succeeded"),
            None,
        )
        if services_tool is not None:
            services_list = services_tool.output.get("services", [])
            if services_list:
                items_str = "; ".join(f"{s['name']} ({s['currency']} {s['price']:.0f}, {s['duration_minutes']} mins)" for s in services_list[:6])
                return f"Our salon offers the following treatments: {items_str}. Would you like to check availability or book one?"
            return f"{biz_name} offers hair styling, coloring, facials, and grooming services. Would you like to check availability for any of these?"

        staff_tool = next(
            (t for t in executed_tools if t.tool_name == AgentToolName.GET_SALON_STAFF and t.status == "succeeded"),
            None,
        )
        if staff_tool is not None:
            staff_list = staff_tool.output.get("staff", [])
            if staff_list:
                names_str = ", ".join(f"{s['name']} ({s['role']})" for s in staff_list[:5])
                return f"Our expert stylists include: {names_str}. Would you like to book an appointment with any of them?"

        # 5. Booking / Rescheduling / Cancellation boundaries (For Clinic / Hospital / non-salon)
        if intent_result.intent == AgentIntent.BOOKING_INTENT:
            summary_tool = next(
                (
                    t
                    for t in executed_tools
                    if t.tool_name == AgentToolName.SAVE_CONVERSATION_SUMMARY
                    and t.status == "succeeded"
                ),
                None,
            )
            prefs = (
                summary_tool.output.get("booking_preferences_captured", {})
                if summary_tool
                else {}
            )
            prefs_text = (
                ", ".join(f"{k}: {v}" for k, v in prefs.items())
                if prefs
                else "your enquiry"
            )
            clarify_suffix = f" {clarification_question}" if clarification_question else ""
            if lang == LanguageCode.HINDI:
                return (
                    f"कृपया ध्यान दें कि मैं सीधे अपॉइंटमेंट बुक नहीं कर सकता, लेकिन मैंने आपकी प्राथमिकता ({prefs_text}) "
                    f"{biz_name} रिसेप्शन टीम के लिए नोट कर ली है।{clarify_suffix}"
                )
            if lang == LanguageCode.HINGLISH:
                return (
                    f"Please note ki main abhi live appointment book nahi kar sakta, lekin maine aapki preference ({prefs_text}) "
                    f"{biz_name} reception team ke liye save kar li hai.{clarify_suffix}"
                )
            return (
                f"Please note that automated appointment booking is not completed on this line, "
                f"but I have saved your booking preferences ({prefs_text}) for the {biz_name} reception team.{clarify_suffix}"
            )

        # 6. Human Escalation response (only confirm if backend returned accepted=True)
        esc_executed = next(
            (
                t
                for t in executed_tools
                if t.tool_name == AgentToolName.REQUEST_HUMAN_ESCALATION
            ),
            None,
        )
        if esc_executed is not None:
            if esc_executed.status == "succeeded" and esc_executed.output.get("accepted"):
                ref = esc_executed.output.get("escalation_reference")
                contact_phone = esc_executed.output.get("contact_phone") or bundle.profile.phone
                if lang == LanguageCode.HINDI:
                    return (
                        f"मैंने {biz_name} स्टाफ के लिए आपका मानव सहायता अनुरोध (संदर्भ: {ref}) दर्ज कर लिया है। "
                        f"अभी किसी स्टाफ सदस्य से तुरंत लाइव संपर्क नहीं हुआ है; आप सीधे {contact_phone or 'रिसेप्शन'} पर भी संपर्क कर सकते हैं।"
                    )
                if lang == LanguageCode.HINGLISH:
                    return (
                        f"Maine {biz_name} team ke liye aapki human escalation request (Reference: {ref}) log kar li hai. "
                        f"Abhi kisi person ko live notify nahi kiya gaya hai; aap directly {contact_phone or 'reception'} par bhi call kar sakte hain."
                    )
                return (
                    f"I have logged human escalation request {ref} (status: pending human review) for the {biz_name} team. "
                    f"Please note that a staff member has not been contacted live yet; you may also reach reception directly at {contact_phone or bundle.profile.email or 'our front desk'}."
                )
            return (
                f"Automated escalation logging is not enabled for {biz_name}, so no escalation ticket was created. "
                f"Please reach our reception desk directly at {bundle.profile.phone or bundle.profile.email or 'our main desk'}."
            )

        # 7. Business Hours tool output
        hours_tool = next(
            (
                t
                for t in executed_tools
                if t.tool_name == AgentToolName.GET_BUSINESS_HOURS
                and t.status == "succeeded"
            ),
            None,
        )
        if hours_tool is not None:
            schedule = hours_tool.output.get("schedule", [])
            tz = hours_tool.output.get("timezone", bundle.hours.timezone)
            parts: List[str] = []
            for item in schedule:
                day_label = WEEKDAY_NAMES.get(int(item["weekday"]), f"Day {item['weekday']}")
                if item.get("is_closed"):
                    parts.append(f"{day_label}: Closed")
                else:
                    parts.append(f"{day_label}: {item.get('opens_at')}–{item.get('closes_at')}")
            joined = "; ".join(parts)
            if lang == LanguageCode.HINDI:
                return f"{biz_name} का समय ({tz}): {joined}।"
            if lang == LanguageCode.HINGLISH:
                return f"{biz_name} ke operating hours ({tz}) hain: {joined}."
            return f"The verified operating hours for {biz_name} ({tz}) are: {joined}."

        # 8. Business Profile / Location tool output
        profile_tool = next(
            (
                t
                for t in executed_tools
                if t.tool_name == AgentToolName.GET_BUSINESS_PROFILE
                and t.status == "succeeded"
            ),
            None,
        )
        if profile_tool is not None:
            out = profile_tool.output
            addr = out.get("address_summary") or "Address not configured in reception records"
            phone = out.get("phone") or "Phone not listed"
            desc = out.get("description") or ""
            if intent_result.intent == AgentIntent.LOCATION:
                if lang == LanguageCode.HINDI:
                    return f"{biz_name} का पता है: {addr}। संपर्क फोन: {phone}।"
                if lang == LanguageCode.HINGLISH:
                    return f"{biz_name} ka address hai: {addr}. Contact phone: {phone}."
                return f"{biz_name} is located at {addr}. You can reach reception at {phone}."
            return (
                f"{biz_name} ({out.get('industry')}): {desc} "
                f"Location: {addr}. Contact: {phone}."
            ).strip()

        # 9. Knowledge Search tool output
        search_tool = next(
            (
                t
                for t in executed_tools
                if t.tool_name == AgentToolName.SEARCH_BUSINESS_KNOWLEDGE
                and t.status == "succeeded"
            ),
            None,
        )
        if search_tool is not None:
            matches = search_tool.output.get("matches", [])
            if matches:
                top = matches[0]
                answer_text = top.get("verified_answer", "")
                if clarification_question:
                    return f"{answer_text} {clarification_question}"
                return f"According to {biz_name}'s verified records: {answer_text}"

            # Empty knowledge search result -> admit uncertainty and never fabricate
            if lang == LanguageCode.HINDI:
                return (
                    f"क्षमा करें, {biz_name} के सत्यापित रिकॉर्ड में इस विषय की जानकारी उपलब्ध नहीं है। "
                    "मैं कोई अनुमानित जानकारी नहीं देना चाहता। क्या मैं आपके लिए हमारे स्टाफ को एस्केलेशन अनुरोध दर्ज करूँ?"
                )
            if lang == LanguageCode.HINGLISH:
                return (
                    f"Maaf kijiye, {biz_name} ke verified records mein iski exact information available nahi hai. "
                    "Kya main aapke liye human staff escalation request log kar doon?"
                )
            return (
                f"I don't have verified information about that in {biz_name}'s records, and I do not want to guess. "
                "Would you like me to log a human escalation request for our reception team?"
            )

        if clarification_question:
            return clarification_question

        return (
            f"I don't have verified details on that for {biz_name}. "
            "Would you like me to check our operating hours, FAQs, or log a request for human staff assistance?"
        )


_default_orchestrator = AgentOrchestrator()


def get_agent_orchestrator() -> AgentOrchestrator:
    """Return the singleton Stage 4 AgentOrchestrator."""
    return _default_orchestrator

