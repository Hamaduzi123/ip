"""
Lens.org API Extractor
Extracts patents from Lens.org patent database
"""

import requests
import time
import json
from datetime import datetime
from typing import List, Dict, Optional
import sys

# Add parent to path for config
sys.path.insert(0, str(__file__).rsplit('\\', 2)[0])
from config import (
    LENS_API_TOKEN, LENS_API_URL, LENS_SEARCH_QUERY,
    LENS_MAX_RESULTS, LENS_BATCH_SIZE, LENS_DELAY_BETWEEN_BATCHES,
    ORGANIZATION_KEYWORDS, QATAR_ORGANIZATIONS
)


class LensExtractor:
    """Extracts patent data from Lens.org API"""

    def __init__(self, logger=None):
        self.api_token = LENS_API_TOKEN
        self.logger = logger
        self.stats = {
            'searched': 0,
            'extracted': 0,
            'errors': 0
        }

    def log(self, message: str, level: str = 'info'):
        """Log a message"""
        if self.logger:
            getattr(self.logger, level)(message)
        print(f"[Lens] {message}")

    def get_headers(self) -> Dict:
        """Get request headers with auth token"""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    def _is_organization(self, name: str) -> bool:
        """
        Check if a name appears to be an organization (not an individual)

        Args:
            name: The applicant/owner name to check

        Returns:
            True if it looks like an organization, False if it looks like an individual
        """
        if not name:
            return False

        name_lower = name.lower().strip()

        # Check if it contains any organization keywords
        for keyword in ORGANIZATION_KEYWORDS:
            if keyword in name_lower:
                return True

        # Check against known Qatar organizations
        for org in QATAR_ORGANIZATIONS:
            if org.lower() in name_lower or name_lower in org.lower():
                return True

        # Heuristics for individual names:
        # - All caps with 2-3 words that look like "LASTNAME FIRSTNAME"
        # - Contains only letters and spaces
        # - No numbers, no special organization indicators
        words = name.split()

        # If it's 2-3 words and all caps, likely an individual
        if len(words) >= 2 and len(words) <= 4:
            # Check if it looks like a person's name (all words are short, no org keywords)
            all_short_words = all(len(w) < 15 for w in words)
            no_numbers = not any(c.isdigit() for c in name)

            # Person names typically don't have these patterns
            has_org_pattern = any(x in name_lower for x in [
                '&', 'and', ',', '.', 'of', 'for', 'the'
            ])

            if all_short_words and no_numbers and not has_org_pattern:
                # Likely an individual - but check one more time for Qatar keyword
                if 'qatar' not in name_lower:
                    return False

        # Default to True if we're not sure (better to include than exclude)
        return True

    def _is_qatar_organization(self, name: str, residence: str = '', country: str = '') -> bool:
        """
        Check if an organization is a QATARI company
        Must have Qatar-related name OR be a known Qatar org
        Just having QA residence is NOT enough (foreign companies have Qatar offices)

        Args:
            name: Organization name
            residence: Residence country code (e.g., 'QA')
            country: Country code from owner data

        Returns:
            True if organization is a Qatari company
        """
        if not name:
            return False

        # Must be an organization first (not an individual person)
        if not self._is_organization(name):
            return False

        name_lower = name.lower().strip()

        # Exclude obvious foreign company suffixes (even if residence=QA)
        # Use word boundaries to avoid false positives (e.g. "texAS" matching "as")
        foreign_suffixes = [
            ' pty ltd', ' pty. ltd',  # Australian
            ' gmbh', ' ag',  # German/Swiss
            ' b.v.', ' bv',  # Dutch
            ' a.s.',  # Norwegian/Danish
            ' s.a.',  # French/Spanish
            ' spa', ' srl',  # Italian
        ]

        foreign_companies = [
            # Auto manufacturers
            'toyota', 'honda', 'hyundai', 'ford', 'general motors', 'gm ',
            'volkswagen', 'bmw', 'mercedes', 'nissan', 'mazda', 'subaru',
            # Tech companies
            'samsung', 'sony', 'lg electronics', 'panasonic', 'philips',
            'microsoft', 'google', 'apple', 'amazon', 'meta', 'intel', 'ibm',
            'huawei', 'xiaomi', 'lenovo', 'dell', 'hp ',
            # Aerospace/Industrial
            'boeing', 'airbus', 'siemens', 'honeywell', 'ge ', 'general electric',
            'lockheed', 'raytheon', 'northrop',
            # Oil (non-Qatar)
            'exxon', 'chevron', 'bp ', 'total ', 'conocophillips',
            # Pharma
            'pfizer', 'novartis', 'roche', 'merck', 'johnson & johnson', 'j&j',
            'glaxo', 'astrazeneca', 'sanofi', 'bayer',
            # Universities (non-Qatar campus)
            'purdue', 'mit ', 'stanford', 'harvard', 'oxford', 'cambridge',
            'yale', 'princeton', 'berkeley', 'caltech', 'ucla', 'eth zurich',
        ]

        for suffix in foreign_suffixes:
            if name_lower.endswith(suffix.strip()) or suffix in name_lower:
                if 'qatar' not in name_lower and 'doha' not in name_lower:
                    return False

        for company in foreign_companies:
            if company in name_lower:
                if 'qatar' not in name_lower and 'doha' not in name_lower:
                    return False

        # Check if name contains Qatar-specific identifiers
        qatar_identifiers = [
            'qatar', 'qatari', 'doha',
            'hbku', 'hmc', 'sidra', 'hamad bin khalifa',
            'aspire zone', 'kahramaa', 'ashghal', 'ooredoo',
            'qstp', 'qnrf', 'qcri', 'qeeri', 'qbri',
        ]

        for identifier in qatar_identifiers:
            if identifier in name_lower:
                return True

        # Education City universities - MUST check residence BEFORE QATAR_ORGANIZATIONS
        # These unis have main campuses elsewhere, only include Qatar campus
        edu_city_names = [
            'texas a&m', 'weill cornell', 'carnegie mellon',
            'northwestern', 'georgetown', 'virginia commonwealth',
            'college of the north atlantic', 'north atlantic'
        ]

        for edu_name in edu_city_names:
            if edu_name in name_lower:
                # Only include if residence is Qatar
                if residence == 'QA' or country == 'QA':
                    return True
                return False  # Non-Qatar campus

        # Check against known Qatar organizations list
        for org in QATAR_ORGANIZATIONS:
            if org.lower() in name_lower or name_lower in org.lower():
                return True

        return False

    def _has_qatar_organization_applicant(self, patent: Dict) -> bool:
        """
        Check if patent has at least one QATAR-BASED organization as applicant
        STRICT: Only checks applicants, must have Qatar keyword in name

        Args:
            patent: Raw patent data from Lens API

        Returns:
            True if patent has a Qatar organization applicant
        """
        biblio = patent.get('biblio', {})
        parties = biblio.get('parties', {})

        # Check applicants ONLY (not owners - too loose)
        for app in parties.get('applicants', []):
            extracted = app.get('extracted_name', {})
            name = extracted.get('value', '') if isinstance(extracted, dict) else ''
            residence = app.get('residence', '')

            if self._is_qatar_organization(name, residence=residence):
                return True

        return False

    def search_patents(self, query: Dict = None, max_results: int = None) -> List[Dict]:
        """
        Search for patents using Lens.org API

        Args:
            query: Search query dict (default: Qatar patents)
            max_results: Maximum results to fetch

        Returns:
            List of patent data dictionaries
        """
        query = query or LENS_SEARCH_QUERY.copy()
        max_results = max_results or LENS_MAX_RESULTS

        self.log(f"Searching Lens.org for Qatar patents...")

        all_patents = []
        offset = 0

        while len(all_patents) < max_results:
            # Update offset in query
            query['from'] = offset
            query['size'] = min(LENS_BATCH_SIZE, max_results - len(all_patents))

            try:
                response = requests.post(
                    LENS_API_URL,
                    headers=self.get_headers(),
                    json=query,
                    timeout=60
                )

                if response.status_code == 200:
                    data = response.json()
                    results = data.get('data', [])
                    total = data.get('total', 0)

                    if not results:
                        self.log(f"No more results after {len(all_patents)}")
                        break

                    all_patents.extend(results)
                    self.log(f"Fetched {offset+1}-{offset+len(results)} of {total} (Total: {len(all_patents)})")

                    offset += len(results)

                    # Check if we've got all results
                    if len(all_patents) >= total:
                        break

                    time.sleep(LENS_DELAY_BETWEEN_BATCHES)

                elif response.status_code == 401:
                    self.log("Authentication failed - check API token", 'error')
                    break
                elif response.status_code == 429:
                    self.log("Rate limited - waiting 60 seconds...", 'warning')
                    time.sleep(60)
                    continue
                else:
                    self.log(f"API error: {response.status_code} - {response.text[:200]}", 'error')
                    self.stats['errors'] += 1
                    break

            except Exception as e:
                self.log(f"Request error: {e}", 'error')
                self.stats['errors'] += 1
                break

        self.stats['searched'] = len(all_patents)
        self.log(f"Total patents found: {len(all_patents)}")

        return all_patents

    def _parse_patent(self, patent: Dict) -> Dict:
        """
        Parse a Lens patent record into standard format

        Args:
            patent: Raw patent data from Lens API

        Returns:
            Standardized patent dictionary
        """
        # Build application number
        jurisdiction = patent.get('jurisdiction', '')
        doc_number = patent.get('doc_number', '')
        kind = patent.get('kind', '')
        app_number = f"{jurisdiction} {doc_number} {kind}".strip()

        # Get biblio data (contains title, parties, etc.)
        biblio = patent.get('biblio', {})
        parties = biblio.get('parties', {})

        # Get title (ENGLISH ONLY) - nested under biblio.invention_title
        title = ''
        titles = biblio.get('invention_title', [])
        if titles:
            # Look for English title ONLY
            for t in titles:
                if t.get('lang') == 'en':
                    title = t.get('text', '')
                    break
            # If no English title, skip this patent
            if not title:
                return None  # Skip non-English patents

        # Get abstract (prefer English) - at top level
        abstract = ''
        abstracts = patent.get('abstract', [])
        if abstracts:
            for a in abstracts:
                if a.get('lang') == 'en':
                    abstract = a.get('text', '')
                    break
            if not abstract and abstracts:
                abstract = abstracts[0].get('text', '')

        # Get applicants - nested under biblio.parties.applicants
        # ONLY include Qatari organizations (filter out foreign co-applicants)
        applicants = []
        for app in parties.get('applicants', []):
            extracted = app.get('extracted_name', {})
            name = extracted.get('value', '') if isinstance(extracted, dict) else ''
            residence = app.get('residence', '')
            if name and self._is_qatar_organization(name, residence=residence):
                applicants.append(name)

        # Get inventors - nested under biblio.parties.inventors
        inventors = []
        for inv in parties.get('inventors', []):
            extracted = inv.get('extracted_name', {})
            name = extracted.get('value', '') if isinstance(extracted, dict) else ''
            if name:
                inventors.append(name)

        # Get owners - nested under biblio.parties.owners_all
        # ONLY include Qatari organizations
        owners = []
        for owner in parties.get('owners_all', []):
            extracted = owner.get('extracted_name', {})
            name = extracted.get('value', '') if isinstance(extracted, dict) else ''
            country = owner.get('extracted_country', '')
            if name and self._is_qatar_organization(name, country=country):
                owners.append(name)

        # Get date
        date_published = patent.get('date_published', '')
        if date_published:
            # Format: YYYY-MM-DD (Lens usually provides this format)
            year = date_published[:4] if len(date_published) >= 4 else ''
        else:
            year = ''

        # Get legal status
        legal_status = ''
        status_data = patent.get('legal_status', {})
        if status_data:
            legal_status = status_data.get('patent_status', '')

        # Build patent URL
        lens_id = patent.get('lens_id', '')
        patent_url = f"https://www.lens.org/lens/patent/{lens_id}" if lens_id else ''

        return {
            'ApplicationNumber': app_number,
            'ApplicationDate': date_published,
            'PatentYear': year,
            'Title': title,
            'Abstract': abstract[:2000] if abstract else '',
            'Applicants': '; '.join(applicants),
            'Inventors': '; '.join(inventors),
            'Owners': '; '.join(owners) if owners else '; '.join(applicants),
            'PatentUrl': patent_url,
            'LegalStatusName': legal_status,
            'Source': 'Lens',
            'ExtractedDate': datetime.now().strftime('%Y-%m-%d'),
        }

    def extract_all(self, query: Dict = None, max_results: int = None,
                    progress_callback=None) -> List[Dict]:
        """
        Main extraction method - searches and parses all patents
        Filters to only include patents with Qatar ORGANIZATION applicants

        Args:
            query: Search query (default: Qatar patents)
            max_results: Maximum patents to extract
            progress_callback: Function to call with progress updates

        Returns:
            List of standardized patent dictionaries
        """
        # Search for patents
        raw_patents = self.search_patents(query, max_results)

        if not raw_patents:
            self.log("No patents found")
            return []

        self.log(f"Filtering {len(raw_patents)} patents for Qatar organizations...")

        # Filter for patents with Qatar organization applicants
        org_patents = []
        skipped_individuals = 0
        for raw in raw_patents:
            if self._has_qatar_organization_applicant(raw):
                org_patents.append(raw)
            else:
                skipped_individuals += 1

        self.log(f"Found {len(org_patents)} patents from Qatar organizations (skipped {skipped_individuals} individual-only patents)")

        if not org_patents:
            self.log("No organization patents found")
            return []

        self.log(f"Parsing {len(org_patents)} organization patents (English only)...")

        # Parse each patent
        patents = []
        skipped_non_english = 0
        for i, raw in enumerate(org_patents):
            if i % 100 == 0:
                self.log(f"Parsing {i+1}/{len(org_patents)}...")
                if progress_callback:
                    progress_callback(i, len(org_patents))

            try:
                parsed = self._parse_patent(raw)
                if parsed is None:
                    skipped_non_english += 1
                    continue
                if parsed.get('Title'):  # Only include patents with titles
                    patents.append(parsed)
            except Exception as e:
                self.stats['errors'] += 1
                continue

        self.stats['extracted'] = len(patents)
        self.log(f"Successfully parsed {len(patents)} English patents (skipped {skipped_non_english} non-English)")

        return patents

    def get_stats(self) -> Dict:
        """Return extraction statistics"""
        return self.stats
