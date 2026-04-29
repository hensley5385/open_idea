import httpx
import xml.etree.ElementTree as ET

def scrape_wwr_jobs():
    url = "https://weworkremotely.com/remote-jobs.rss"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = httpx.get(url, headers=headers, follow_redirects=True)
        response.raise_for_status()

        # Parse RSS without external XML parser dependencies (e.g. lxml).
        root = ET.fromstring(response.text)
        items = root.findall(".//item")

        jobs = []
        for item in items:
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")

            title = (title_el.text or "").strip() if title_el is not None else "No Title"
            link = (link_el.text or "").strip() if link_el is not None else None
            description = (desc_el.text or "").strip() if desc_el is not None else ""
            
            if link:
                jobs.append({
                    "title": title,
                    "link": link,
                    "description": description
                })
        
        return jobs
    except Exception as e:
        print(f"Scraping error: {e}")
        return []

def scrape_freelancers(keyword):
    # This is a mock implementation as scraping LinkedIn/Freelancer directly 
    # usually requires complex anti-bot bypass or API access.
    # We simulate the scraping results for the demonstration.
    
    # In a real scenario, you'd use something like Selenium or a specialized scraping API.
    print(f"Scouting for: {keyword}")
    
    # Mock data based on the keyword
    mock_results = [
        {"name": f"Expert {keyword} 1", "link": f"https://linkedin.com/in/expert1", "skills": f"{keyword}, Design, Strategy", "source": "LinkedIn"},
        {"name": f"Pro {keyword} 2", "link": f"https://freelancer.com/u/pro2", "skills": f"{keyword}, Development", "source": "Freelancer.com"},
        {"name": f"Senior {keyword} 3", "link": f"https://indeed.com/r/senior3", "skills": f"{keyword}, Management", "source": "Indeed"},
    ]
    
    return mock_results

if __name__ == "__main__":
    jobs = scrape_wwr_jobs()
    print(f"Scraped {len(jobs)} jobs.")
    
    freelancers = scrape_freelancers("Logo Designer")
    print(f"Sourced {len(freelancers)} freelancers.")

