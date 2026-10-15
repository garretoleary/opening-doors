"""Writes call_notes.json: one invented first-call note per account, as the AE might type it
after a fifteen-minute call. Every person, quote and number is invented.
Run: python -m opening_doors.book.make_call_notes
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).with_name("call_notes.json")

NOTES = {
    "acc-01": "Spoke to Priya Oduya-Marsh (COO) for 15 min. Confirms 'one login for every site' is in her 100-day plan, due mid December. Pain: leavers keep access in the cloud apps for weeks; two near misses this quarter. Metric she liked: share of sites and apps on one login, 0% today. Budget sits with her; the CFO signs anything over a set threshold. Ruaridh Okafor-Lindley (Head of IT) will run delivery and is keen. She wants a plan she can show the board in November. Asked who else should be in: she said the CFO and the head of HR.",
    "acc-02": "Call with Ingrid Fallowmere (CIO). ERP replatform approved; contractors up 40% and onboarding them by spreadsheet is the sore point. Wants contractor access sorted before the replatform build starts in January. Finance Director Dafydd Okonkwo-Price owns the replatform budget. No formal process yet; steering group meets monthly.",
    "acc-03": "Marcus Vellacott (CISO, new) on the phone. Clinical records audit in March 2027; last year's access reviews were done by hand and flagged. Three identity roles open and unfilled. Dr Achterberg (CMIO) is the clinical voice and must be in the room. Budget request goes to the board in January.",
    "acc-04": "Obi Lansdowne (IT Director). Bakery group acquisition closed 30 September; two directories and no plan to merge. Group CFO Helena Thorsby-Kane wants integration costs visible by Q1. Pain: duplicate accounts and a payroll error traced to a mismatched identity. Wants a 90-day integration view.",
    "acc-05": "Kwame Ashdown (Head of Technology). Cloud migration RFP out; identity is workstream 2 and has no owner yet. COO Celestine Marrow chairs the RFP panel. Shortlist decided before Christmas. Pain: VPN for everyone and password resets eat the service desk.",
    "acc-06": "Sunita Fairweather (CISO). Credential-stuffing incident reported to the regulator; MD Gareth Ilunga-Price wants a fix before the next board. Field staff on shared tablets with passwords only. Regulator follow-up in 60 days. Budget available this year if the plan is credible.",
    "acc-07": "Lorna Quist (CIO). Irish entry next year, 400 hires. Call centres still on the legacy directory. CEO Fenwick Adebayo-Ross wants new hires live on day one. Decision by Q1 board; she writes the paper.",
    "acc-08": "Imogen Castellane (Head of Security). Audit found 212 SaaS apps, 140 outside IT. COO Ravi Blackwood-Nair asked for a plan to bring them under control by March. Pain: no view of who has what. Wants numbers for the audit committee.",
    "acc-09": "Bea Trantham (IT Manager). First Head of Information Security being hired; Finance Director Alasdair Penhaligon-Osei is sponsor. One shared admin account per building is the known risk. Small budget, quick win wanted before the new hire starts.",
    "acc-10": "Margarethe Olufemi-Stroud (Group CIO). Merger completes January 2027; identity named a day-one risk in the integration plan. Programme Director Callum Reinholt owns the plan; the two boards must agree spend. Wants a joint design agreed before completion.",
    "acc-11": "Nadia Ellsworth-Bai (Head of IT). Regulator noted shared credentials on the shop floor. VP Quality Dr Yusuf Carrowmore owns the response, due at the next inspection in six months. Pain: shift workers share badge logins to save time. Budget from the quality remediation fund.",
    "acc-12": "Piers Haldane (CISO). 9,000 seasonal staff to onboard by mid November; store staff share logins. New CDO Siobhan Marchetti-Oyelaran wants online and store joined up and will sponsor. Metric: hours to first login for a seasonal hire, two days today.",
    "acc-13": "Declan Morrowfield (Head of Compliance). Accreditation renewal June 2027; identity controls in scope and multi-factor missing outside IT. MD Henrietta Ashby-Kalu signs off. Wants a gap list and a dated plan.",
    "acc-14": "Mairead Konstantin (Head of OT Security). Phishing reached operations staff; disclosed in the annual report. CIO Oluwaseun Trevithick wants office and operations identity joined without risking the plant. Regulator interest. Cautious, wants a pilot first.",
    "acc-15": "Freya Abernethy (Head of Technology). Three newsrooms merged into one hub; 600 roles changing and each title has its own logins. CEO Jonah Petrakis-Lowe wants the hub live by February. Pain: journalists locked out when they move desks.",
    "acc-16": "Rupert Olawale (COO). Buying 40 practices a year, each with its own IT. Clinical Director Dr Amara Fitzwilliam-Sen worries about clinicians' access to records across sites. Wants a repeatable 30-day onboarding for each practice. Budget per acquisition.",
    "acc-17": "Hamish Delacroix (CISO). Operational resilience deadline March 2027; privileged access still manual and named as a gap. CRO Theodora Nkemelu-Vance owns the deadline and reports to the board quarterly. Wants evidence for the regulator by January.",
    "acc-18": "Benedict Oyelowo-Hart (Group IT Director). Board wants 15% IT cost cut; four directories after four acquisitions and 60 overlapping tools. Finance Director Carys Lindqvist tracks the savings. Wants a consolidation number he can commit to.",
    "acc-19": "Leon Starkadder (Head of Digital). Agency staff are 30% of shifts and onboarding takes four days on paper. COO Grace Adeyemi-Thorne wants it under one day. Pain: agency nurses without system access on their first shift. Budget from the operations line.",
    "acc-20": "Elspeth Nwachukwu (IT Director). New CFO Vikram Ashdown-Reilly is reviewing digital spend; site offices on local accounts. She wants a case that survives his review. Decision tied to the spring budget.",
    "acc-21": "Oliver Sandqvist (Head of IT). Safeguarding review requires named-user access in every school; most schools share staff-room logins. Chief Executive Dr Ngozi Bramblecote owns the response to the trust board in January. 48 schools, small team.",
    "acc-22": "Fergus Mallinder (Head of IT). New plant and 700 hires over 18 months; multi-factor only for remote. Site Director Annika Berglund-Oyo wants new starters working on day one. Budget inside the plant project.",
    "acc-23": "Tamsin Oyelaran (IT Director). 220 sites, 40% staff turnover, general managers create accounts in three systems. COO Cassius Ferreira-Blythe wants one process. Pain: ex-staff still on the till system. Wants a pilot in 20 sites first.",
    "acc-24": "Dominic Alderley (CISO). 'Cloud by 2028' approved; identity programme starts Q1 2027 and Group CIO Katarzyna Umeh-Fairfax owns it. Large on-prem estate. Wants the design principles settled before the programme starts; procurement will be formal.",
    "acc-25": "Sally Varndean (Head of IT). Ransomware at a competitor prompted a board question on access; warehouse PCs on shared logins. MD Jude Harrowell-Mensah wants an answer for the board in six weeks. Budget modest; wants the first step costed.",
}

assert len(NOTES) == 25

def build() -> dict:
    return {
        "notice": "All data invented. Every call note, person, quote and number here is made up.",
        "as_of": "2026-10-15",
        "notes": [{"id": k, "note": v, "invented": True} for k, v in NOTES.items()],
    }

if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} with {len(NOTES)} notes")
