"""
CSV Exporter for AgentDesk Lead Records.
"""
import csv
import io
from typing import List
try:
    from .models import LeadRecord
except (ImportError, ValueError):
    from models import LeadRecord

CSV_HEADERS = [
    "ID",
    "Company Name",
    "Contact Name",
    "Contact Role",
    "Email",
    "Website",
    "Industry",
    "Location",
    "Source Note",
    "Created At",
]

def generate_leads_csv(leads: List[LeadRecord]) -> str:
    """
    Serializes a list of LeadRecord items into an RFC 4180 compliant CSV string.
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")

    writer.writerow(CSV_HEADERS)

    for lead in leads:
        writer.writerow([
            lead.id,
            lead.company_name,
            lead.contact_name,
            lead.contact_role,
            lead.email,
            lead.website,
            lead.industry,
            lead.location,
            lead.source_note,
            lead.created_at,
        ])

    return output.getvalue()
