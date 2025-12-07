"""
Patent Pipeline Configuration
All settings and API credentials in one place
"""

import os
from pathlib import Path

# =============================================================================
# PATHS
# =============================================================================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = DATA_DIR / "logs"

# Master output file
MASTER_FILE = DATA_DIR / "master_patents.xlsx"

# State file (tracks last run, processed IDs, etc.)
STATE_FILE = DATA_DIR / "pipeline_state.json"

# =============================================================================
# API CREDENTIALS
# =============================================================================

# EPO OPS API
EPO_CONSUMER_KEY = os.environ.get("EPO_CONSUMER_KEY", "3WzKqrKkYBymV5nyBwP7GnbviY05Sw2Yb8GHZ5btxt1AYGPD")
EPO_CONSUMER_SECRET = os.environ.get("EPO_CONSUMER_SECRET", "J6Q3JIOh2iW7O4frxNCw7feo8ENYu2j7j0ey0fI9cs6hYfqXAQ7nGq2K7EteUkAG")

# Lens.org API
LENS_API_TOKEN = os.environ.get("LENS_API_TOKEN", "O3QvWqvS0lh9oIrq5YJVpLUkjrZf4oJHXvWldEdl5E9D8lmD8COC")

# =============================================================================
# LENS API SETTINGS
# =============================================================================
LENS_API_URL = "https://api.lens.org/patent/search"

# Search query for Qatar patents (Lens uses different syntax)
# Broad search to capture ALL Qatar-related patents:
# - applicant.name:Qatar (organizations with "Qatar" in name)
# - applicant.residence:QA (applicants from Qatar)
# - inventor.residence:QA (inventors from Qatar)
# Filtering for organizations vs individuals happens in the extractor
LENS_SEARCH_QUERY = {
    "query": {
        "bool": {
            "should": [
                {"query_string": {"query": "applicant.name:Qatar"}},
                {"query_string": {"query": "applicant.residence:QA"}},
                {"query_string": {"query": "inventor.residence:QA"}}
            ],
            "minimum_should_match": 1
        }
    },
    "size": 100,
    "from": 0,
    "include": [
        "lens_id",
        "jurisdiction",
        "doc_number",
        "kind",
        "date_published",
        "biblio",
        "abstract",
        "legal_status"
    ]
}

# Keywords that indicate an organization (not an individual)
ORGANIZATION_KEYWORDS = [
    'university', 'univ', 'college', 'institute', 'institution',
    'foundation', 'corporation', 'corp', 'company', 'co',
    'hospital', 'medical', 'medicine', 'clinic', 'health',
    'research', 'laboratory', 'lab', 'center', 'centre',
    'authority', 'ministry', 'government', 'council',
    'bank', 'petroleum', 'oil', 'gas', 'energy',
    'qatar', 'qf', 'qu', 'hbku', 'hmc', 'sidra',
    'texas a&m', 'weill cornell', 'carnegie mellon', 'northwestern',
    'georgetown', 'virginia commonwealth', 'north atlantic',
    'iberdrola', 'maersk', 'exxon', 'shell', 'total',
    'llc', 'ltd', 'inc', 'plc', 'sa', 'as', 'ag',
    'gmbh', 'bv', 'nv', 'spa', 'srl',
]

# Known Qatar organizations (exact matches after standardization)
QATAR_ORGANIZATIONS = [
    'Qatar Foundation for Education, Science and Community Development',
    'Qatar University',
    'Hamad Medical Corporation',
    'Sidra Medicine',
    'Hamad Bin Khalifa University',
    'Texas A&M University at Qatar',
    'Weill Cornell Medicine-Qatar',
    'Carnegie Mellon University in Qatar',
    'Northwestern University in Qatar',
    'Georgetown University in Qatar',
    'Virginia Commonwealth University in Qatar',
    'College of the North Atlantic Qatar',
    'University of Doha for Science and Technology',
    'Qatar Petroleum',
    'Qatar Energy',
    'Qatar National Research Fund',
    'Qatar Computing Research Institute',
    'Qatar Environment and Energy Research Institute',
    'Qatar Biomedical Research Institute',
    'Qatar Biobank',
    'Qatar Genome Programme',
    'Qatar Investment Authority',
    'Qatar Football Association',
    'Qatar Ministry of Education and Higher Education',
    'Maersk Oil Qatar AS',
    'Iberdrola QSTP LLC',
    'Anti-Doping Lab Qatar',
    'Qatar Fertiliser Company',
    'Qatar Airways',
    'Qatar National Bank',
    'Ooredoo',
    'Kahramaa',
    'Ashghal',
    'Qatar Rail',
    'Qatar Museums',
    'Qatar Science and Technology Park',
    'QSTP',
]

LENS_MAX_RESULTS = 5000
LENS_BATCH_SIZE = 100
LENS_DELAY_BETWEEN_BATCHES = 1.0  # Lens has stricter rate limits

# =============================================================================
# EPO API SETTINGS
# =============================================================================
EPO_AUTH_URL = "https://ops.epo.org/3.2/auth/accesstoken"
EPO_SEARCH_URL = "https://ops.epo.org/3.2/rest-services/published-data/search"
EPO_BIBLIO_URL = "https://ops.epo.org/3.2/rest-services/published-data/publication/epodoc"

# Search query for Qatar patents
EPO_SEARCH_QUERY = "pa=Qatar"
EPO_MAX_RESULTS = 5000
EPO_BATCH_SIZE = 100

# Rate limiting
EPO_REQUESTS_PER_SECOND = 10
EPO_DELAY_BETWEEN_BATCHES = 0.5

# =============================================================================
# DATA STANDARDIZATION RULES
# =============================================================================

# Institution name standardization mapping
# Order matters! More specific patterns should come before general ones
INSTITUTION_STANDARDS = {
    # =========================================================================
    # QATAR FOUNDATION - all variations (most common)
    # =========================================================================
    r'qatar\s*found.*education.*science.*community.*dev.*': 'Qatar Foundation for Education, Science and Community Development',
    r'qatar\s*found.*education.*science.*community': 'Qatar Foundation for Education, Science and Community Development',
    r'qatar\s*found.*science.*education.*community': 'Qatar Foundation for Education, Science and Community Development',
    r'qatar\s*found.*science.*education.*social': 'Qatar Foundation for Education, Science and Community Development',
    r'qatar\s*found.*for\s*science\s*education': 'Qatar Foundation for Education, Science and Community Development',
    r'qatar\s*found.*education.*science.*': 'Qatar Foundation for Education, Science and Community Development',
    r'qatar\s*found.*science.*community': 'Qatar Foundation for Education, Science and Community Development',
    r'qatar\s*foundation\s*for\s*education': 'Qatar Foundation for Education, Science and Community Development',
    r'qatar\s*foundation\s*for\s*ed\.?\s*science': 'Qatar Foundation for Education, Science and Community Development',
    r'^qatar\s*foundation\s*,?\s*$': 'Qatar Foundation for Education, Science and Community Development',
    r'^qatar\s*found\.?\s*,?\s*$': 'Qatar Foundation for Education, Science and Community Development',
    r'^qatar\s*found\s+for\s+': 'Qatar Foundation for Education, Science and Community Development',
    r'qatar\s*founation': 'Qatar Foundation for Education, Science and Community Development',  # typo
    r'qatar\s*foundatiion': 'Qatar Foundation for Education, Science and Community Development',  # typo
    r'qatar\s*foundat?ion': 'Qatar Foundation for Education, Science and Community Development',  # typo
    r'qator\s*found': 'Qatar Foundation for Education, Science and Community Development',  # typo
    r'qf\s*for\s*education': 'Qatar Foundation for Education, Science and Community Development',
    r'^qatar\s+found\s*$': 'Qatar Foundation for Education, Science and Community Development',

    # =========================================================================
    # QATAR MINISTRY OF EDUCATION AND HIGHER EDUCATION
    # =========================================================================
    r'qatar\s*mini.*education.*higher': 'Qatar Ministry of Education and Higher Education',
    r'qatar\s*ministry.*education.*higher': 'Qatar Ministry of Education and Higher Education',
    r'qatar\s*ministry\s*of\s*education': 'Qatar Ministry of Education and Higher Education',
    r'qatar\s*mini.*of.*education': 'Qatar Ministry of Education and Higher Education',  # typo: mini instead of ministry
    r'ministry.*education.*qatar': 'Qatar Ministry of Education and Higher Education',
    r'^moe\s*qatar': 'Qatar Ministry of Education and Higher Education',
    r'^moehe\s*$': 'Qatar Ministry of Education and Higher Education',

    # =========================================================================
    # QATAR UNIVERSITY - all variations
    # =========================================================================
    r'^univ\.?\s*qatar': 'Qatar University',
    r'^qatar\s*university\s*qstp.*': 'Qatar University',
    r'^qatar\s*university\s*,?\s*$': 'Qatar University',
    r'^qatar\s*univ\.?\s*': 'Qatar University',
    r'^quatar\s*univ': 'Qatar University',  # typo
    r'qatar\s*university\s*global\s*patent': 'Qatar University',
    r'qatar\s*university\s*office': 'Qatar University',
    r'qatar\s*university\s*al\s*tarfa': 'Qatar University',
    r'^qu\s*qstp': 'Qatar University',

    # =========================================================================
    # HAMAD MEDICAL CORPORATION
    # =========================================================================
    r'hamad\s*med.*corp': 'Hamad Medical Corporation',
    r'^hamad\s*medical\s*$': 'Hamad Medical Corporation',
    r'^hmc\s*$': 'Hamad Medical Corporation',

    # =========================================================================
    # SIDRA MEDICINE / SIDRA MEDICAL
    # =========================================================================
    r'^sidra\s*med.*': 'Sidra Medicine',
    r'^sidra\s*research': 'Sidra Medicine',

    # =========================================================================
    # HAMAD BIN KHALIFA UNIVERSITY
    # =========================================================================
    r'hamad\s*bin\s*khalifa\s*univ.*': 'Hamad Bin Khalifa University',
    r'^hbku\s*$': 'Hamad Bin Khalifa University',

    # =========================================================================
    # QATAR FOOTBALL ASSOCIATION
    # =========================================================================
    r'qatar\s*football\s*ass.*': 'Qatar Football Association',
    r'^qfa\s*$': 'Qatar Football Association',

    # =========================================================================
    # MAERSK OIL QATAR
    # =========================================================================
    r'maersk\s*oil\s*qatar.*': 'Maersk Oil Qatar AS',
    r'^maersk\s*qatar': 'Maersk Oil Qatar AS',

    # =========================================================================
    # COLLEGE OF NORTH ATLANTIC QATAR
    # =========================================================================
    r'college.*north\s*atlantic.*qatar': 'College of the North Atlantic Qatar',
    r'^cna\s*qatar': 'College of the North Atlantic Qatar',
    r'^cna-q': 'College of the North Atlantic Qatar',

    # =========================================================================
    # TEXAS A&M UNIVERSITY AT QATAR
    # =========================================================================
    r'texas\s*a\s*&?\s*m\s*univ.*': 'Texas A&M University at Qatar',
    r'^tamu\s*qatar': 'Texas A&M University at Qatar',
    r'^tamuq': 'Texas A&M University at Qatar',

    # =========================================================================
    # WEILL CORNELL MEDICINE-QATAR
    # =========================================================================
    r'weill\s*cornell.*': 'Weill Cornell Medicine-Qatar',
    r'^wcm-?q': 'Weill Cornell Medicine-Qatar',

    # =========================================================================
    # NORTHWESTERN UNIVERSITY IN QATAR
    # =========================================================================
    r'northwestern.*qatar': 'Northwestern University in Qatar',
    r'^nu-?q': 'Northwestern University in Qatar',

    # =========================================================================
    # CARNEGIE MELLON UNIVERSITY IN QATAR
    # =========================================================================
    r'carnegie\s*mellon.*': 'Carnegie Mellon University in Qatar',
    r'^cmu-?q': 'Carnegie Mellon University in Qatar',

    # =========================================================================
    # GEORGETOWN UNIVERSITY IN QATAR
    # =========================================================================
    r'georgetown.*qatar': 'Georgetown University in Qatar',
    r'^gu-?q': 'Georgetown University in Qatar',

    # =========================================================================
    # VIRGINIA COMMONWEALTH UNIVERSITY IN QATAR
    # =========================================================================
    r'virginia\s*commonwealth.*qatar': 'Virginia Commonwealth University in Qatar',
    r'^vcu-?q': 'Virginia Commonwealth University in Qatar',

    # =========================================================================
    # UNIVERSITY OF DOHA FOR SCIENCE AND TECHNOLOGY
    # =========================================================================
    r'university\s*of\s*doha': 'University of Doha for Science and Technology',
    r'^udst': 'University of Doha for Science and Technology',

    # =========================================================================
    # OTHER QATAR ORGANIZATIONS
    # =========================================================================
    r'qatar\s*fertiliser': 'Qatar Fertiliser Company',
    r'anti.*doping.*qatar': 'Anti-Doping Lab Qatar',
    r'qatar\s*invest.*authority': 'Qatar Investment Authority',
    r'^qia\s*$': 'Qatar Investment Authority',
    r'qatar\s*petroleum': 'Qatar Petroleum',
    r'^qp\s*$': 'Qatar Petroleum',
    r'qatar\s*energy': 'Qatar Energy',
    r'qatar\s*national\s*research\s*fund': 'Qatar National Research Fund',
    r'^qnrf\s*$': 'Qatar National Research Fund',
    r'qatar\s*biobank': 'Qatar Biobank',
    r'qatar\s*genome': 'Qatar Genome Programme',
    r'qatar\s*computing\s*research': 'Qatar Computing Research Institute',
    r'^qcri\s*$': 'Qatar Computing Research Institute',
    r'qatar\s*environment.*energy': 'Qatar Environment and Energy Research Institute',
    r'^qeeri\s*$': 'Qatar Environment and Energy Research Institute',
    r'qatar\s*biomedical\s*research': 'Qatar Biomedical Research Institute',
    r'^qbri\s*$': 'Qatar Biomedical Research Institute',
    r'iberdrola\s*qstp': 'Iberdrola QSTP LLC',
}

# Known organizations (for filtering individuals)
KNOWN_ORGANIZATIONS = [
    'Qatar Foundation for Education, Science and Community Development',
    'Qatar University',
    'Hamad Medical Corporation',
    'Sidra Medicine',
    'Hamad Bin Khalifa University',
    'Qatar Football Association',
    'Maersk Oil Qatar AS',
    'College of the North Atlantic Qatar',
    'Texas A&M University at Qatar',
    'Weill Cornell Medicine-Qatar',
    'Northwestern University in Qatar',
    'Carnegie Mellon University in Qatar',
    'University of Doha for Science and Technology',
    'Qatar Fertiliser Company',
    'Anti-Doping Lab Qatar',
    'Qatar Investment Authority',
    'Qatar Petroleum',
    'Qatar Energy',
    'Iberdrola QSTP LLC',
    'Qatar Ministry of Education and Higher Education',
    'Qatar National Research Fund',
    'Qatar Computing Research Institute',
    'Qatar Environment and Energy Research Institute',
    'Qatar Biomedical Research Institute',
    'Qatar Biobank',
    'Qatar Genome Programme',
]

# Garbage fragments to remove (incomplete or duplicate name parts)
GARBAGE_FRAGMENTS = [
    r'^science\s*(and|&)?\s*community.*$',
    r'^education\s*(and|&)?\s*science.*$',
    r'^community\s*development.*$',
    r'^social\s*development.*$',
    r'^higher\s*education.*$',
    r'^(and|&)\s+\w+.*$',
    r'^for\s+\w+.*$',
]

# =============================================================================
# OUTPUT FORMAT (matches CurrentIPs format)
# =============================================================================
OUTPUT_COLUMNS = [
    'ResourceId',
    'ApplicationNumber',
    'ApplicationDate',
    'PatentYear',
    'Title',
    'Abstract',
    'Applicants',
    'Inventors',
    'Owners',
    'PatentUrl',
    'DocumentTypeId',
    'DocumentTypeName',
    'LegalStatusName',
    'Source',  # EPO, Lens, WIPO, etc.
    'ExtractedDate',  # When we extracted this record
]
