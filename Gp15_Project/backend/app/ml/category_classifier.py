

import re

CATEGORIES = {
    "meeting": [
        r"\bmeeting\b", r"\bcall\b", r"\bconference\b",r"\bvideo meeting\b", r"\bdiscussion\b",r"\follow[- ]?up\b",
        r"\bsync\b", r"\bcatch up\b", r"\bvideo call\b", r"\bzoom\b", r"\bteams\b", r"\bcalendar\b", r"\bschedule\b",
        r"\bappointment\b", r"\bwebinar\b", r"\bworkshop\b", r"\btraining\b", r"\bagenda\b", r"\bminutes\b",r"\breschedule\b", r"\bfollow up\b"
    ],
    "task": [
        r"\bplease\b.*\b(send|review|update|complete)\b",
        r"\baction required\b", r"\bkindly\b",
        r"\bassigned\b", r"\bto-do\b"
    ],
    "deadline": [
        r"\bdeadline\b", r"\bdue\b", r"\bsubmit\b",
        r"\bEOD\b", r"\bend of day\b"
    ],
    "hr": [
        r"\bsalary\b", r"\bpayroll\b", r"\bpolicy\b",
        r"\bHR\b", r"\bleave\b", r"\bholiday\b"
    ],
    "recruitment": [
        r"\bjob\b", r"\bopening\b", r"\bhiring\b",
        r"\brecruitment\b", r"\bposition\b", r"\bcareer\b"
    ],
    "finance": [
        r"\binvoice\b", r"\bpayment\b", r"\bbudget\b",
        r"\bfinance\b", r"\btransaction\b"
    ],
    "notification": [
        r"\balert\b", r"\bverification\b",
        r"\bsecurity\b", r"\bcongratulations\b",
        r"\bupdate\b"
    ],
    "marketing": [
        r"\boffer\b", r"\bdiscount\b", r"\bpromotion\b",
        r"\bmarketing\b", r"\bsale\b"
    ],
    
    "linkedin": [
        r"\blinkedin\b", 
        # r"\bconnection\b", r"\bendorsement\b",r"\brecommend\b",r"\bviews\b",
        # r"\brecommendation\b", r"\bprofile\b", r"\bnetwork\b",r"\bmessage\b", r"\bcontact\b", r"\bjob\b", r"\bopportunity\b"
    ],
    "presentation": [
        r"\bpresentation\b", r"\bdeck\b", r"\bslides\b",
        r"\bpitch\b", r"\breport\b", r"\bproposal\b",r"\breschedul\b", r"\bpostpone\b", r"\bdelay\b"
    ],
    "office": [
        r"\bprinter\b", r"\bmaintenance\b", r"\bfacility\b",
        r"\boffice\b", r"\bworkspace\b", r"\bcleaning\b"
    ],
    "files":[
        r"\bfile\b", r"\bdocument\b", r"\battachment\b",r"\battached\b",r"\bFolder\b",r"\bShared\b"
        r"\bpdf\b", r"\bword\b", r"\bppt\b",r"\bspreadsheet\b", r"\bdrive\b", r"\bshare\b", r"\baccess\b", r"\bpermission\b",
        r"\bversion\b", r"\brevision\b", r"\bupdate\b",r"\bscreenshot\b", r"\bphoto\b", r"\bimage\b",r"\bfolder\b",r"\bdrive\b",r"\bshared\b"
        r"\bcontribute\b",r"\bshared with you\b",r"\bfiles\b",r"\brelated to\b"
    ]
}

def detect_category(text: str) -> str:
    text = text.lower()

    for category, patterns in CATEGORIES.items():
        for pattern in patterns:
            if re.search(pattern, text):
                return category

    return "none"
