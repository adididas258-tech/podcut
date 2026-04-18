import os
import json
import anthropic
from flask import Flask, jsonify, request
from flask_cors import CORS
from news_service import fetch_articles, get_article, get_full_article_content

app = Flask(__name__)
CORS(app)

def get_claude():
    api_key = request.headers.get("X-API-Key") or os.environ.get("ANTHROPIC_API_KEY", "")
    return anthropic.Anthropic(api_key=api_key)


@app.route("/api/feed")
def feed():
    category = request.args.get("category")
    force = request.args.get("refresh") == "true"
    articles = fetch_articles(force=force)
    if category and category != "All":
        articles = [a for a in articles if a["category"] == category]
    return jsonify({"articles": articles[:40], "total": len(articles)})


@app.route("/api/article/<article_id>")
def article_detail(article_id):
    article = get_article(article_id)
    if not article:
        return jsonify({"error": "Article not found"}), 404

    content = get_full_article_content(article["url"])
    article_with_content = {**article, "full_content": content}

    try:
        client = get_claude()
        context = f"Title: {article['title']}\n\nContent: {content or article['summary']}"
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": f"""You are an expert analyst for a serious, intelligent news platform.

Analyze this article and return ONLY a valid JSON object with these exact keys:
- "analysis": 2-3 sentence sharp editorial analysis of why this matters
- "key_points": array of exactly 3 concise bullet strings (each under 15 words)
- "significance": one sentence on the broader significance
- "sentiment": one of "Positive", "Negative", "Neutral", "Mixed"
- "tags": array of 2-4 relevant topic strings

Article:
{context}

Return ONLY the JSON object, no other text."""
            }]
        )
        analysis = json.loads(response.content[0].text.strip())
    except Exception as e:
        analysis = {
            "analysis": article["summary"],
            "key_points": [],
            "significance": "",
            "sentiment": "Neutral",
            "tags": [article["category"]],
        }

    return jsonify({**article_with_content, "ai_analysis": analysis})


@app.route("/api/deep-dive/<article_id>")
def deep_dive(article_id):
    article = get_article(article_id)
    if not article:
        return jsonify({"error": "Article not found"}), 404

    content = get_full_article_content(article["url"])
    context = f"Title: {article['title']}\n\nContent: {content or article['summary']}"

    try:
        client = get_claude()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1200,
            messages=[{
                "role": "user",
                "content": f"""You are a senior analyst writing for a sophisticated, intellectually curious audience.

Produce a deep-dive analysis of this article. Return ONLY a valid JSON object with:
- "headline": compelling re-framing of the story (under 12 words)
- "executive_summary": 3-4 sentences of sharp, insightful analysis
- "context": 2-3 sentences on historical or industry context
- "implications": array of 3 strings, each describing a forward-looking implication
- "counterpoints": 1-2 sentences presenting a critical or opposing perspective
- "related_themes": array of 3 broader themes this story connects to
- "questions_raised": array of 3 important questions this story leaves unanswered
- "reading_list": array of 2 suggested search queries for further reading

Article:
{context}

Return ONLY the JSON object."""
            }]
        )
        result = json.loads(response.content[0].text.strip())
    except Exception as e:
        result = {"error": str(e), "executive_summary": article["summary"]}

    return jsonify(result)


@app.route("/api/explain", methods=["POST"])
def explain():
    data = request.get_json()
    passage = data.get("passage", "")
    article_context = data.get("article_title", "")
    mode = data.get("mode", "explain")  # "explain", "simplify", "expand"

    prompts = {
        "explain": f"Explain this passage clearly in 2-3 sentences for an intelligent general audience. Be direct and informative.",
        "simplify": f"Explain this in plain language, as if talking to someone unfamiliar with the topic. Keep it to 2 sentences.",
        "expand": f"Expand on this passage with additional context, data, or analysis in 3-4 sentences.",
    }

    try:
        client = get_claude()
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": f"""Article: "{article_context}"

Passage: "{passage}"

{prompts.get(mode, prompts['explain'])}

Return ONLY a JSON object: {{"explanation": "your response here"}}"""
            }]
        )
        result = json.loads(response.content[0].text.strip())
    except Exception as e:
        result = {"explanation": "Unable to generate explanation at this time."}

    return jsonify(result)


@app.route("/api/categories")
def categories():
    articles = fetch_articles()
    cats = sorted(set(a["category"] for a in articles))
    return jsonify({"categories": ["All"] + cats})


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5174)
