"""
Force Agents Architecture for ExamRankers India:
Autonomous senior-level specialist agents based on the NEXUS & Agency-Agents standard.

Encompasses:
- Executive Leadership: CEO, AI Lead Director, Department Managers
- Research Division: Exam Intelligence & Curriculum Research
- Design & UI/UX Division: UI/UX Architect & Brand Visuals Designer
- Academic Faculty: Marathi, English, Maths/Reasoning, Current Affairs
- Operational Swarm: Channel Branding, Packaging, Marketing, Fulfillment
"""

from .base_agent import BaseSeniorAgent

# Operations, Branding & Commerce
from .channel_branding_agent import ChannelBrandingAgent

# Academic Faculty Division
from .content_faculty_agents import (
    CurrentAffairsSeniorEditor,
    EnglishSeniorFaculty,
    MarathiSeniorFaculty,
    MathsReasoningSeniorFaculty,
)

# Design & UI/UX Division
from .design_uiux_agents import (
    BrandVisualsDesigner,
    UIUXDesignArchitect,
)
from .digital_product_agent import DEFAULT_PRODUCTS, DigitalProductPackagingAgent

# Executive Leadership & AI Department Managers
from .executive_agents import (
    AcademicDeanManager,
    AILeadDirector,
    ChiefExecutiveOfficer,
    CommerceOperationsManager,
    GrowthMarketingManager,
)
from .fulfillment_email_agent import FulfillmentEmailAgent
from .marketing_sales_agent import MarketingSalesAgent

# Research & Intelligence Division
from .research_agents import (
    CurriculumResearchSynthesist,
    ExamIntelligenceResearcher,
)

__all__ = [
    "BaseSeniorAgent",
    "DEFAULT_PRODUCTS",
    # Executive
    "ChiefExecutiveOfficer",
    "AILeadDirector",
    "AcademicDeanManager",
    "GrowthMarketingManager",
    "CommerceOperationsManager",
    # Research
    "ExamIntelligenceResearcher",
    "CurriculumResearchSynthesist",
    # Design & UI/UX
    "UIUXDesignArchitect",
    "BrandVisualsDesigner",
    # Faculty
    "MarathiSeniorFaculty",
    "EnglishSeniorFaculty",
    "MathsReasoningSeniorFaculty",
    "CurrentAffairsSeniorEditor",
    # Operations
    "ChannelBrandingAgent",
    "DigitalProductPackagingAgent",
    "MarketingSalesAgent",
    "FulfillmentEmailAgent",
]
