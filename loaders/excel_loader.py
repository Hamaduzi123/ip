"""
Excel Loader Module
Handles loading and saving patent data to Excel files
"""

import pandas as pd
from pathlib import Path
from typing import Optional
from datetime import datetime
import sys

# Add parent to path for config
sys.path.insert(0, str(__file__).rsplit('\\', 2)[0])
from config import MASTER_FILE, DATA_DIR, OUTPUT_COLUMNS


class ExcelLoader:
    """Handles Excel file operations for patent data"""

    def __init__(self, logger=None):
        self.logger = logger
        self.master_file = MASTER_FILE

    def log(self, message: str, level: str = 'info'):
        """Log a message"""
        if self.logger:
            getattr(self.logger, level)(message)
        print(f"[Loader] {message}")

    def load_existing(self, file_path: Path = None) -> Optional[pd.DataFrame]:
        """
        Load existing patent data from Excel file

        Args:
            file_path: Path to Excel file (default: master file)

        Returns:
            DataFrame or None if file doesn't exist
        """
        file_path = file_path or self.master_file

        if not file_path.exists():
            self.log(f"No existing file found at {file_path}")
            return None

        try:
            df = pd.read_excel(file_path)
            self.log(f"Loaded {len(df)} existing patents from {file_path.name}")
            return df
        except Exception as e:
            self.log(f"Error loading file: {e}", 'error')
            return None

    def save(self, df: pd.DataFrame, file_path: Path = None,
             backup: bool = True) -> bool:
        """
        Save patent data to Excel file

        Args:
            df: DataFrame to save
            file_path: Path to save to (default: master file)
            backup: Whether to create a backup of existing file

        Returns:
            True if successful, False otherwise
        """
        file_path = file_path or self.master_file

        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create backup if file exists
        if backup and file_path.exists():
            backup_name = f"{file_path.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            backup_path = file_path.parent / backup_name
            try:
                existing = pd.read_excel(file_path)
                existing.to_excel(backup_path, index=False)
                self.log(f"Created backup: {backup_name}")
            except Exception as e:
                self.log(f"Warning: Could not create backup: {e}", 'warning')

        # Save new file
        try:
            df.to_excel(file_path, index=False)
            self.log(f"Saved {len(df)} patents to {file_path.name}")
            return True
        except PermissionError:
            # Try saving to alternative filename
            alt_path = file_path.parent / f"{file_path.stem}_updated_{datetime.now().strftime('%H%M%S')}.xlsx"
            try:
                df.to_excel(alt_path, index=False)
                self.log(f"File in use, saved to: {alt_path.name}")
                return True
            except Exception as e:
                self.log(f"Error saving file: {e}", 'error')
                return False
        except Exception as e:
            self.log(f"Error saving file: {e}", 'error')
            return False

    def export_for_innolight(self, df: pd.DataFrame,
                            output_name: str = "CurrentIPs_Export.xlsx") -> bool:
        """
        Export data in the exact format expected by Innolight/CurrentIPs

        Args:
            df: DataFrame to export
            output_name: Output filename

        Returns:
            True if successful
        """
        output_path = DATA_DIR / output_name

        # Ensure correct columns
        export_df = df.copy()

        # Remove internal columns not needed for export
        internal_cols = ['Source', 'ExtractedDate']
        for col in internal_cols:
            if col in export_df.columns:
                export_df = export_df.drop(columns=[col])

        return self.save(export_df, output_path, backup=False)

    def get_summary(self, df: pd.DataFrame) -> dict:
        """
        Get summary statistics of the data

        Args:
            df: DataFrame to summarize

        Returns:
            Dictionary with summary statistics
        """
        summary = {
            'total_patents': len(df),
            'with_title': (df['Title'] != '').sum() if 'Title' in df.columns else 0,
            'with_applicants': (df['Applicants'] != '').sum() if 'Applicants' in df.columns else 0,
            'with_inventors': (df['Inventors'] != '').sum() if 'Inventors' in df.columns else 0,
            'year_range': '',
            'sources': {},
            'top_applicants': [],
        }

        # Year range
        if 'PatentYear' in df.columns:
            years = df['PatentYear'].dropna()
            years = years[years != '']
            if len(years) > 0:
                summary['year_range'] = f"{years.min()} - {years.max()}"

        # Sources breakdown
        if 'Source' in df.columns:
            summary['sources'] = df['Source'].value_counts().to_dict()

        # Top applicants
        if 'Applicants' in df.columns:
            all_apps = []
            for apps in df['Applicants'].dropna():
                if apps:
                    all_apps.extend([a.strip() for a in str(apps).split(';')])
            if all_apps:
                top = pd.Series(all_apps).value_counts().head(10)
                summary['top_applicants'] = [(app, int(count)) for app, count in top.items()]

        return summary
