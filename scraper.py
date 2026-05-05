import httpx
import xml.etree.ElementTree as ET
import asyncio
from playwright.async_api import async_playwright
import random
import datetime
import re

# Shared headers for stealth
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
]

async def scrape_wwr_jobs():
    url = "https://weworkremotely.com/remote-jobs.rss"
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            items = root.findall(".//item")
            jobs = []
            for item in items:
                title = (item.find("title").text or "No Title").strip()
                link = (item.find("link").text or "").strip()
                description = (item.find("description").text or "").strip()
                clean_desc = re.sub('<[^<]+?>', '', description)[:1000]
                if link:
                    jobs.append({
                        "title": title,
                        "link": link,
                        "description": clean_desc,
                        "source": "WWR"
                    })
            return jobs
    except Exception as e:
        print(f"WWR Scraping error: {e}")
        return []

async def scrape_reddit_jobs():
    subreddits = ["forhire", "remotework", "jobbit", "reactjs", "python"]
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    jobs = []
    ns = {'ns': 'http://www.w3.org/2005/Atom'}
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        for sub in subreddits:
            url = f"https://www.reddit.com/r/{sub}/new/.rss"
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    root = ET.fromstring(response.text)
                    entries = root.findall('ns:entry', ns)
                    for entry in entries:
                        title = entry.find('ns:title', ns).text
                        link = entry.find('ns:link', ns).attrib['href']
                        content_el = entry.find('ns:content', ns)
                        description = content_el.text if content_el is not None else ""
                        clean_desc = re.sub('<[^<]+?>', '', description)[:1500]
                        if "[hiring]" in title.lower() or "hiring" in title.lower():
                            jobs.append({
                                "title": f"r/{sub}: {title}",
                                "link": link,
                                "description": clean_desc,
                                "source": "Reddit"
                            })
            except Exception as e:
                print(f"Reddit r/{sub} Scraping error: {e}")
    return jobs

async def scrape_hn_jobs():
    # Targets Hacker News "Who is hiring" threads
    url = "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=1"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            data = resp.json()
            if data['hits']:
                latest_thread = data['hits'][0]
                thread_id = latest_thread['objectID']
                title = latest_thread['title']
                comments_url = f"https://hn.algolia.com/api/v1/search?tags=comment,story_{thread_id}&hitsPerPage=100"
                c_resp = await client.get(comments_url)
                c_data = c_resp.json()
                jobs = []
                for hit in c_data['hits']:
                    desc = hit.get('comment_text', '')
                    clean_desc = re.sub('<[^<]+?>', '', desc)[:1500]
                    # Filter for Full Stack or Web Dev if possible, or just take all high quality ones
                    if any(kw in clean_desc.lower() for kw in ["full stack", "frontend", "backend", "web", "react", "node"]):
                        jobs.append({
                            "title": f"HN Hiring: {title[:50]}... (by {hit['author']})",
                            "link": f"https://news.ycombinator.com/item?id={hit['objectID']}",
                            "description": clean_desc,
                            "source": "HackerNews"
                        })
                return jobs
    except Exception as e:
        print(f"HN Scraping error: {e}")
    return []

async def scrape_simplyhired_jobs():
    jobs = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = await context.new_page()
            url = "https://www.simplyhired.com/search?q=full+stack+web+developer&l=Remote"
            await page.goto(url)
            try:
                await page.wait_for_selector('li[data-testid="jobs-list-item"]', timeout=10000)
            except:
                await browser.close()
                return []
            job_elements = await page.query_selector_all('li[data-testid="jobs-list-item"]')
            for job in job_elements:
                title_el = await job.query_selector('h3')
                title = await title_el.inner_text() if title_el else "No Title"
                link_el = await job.query_selector('a')
                link = await link_el.get_attribute('href') if link_el else "#"
                if not link.startswith("http"):
                    link = f"https://www.simplyhired.com{link}"
                snippet_el = await job.query_selector('p[data-testid="jobSnippet"]')
                description = await snippet_el.inner_text() if snippet_el else "Detailed job on SimplyHired"
                jobs.append({
                    "title": title,
                    "link": link,
                    "description": description,
                    "source": "SimplyHired"
                })
            await browser.close()
    except Exception as e:
        print(f"SimplyHired Scraping error: {e}")
    return jobs

async def scrape_remoteok_jobs():
    url = "https://remoteok.com/remote-jobs.rss"
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            items = root.findall(".//item")
            jobs = []
            for item in items:
                title = item.find("title").text
                link = item.find("link").text
                description = item.find("description").text if item.find("description") is not None else ""
                clean_desc = re.sub('<[^<]+?>', '', description)[:1000]
                jobs.append({
                    "title": title,
                    "link": link,
                    "description": clean_desc,
                    "source": "RemoteOK"
                })
            return jobs
    except Exception as e:
        print(f"RemoteOK Scraping error: {e}")
        return []

async def scrape_x_jobs():
    """Scrapes X (Twitter) for job postings using Playwright (Best Effort)."""
    jobs = []
    queries = ["hiring full stack remote", "hiring web developer remote"]
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = await context.new_page()
            for query in queries:
                url = f"https://twitter.com/search?q={query.replace(' ', '%20')}&f=live"
                try:
                    await page.goto(url, timeout=30000)
                    await asyncio.sleep(5)
                    tweets = await page.query_selector_all('article[data-testid="tweet"]')
                    for tweet in tweets[:10]:
                        text_el = await tweet.query_selector('div[data-testid="tweetText"]')
                        text = await text_el.inner_text() if text_el else ""
                        link_el = await tweet.query_selector('a[href*="/status/"]')
                        link_suffix = await link_el.get_attribute('href') if link_el else ""
                        link = f"https://twitter.com{link_suffix}" if link_suffix else "https://twitter.com"
                        if text:
                            jobs.append({
                                "title": f"X Job: {text[:60]}...",
                                "link": link,
                                "description": text,
                                "source": "X"
                            })
                except:
                    continue
            await browser.close()
    except Exception as e:
        print(f"X Scraping error: {e}")
    return jobs

async def scrape_threads_jobs():
    """Scrapes Threads.net for job postings (Best Effort)."""
    jobs = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
            page = await context.new_page()
            url = "https://www.threads.net/search?q=hiring%20full%20stack%20remote"
            await page.goto(url)
            await asyncio.sleep(5)
            # Threads is very restrictive, this is a placeholder for actual scraping logic if bypass is found
            # For now, it might just return empty if blocked by login wall
            await browser.close()
    except Exception as e:
        print(f"Threads Scraping error: {e}")
    return jobs

async def scrape_all_jobs():
    # Run multiple scrapers concurrently for performance
    tasks = [
        scrape_wwr_jobs(),
        scrape_reddit_jobs(),
        scrape_hn_jobs(),
        scrape_remoteok_jobs(),
        scrape_simplyhired_jobs(),
        scrape_x_jobs(),
        scrape_threads_jobs()
    ]
    results = await asyncio.gather(*tasks)
    all_jobs = []
    for res in results:
        all_jobs.extend(res)
    return all_jobs

def scrape_freelancers(keyword):
    print(f"Scouting for: {keyword}")
    return [
        {"name": f"Expert {keyword} 1", "link": f"https://linkedin.com/in/expert1", "skills": f"{keyword}, Design", "source": "LinkedIn"},
        {"name": f"Pro {keyword} 2", "link": f"https://freelancer.com/u/pro2", "skills": f"{keyword}, Dev", "source": "Freelancer.com"},
    ]

if __name__ == "__main__":
    jobs = asyncio.run(scrape_all_jobs())
    print(f"Scraped {len(jobs)} total jobs.")
