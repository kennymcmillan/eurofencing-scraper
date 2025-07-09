"""
Configuration file for EuroFencing Scraper
==========================================
"""

import os
from typing import Dict, Any

# Database Configuration for sportsanalytics
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'your_username'),
    'password': os.getenv('DB_PASSWORD', 'your_password'),
    'database': os.getenv('DB_NAME', 'sportsanalytics'),
    'port': int(os.getenv('DB_PORT', 3306))
}

# Scraping Configuration
SCRAPING_CONFIG = {
    'base_url': 'https://www.eurofencing.info',
    'delay_between_requests': 2,  # seconds
    'timeout': 30,  # seconds
    'max_retries': 3,
    'headless': True,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# Priority Countries (for targeted scraping)
PRIORITY_COUNTRIES = [
    'QAT',  # Qatar
    'UAE',  # United Arab Emirates
    'SAU',  # Saudi Arabia
    'KUW',  # Kuwait
    'BHR',  # Bahrain
    'FRA',  # France
    'ITA',  # Italy
    'GER',  # Germany
    'RUS',  # Russia
    'HUN',  # Hungary
    'POL',  # Poland
    'ESP',  # Spain
    'GBR',  # Great Britain
    'UKR',  # Ukraine
    'USA',  # United States
]

# Export Configuration
EXPORT_CONFIG = {
    'output_directory': './eurofencing_data',
    'file_formats': ['csv', 'json', 'excel'],
    'include_timestamp': True,
    'backup_enabled': True
}

# EuroFencing Specific Configuration
EUROFENCING_CONFIG = {
    'filters': {
        'genders': ['men', 'women'],
        'weapons': ['foil', 'epee', 'sabre'],
        'age_categories': ['cadet', 'u23', 'u14'],  # Cadet = U17
        'seasons': ['2025', '2024', '2023', '2022', '2021', '2020', '2019', '2018']
    },
    'urls': {
        'fencers': '/competitions/fencers',
        'individual_rankings': '/rankings/individual-rankings',
        'team_rankings': '/rankings/team-rankings',
        'competitions': '/competitions/latest-results'
    },
    'pagination': {
        'items_per_page': 20,
        'max_pages_per_request': 100
    }
}

# Database Table Schemas
DATABASE_SCHEMAS = {
    'eurofencing_fencers': """
        CREATE TABLE IF NOT EXISTS eurofencing_fencers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            licence VARCHAR(20) UNIQUE NOT NULL,
            first_name VARCHAR(100),
            last_name VARCHAR(100),
            full_name VARCHAR(200) GENERATED ALWAYS AS (CONCAT(first_name, ' ', last_name)) STORED,
            club VARCHAR(200),
            nation VARCHAR(10),
            birth_year INT,
            gender VARCHAR(1),
            handedness VARCHAR(20),
            scraped_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_date DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_nation (nation),
            INDEX idx_name (last_name, first_name),
            INDEX idx_birth_year (birth_year),
            INDEX idx_gender (gender),
            INDEX idx_licence (licence)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    
    'eurofencing_rankings': """
        CREATE TABLE IF NOT EXISTS eurofencing_rankings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            rank_position INT,
            competition VARCHAR(200),
            venue VARCHAR(100),
            nation VARCHAR(10),
            category VARCHAR(50),
            discipline VARCHAR(50),
            coefficient DECIMAL(5,2),
            season VARCHAR(10),
            weapon VARCHAR(20),
            age_group VARCHAR(20),
            gender VARCHAR(10),
            country_filter VARCHAR(10),
            scraped_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_date DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_season_weapon (season, weapon),
            INDEX idx_nation (nation),
            INDEX idx_rank (rank_position),
            INDEX idx_age_group (age_group),
            INDEX idx_gender (gender),
            UNIQUE KEY unique_ranking (competition, venue, season, weapon, age_group, gender, rank_position)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    
    'eurofencing_scraping_log': """
        CREATE TABLE IF NOT EXISTS eurofencing_scraping_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            scraping_session_id VARCHAR(50),
            data_type ENUM('fencers', 'rankings', 'competitions'),
            filters_applied JSON,
            records_scraped INT,
            pages_processed INT,
            start_time DATETIME,
            end_time DATETIME,
            duration_seconds INT,
            status ENUM('started', 'completed', 'failed', 'interrupted'),
            error_message TEXT,
            scraped_date DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """
}

# Validation Rules
VALIDATION_RULES = {
    'fencer': {
        'licence': r'^[0-9]{8}$',  # 8-digit licence numbers
        'nation': r'^[A-Z]{3}$',  # 3-letter country codes
        'birth_year': (1900, 2020),  # Valid birth year range
        'required_fields': ['licence', 'last_name', 'nation']
    },
    'ranking': {
        'rank_position': (1, 1000),  # Valid ranking range
        'coefficient': (0.0, 10.0),  # Valid coefficient range
        'required_fields': ['rank_position', 'competition', 'season', 'weapon']
    }
}