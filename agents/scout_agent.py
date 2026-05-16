"""
agents/scout_agent.py — Scout Agent (Free APIs)
"""
import os
import re
import hashlib
import logging
import requests
from datetime import datetime
from typing import List, Dict, Optional, Callable

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


class ScoutAgent:
    def __init__(self):
        self.seen_hashes = set()
        self.jsearch_key = os.getenv("RAPIDAPI_KEY", "")
        self.adzuna_app_id = os.getenv("ADZUNA_APP_ID", "")
        self.adzuna_app_key = os.getenv("ADZUNA_APP_KEY", "")

    def run(
        self,
        roles: list,
        locations: list,
        work_types: list,
        max_per_query: int = 20,
        max_per_source: int = None,
        progress_callback=None,
    ) -> list:
        
        limit = max_per_source if max_per_source is not None else max_per_query
        all_jobs = []

        # JSearch
        if self.jsearch_key:
            if progress_callback:
                progress_callback(15, "🔍 JSearch se jobs fetch kar raha hoon...")
            try:
                jobs = self._fetch_jsearch(roles, locations, limit)
                all_jobs.extend(jobs)
                logger.info(f"JSearch: {len(jobs)} jobs")
            except Exception as e:
                logger.warning(f"JSearch error: {e}")

        # Adzuna
        if self.adzuna_app_id and self.adzuna_app_key:
            if progress_callback:
                progress_callback(50, "📊 Adzuna se jobs fetch kar raha hoon...")
            try:
                jobs = self._fetch_adzuna(roles, locations, limit)
                all_jobs.extend(jobs)
                logger.info(f"Adzuna: {len(jobs)} jobs")
            except Exception as e:
                logger.warning(f"Adzuna error: {e}")

        if progress_callback:
            progress_callback(85, "🔄 Duplicates hata raha hoon...")

        unique = self._deduplicate(all_jobs)
        final = self._score_jobs(unique, roles, locations)

        if progress_callback:
            progress_callback(95, f"✅ {len(final)} unique jobs mili!")

        return final

    def _fetch_jsearch(self, roles: list, locations: list, limit: int) -> list:
        jobs = []
        for role in roles[:3]:
            for loc in locations[:2]:
                try:
                    query = f"{role} {loc}"
                    url = "https://jsearch.p.rapidapi.com/search"
                    response = requests.get(
                        url,
                        headers={
                            "X-RapidAPI-Key": self.jsearch_key,
                            "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
                        },
                        params={
                            "query": query,
                            "page": "1",
                            "num_pages": "1",
                            "date_posted": "week",
                        },
                        timeout=15,
                    )
                    if response.status_code != 200:
                        continue
                    data = response.json()
                    results = data.get("data", [])
                    for item in results[:limit]:
                        title = item.get("job_title", "")
                        if not title:
                            continue
                        desc = item.get("job_description", "")[:800]
                        desc = re.sub(r"<[^>]+>", " ", desc)
                        job = {
                            "id": hashlib.md5(f"{title}_{item.get('employer_name','')}".encode()).hexdigest()[:16],
                            "title": title,
                            "company": item.get("employer_name", "Unknown"),
                            "location": item.get("job_city", "Remote") or item.get("job_country", "Remote"),
                            "description": desc,
                            "url": item.get("job_apply_link", ""),
                            "source": "JSearch",
                            "posted_date": item.get("job_posted_at_datetime_utc", "Recent")[:10],
                            "scraped_at": datetime.utcnow().isoformat(),
                            "quick_score": 0,
                            "status": "new",
                            "is_remote": "remote" in title.lower(),
                            "salary": item.get("job_salary", ""),
                            "tags": [role],
                        }
                        jobs.append(job)
                except Exception as e:
                    logger.warning(f"JSearch error: {e}")
        return jobs

    def _fetch_adzuna(self, roles: list, locations: list, limit: int) -> list:
        jobs = []
        country_map = {
            "Pakistan": "pk", "Islamabad": "pk", "Lahore": "pk", "Karachi": "pk",
            "Remote": "us", "USA": "us", "UK": "gb",
        }
        for role in roles[:3]:
            for loc in locations[:2]:
                country_code = country_map.get(loc, "us")
                try:
                    url = f"https://api.adzuna.com/v1/api/jobs/{country_code}/search/1"
                    response = requests.get(
                        url,
                        params={
                            "app_id": self.adzuna_app_id,
                            "app_key": self.adzuna_app_key,
                            "what": role,
                            "where": "" if loc == "Remote" else loc,
                            "results_per_page": limit,
                        },
                        timeout=15,
                    )
                    if response.status_code != 200:
                        continue
                    data = response.json()
                    results = data.get("results", [])
                    for item in results[:limit]:
                        title = item.get("title", "")
                        if not title:
                            continue
                        desc = item.get("description", "")[:800]
                        desc = re.sub(r"<[^>]+>", " ", desc)
                        job = {
                            "id": hashlib.md5(str(item.get("id", title)).encode()).hexdigest()[:16],
                            "title": title,
                            "company": item.get("company", {}).get("display_name", "Unknown"),
                            "location": item.get("location", {}).get("display_name", "Remote"),
                            "description": desc,
                            "url": item.get("redirect_url", ""),
                            "source": "Adzuna",
                            "posted_date": item.get("created", "Recent")[:10],
                            "scraped_at": datetime.utcnow().isoformat(),
                            "quick_score": 0,
                            "status": "new",
                            "is_remote": "remote" in title.lower(),
                            "salary": f"{item.get('salary_min', '')} - {item.get('salary_max', '')}",
                            "tags": [role],
                        }
                        jobs.append(job)
                except Exception as e:
                    logger.warning(f"Adzuna error: {e}")
        return jobs

    def _deduplicate(self, jobs: list) -> list:
        unique = []
        for job in jobs:
            key = f"{job['title'].lower()}|{job['company'].lower()}"
            h = hashlib.md5(key.encode()).hexdigest()[:16]
            if h not in self.seen_hashes:
                self.seen_hashes.add(h)
                unique.append(job)
        return unique

    def _score_jobs(self, jobs: list, roles: list, locations: list) -> list:
        role_kws = [r.lower() for r in roles]
        for job in jobs:
            text = (job["title"] + " " + job["description"]).lower()
            found = sum(1 for kw in role_kws if kw in text)
            score = round((found / max(len(role_kws), 1)) * 100)
            if job.get("is_remote"):
                score = min(score + 15, 100)
            job["quick_score"] = score
        return sorted(jobs, key=lambda j: j["quick_score"], reverse=True)


def save_jobs_to_firebase(db, jobs: list) -> int:
    if not jobs:
        return 0
    saved = 0
    for job in jobs:
        try:
            ref = db.collection("jobs").document(job["id"])
            ref.set(job, merge=True)
            saved += 1
        except Exception as e:
            logger.warning(f"Save error: {e}")
    return saved