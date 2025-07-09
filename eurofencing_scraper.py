#!/usr/bin/env python3
"""
EuroFencing Comprehensive Data Scraper
=====================================

A complete Python solution for scraping all rankings data from EuroFencing website:
- Individual fencer database (50,000+ records)
- Rankings by weapon/age/season/country
- Competition results and team rankings
- Automated pagination and data export

Author: Sports Analytics System
Database: sportsanalytics (Oracle MySQL)
"""

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pandas as pd
import json
import time
import logging
from datetime import datetime
import os
from typing import Dict, List, Optional
import mysql.connector
from dataclasses import dataclass
import concurrent.futures
from urllib.parse import urljoin
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('eurofencing_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class FencerProfile:
    """Individual fencer data structure"""
    licence: str
    first_name: str
    last_name: str
    club: str
    nation: str
    birth_year: int
    gender: str
    handedness: str
    
@dataclass
class RankingEntry:
    """Individual ranking entry structure"""
    rank: int
    competition: str
    venue: str
    nation: str
    category: str
    discipline: str
    coefficient: float
    season: str
    weapon: str
    age_group: str
    gender: str

class EuroFencingScraper:
    """Main scraper class for EuroFencing data extraction"""
    
    def __init__(self, db_config: Optional[Dict] = None, headless: bool = True):
        """Initialize the scraper with database connection and browser setup"""
        self.base_url = "https://www.eurofencing.info"
        self.db_config = db_config
        self.headless = headless
        self.driver = None
        self.session = requests.Session()
        
        # Data storage
        self.fencers_data = []
        self.rankings_data = []
        
        # Filter configurations
        self.filter_config = {
            'genders': ['men', 'women'],
            'weapons': ['foil', 'epee', 'sabre'],
            'age_categories': ['cadet', 'u23', 'u14'],
            'seasons': ['2025', '2024', '2023', '2022', '2021', '2020', '2019', '2018'],
            'countries': []  # Will be populated dynamically
        }
        
    def setup_driver(self) -> webdriver.Chrome:
        """Setup Chrome WebDriver with optimized options"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(10)
        return self.driver
    
    def handle_cookie_consent(self):
        """Handle cookie consent dialog"""
        try:
            wait = WebDriverWait(self.driver, 5)
            # Try multiple possible cookie consent selectors
            consent_selectors = [
                "//button[contains(text(), 'Allow')]",
                "//button[contains(text(), 'Accept')]",
                "//button[contains(text(), 'OK')]",
                ".cookie-accept",
                "#cookie-accept"
            ]
            
            for selector in consent_selectors:
                try:
                    if selector.startswith("//"):
                        button = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    else:
                        button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    button.click()
                    logger.info("Cookie consent handled")
                    time.sleep(2)
                    return
                except TimeoutException:
                    continue
                    
        except Exception as e:
            logger.warning(f"Could not handle cookie consent: {e}")
    
    def get_countries_list(self) -> List[str]:
        """Extract all available countries from the dropdown"""
        try:
            self.driver.get(f"{self.base_url}/competitions/fencers")
            self.handle_cookie_consent()
            
            # Wait for country dropdown to load
            country_select = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "select"))
            )
            
            # Find the country dropdown (usually the first one)
            select_elements = self.driver.find_elements(By.TAG_NAME, "select")
            for select_elem in select_elements:
                options = select_elem.find_elements(By.TAG_NAME, "option")
                if len(options) > 50:  # Country dropdown has many options
                    countries = []
                    for option in options[1:]:  # Skip first empty option
                        value = option.get_attribute("value")
                        if value and len(value) == 3:  # Country codes are 3 letters
                            countries.append(value)
                    self.filter_config['countries'] = countries
                    logger.info(f"Found {len(countries)} countries")
                    return countries
            
        except Exception as e:
            logger.error(f"Error getting countries list: {e}")
            return []
    
    def scrape_fencers_page(self, page: int = 1, country: str = "", 
                           first_name: str = "", last_name: str = "",
                           gender: str = "") -> List[FencerProfile]:
        """Scrape a single page of fencers data"""
        try:
            url = f"{self.base_url}/competitions/fencers"
            self.driver.get(url)
            
            # Fill in search filters if provided
            if country:
                country_select = Select(self.driver.find_element(By.NAME, "country"))
                country_select.select_by_value(country)
            
            if first_name:
                first_name_input = self.driver.find_element(By.NAME, "firstName")
                first_name_input.clear()
                first_name_input.send_keys(first_name)
            
            if last_name:
                last_name_input = self.driver.find_element(By.NAME, "lastName")
                last_name_input.clear()
                last_name_input.send_keys(last_name)
            
            if gender:
                gender_select = Select(self.driver.find_element(By.NAME, "gender"))
                gender_select.select_by_value(gender)
            
            # Submit search
            search_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            search_button.click()
            
            # Wait for results to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
            
            # Navigate to specific page if needed
            if page > 1:
                try:
                    page_link = self.driver.find_element(By.XPATH, f"//a[contains(@data-page, '{page}')]")
                    page_link.click()
                    time.sleep(3)
                except NoSuchElementException:
                    logger.warning(f"Page {page} not found")
                    return []
            
            # Extract fencer data from table
            fencers = []
            rows = self.driver.find_elements(By.CSS_SELECTOR, "tr")
            
            for row in rows[1:]:  # Skip header row
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 7:
                        fencer = FencerProfile(
                            licence=cells[0].text.strip(),
                            last_name=cells[1].text.strip(),
                            first_name=cells[2].text.strip(),
                            club=cells[3].text.strip(),
                            nation=cells[4].text.strip(),
                            birth_year=int(cells[5].text.strip()) if cells[5].text.strip().isdigit() else 0,
                            gender="M" if "men" in gender.lower() else "F" if "women" in gender.lower() else "",
                            handedness=cells[6].text.strip() if len(cells) > 6 else ""
                        )
                        fencers.append(fencer)
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parsing fencer row: {e}")
                    continue
            
            logger.info(f"Scraped {len(fencers)} fencers from page {page}")
            return fencers
            
        except Exception as e:
            logger.error(f"Error scraping fencers page {page}: {e}")
            return []
    
    def scrape_rankings(self, gender: str, weapon: str, age_category: str, 
                       season: str, country: str = "") -> List[RankingEntry]:
        """Scrape rankings for specific filter combination"""
        try:
            url = f"{self.base_url}/rankings/individual-rankings"
            self.driver.get(url)
            
            # Set up filters
            selects = self.driver.find_elements(By.TAG_NAME, "select")
            
            if len(selects) >= 5:
                # Gender
                Select(selects[0]).select_by_value(gender)
                time.sleep(1)
                
                # Weapon
                Select(selects[1]).select_by_value(weapon)
                time.sleep(1)
                
                # Age category
                Select(selects[2]).select_by_value(age_category)
                time.sleep(1)
                
                # Season
                Select(selects[3]).select_by_value(season)
                time.sleep(1)
                
                # Country (if specified)
                if country:
                    Select(selects[4]).select_by_value(country)
                    time.sleep(1)
            
            # Submit search
            search_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            search_button.click()
            
            # Wait for results
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "table"))
            )
            
            # Extract ranking data
            rankings = []
            rows = self.driver.find_elements(By.CSS_SELECTOR, "tr")
            
            for row in rows[1:]:  # Skip header
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 6:
                        ranking = RankingEntry(
                            rank=int(cells[0].text.strip()) if cells[0].text.strip().isdigit() else 0,
                            competition=cells[1].text.strip(),
                            venue=cells[2].text.strip(),
                            nation=cells[3].text.strip(),
                            category=cells[4].text.strip(),
                            discipline=cells[5].text.strip(),
                            coefficient=float(cells[6].text.strip()) if len(cells) > 6 and cells[6].text.strip().replace('.','').isdigit() else 0.0,
                            season=season,
                            weapon=weapon,
                            age_group=age_category,
                            gender=gender
                        )
                        rankings.append(ranking)
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parsing ranking row: {e}")
                    continue
            
            logger.info(f"Scraped {len(rankings)} rankings for {gender}/{weapon}/{age_category}/{season}")
            return rankings
            
        except Exception as e:
            logger.error(f"Error scraping rankings: {e}")
            return []
    
    def scrape_all_fencers(self, max_pages: int = None, countries: List[str] = None) -> List[FencerProfile]:
        """Scrape all fencers with pagination"""
        all_fencers = []
        countries_to_scrape = countries or self.filter_config['countries'][:10]  # Limit for demo
        
        if not self.driver:
            self.setup_driver()
        
        try:
            for country in countries_to_scrape:
                logger.info(f"Scraping fencers for country: {country}")
                page = 1
                
                while True:
                    if max_pages and page > max_pages:
                        break
                    
                    fencers = self.scrape_fencers_page(page=page, country=country)
                    if not fencers:
                        break
                    
                    all_fencers.extend(fencers)
                    page += 1
                    
                    # Add delay to be respectful
                    time.sleep(2)
                
                logger.info(f"Completed {country}: {len(all_fencers)} total fencers")
        
        except KeyboardInterrupt:
            logger.info("Scraping interrupted by user")
        
        self.fencers_data = all_fencers
        return all_fencers
    
    def scrape_all_rankings(self, countries: List[str] = None, limit_combinations: int = None) -> List[RankingEntry]:
        """Scrape all ranking combinations"""
        all_rankings = []
        combinations_scraped = 0
        
        if not self.driver:
            self.setup_driver()
        
        try:
            for gender in self.filter_config['genders']:
                for weapon in self.filter_config['weapons']:
                    for age_category in self.filter_config['age_categories']:
                        for season in self.filter_config['seasons']:
                            if limit_combinations and combinations_scraped >= limit_combinations:
                                break
                            
                            logger.info(f"Scraping: {gender}/{weapon}/{age_category}/{season}")
                            rankings = self.scrape_rankings(gender, weapon, age_category, season)
                            all_rankings.extend(rankings)
                            combinations_scraped += 1
                            
                            # Add delay
                            time.sleep(3)
                        
                        if limit_combinations and combinations_scraped >= limit_combinations:
                            break
                    if limit_combinations and combinations_scraped >= limit_combinations:
                        break
                if limit_combinations and combinations_scraped >= limit_combinations:
                    break
        
        except KeyboardInterrupt:
            logger.info("Rankings scraping interrupted by user")
        
        self.rankings_data = all_rankings
        return all_rankings
    
    def export_to_csv(self, filename_prefix: str = "eurofencing"):
        """Export scraped data to CSV files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if self.fencers_data:
            fencers_df = pd.DataFrame([fencer.__dict__ for fencer in self.fencers_data])
            fencers_file = f"{filename_prefix}_fencers_{timestamp}.csv"
            fencers_df.to_csv(fencers_file, index=False)
            logger.info(f"Exported {len(self.fencers_data)} fencers to {fencers_file}")
        
        if self.rankings_data:
            rankings_df = pd.DataFrame([ranking.__dict__ for ranking in self.rankings_data])
            rankings_file = f"{filename_prefix}_rankings_{timestamp}.csv"
            rankings_df.to_csv(rankings_file, index=False)
            logger.info(f"Exported {len(self.rankings_data)} rankings to {rankings_file}")
    
    def export_to_json(self, filename_prefix: str = "eurofencing"):
        """Export scraped data to JSON files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if self.fencers_data:
            fencers_file = f"{filename_prefix}_fencers_{timestamp}.json"
            with open(fencers_file, 'w') as f:
                json.dump([fencer.__dict__ for fencer in self.fencers_data], f, indent=2)
            logger.info(f"Exported {len(self.fencers_data)} fencers to {fencers_file}")
        
        if self.rankings_data:
            rankings_file = f"{filename_prefix}_rankings_{timestamp}.json"
            with open(rankings_file, 'w') as f:
                json.dump([ranking.__dict__ for ranking in self.rankings_data], f, indent=2)
            logger.info(f"Exported {len(self.rankings_data)} rankings to {rankings_file}")
    
    def save_to_database(self):
        """Save scraped data to MySQL database"""
        if not self.db_config:
            logger.warning("No database configuration provided")
            return
        
        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Create tables if they don't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS eurofencing_fencers (
                    licence VARCHAR(20) PRIMARY KEY,
                    first_name VARCHAR(100),
                    last_name VARCHAR(100),
                    club VARCHAR(200),
                    nation VARCHAR(10),
                    birth_year INT,
                    gender VARCHAR(1),
                    handedness VARCHAR(20),
                    scraped_date DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
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
                    scraped_date DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Insert fencers data
            if self.fencers_data:
                fencer_values = [
                    (f.licence, f.first_name, f.last_name, f.club, f.nation, 
                     f.birth_year, f.gender, f.handedness)
                    for f in self.fencers_data
                ]
                cursor.executemany("""
                    INSERT IGNORE INTO eurofencing_fencers 
                    (licence, first_name, last_name, club, nation, birth_year, gender, handedness)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, fencer_values)
                logger.info(f"Inserted {len(self.fencers_data)} fencers to database")
            
            # Insert rankings data
            if self.rankings_data:
                ranking_values = [
                    (r.rank, r.competition, r.venue, r.nation, r.category, r.discipline,
                     r.coefficient, r.season, r.weapon, r.age_group, r.gender)
                    for r in self.rankings_data
                ]
                cursor.executemany("""
                    INSERT INTO eurofencing_rankings 
                    (rank_position, competition, venue, nation, category, discipline,
                     coefficient, season, weapon, age_group, gender)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, ranking_values)
                logger.info(f"Inserted {len(self.rankings_data)} rankings to database")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Database error: {e}")
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
        if hasattr(self, 'session'):
            self.session.close()

def main():
    """Main execution function with example usage"""
    
    # Database configuration for sportsanalytics
    db_config = {
        'host': 'localhost',  # Update with your host
        'user': 'your_username',  # Update with your username
        'password': 'your_password',  # Update with your password
        'database': 'sportsanalytics'
    }
    
    # Initialize scraper
    scraper = EuroFencingScraper(db_config=db_config, headless=True)
    
    try:
        logger.info("Starting EuroFencing comprehensive scraping...")
        
        # Setup browser
        scraper.setup_driver()
        
        # Get available countries
        countries = scraper.get_countries_list()
        logger.info(f"Found {len(countries)} countries to scrape")
        
        # Phase 1: Sample scraping (first 5 countries, 2 pages each)
        logger.info("Phase 1: Sample fencers extraction")
        sample_countries = countries[:5] if countries else ["QAT", "UAE", "SAU", "FRA", "GER"]
        fencers = scraper.scrape_all_fencers(max_pages=2, countries=sample_countries)
        logger.info(f"Scraped {len(fencers)} fencers")
        
        # Phase 2: Sample rankings (first 10 combinations)
        logger.info("Phase 2: Sample rankings extraction")
        rankings = scraper.scrape_all_rankings(limit_combinations=10)
        logger.info(f"Scraped {len(rankings)} ranking entries")
        
        # Export data
        scraper.export_to_csv("eurofencing_sample")
        scraper.export_to_json("eurofencing_sample")
        
        # Save to database (uncomment when ready)
        # scraper.save_to_database()
        
        logger.info("Scraping completed successfully!")
        
        # Print summary
        print(f"\n{'='*50}")
        print("EUROFENCING SCRAPING SUMMARY")
        print(f"{'='*50}")
        print(f"Fencers scraped: {len(fencers)}")
        print(f"Rankings scraped: {len(rankings)}")
        print(f"Countries available: {len(countries)}")
        print(f"Total possible combinations: {len(scraper.filter_config['genders']) * len(scraper.filter_config['weapons']) * len(scraper.filter_config['age_categories']) * len(scraper.filter_config['seasons'])}")
        print(f"Files exported: CSV and JSON formats")
        print(f"{'='*50}")
        
    except Exception as e:
        logger.error(f"Main execution error: {e}")
    
    finally:
        scraper.cleanup()

if __name__ == "__main__":
    main()
