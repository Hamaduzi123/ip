"""
Patent Data Cleaner and Transformer
Standardizes, cleans, and deduplicates patent data
"""

import re
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime
import sys

# Add parent to path for config
sys.path.insert(0, str(__file__).rsplit('\\', 2)[0])
from config import INSTITUTION_STANDARDS, KNOWN_ORGANIZATIONS, OUTPUT_COLUMNS, GARBAGE_FRAGMENTS


class PatentCleaner:
    """Cleans and standardizes patent data"""

    def __init__(self, logger=None):
        self.logger = logger
        self.stats = {
            'input_count': 0,
            'output_count': 0,
            'duplicates_removed': 0,
            'non_english_removed': 0,
            'names_standardized': 0,
        }

    def log(self, message: str, level: str = 'info'):
        """Log a message"""
        if self.logger:
            getattr(self.logger, level)(message)
        print(f"[Cleaner] {message}")

    def clean(self, patents: List[Dict]) -> pd.DataFrame:
        """
        Main cleaning method - applies all transformations

        Args:
            patents: List of patent dictionaries

        Returns:
            Cleaned DataFrame
        """
        self.stats['input_count'] = len(patents)
        self.log(f"Cleaning {len(patents)} patents...")

        # Convert to DataFrame
        df = pd.DataFrame(patents)

        # Step 1: Remove non-English titles
        df = self._remove_non_english(df)

        # Step 2: Clean and standardize all text fields
        df = self._clean_text_fields(df)

        # Step 3: Standardize institution names
        df = self._standardize_institutions(df)

        # Step 4: Format dates
        df = self._format_dates(df)

        # Step 5: Remove duplicates
        df = self._deduplicate(df)

        # Step 6: Add standard columns
        df = self._add_standard_columns(df)

        # Step 7: Ensure column order
        df = self._ensure_columns(df)

        self.stats['output_count'] = len(df)
        self.log(f"Cleaning complete: {len(df)} patents remaining")

        return df

    def _remove_non_english(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove patents with non-English titles (Cyrillic, Chinese, Korean, Arabic)"""
        non_english_pattern = r'[\u0400-\u04FF\u4e00-\u9fff\uac00-\ud7af\u0600-\u06FF]'

        mask = df['Title'].apply(
            lambda x: bool(re.search(non_english_pattern, str(x))) if pd.notna(x) else False
        )

        removed = mask.sum()
        self.stats['non_english_removed'] = removed

        if removed > 0:
            self.log(f"Removed {removed} non-English patents")

        return df[~mask].reset_index(drop=True)

    def _clean_text_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean whitespace and special characters from text fields"""

        def clean_text(value):
            if pd.isna(value) or not value:
                return ''
            return str(value).strip()

        # Clean simple text fields
        for col in ['Title', 'Abstract', 'ApplicationNumber']:
            if col in df.columns:
                df[col] = df[col].apply(clean_text)

        return df

    def _standardize_institutions(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize institution names in Applicants, Inventors, Owners"""

        def standardize_name(name: str) -> str:
            """Standardize a single name"""
            if not name:
                return ''

            name = str(name).strip()

            # Remove country codes like [QA], [US], [GB]
            name = re.sub(r'\s*\[[A-Z]{2}\]\s*', '', name)

            # Remove trailing commas and punctuation
            name = name.strip(' ,;.')

            if not name:
                return ''

            # Check if this is a garbage fragment (incomplete name part)
            name_lower = name.lower().strip()
            for garbage_pattern in GARBAGE_FRAGMENTS:
                if re.match(garbage_pattern, name_lower, re.IGNORECASE):
                    return ''  # Skip this garbage fragment

            # Check against institution standards
            for pattern, standard in INSTITUTION_STANDARDS.items():
                if re.match(pattern, name_lower):
                    self.stats['names_standardized'] += 1
                    return standard

            # Convert ALL CAPS to Title Case (preserve short acronyms)
            if name.isupper() and len(name) > 4:
                words = name.split()
                result = []
                for w in words:
                    if len(w) <= 3 and w.isalpha():
                        result.append(w)  # Keep short acronyms
                    else:
                        result.append(w.title())
                name = ' '.join(result)

            # Remove commas from person names (normalize format)
            if ',' in name and len(name.split(',')) == 2:
                parts = name.split(',')
                # Check if it looks like "LASTNAME, FIRSTNAME"
                if len(parts[0].split()) == 1 and len(parts[1].strip().split()) <= 2:
                    name = f"{parts[1].strip()} {parts[0].strip()}"
                    if name.isupper():
                        name = name.title()

            return name.strip()

        def clean_name_field(value: str) -> str:
            """Clean a field with multiple semicolon-separated names"""
            if pd.isna(value) or not value:
                return ''

            parts = str(value).split(';')
            cleaned = []
            seen = set()

            for p in parts:
                p = standardize_name(p)
                if not p:
                    continue

                # Deduplicate (case-insensitive)
                norm_key = re.sub(r'[^a-z0-9]', '', p.lower())

                if norm_key and len(norm_key) > 1 and norm_key not in seen:
                    seen.add(norm_key)
                    cleaned.append(p)

            return '; '.join(cleaned)

        # Apply to name fields
        for col in ['Applicants', 'Inventors', 'Owners']:
            if col in df.columns:
                df[col] = df[col].apply(clean_name_field)

        return df

    def _format_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Format dates to YYYY-MM-DD"""

        def format_date(d):
            if pd.isna(d) or not d:
                return ''
            d = str(d).strip()
            # Format: YYYYMMDD -> YYYY-MM-DD
            if len(d) == 8 and d.isdigit():
                return f'{d[:4]}-{d[4:6]}-{d[6:8]}'
            return d

        if 'ApplicationDate' in df.columns:
            df['ApplicationDate'] = df['ApplicationDate'].apply(format_date)
            df['PatentYear'] = df['ApplicationDate'].str[:4]

        return df

    def _deduplicate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicate patents"""
        initial_count = len(df)

        # Deduplicate by ApplicationNumber
        df = df.drop_duplicates(subset=['ApplicationNumber'], keep='first')

        # Also check for duplicates by Title (same invention, different filings)
        # We keep first occurrence
        df['title_norm'] = df['Title'].str.lower().str[:100]
        df = df.drop_duplicates(subset=['title_norm'], keep='first')
        df = df.drop(columns=['title_norm'])

        removed = initial_count - len(df)
        self.stats['duplicates_removed'] = removed

        if removed > 0:
            self.log(f"Removed {removed} duplicate patents")

        return df.reset_index(drop=True)

    def _add_standard_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add standard columns required for output"""

        # ResourceId (auto-increment starting from max existing + 1)
        if 'ResourceId' not in df.columns:
            df['ResourceId'] = range(50000, 50000 + len(df))

        # Document type
        if 'DocumentTypeId' not in df.columns:
            df['DocumentTypeId'] = 3

        if 'DocumentTypeName' not in df.columns:
            df['DocumentTypeName'] = 'Patent Application'

        # Legal status
        if 'LegalStatusName' not in df.columns:
            df['LegalStatusName'] = 'PENDING'

        # Source (if not present)
        if 'Source' not in df.columns:
            df['Source'] = 'EPO'

        # Extracted date
        if 'ExtractedDate' not in df.columns:
            df['ExtractedDate'] = datetime.now().strftime('%Y-%m-%d')

        return df

    def _ensure_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ensure all required columns exist and are in correct order"""
        for col in OUTPUT_COLUMNS:
            if col not in df.columns:
                df[col] = ''

        # Reorder columns
        return df[OUTPUT_COLUMNS]

    def merge_with_existing(self, new_df: pd.DataFrame,
                           existing_df: pd.DataFrame) -> pd.DataFrame:
        """
        Merge new patents with existing data, removing duplicates
        IMPORTANT: Standardizes ALL data (both new and existing) for consistency

        Args:
            new_df: New patents DataFrame
            existing_df: Existing patents DataFrame

        Returns:
            Merged DataFrame with duplicates removed and ALL names standardized
        """
        self.log(f"Merging {len(new_df)} new patents with {len(existing_df)} existing...")

        # FIRST: Standardize the existing data too!
        self.log("Standardizing existing data for consistency...")
        existing_df = self._standardize_institutions(existing_df.copy())
        existing_df = self._clean_text_fields(existing_df)

        # Normalize application numbers for comparison
        def normalize_app_num(x):
            if pd.isna(x):
                return ''
            return str(x).replace(' ', '').replace('.', '').replace('-', '').upper().strip()

        new_df['_norm_app'] = new_df['ApplicationNumber'].apply(normalize_app_num)
        existing_df['_norm_app'] = existing_df['ApplicationNumber'].apply(normalize_app_num)

        # Also normalize titles
        new_df['_norm_title'] = new_df['Title'].str.lower().str[:100]
        existing_df['_norm_title'] = existing_df['Title'].str.lower().str[:100]

        # Find truly new patents (not in existing by app number OR title)
        existing_apps = set(existing_df['_norm_app'])
        existing_titles = set(existing_df['_norm_title'].dropna())

        mask = ~(
            new_df['_norm_app'].isin(existing_apps) |
            new_df['_norm_title'].isin(existing_titles)
        )

        truly_new = new_df[mask].copy()

        self.log(f"Found {len(truly_new)} truly new patents")

        # Update ResourceIds for new patents
        if len(existing_df) > 0:
            max_id = existing_df['ResourceId'].max()
        else:
            max_id = 50000

        truly_new['ResourceId'] = range(int(max_id) + 1, int(max_id) + 1 + len(truly_new))

        # Combine
        combined = pd.concat([existing_df, truly_new], ignore_index=True)

        # Drop helper columns
        combined = combined.drop(columns=['_norm_app', '_norm_title'], errors='ignore')

        # FINAL PASS: Standardize entire combined dataset to ensure consistency
        self.log("Final standardization pass on merged data...")
        combined = self._standardize_institutions(combined)
        combined = self._clean_text_fields(combined)

        # Ensure columns
        combined = self._ensure_columns(combined)

        self.log(f"Final merged count: {len(combined)}")

        return combined

    def get_stats(self) -> Dict:
        """Return cleaning statistics"""
        return self.stats
