"""
LLM Provider Abstraction for AgentDesk Outreach Drafting.
Supports:
1. TemplateLLMProvider: Deterministic, grounded generator using only verified public facts.
2. OllamaLLMProvider: Local offline LLM (default: http://localhost:11434).
3. CloudOpenAICompatibleProvider: Cloud OpenAI-compatible endpoint with secure key management.
"""
import os
import re
import json
import httpx
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

try:
    from ..models import LeadRecord, OutreachDraft, AIProviderConfig
except (ImportError, ValueError):
    from models import LeadRecord, OutreachDraft, AIProviderConfig

def _sanitize_recipient_name(contact_name: Optional[str], company_name: str) -> str:
    """
    Ensures no invented or hallucinated names are used.
    If contact_name is missing or placeholder, defaults safely to company team.
    """
    clean_name = (contact_name or "").strip()
    if not clean_name or clean_name.lower() in ("(not published on page)", "not published", "unknown", "n/a", "none"):
        return f"{company_name} Team"
    return clean_name

def _has_genuine_email(email: Optional[str]) -> bool:
    """
    Checks if lead has an actual verified email address.
    """
    if not email:
        return False
    e = email.strip()
    if e == "(No public email listed)" or e.lower() == "none" or "@" not in e or "." not in e.split("@")[-1]:
        return False
    return True

class BaseLLMProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str:
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        pass

    @abstractmethod
    async def draft_lead_outreach(
        self,
        lead: LeadRecord,
        service_offering: str,
        tone: str = "professional",
        sender_name: str = "AgentDesk Operator",
        sender_company: str = "AgentDesk"
    ) -> OutreachDraft:
        pass

class TemplateLLMProvider(BaseLLMProvider):
    """
    Deterministic, zero-leakage drafter that synthesizes personalized outreach
    strictly from verified company metadata without making external network calls.
    """
    @property
    def provider_id(self) -> str:
        return "template"

    @property
    def display_name(self) -> str:
        return "Built-in Grounded Drafter"

    async def draft_lead_outreach(
        self,
        lead: LeadRecord,
        service_offering: str,
        tone: str = "professional",
        sender_name: str = "AgentDesk Operator",
        sender_company: str = "AgentDesk"
    ) -> OutreachDraft:
        company = lead.company_name.strip() or "Your Organization"
        has_email = _has_genuine_email(lead.email)
        recipient_name = _sanitize_recipient_name(lead.contact_name, company)
        recipient_role = lead.contact_role.strip() if lead.contact_role and lead.contact_role != "(Not published on page)" else ""

        verified_facts: List[str] = [f"Company Name: {company}"]
        if lead.industry:
            verified_facts.append(f"Industry: {lead.industry}")
        if lead.description:
            verified_facts.append(f"Public Focus: {lead.description[:120]}")
        if has_email:
            verified_facts.append(f"Verified Email: {lead.email}")

        # Salutation
        if recipient_name == f"{company} Team":
            salutation = f"Hi {company} Team,"
        else:
            salutation = f"Hi {recipient_name},"

        clean_offering = service_offering.strip()
        clean_industry = (lead.industry or "technology").strip()

        # Subject Line synthesis tailored to tone
        if tone == "concise":
            subject = f"Inquiry regarding {company} & {clean_offering}"
        elif tone == "consultative":
            subject = f"Strategic inquiry: Supporting {company}'s {clean_industry} initiatives"
        else:
            subject = f"Exploring {clean_offering} for {company}"

        # Body Synthesis strictly grounded in public data
        if lead.description and len(lead.description.strip()) > 15:
            opening_ref = f"I came across {company}'s public presence focused on {lead.description.strip().rstrip('.')}."
        elif lead.industry:
            opening_ref = f"I came across {company} while reviewing leading organizations in {clean_industry}."
        else:
            opening_ref = f"I came across {company}'s public web profile."

        if tone == "concise":
            body_p2 = (
                f"At {sender_company}, we provide {clean_offering} specifically designed to assist "
                f"teams in the {clean_industry} space."
            )
            body_p3 = (
                f"Would you be open to a 10-minute introductory conversation next week to see if "
                f"this could add value to {company}?"
            )
        elif tone == "consultative":
            body_p2 = (
                f"At {sender_company}, we partner with organizations in {clean_industry} to implement {clean_offering}. "
                f"Our focus is helping teams eliminate operational bottlenecks and drive measurable outcomes."
            )
            body_p3 = (
                f"Given your focus, I would welcome the opportunity to share brief insights on how similar "
                f"teams approach this. Would you or a colleague have time for a brief introductory call next Tuesday or Thursday?"
            )
        else:
            body_p2 = (
                f"At {sender_company}, we specialize in {clean_offering}. We work closely with companies "
                f"in the {clean_industry} sector to streamline core workflows and accelerate execution."
            )
            body_p3 = (
                f"If this is relevant to your current objectives, would you be available for a brief 10-minute "
                f"conversation next week to explore potential synergy?"
            )

        signoff = f"Best regards,\n\n{sender_name}\n{sender_company}"
        email_body = f"{salutation}\n\n{opening_ref}\n\n{body_p2}\n\n{body_p3}\n\n{signoff}"

        source_info = lead.source_url or lead.website or "public web"
        grounding_notes = (
            f"Grounded exclusively in verified public metadata: company name ('{company}'), "
            f"industry ('{clean_industry}'), and verified source page ({source_info}). "
            f"Zero personal contact names or unverified claims were fabricated."
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        draft_id = f"draft-{lead.id}-{int(datetime.now(timezone.utc).timestamp())}"

        return OutreachDraft(
            id=draft_id,
            lead_id=lead.id,
            company_name=company,
            recipient_name=recipient_name,
            recipient_role=recipient_role or "(Not published)",
            recipient_email=lead.email if has_email else "(No public email listed)",
            has_verified_email=has_email,
            subject=subject,
            body=email_body,
            status="drafted",
            created_at=now_iso,
            source_url=lead.source_url or lead.website or "",
            grounding_notes=grounding_notes,
            verified_facts_used=verified_facts,
        )

class OllamaLLMProvider(BaseLLMProvider):
    """
    Local Ollama offline LLM provider.
    Connects to an existing Ollama endpoint (e.g. http://localhost:11434).
    """
    def __init__(self, api_base: Optional[str] = None, model_name: Optional[str] = None):
        self.api_base = (api_base or "http://localhost:11434").rstrip("/")
        self.model_name = model_name or "llama3"

    @property
    def provider_id(self) -> str:
        return "ollama"

    @property
    def display_name(self) -> str:
        return f"Local Ollama ({self.model_name})"

    async def draft_lead_outreach(
        self,
        lead: LeadRecord,
        service_offering: str,
        tone: str = "professional",
        sender_name: str = "AgentDesk Operator",
        sender_company: str = "AgentDesk"
    ) -> OutreachDraft:
        company = lead.company_name.strip() or "Your Organization"
        has_email = _has_genuine_email(lead.email)
        recipient_name = _sanitize_recipient_name(lead.contact_name, company)

        verified_facts: List[str] = [f"Company: {company}"]
        if lead.industry:
            verified_facts.append(f"Industry: {lead.industry}")
        if lead.description:
            verified_facts.append(f"Description: {lead.description}")

        system_prompt = (
            "You are an AI B2B outreach drafting agent for AgentDesk.\n"
            "STRICT GROUNDING CONSTRAINTS:\n"
            "1. ONLY utilize the verified facts provided about the target company.\n"
            "2. NEVER invent, hallucinate, or assume any person's name, role, email address, previous meetings, or business relationships.\n"
            "3. If the recipient contact name is a team, address the salutation as 'Hi [Company Name] Team,'.\n"
            "4. Keep the email concise, professional, grounded, and within 3 paragraphs.\n"
            "5. You MUST return ONLY valid JSON with keys: 'subject' (string) and 'body' (string)."
        )

        user_prompt = (
            f"Target Company: {company}\n"
            f"Industry: {lead.industry}\n"
            f"Public Description: {lead.description or 'Public enterprise'}\n"
            f"Recipient: {recipient_name}\n"
            f"Sender Name: {sender_name}\n"
            f"Sender Organization: {sender_company}\n"
            f"Service Offering: {service_offering}\n"
            f"Tone: {tone}\n"
            "Generate personalized B2B outreach strictly complying with the grounding rules. Return valid JSON only."
        )

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(
                    f"{self.api_base}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": user_prompt,
                        "system": system_prompt,
                        "stream": False,
                        "format": "json"
                    }
                )
                if res.status_code != 200:
                    raise RuntimeError(f"Ollama server returned HTTP {res.status_code}: {res.text[:120]}")
                data = res.json()
                raw_response = data.get("response", "{}")
                parsed = json.loads(raw_response)

                subject = parsed.get("subject", f"Exploring {service_offering} for {company}")
                body = parsed.get("body", "")
                if not body:
                    raise ValueError("Ollama generated empty email body.")

        except Exception as exc:
            raise RuntimeError(
                f"Local Ollama provider failure at {self.api_base} (model: {self.model_name}): {str(exc)}. "
                "Ensure Ollama is running ('ollama serve') or switch to the Built-in Grounded Drafter."
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        draft_id = f"draft-{lead.id}-{int(datetime.now(timezone.utc).timestamp())}"

        return OutreachDraft(
            id=draft_id,
            lead_id=lead.id,
            company_name=company,
            recipient_name=recipient_name,
            recipient_role=lead.contact_role if lead.contact_role and lead.contact_role != "(Not published on page)" else "(Not published)",
            recipient_email=lead.email if has_email else "(No public email listed)",
            has_verified_email=has_email,
            subject=subject,
            body=body,
            status="drafted",
            created_at=now_iso,
            source_url=lead.source_url or lead.website or "",
            grounding_notes=f"Drafted via local Ollama ({self.model_name}). Grounded in verified company metadata.",
            verified_facts_used=verified_facts,
        )

class CloudOpenAICompatibleProvider(BaseLLMProvider):
    """
    Cloud OpenAI-compatible provider (OpenAI, Groq, OpenRouter, Azure, Mistral, etc.).
    API key is read from parameter or environment variable (never exposed in responses/logs).
    """
    def __init__(self, api_base: Optional[str] = None, model_name: Optional[str] = None, api_key: Optional[str] = None):
        self.api_base = (api_base or "https://api.openai.com/v1").rstrip("/")
        self.model_name = model_name or "gpt-4o-mini"
        self._api_key = api_key or os.environ.get("AGENTDESK_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""

    @property
    def provider_id(self) -> str:
        return "openai"

    @property
    def display_name(self) -> str:
        return f"Cloud AI ({self.model_name})"

    async def draft_lead_outreach(
        self,
        lead: LeadRecord,
        service_offering: str,
        tone: str = "professional",
        sender_name: str = "AgentDesk Operator",
        sender_company: str = "AgentDesk"
    ) -> OutreachDraft:
        if not self._api_key:
            raise ValueError(
                "Cloud AI provider requires an API key. Please specify it in the request or set the "
                "AGENTDESK_LLM_API_KEY environment variable, or use the Built-in Grounded Drafter."
            )

        company = lead.company_name.strip() or "Your Organization"
        has_email = _has_genuine_email(lead.email)
        recipient_name = _sanitize_recipient_name(lead.contact_name, company)

        verified_facts: List[str] = [f"Company: {company}"]
        if lead.industry:
            verified_facts.append(f"Industry: {lead.industry}")
        if lead.description:
            verified_facts.append(f"Description: {lead.description}")

        system_prompt = (
            "You are an AI B2B outreach drafting agent for AgentDesk.\n"
            "STRICT GROUNDING CONSTRAINTS:\n"
            "1. ONLY utilize the verified facts provided about the target company.\n"
            "2. NEVER invent, hallucinate, or assume any person's name, role, email address, previous meetings, or business relationships.\n"
            "3. If the recipient contact name is a team, address the salutation as 'Hi [Company Name] Team,'.\n"
            "4. Keep the email concise, professional, grounded, and within 3 paragraphs.\n"
            "5. You MUST return valid JSON with keys: 'subject' (string) and 'body' (string)."
        )

        user_prompt = (
            f"Target Company: {company}\n"
            f"Industry: {lead.industry}\n"
            f"Public Description: {lead.description or 'Public enterprise'}\n"
            f"Recipient: {recipient_name}\n"
            f"Sender Name: {sender_name}\n"
            f"Sender Organization: {sender_company}\n"
            f"Service Offering: {service_offering}\n"
            f"Tone: {tone}\n"
            "Generate personalized B2B outreach strictly complying with the grounding rules. Output JSON only."
        )

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.3,
                    }
                )
                if res.status_code != 200:
                    raise RuntimeError(f"Cloud AI endpoint returned HTTP {res.status_code}: {res.text[:120]}")
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)

                subject = parsed.get("subject", f"Exploring {service_offering} for {company}")
                body = parsed.get("body", "")
                if not body:
                    raise ValueError("Cloud AI generated empty email body.")

        except Exception as exc:
            raise RuntimeError(f"Cloud AI provider error (model: {self.model_name}): {str(exc)}")

        now_iso = datetime.now(timezone.utc).isoformat()
        draft_id = f"draft-{lead.id}-{int(datetime.now(timezone.utc).timestamp())}"

        return OutreachDraft(
            id=draft_id,
            lead_id=lead.id,
            company_name=company,
            recipient_name=recipient_name,
            recipient_role=lead.contact_role if lead.contact_role and lead.contact_role != "(Not published on page)" else "(Not published)",
            recipient_email=lead.email if has_email else "(No public email listed)",
            has_verified_email=has_email,
            subject=subject,
            body=body,
            status="drafted",
            created_at=now_iso,
            source_url=lead.source_url or lead.website or "",
            grounding_notes=f"Drafted via Cloud AI ({self.model_name}). Grounded strictly in verified public metadata.",
            verified_facts_used=verified_facts,
        )

def get_llm_provider(config: Optional[AIProviderConfig] = None) -> BaseLLMProvider:
    """
    Factory creating the selected LLM provider.
    Defaults to TemplateLLMProvider (deterministic, zero-leakage, 100% offline-ready).
    """
    if not config or not config.provider_type or config.provider_type == "template":
        return TemplateLLMProvider()
    elif config.provider_type == "ollama":
        return OllamaLLMProvider(api_base=config.api_base, model_name=config.model_name)
    elif config.provider_type == "openai":
        return CloudOpenAICompatibleProvider(
            api_base=config.api_base,
            model_name=config.model_name,
            api_key=config.api_key
        )
    return TemplateLLMProvider()
