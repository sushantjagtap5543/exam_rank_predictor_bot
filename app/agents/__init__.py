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

# Executive Leadership & AI Department Managers
from .executive_agents import (
    ChiefExecutiveOfficer,
    AILeadDirector,
    AcademicDeanManager,
    GrowthMarketingManager,
    CommerceOperationsManager,
)

# Research & Intelligence Division
from .research_agents import (
    ExamIntelligenceResearcher,
    CurriculumResearchSynthesist,
)

# Design & UI/UX Division
from .design_uiux_agents import (
    UIUXDesignArchitect,
    BrandVisualsDesigner,
)

# Academic Faculty Division
from .content_faculty_agents import (
    MarathiSeniorFaculty,
    EnglishSeniorFaculty,
    MathsReasoningSeniorFaculty,
    CurrentAffairsSeniorEditor,
)

# Operations, Branding & Commerce
from .channel_branding_agent import ChannelBrandingAgent
from .digital_product_agent import DigitalProductPackagingAgent, DEFAULT_PRODUCTS
from .marketing_sales_agent import MarketingSalesAgent
from .fulfillment_email_agent import FulfillmentEmailAgent

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
