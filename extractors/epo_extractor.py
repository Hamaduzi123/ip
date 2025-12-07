"""
EPO OPS API Extractor
Extracts patents from European Patent Office API
"""

import requests
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Optional
import sys

# Add parent to path for config
sys.path.insert(0, str(__file__).rsplit('\\', 2)[0])
from config import (
    EPO_CONSUMER_KEY, EPO_CONSUMER_SECRET,
    EPO_AUTH_URL, EPO_SEARCH_URL, EPO_BIBLIO_URL,
    EPO_SEARCH_QUERY, EPO_MAX_RESULTS, EPO_BATCH_SIZE,
    EPO_DELAY_BETWEEN_BATCHES
)


class EPOExtractor:
    """Extracts patent data from EPO OPS API"""

    def __init__(self, logger=None):
        self.access_token = None
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
        print(f"[EPO] {message}")

    def authenticate(self) -> bool:
        """Get OAuth access token from EPO"""
        self.log("Authenticating with EPO OPS API...")

        try:
            response = requests.post(
                EPO_AUTH_URL,
                data={"grant_type": "client_credentials"},
                auth=(EPO_CONSUMER_KEY, EPO_CONSUMER_SECRET),
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")
                self.log("Authentication successful")
                return True
            else:
                self.log(f"Authentication failed: {response.status_code}", 'error')
                return False

        except Exception as e:
            self.log(f"Authentication error: {e}", 'error')
            return False

    def get_headers(self) -> Dict:
        """Get request headers with auth token"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/xml"
        }

    def search_patents(self, query: str = None, max_results: int = None) -> List[Dict]:
        """Search for patents using CQL query"""
        query = query or EPO_SEARCH_QUERY
        max_results = max_results or EPO_MAX_RESULTS

        self.log(f"Searching for: {query}")

        all_doc_ids = []
        start = 1

        while len(all_doc_ids) < max_results:
            end = min(start + EPO_BATCH_SIZE - 1, max_results)

            params = {
                "q": query,
                "Range": f"{start}-{end}"
            }

            try:
                response = requests.get(
                    EPO_SEARCH_URL,
                    params=params,
                    headers=self.get_headers(),
                    timeout=60
                )

                if response.status_code == 200:
                    doc_ids = self._parse_search_results(response.text)
                    if not doc_ids:
                        self.log(f"No more results after {len(all_doc_ids)}")
                        break
                    all_doc_ids.extend(doc_ids)
                    self.log(f"Fetched {start}-{end}: {len(doc_ids)} results (Total: {len(all_doc_ids)})")
                    start += EPO_BATCH_SIZE
                    time.sleep(EPO_DELAY_BETWEEN_BATCHES)

                elif response.status_code == 404:
                    self.log("No more results")
                    break
                elif response.status_code == 403:
                    self.log("Access denied - re-authenticating...")
                    if self.authenticate():
                        continue
                    break
                else:
                    self.log(f"Search error: {response.status_code}", 'error')
                    break

            except Exception as e:
                self.log(f"Search error: {e}", 'error')
                self.stats['errors'] += 1
                break

        self.stats['searched'] = len(all_doc_ids)
        self.log(f"Total documents found: {len(all_doc_ids)}")

        # Remove duplicates
        unique_docs = {}
        for doc in all_doc_ids:
            key = f"{doc.get('country', '')}{doc.get('doc_number', '')}"
            if key not in unique_docs:
                unique_docs[key] = doc

        return list(unique_docs.values())

    def _parse_search_results(self, xml_text: str) -> List[Dict]:
        """Parse search results XML to get document IDs"""
        doc_ids = []

        try:
            root = ET.fromstring(xml_text)

            for elem in root.iter():
                if 'publication-reference' in elem.tag:
                    doc_id = {}
                    for child in elem.iter():
                        if 'country' in child.tag:
                            doc_id['country'] = child.text
                        elif 'doc-number' in child.tag:
                            doc_id['doc_number'] = child.text
                        elif 'kind' in child.tag:
                            doc_id['kind'] = child.text

                    if doc_id.get('country') and doc_id.get('doc_number'):
                        doc_ids.append(doc_id)

        except Exception as e:
            self.log(f"Parse error: {e}", 'error')

        return doc_ids

    def get_patent_details(self, doc_id: Dict) -> Optional[Dict]:
        """Get full bibliographic details for a patent"""
        country = doc_id.get('country', '')
        number = doc_id.get('doc_number', '')
        kind = doc_id.get('kind', '')

        url = f"{EPO_BIBLIO_URL}/{country}.{number}.{kind}/biblio"

        try:
            response = requests.get(
                url,
                headers=self.get_headers(),
                timeout=30
            )

            if response.status_code == 200:
                return self._parse_biblio(response.text, doc_id)
            else:
                return None

        except Exception as e:
            self.stats['errors'] += 1
            return None

    def _parse_biblio(self, xml_text: str, doc_id: Dict) -> Dict:
        """Parse bibliographic data from XML"""
        patent = {
            'ApplicationNumber': f"{doc_id.get('country', '')} {doc_id.get('doc_number', '')} {doc_id.get('kind', '')}".strip(),
            'Title': '',
            'Abstract': '',
            'Applicants': '',
            'Inventors': '',
            'Owners': '',
            'ApplicationDate': '',
            'PatentYear': '',
            'PatentUrl': f"https://worldwide.espacenet.com/patent/search?q=pn%3D{doc_id.get('country', '')}{doc_id.get('doc_number', '')}",
            'Source': 'EPO',
            'ExtractedDate': datetime.now().strftime('%Y-%m-%d'),
        }

        try:
            root = ET.fromstring(xml_text)

            # Extract title (prefer English)
            for elem in root.iter():
                if 'invention-title' in elem.tag:
                    lang = elem.get('lang', '')
                    if lang == 'en' or not patent['Title']:
                        patent['Title'] = elem.text or ''

            # Extract applicants
            applicants = []
            for elem in root.iter():
                if 'applicant' in elem.tag:
                    for name_elem in elem.iter():
                        if 'name' in name_elem.tag and name_elem.text:
                            applicants.append(name_elem.text.strip())
            patent['Applicants'] = '; '.join(list(set(applicants)))
            patent['Owners'] = patent['Applicants']

            # Extract inventors
            inventors = []
            for elem in root.iter():
                if 'inventor' in elem.tag:
                    for name_elem in elem.iter():
                        if 'name' in name_elem.tag and name_elem.text:
                            inventors.append(name_elem.text.strip())
            patent['Inventors'] = '; '.join(list(set(inventors)))

            # Extract dates
            for elem in root.iter():
                if 'publication-reference' in elem.tag:
                    for date_elem in elem.iter():
                        if 'date' in date_elem.tag and date_elem.text:
                            patent['ApplicationDate'] = date_elem.text
                            patent['PatentYear'] = date_elem.text[:4] if len(date_elem.text) >= 4 else ''
                            break

            # Extract abstract
            for elem in root.iter():
                if 'abstract' in elem.tag:
                    lang = elem.get('lang', '')
                    if lang == 'en' or not patent['Abstract']:
                        text_parts = []
                        for p in elem.iter():
                            if p.text:
                                text_parts.append(p.text)
                        patent['Abstract'] = ' '.join(text_parts)[:2000]

        except Exception as e:
            pass

        return patent

    def extract_all(self, query: str = None, max_results: int = None,
                    progress_callback=None) -> List[Dict]:
        """
        Main extraction method - searches and gets details for all patents

        Args:
            query: CQL search query (default: pa=Qatar)
            max_results: Maximum patents to extract
            progress_callback: Function to call with progress updates

        Returns:
            List of patent dictionaries
        """
        # Authenticate
        if not self.authenticate():
            self.log("Authentication failed!", 'error')
            return []

        # Search for patents
        doc_ids = self.search_patents(query, max_results)

        if not doc_ids:
            self.log("No patents found")
            return []

        self.log(f"Extracting details for {len(doc_ids)} patents...")

        # Get details for each patent
        patents = []
        for i, doc_id in enumerate(doc_ids):
            if i % 50 == 0:
                self.log(f"Processing {i+1}/{len(doc_ids)}...")
                if progress_callback:
                    progress_callback(i, len(doc_ids))

            details = self.get_patent_details(doc_id)
            if details:
                patents.append(details)

            # Rate limiting
            if i % 10 == 0:
                time.sleep(1)

        self.stats['extracted'] = len(patents)
        self.log(f"Extracted {len(patents)} patents successfully")

        return patents

    def get_stats(self) -> Dict:
        """Return extraction statistics"""
        return self.stats
