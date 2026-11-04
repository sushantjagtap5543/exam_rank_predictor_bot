"""
Force Agents Architecture for ExamRankers India:
Autonomous senior-level specialist agents for exam branding, content generation,
digital products packaging, conversion marketing, and automated fulfillment.
"""

from .base_agent import BaseSeniorAgent
from .channel_branding_agent import ChannelBrandingAgent
from .content_faculty_agents import (
    MarathiSeniorFaculty,
    EnglishSeniorFaculty,
    MathsReasoningSeniorFaculty,
    CurrentAffairsSeniorEditor,
)
from .digital_product_agent import DigitalProductPackagingAgent
from .marketing_sales_agent import MarketingSalesAgent
from .fulfillment_email_agent import FulfillmentEmailAgent

__all__ = [
    "BaseSeniorAgent",
    "ChannelBrandingAgent",
    "MarathiSeniorFaculty",
    "EnglishSeniorFaculty",
    "MathsReasoningSeniorFaculty",
    "CurrentAffairsSeniorEditor",
    "DigitalProductPackagingAgent",
    "MarketingSalesAgent",
    "FulfillmentEmailAgent",
]

