# Tavily Integration Guide

## What is Tavily?

Tavily is an AI-powered research API that solves the fundamental limitation of HTML-only scraping:

**Problem with Brave Search + trafilatura:**
- Cannot read JavaScript-rendered content
- Fails on modern websites (news sites, social media, many blogs)
- Returns empty or partial content even when URLs are found

**Tavily Solution:**
- Uses headless browsers to render JavaScript
- Production-grade content extraction
- Better relevance ranking
- Simpler codebase (replaces 500+ lines with one API call)

## Quick Start

### 1. Get Tavily API Key

1. Go to https://tavily.com
2. Sign up for free account
3. Get your API key
4. Free tier: 1000 searches/month

### 2. Install Tavily SDK

```bash
pip install tavily-python
```

### 3. Configure Environment

Edit your `.env` file:

```bash
# Add your Tavily API key
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxxxx
```

### 4. Test It

Run your CLI:

```bash
python main.py
```

Try the same queries that failed before:
- "can donald trump attack greenland"
- "can greenland defend itself"

You should now get **full content** from modern news sites instead of empty extracts.

## How It Works

### Current Architecture (Tavily-only):
```
User Query
  ↓
Tavily API → Returns full extracted content (handles JavaScript) ✅
  ↓
Clean, relevant sources ready for LLM
```

**Removed components:**
- ❌ Brave Search API
- ❌ WebFetcher (HTTP client)
- ❌ ContentExtractor (trafilatura/BeautifulSoup)
- ❌ SearchProvider base class

**Result:** ~500 lines of complex code replaced with one simple API call.

## Architecture Changes

### Files Created:
1. **tools/web/tavily_client.py** - Tavily API client
2. **tools/web/tavily_service.py** - Research service using Tavily

### Files Simplified:
3. **tools/web/factory.py** - Now only creates Tavily service (simplified from 80 lines to 40 lines)
4. **.env** - Removed Brave settings, only TAVILY_API_KEY needed

### Files REMOVED (no longer needed):
- ❌ **search_brave.py** - Replaced by Tavily API
- ❌ **fetcher.py** - Tavily handles fetching with headless browser
- ❌ **extractor.py** - Tavily handles extraction
- ❌ **search_provider_base.py** - No longer needed
- ❌ **research_service.py** - Replaced by tavily_service.py

**Code reduction:** ~500 lines removed, codebase significantly simplified.

## Cost

### Tavily Pricing:
- **Free tier:** 1000 searches/month
- **Paid:** $1 per 1000 searches ($0.001 per search)
- **Enterprise:** Custom pricing for high volume

For most development and testing, the free tier is sufficient. Production usage typically costs less than $10/month for moderate traffic.

## Testing

### Test 1: Modern News Site (JavaScript-heavy)

**Query:** "can donald trump attack greenland"

**Expected Results:**
- ✅ URLs found from reputable sources
- ✅ Full content extracted (not empty)
- ✅ Relevant excerpts with actual information
- ✅ 3-5 high-quality sources

### Test 2: Follow-up Query

**Query:** "can greenland defend itself"

**Expected Results:**
- ✅ Triggers research (military/defense topic)
- ✅ Returns military analysis sources
- ✅ Full content about Greenland's defense capabilities
- ✅ NATO/Denmark defense relationship explained

### Test 3: Meta Command

**Query:** "can u check over internet for more info"

**Expected:**
- Query refiner detects meta-command
- Uses previous question context
- Performs new search with refined query

## Troubleshooting

### Error: "TAVILY_API_KEY not set"
- Make sure you added `TAVILY_API_KEY=tvly-xxx` to your `.env` file
- Make sure you set `USE_TAVILY=true`

### Error: "tavily-python not found"
- Run: `pip install tavily-python`

### Still getting empty content
- Check that `TAVILY_API_KEY` is set correctly in `.env`
- Check logs for "🚀 Using Tavily for web research"
- Verify your Tavily API key is valid at https://tavily.com

### Tavily returning fewer sources
- Tavily filters out low-quality sources automatically
- This is GOOD - fewer but higher quality results

## Next Steps

1. Install: `pip install tavily-python`
2. Get API key: https://tavily.com (free tier: 1000 searches/month)
3. Update `.env`: Set `TAVILY_API_KEY=tvly-your-key-here`
4. Test with your queries
5. Enjoy much better research results!

## Benefits Summary

✅ **JavaScript rendering** - Reads all modern websites
✅ **Simpler codebase** - ~500 lines of code removed
✅ **Better quality** - Production-grade extraction
✅ **Free tier** - 1000 searches/month at no cost
✅ **Reliable** - No more empty content issues
