import json
import logging
import os
from typing import Any, Dict, List, Optional
import numpy as np

from ingestion.embeddings import get_embedding, get_embeddings
from ingestion.rss_fetcher import fetch_all_feeds
from ingestion.news_extractor import extract_news

logger = logging.getLogger(__name__)

class SignalMonitor:
    def __init__(self, profiles_path: str = "data/mission_profiles.json"):
        self.profiles_path = profiles_path
        self.profiles = self._load_profiles()
        self.mission_vectors: Dict[str, np.ndarray] = {}
        self.refresh_mission_embeddings()

    def _load_profiles(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.profiles_path):
            return []
        try:
            with open(self.profiles_path, "r") as f:
                return json.load(f).get("profiles", [])
        except Exception as e:
            logger.error(f"Failed to load mission profiles: {e}")
            return []

    def refresh_mission_embeddings(self):
        """Pre-calculate embeddings for all mission profiles."""
        for profile in self.profiles:
            text = f"{profile['name']}: {profile['description']}"
            # Include keywords for extra semantic weight
            if profile.get('keywords'):
                text += " Keywords: " + ", ".join(profile['keywords'])
            
            try:
                self.mission_vectors[profile['id']] = get_embedding(text, role="query")
                logger.info(f"Embedded mission profile: {profile['id']}")
            except Exception as e:
                logger.error(f"Failed to embed profile {profile['id']}: {e}")

    def fetch_headlines_firehose(self) -> List[Dict[str, Any]]:
        """
        Simulate a news firehose. 
        In a production environment, this would call NewsAPI or a similar firehose.
        For now, we use a wide set of broad RSS categories as the input stream.
        """
        from config.rss_sources import RSS_FEEDS
        # Use all categories to get a "firehose" effect
        broad_feeds = []
        for cat, feeds in RSS_FEEDS.items():
            for lbl, url in feeds:
                broad_feeds.append((cat, lbl, url))
        
        # We only want headlines/summaries at this stage (fast pass)
        # We bypass full text extraction in the initial fetch to keep it light
        articles = fetch_all_feeds(broad_feeds, skip_seen=True)
        return articles

    def screen_signals(self, articles: List[Dict[str, Any]], threshold: float = 0.75) -> List[Dict[str, Any]]:
        """
        Filter a batch of articles against all mission profiles using semantic similarity.
        """
        if not articles or not self.mission_vectors:
            return []

        # Extract headlines for batch embedding
        headlines = [a.get("title", "") for a in articles]
        headline_vectors = get_embeddings(headlines, role="passage")
        
        signals = []
        for i, h_vec in enumerate(headline_vectors):
            if h_vec is None:
                continue
            
            best_score = 0.0
            best_profile = None
            
            for pid, m_vec in self.mission_vectors.items():
                score = np.dot(h_vec, m_vec) # Assuming normalized vectors
                if score > best_score:
                    best_score = score
                    best_profile = pid
            
            if best_score >= threshold:
                article = articles[i]
                article["signal_score"] = float(best_score)
                article["matched_profile"] = best_profile
                signals.append(article)
        
        logger.info(f"Screening complete. Found {len(signals)}/{len(articles)} high-signal articles.")
        return sorted(signals, key=lambda x: x["signal_score"], reverse=True)

    def process_high_signal_news(self, threshold: float = 0.8) -> List[Dict[str, Any]]:
        """
        Main loop: Fetch → Screen → (Optional: Deep Extraction) → Result.
        """
        logger.info("Starting Signal Monitor cycle...")
        firehose = self.fetch_headlines_firehose()
        signals = self.screen_signals(firehose, threshold=threshold)
        
        # For top signals, we ensure full text is extracted if not already present
        # (Though rss_fetcher already tries this, we might want a re-pass with a better extractor here)
        return signals

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    monitor = SignalMonitor()
    results = monitor.process_high_signal_news(threshold=0.7)
    for res in results[:10]:
        print(f"[{res['matched_profile']}] Score: {res['signal_score']:.2f} | {res['title']}")
