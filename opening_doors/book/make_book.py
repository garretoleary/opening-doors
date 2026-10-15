"""Writes accounts.json. Every company, person, signal and number here is invented.
No name is a real firm. Run: python -m opening_doors.book.make_book
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).with_name("accounts.json")

# name, sector, hq, employees, people [(name, role)], signals [(kind, text, date)], how staff access systems today (invented, no sign-in details)
RAW = [
    ("Harrowgate Lumen", "Commercial lighting and building controls", "Leeds, UK", 8200,
     [("Priya Oduya-Marsh", "COO, joined September 2026"), ("Tomasz Reardon", "Head of IT")],
     [("new executive", "New COO started 1 September; first 100 days plan mentions 'one login for every site'", "2026-09-01"),
      ("hiring", "Two open roles: Identity Engineer, IAM Programme Lead", "2026-10-02")],
     "Mixed: on-prem directory plus three cloud apps each with their own logins"),
    ("Veldstone Marine", "Port logistics and ship servicing", "Southampton, UK", 11400,
     [("Ingrid Fallowmere", "CIO"), ("Dafydd Okonkwo-Price", "Finance Director")],
     [("ERP replatform", "Board minutes: ERP replatform approved, go-live target Q3 2027", "2026-09-18"),
      ("contractor surge", "Contractor headcount up 40% for the replatform", "2026-10-06")],
     "Legacy directory; contractors onboarded by email and spreadsheet"),
    ("Quillon Health", "Private diagnostics clinics", "Manchester, UK", 6300,
     [("Dr Rosalind Achterberg", "Chief Medical Information Officer"), ("Marcus Vellacott", "CISO, appointed July 2026")],
     [("hiring", "Three open identity roles posted in one week", "2026-10-08"),
      ("regulation", "Clinical records audit due March 2027; access reviews flagged last year", "2026-08-20")],
     "Shared ward logins; access reviews done by hand twice a year"),
    ("Brackwater Foods", "Chilled food manufacturing", "Norwich, UK", 9700,
     [("Helena Thorsby-Kane", "Group CFO"), ("Obi Lansdowne", "IT Director")],
     [("acquisition", "Acquisition of a 1,800-person bakery group closed 30 September; integration starts now", "2026-09-30")],
     "Two directories after the acquisition, no plan yet to merge them"),
    ("Orrin & Tave", "Insurance broking", "Bristol, UK", 4800,
     [("Celestine Marrow", "Chief Operating Officer"), ("Kwame Ashdown", "Head of Technology")],
     [("RFP", "Cloud migration RFP issued; identity and access listed as workstream 2", "2026-10-05")],
     "Data centre directory, VPN for everyone, no single sign-on"),
    ("Pellmoor Rail Services", "Rail maintenance contractor", "Derby, UK", 7600,
     [("Gareth Ilunga-Price", "Managing Director"), ("Sunita Fairweather", "CISO")],
     [("incident", "Credential-stuffing incident disclosed to regulator; no data loss claimed", "2026-09-12")],
     "Password-only logins for field staff on shared tablets"),
    ("Caskellon Energy", "Regional gas and power retailer", "Glasgow, UK", 5900,
     [("Fenwick Adebayo-Ross", "CEO"), ("Lorna Quist", "CIO")],
     [("new executive", "New CIO, previously ran a cloud-first programme at a larger utility", "2026-08-15"),
      ("expansion", "Entering the Irish market in 2027; 400 new hires planned", "2026-10-01")],
     "Cloud directory for head office, legacy for call centres"),
    ("Tarnbeck Logistics", "Parcel and pallet network", "Warrington, UK", 14200,
     [("Ravi Blackwood-Nair", "COO"), ("Imogen Castellane", "Head of Security")],
     [("SaaS sprawl", "Internal audit counted 212 SaaS apps, 140 outside IT control", "2026-09-25")],
     "SSO for 30 apps; the rest are individual logins"),
    ("Mirrenhall Group", "Student accommodation operator", "Edinburgh, UK", 4300,
     [("Alasdair Penhaligon-Osei", "Finance Director"), ("Bea Trantham", "IT Manager")],
     [("hiring", "First ever Head of Information Security role advertised", "2026-10-09")],
     "One shared admin account per building"),
    ("Dunwold Civil", "Civil engineering contractor", "Birmingham, UK", 12800,
     [("Margarethe Olufemi-Stroud", "Group CIO"), ("Callum Reinholt", "Programme Director")],
     [("merger", "Merger with a 5,000-person rival announced; completion expected January 2027", "2026-10-03")],
     "Two of everything; identity named as a day-one integration risk"),
    ("Sablefern Pharma Services", "Contract pharmaceutical manufacturing", "Macclesfield, UK", 6800,
     [("Dr Yusuf Carrowmore", "VP Quality"), ("Nadia Ellsworth-Bai", "Head of IT")],
     [("regulation", "Regulator inspection noted shared credentials on the shop floor", "2026-09-08")],
     "Shared badge logins on production lines"),
    ("Lantergate Retail", "Homeware chain, 190 stores", "Nottingham, UK", 15600,
     [("Siobhan Marchetti-Oyelaran", "Chief Digital Officer"), ("Piers Haldane", "CISO")],
     [("new executive", "New CDO, hired to 'join up online and store'", "2026-09-20"),
      ("seasonal", "9,000 seasonal staff to onboard by mid-November", "2026-10-10")],
     "Store staff share tills and logins; head office on cloud SSO"),
    ("Corvane Aerospace Components", "Precision parts for aircraft", "Preston, UK", 5200,
     [("Henrietta Ashby-Kalu", "Managing Director"), ("Declan Morrowfield", "Head of Compliance")],
     [("regulation", "Defence supply-chain accreditation renewal due June 2027, identity controls in scope", "2026-08-28")],
     "On-prem only, no multi-factor outside IT"),
    ("Whitlowe Water", "Regional water utility", "Exeter, UK", 4600,
     [("Oluwaseun Trevithick", "CIO"), ("Mairead Konstantin", "Head of OT Security")],
     [("incident", "Phishing campaign reached operations staff; disclosed in annual report", "2026-09-30")],
     "Separate identity for office and operations networks"),
    ("Greyhallow Media", "Regional news and radio group", "Cardiff, UK", 4100,
     [("Jonah Petrakis-Lowe", "CEO"), ("Freya Abernethy", "Head of Technology")],
     [("restructure", "Three newsrooms merged into one hub; 600 roles changing", "2026-10-07")],
     "Each title has its own systems and logins"),
    ("Ashcombe Dental Partners", "Dental practice group, 310 sites", "Reading, UK", 7100,
     [("Dr Amara Fitzwilliam-Sen", "Clinical Director"), ("Rupert Olawale", "COO")],
     [("acquisition", "Buying 40 practices a year; each arrives with its own IT", "2026-09-15")],
     "Practice-level logins; no central directory"),
    ("Stornbridge Capital Partners", "Asset management", "London, UK", 4400,
     [("Theodora Nkemelu-Vance", "Chief Risk Officer"), ("Hamish Delacroix", "CISO")],
     [("regulation", "Operational resilience deadline March 2027; access control a named gap", "2026-09-22")],
     "Cloud SSO in place; privileged access still manual"),
    ("Fellbrook Automotive Retail", "Car dealership group", "Leicester, UK", 8900,
     [("Benedict Oyelowo-Hart", "Group IT Director"), ("Carys Lindqvist", "Finance Director")],
     [("cost", "Board asked for 15% IT cost cut; 60 overlapping tools identified", "2026-10-04")],
     "Four directories after four acquisitions"),
    ("Morrowick Care Homes", "Residential care operator", "Sheffield, UK", 13500,
     [("Grace Adeyemi-Thorne", "Chief Operating Officer"), ("Leon Starkadder", "Head of Digital")],
     [("hiring", "Agency staff now 30% of shifts; onboarding takes four days", "2026-09-27")],
     "Paper sign-in sheets for agency staff systems access"),
    ("Kestrelmoor Construction", "Housebuilder", "Milton Keynes, UK", 6200,
     [("Vikram Ashdown-Reilly", "CFO"), ("Elspeth Nwachukwu", "IT Director")],
     [("new executive", "New CFO from a listed competitor; known for digital spend reviews", "2026-09-05")],
     "Site offices on local accounts"),
    ("Haverlane Education Trust", "Multi-academy trust, 48 schools", "Leeds, UK", 5100,
     [("Dr Ngozi Bramblecote", "Chief Executive"), ("Oliver Sandqvist", "Head of IT")],
     [("regulation", "Safeguarding review called for named-user access in every school", "2026-10-01")],
     "Shared staff-room logins at most schools"),
    ("Tollwick Chemicals", "Specialty chemicals", "Middlesbrough, UK", 4900,
     [("Annika Berglund-Oyo", "Site Director"), ("Fergus Mallinder", "Head of IT")],
     [("expansion", "New plant in Teesside; 700 hires over 18 months", "2026-09-10")],
     "On-prem directory, multi-factor for remote only"),
    ("Brindlemere Hospitality", "Hotels and pubs, 220 sites", "York, UK", 16800,
     [("Cassius Ferreira-Blythe", "Chief Operating Officer"), ("Tamsin Oyelaran", "IT Director")],
     [("SaaS sprawl", "Rota, till, and booking systems all have separate staff logins; 40% turnover", "2026-09-29")],
     "No central identity; general managers create accounts"),
    ("Ravensholt Engineering Group", "Industrial pumps and valves", "Huddersfield, UK", 19200,
     [("Katarzyna Umeh-Fairfax", "Group CIO"), ("Dominic Alderley", "CISO")],
     [("cloud", "Board approved 'cloud by 2028'; identity programme to start Q1 2027", "2026-10-02")],
     "Large on-prem estate; cloud pilot in one division"),
    ("Pennywhistle Logistics", "Food distribution to restaurants", "Bradford, UK", 7300,
     [("Jude Harrowell-Mensah", "Managing Director"), ("Sally Varndean", "Head of IT")],
     [("incident", "Ransomware at a competitor prompted a board question on access", "2026-10-11")],
     "Warehouse PCs on shared logins"),
]

assert len(RAW) == 25, len(RAW)

ICP = {
    "name": "Ideal client profile (invented, for the demo)",
    "size": "4,000 to 20,000 employees",
    "geography": "UK headquartered",
    "fit": [
        "many frontline, contractor or agency staff who share logins today",
        "a live trigger in the last 90 days: new executive, merger or acquisition, regulation, incident, replatform or RFP",
        "a named economic buyer at COO, CIO, CFO or CISO level",
        "more than one directory or identity set-up after acquisitions",
    ],
    "avoid": ["no trigger in the last 90 days", "central single sign-on already covering frontline staff"],
}

def build() -> dict:
    accounts = []
    for i, (name, sector, hq, employees, people, signals, identity) in enumerate(RAW, start=1):
        accounts.append({
            "id": f"acc-{i:02d}",
            "name": name,
            "sector": sector,
            "hq": hq,
            "employees": employees,
            "relationship": "none",
            "people": [{"name": n, "role": r} for n, r in people],
            "signals": [{"kind": k, "text": t, "date": d} for k, t, d in signals],
            "access_setup_today": identity,
            "invented": True,
        })
    return {
        "notice": "All data invented. Every company, person, signal and number is made up. No name is a real firm.",
        "as_of": "2026-10-15",
        "icp": ICP,
        "accounts": accounts,
    }

if __name__ == "__main__":
    OUT.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} with {len(RAW)} accounts")
