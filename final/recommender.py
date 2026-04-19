from __future__ import annotations

import logging
import math
import random
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from database import DB_PATH, db_connect, fetch_categories, import_csvs, init_db
from ddqn_agent import DDQNAgent
from utils import (
    category_preference_from_text,
    clamp,
    compute_interaction_score,
    compute_reward,
    diversity_limited,
    lexical_similarity,
    normalize_0_1,
    small_randomness,
)
from webcam_attention import (
    compute_attention_score,
    compute_energy_score,
    compute_gaze_score,
    get_latest_attention_snapshot,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except Exception:
    TfidfVectorizer = None
    cosine_similarity = None


class NewsRecommender:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._agents: dict[str, DDQNAgent] = {}
        self._tfidf_vectorizer = None  # cached at first use
        init_db(db_path)
        with db_connect(db_path) as conn:
            news_count = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
        if news_count == 0:
            import_csvs(db_path=db_path, force=False)

    def categories(self) -> list[str]:
        return fetch_categories(self.db_path)

    def _agent(self, user_id: str) -> DDQNAgent:
        categories = self.categories()
        agent = self._agents.get(user_id)
        if agent is None or agent.categories != categories:
            agent = DDQNAgent(categories, user_id=user_id, db_path=self.db_path)
            self._agents[user_id] = agent
        return agent

    def _ensure_vectorizer(self) -> None:
        if self._tfidf_vectorizer is not None or TfidfVectorizer is None:
            return
        try:
            with db_connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT category, subcategory, abstract FROM news LIMIT 15000"
                ).fetchall()
            docs = [f"{r['category']} {r['subcategory']} {r['abstract']}" for r in rows]
            self._tfidf_vectorizer = TfidfVectorizer(max_features=2000, stop_words="english")
            self._tfidf_vectorizer.fit(docs)
            logger.info("TF-IDF vectorizer fitted on %d articles", len(docs))
        except Exception as exc:
            logger.warning("TF-IDF vectorizer init failed: %s", exc)
            self._tfidf_vectorizer = None

    def onboard_user(self, payload: dict[str, Any]) -> dict[str, Any]:
        categories = self.categories()
        user_id = payload.get("user_id") or f"user_{random.randint(10000, 99999)}"
        interests = payload.get("interests", [])
        if isinstance(interests, str):
            interests = [interests]
        interest_text = " ".join(interests + [payload.get("mood", ""), payload.get("sample_click", "")])
        exploration = float(payload.get("exploration_preference", 0.25))
        attention = 0.55 + min(float(payload.get("time_available", 10)) / 60.0, 0.25)
        interaction = 0.45 + (0.15 if payload.get("sample_click") else 0.0)

        with db_connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO users
                (user_id, user_interest_text, mood, time_available, time_of_day,
                 current_location, attention_score, interaction_score, recent_activity,
                 exploration_signal, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    user_id,
                    interest_text,
                    payload.get("mood", ""),
                    float(payload.get("time_available", 10)),
                    payload.get("time_of_day", ""),
                    payload.get("location", ""),
                    clamp(attention),
                    clamp(interaction),
                    clamp(interaction),
                    clamp(exploration),
                ),
            )
            prefs = category_preference_from_text(categories, interest_text)
            for cat, pref in prefs.items():
                if cat in categories:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO user_category_prefs
                        (user_id, category, preference, dislikes, blocked_until_step, updated_at)
                        VALUES (?, ?, ?, 0, 0, CURRENT_TIMESTAMP)
                        """,
                        (user_id, cat, pref),
                    )
        self._agent(user_id).save()
        return {"user_id": user_id, "categories": categories, "message": "onboarded"}

    def _user_row(self, user_id: str):
        with db_connect(self.db_path) as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if row is None:
                self.onboard_user({"user_id": user_id, "interests": [], "exploration_preference": 0.3})
                row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row

    def _category_pref(self, user_id: str, category: str) -> float:
        with db_connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT preference FROM user_category_prefs WHERE user_id = ? AND category = ?",
                (user_id, category),
            ).fetchone()
        return clamp(row["preference"] if row else 0.2)

    def _all_category_prefs(self, user_id: str) -> dict[str, float]:
        with db_connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT category, preference FROM user_category_prefs WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return {r["category"]: clamp(r["preference"]) for r in rows}

    def build_state(self, user_id: str, category: str, overrides: dict[str, Any] | None = None) -> list[float]:
        row = self._user_row(user_id)
        all_prefs = self._all_category_prefs(user_id)
        return self.build_state_from_row(row, category, all_prefs, overrides)

    def build_state_from_row(
        self,
        user_row,
        category: str,
        all_prefs: dict[str, float],
        overrides: dict[str, Any] | None = None,
    ) -> list[float]:
        overrides = overrides or {}
        return [
            normalize_0_1(overrides.get("attention_score", user_row["attention_score"])),
            normalize_0_1(overrides.get("interaction_score", user_row["interaction_score"])),
            normalize_0_1(user_row["recent_activity"]),
            all_prefs.get(category, 0.2),
            normalize_0_1(overrides.get("exploration_signal", user_row["exploration_signal"])),
        ]

    def blocked_categories(self, user_id: str, agent_step: int) -> set[str]:
        with db_connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT category FROM user_category_prefs
                WHERE user_id = ? AND dislikes >= 2 AND blocked_until_step > ?
                """,
                (user_id, agent_step),
            ).fetchall()
        return {r["category"] for r in rows}

    def _recent_memory(self, user_id: str) -> tuple[set[str], Counter[str]]:
        with db_connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT news_id, category FROM user_memory
                WHERE user_id = ?
                ORDER BY position DESC
                LIMIT 80
                """,
                (user_id,),
            ).fetchall()
        return {r["news_id"] for r in rows}, Counter(r["category"] for r in rows)

    def _recent_liked_boosts(self, user_id: str) -> dict[str, float]:
        with db_connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT category, COUNT(*) AS likes
                FROM (
                    SELECT category
                    FROM interactions
                    WHERE user_id = ? AND liked = 1
                    ORDER BY created_at DESC
                    LIMIT 30
                )
                GROUP BY category
                """,
                (user_id,),
            ).fetchall()
        return {r["category"]: min(0.20, 0.05 * int(r["likes"])) for r in rows}

    def _candidate_rows(
        self,
        user_id: str,
        limit: int = 25,
        mode: str = "personalized",
        blocked: set[str] | None = None,
        location: str | None = None,
    ) -> list[dict[str, Any]]:
        blocked = blocked or set()
        seen_news, _ = self._recent_memory(user_id)
        blocked_sql = ",".join("?" for _ in blocked) or "''"
        seen_sql = ",".join("?" for _ in seen_news) or "''"
        params: list[Any] = list(blocked) + list(seen_news)
        location_clause = ""
        if location:
            location_clause = " AND location = ?"
            params.append(location)
        where = f"WHERE category NOT IN ({blocked_sql}) AND news_id NOT IN ({seen_sql}){location_clause}"

        if mode == "trending":
            order = """
            ORDER BY COALESCE((SELECT trending_score FROM category_stats s WHERE s.category = news.category), 0) DESC,
                     RANDOM()
            """
        elif mode == "random":
            order = "ORDER BY RANDOM()"
        else:
            order = """
            ORDER BY COALESCE((SELECT preference FROM user_category_prefs p
                               WHERE p.user_id = ? AND p.category = news.category), 0.2) DESC,
                     RANDOM()
            """
            params = params + [user_id]

        with db_connect(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT news_id, category, subcategory, location, preferred_time, age_group,
                       article_length, abstract, full_article, url
                FROM news
                {where}
                {order}
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def _fetch_candidates_conn(
        self,
        conn,
        user_id: str,
        seen_news: set[str],
        blocked: set[str],
        pool_size: int = 25,
        location: str | None = None,
    ) -> list[dict[str, Any]]:
        blocked_sql = ",".join("?" for _ in blocked) or "''"
        seen_sql = ",".join("?" for _ in seen_news) or "''"
        base_filter = f"news.category NOT IN ({blocked_sql}) AND news.news_id NOT IN ({seen_sql})"
        base_params = list(blocked) + list(seen_news)
        if location:
            base_filter += " AND news.location = ?"
            base_params.append(location)

        SELECT_COLS = (
            "news.news_id, news.category, news.subcategory, news.location,"
            " news.preferred_time, news.age_group, news.article_length,"
            " news.abstract, news.full_article, news.url"
        )

        mix = [
            ("personalized", max(1, round(pool_size * 0.6))),
            ("trending", max(1, round(pool_size * 0.2))),
            ("random", pool_size - round(pool_size * 0.6) - round(pool_size * 0.2)),
        ]

        candidates: list[dict[str, Any]] = []
        global_seen = set(seen_news)

        for mode, count in mix:
            if mode == "personalized":
                sql = (
                    f"SELECT {SELECT_COLS}"
                    " FROM news"
                    " LEFT JOIN user_category_prefs ucp"
                    "   ON ucp.user_id = ? AND ucp.category = news.category"
                    f" WHERE {base_filter}"
                    " ORDER BY COALESCE(ucp.preference, 0.2) DESC, RANDOM()"
                    " LIMIT ?"
                )
                params = [user_id] + base_params + [max(25, count * 3)]
            elif mode == "trending":
                sql = (
                    f"SELECT {SELECT_COLS}"
                    " FROM news"
                    " LEFT JOIN category_stats cs ON cs.category = news.category"
                    f" WHERE {base_filter}"
                    " ORDER BY COALESCE(cs.trending_score, 0) DESC, RANDOM()"
                    " LIMIT ?"
                )
                params = base_params + [max(25, count * 3)]
            else:
                sql = (
                    f"SELECT {SELECT_COLS} FROM news"
                    f" WHERE {base_filter}"
                    " ORDER BY RANDOM()"
                    " LIMIT ?"
                )
                params = base_params + [max(25, count * 3)]

            rows = conn.execute(sql, params).fetchall()

            added = 0
            for r in rows:
                row = dict(r)
                if row["news_id"] not in global_seen:
                    row["source_mix"] = mode
                    candidates.append(row)
                    global_seen.add(row["news_id"])
                    added += 1
                if added >= count:
                    break

        return candidates

    def _category_balanced_rows(
        self,
        user_id: str,
        per_category: int = 4,
        blocked: set[str] | None = None,
        exclude_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        blocked = blocked or set()
        exclude_ids = exclude_ids or set()
        seen_news, _ = self._recent_memory(user_id)
        exclude = seen_news | exclude_ids
        rows: list[dict[str, Any]] = []
        with db_connect(self.db_path) as conn:
            for category in self.categories():
                if category in blocked:
                    continue
                exclude_sql = ",".join("?" for _ in exclude) or "''"
                query = f"""
                    SELECT news_id, category, subcategory, location, preferred_time, age_group,
                           article_length, abstract, full_article, url
                    FROM news
                    WHERE category = ? AND news_id NOT IN ({exclude_sql})
                    ORDER BY RANDOM()
                    LIMIT ?
                """
                params = [category, *exclude, per_category]
                for row in conn.execute(query, params).fetchall():
                    rows.append(dict(row))
                    exclude.add(row["news_id"])
        return rows

    def _similarities(self, user_text: str, candidates: list[dict[str, Any]]) -> list[float]:
        docs = [
            f"{c.get('category','')} {c.get('subcategory','')} {c.get('abstract','')}"
            for c in candidates
        ]
        if TfidfVectorizer is None or cosine_similarity is None:
            return lexical_similarity(user_text, docs)
        try:
            self._ensure_vectorizer()
            if self._tfidf_vectorizer is not None:
                vecs = self._tfidf_vectorizer.transform([user_text] + docs)
            else:
                vecs = TfidfVectorizer(max_features=2000, stop_words="english").fit_transform(
                    [user_text] + docs
                )
            sims = cosine_similarity(vecs[0:1], vecs[1:]).ravel()
            return [float(x) for x in sims]
        except ValueError:
            return lexical_similarity(user_text, docs)

    def recommend(self, user_id: str, k: int = 8, mode: str | None = None, location: str | None = None, mood: str | None = None) -> dict[str, Any]:
        k = max(8, min(10, int(k)))
        categories = self.categories()
        agent = self._agent(user_id)

        # --- single DB round-trip for all read operations ---
        with db_connect(self.db_path) as conn:
            user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            if user is None:
                self.onboard_user({"user_id": user_id, "interests": [], "exploration_preference": 0.3})
                user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

            blocked = {
                r["category"]
                for r in conn.execute(
                    "SELECT category FROM user_category_prefs WHERE user_id = ? AND dislikes >= 2 AND blocked_until_step > ?",
                    (user_id, agent.step),
                ).fetchall()
            }

            memory_rows = conn.execute(
                "SELECT news_id, category FROM user_memory WHERE user_id = ? ORDER BY position DESC LIMIT 80",
                (user_id,),
            ).fetchall()
            seen_news = {r["news_id"] for r in memory_rows}
            recent_category_counts = Counter(r["category"] for r in memory_rows)

            liked_rows = conn.execute(
                """
                SELECT category, COUNT(*) AS likes
                FROM (SELECT category FROM interactions WHERE user_id = ? AND liked = 1
                      ORDER BY created_at DESC LIMIT 30)
                GROUP BY category
                """,
                (user_id,),
            ).fetchall()
            recent_liked_boosts = {r["category"]: min(0.20, 0.05 * int(r["likes"])) for r in liked_rows}

            all_prefs = {
                r["category"]: clamp(r["preference"])
                for r in conn.execute(
                    "SELECT category, preference FROM user_category_prefs WHERE user_id = ?",
                    (user_id,),
                ).fetchall()
            }

            trending = {
                r["category"]: float(r["trending_score"] or 0)
                for r in conn.execute("SELECT category, trending_score FROM category_stats")
            }

            recent_rows = conn.execute(
                """
                SELECT category, liked FROM interactions
                WHERE user_id = ?
                ORDER BY rowid DESC
                LIMIT 20
                """,
                (user_id,),
            ).fetchall()
            liked_cats = {r["category"] for r in recent_rows if r["liked"] == 1}
            disliked_cats = {r["category"] for r in recent_rows if r["liked"] == 0}

            if mode == "trending":
                candidates = self._candidate_rows(user_id, limit=25, mode="trending", blocked=blocked, location=location)
            else:
                candidates = self._fetch_candidates_conn(conn, user_id, seen_news, blocked, pool_size=25, location=location)
        # --- end single DB block ---

        latest_snapshot = get_latest_attention_snapshot()
        # 🔥 FIXED ATTENTION PIPELINE
        _norm_att = latest_snapshot.get("normalized_attention")

        if _norm_att is None or not isinstance(_norm_att, (int, float)):
            _raw = float(latest_snapshot.get("attention_score") or 0.0)
            _norm_att = _raw if _raw <= 1.0 else _raw / 100.0

        current_attention = clamp(float(_norm_att))

# 🔥 REMOVE FORCED RESET (this was breaking real-time updates)
# if current_attention < 0.05:
#     current_attention = 0.5
        attention_source = str(latest_snapshot.get("source", "frontend") or "frontend")

        cat_indices = {cat: idx for idx, cat in enumerate(categories)}
        state_overrides = {"attention_score": current_attention}

        def score_candidates(rows: list[dict[str, Any]], liked_cats: set, disliked_cats: set) -> list[dict[str, Any]]:
            if not rows:
                return []
            states = [self.build_state_from_row(user, r["category"], all_prefs, state_overrides) for r in rows]
            q_matrix = agent.q_values_batch(states)
            sims = self._similarities(user["user_interest_text"], rows)
            scored_rows = []
            for row, sim, q_row in zip(rows, sims, q_matrix):
                cat = row["category"]
                q_raw = float(q_row[cat_indices[cat]]) if cat in cat_indices else 0.0
                q_norm = float(1.0 / (1.0 + np.exp(-q_raw)))
                trend = clamp(trending.get(cat, 0.0))
                recency_boost = recent_liked_boosts.get(cat, 0.0)
                saturation = min(0.35, 0.10 * recent_category_counts.get(cat, 0))
                category_pref = all_prefs.get(cat, 0.2)
                # 🔥 STRONGER ATTENTION IMPACT (makes system responsive)
                attention_boost = 0.25 * current_attention * (1.2 if attention_source == "webcam" else 1.0)
                final = clamp(
                    0.30 * q_norm
                    + 0.24 * clamp(sim)
                    + 0.14 * trend
                    + 0.12 * category_pref
                    + attention_boost
                    + recency_boost
                    + small_randomness()
                    - saturation
                )
                if cat in liked_cats:
                    final += 0.25
                if cat in disliked_cats:
                    final -= 0.5
                final = clamp(final)
                row.update(
                    {
                        "score": round(final, 4),
                        "q_value": round(q_raw, 4),
                        "similarity": round(float(sim), 4),
                        "trending": round(trend, 4),
                        "recency_boost": round(recency_boost, 4),
                        "saturation_penalty": round(saturation, 4),
                        "hitl_decision": "auto_skip" if final < 0.03 else "ask_continue" if final < 0.50 else "keep",
                    }
                )
                scored_rows.append(row)
            return scored_rows

        scored = score_candidates(candidates, liked_cats, disliked_cats)
        scored.sort(key=lambda x: x["score"], reverse=True)

        liked_pool: list[dict[str, Any]] = []
        trending_pool: list[dict[str, Any]] = []
        random_pool: list[dict[str, Any]] = []

        for item in scored:
            cat = item["category"]
            if cat in disliked_cats:
                continue
            if cat in liked_cats:
                liked_pool.append(item)
            elif item.get("trending", 0) > 0.5:
                trending_pool.append(item)
            else:
                random_pool.append(item)

        random.shuffle(liked_pool)
        random.shuffle(trending_pool)
        random.shuffle(random_pool)

        liked_k = int(0.45 * k)
        trending_k = int(0.25 * k)
        random_k = k - liked_k - trending_k

        final_mix: list[dict[str, Any]] = []
        final_mix.extend(liked_pool[:liked_k])
        final_mix.extend(trending_pool[:trending_k])
        final_mix.extend(random_pool[:random_k])

        remaining = k - len(final_mix)
        if remaining > 0:
            leftovers = liked_pool[liked_k:] + trending_pool[trending_k:] + random_pool[random_k:]
            random.shuffle(leftovers)
            final_mix.extend(leftovers[:remaining])

        if len(final_mix) < k:
            fallback_rows = []
            for row in self._category_balanced_rows(user_id, per_category=2, blocked=blocked, exclude_ids=seen_news):
                row["source_mix"] = "balanced"
                fallback_rows.append(row)
                if len(fallback_rows) >= 30:
                    break
            extra_scored = score_candidates(fallback_rows, liked_cats, disliked_cats)
            for item in extra_scored:
                cat = item["category"]
                if cat not in disliked_cats:
                    final_mix.append(item)
            random.shuffle(final_mix)

        category_count: dict[str, int] = {}
        filtered: list[dict[str, Any]] = []
        for item in final_mix:
            cat = item["category"]
            if category_count.get(cat, 0) < 2:
                filtered.append(item)
                category_count[cat] = category_count.get(cat, 0) + 1

        selected = filtered[:k]
        random.shuffle(selected)

        logger.info(
            "recommend user=%s k=%s selected=%s",
            user_id,
            k,
            [(item["news_id"], item["category"], item["score"]) for item in selected],
        )
        return {
            "user_id": user_id,
            "k": k,
            "blocked_categories": sorted(blocked),
            "recommendations": selected,
        }

    def poll_feedback(self, user_id: str, news_id: str, liked: int) -> dict[str, Any]:
        with db_connect(self.db_path) as conn:
            news = conn.execute("SELECT category FROM news WHERE news_id = ?", (news_id,)).fetchone()
            if news is None:
                raise ValueError(f"Unknown news_id: {news_id}")
            category = news["category"]

            row = conn.execute(
                "SELECT preference, dislikes FROM user_category_prefs WHERE user_id = ? AND category = ?",
                (user_id, category),
            ).fetchone()
            old_pref = float(row["preference"]) if row else 0.2
            old_dislikes = int(row["dislikes"]) if row else 0

            pref_delta = 0.10 if liked else -0.12
            new_pref = clamp(old_pref + pref_delta)
            dislikes = 0 if liked else old_dislikes + 1
            agent = self._agent(user_id)
            blocked_until = (agent.step + 15) if (not liked and dislikes >= 2) else 0

            conn.execute(
                """
                INSERT OR REPLACE INTO user_category_prefs
                (user_id, category, preference, dislikes, blocked_until_step, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (user_id, category, new_pref, dislikes, blocked_until),
            )

        logger.info(
            "poll_feedback user=%s news=%s category=%s liked=%s delta=%.2f new_pref=%.3f",
            user_id, news_id, category, liked, pref_delta, new_pref,
        )
        return {
            "user_id": user_id,
            "news_id": news_id,
            "category": category,
            "liked": liked,
            "pref_delta": pref_delta,
            "new_pref": round(new_pref, 4),
            "message": "poll feedback applied",
        }

    def feedback(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_id = payload["user_id"]
        news_id = payload["news_id"]
        time_spent = float(payload.get("time_spent", 0))
        liked = int(payload.get("liked", 0))
        skipped = int(payload.get("skipped", 0))
        scroll_depth = float(payload.get("scroll_depth", 0.0))
        click_val = float(payload.get("click_val", 1 if liked else 0))
        poll_val = clamp(float(payload.get("poll_val", 0.5)))
        final_score = float(payload.get("final_score", 0.0))
        similarity = float(payload.get("similarity", 0.0))
        trending = float(payload.get("trending", 0.0))
        brightness = self._metric(payload, "brightness", 50.0, 0.0, 100.0)
        eye_openness = self._metric(payload, "eye_openness", 70.0, 0.0, 100.0)
        movement = self._metric(payload, "movement", 20.0, 0.0, 100.0)
        energy_score = self._metric(
            payload,
            "energy_score",
            compute_energy_score(brightness, eye_openness, movement),
            0.0,
            100.0,
        )
        gaze_score = self._metric(
            payload,
            "gaze_score",
            compute_gaze_score(brightness, eye_openness, movement),
            0.0,
            1.0,
        )
        normalized_attention = payload.get("normalized_attention", payload.get("attention_score", 0.5))
        normalized_attention = normalize_0_1(normalized_attention)
        if normalized_attention <= 0 and (energy_score > 0 or gaze_score > 0):
            normalized_attention = normalize_0_1(compute_attention_score(energy_score, gaze_score))
        attention_score = normalized_attention
        face_detected = int(bool(payload.get("face_detected", 0)))
        attention_source = str(payload.get("attention_source", payload.get("source", "frontend")) or "frontend")

        with db_connect(self.db_path) as conn:
            news = conn.execute("SELECT category FROM news WHERE news_id = ?", (news_id,)).fetchone()
            if news is None:
                raise ValueError(f"Unknown news_id: {news_id}")
            category = news["category"]

            user_row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
            all_prefs = {
                r["category"]: clamp(r["preference"])
                for r in conn.execute(
                    "SELECT category, preference FROM user_category_prefs WHERE user_id = ?",
                    (user_id,),
                ).fetchall()
            }

        long_term_history = clamp(all_prefs.get(category, 0.2))
        interaction_score = compute_interaction_score(click_val, poll_val, time_spent, long_term_history)

        reward = compute_reward(liked, time_spent, similarity)
        state_overrides = {"attention_score": attention_score, "interaction_score": interaction_score}
        state = self.build_state_from_row(user_row, category, all_prefs, state_overrides)

        categories = self.categories()
        agent = self._agent(user_id)
        q_value = float(agent.q_values(state)[categories.index(category)]) if category in categories else 0.0

        pref_delta = 0.14 + 0.08 * attention_score if liked else -0.18 - 0.10 * (1.0 - attention_score)
        if time_spent > 6:
            pref_delta += 0.05
        elif time_spent < 2:
            pref_delta -= 0.05
        if time_spent > 15:
            pref_delta += 0.08 if liked else -0.08

        with db_connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT preference, dislikes FROM user_category_prefs WHERE user_id = ? AND category = ?",
                (user_id, category),
            ).fetchone()
            old_pref = float(row["preference"]) if row else 0.2
            old_dislikes = int(row["dislikes"]) if row else 0
            new_pref = clamp(old_pref + pref_delta)
            dislikes = 0 if liked else old_dislikes + 1
            if not liked and attention_score < 0.35:
                blocked_until = agent.step + 30
            elif dislikes >= 2:
                blocked_until = agent.step + 20
            else:
                blocked_until = 0

            conn.execute(
                """
                INSERT OR REPLACE INTO user_category_prefs
                (user_id, category, preference, dislikes, blocked_until_step, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (user_id, category, new_pref, dislikes, blocked_until),
            )
            conn.execute(
                """
                INSERT INTO interactions
                (user_id, news_id, category, time_spent, liked, skipped, scroll_depth,
                 click_val, reward, attention_score, interaction_score, final_score,
                 q_value, similarity, trending, brightness, eye_openness, movement,
                 energy_score, gaze_score, normalized_attention, attention_source,
                 poll_val, long_term_history)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id, news_id, category, time_spent, liked, skipped, scroll_depth,
                    click_val, reward, attention_score, interaction_score, final_score,
                    q_value, similarity, trending, brightness, eye_openness, movement,
                    energy_score, gaze_score, normalized_attention, attention_source,
                    poll_val, long_term_history,
                ),
            )
            conn.execute(
                """
                INSERT INTO attention_events
                (user_id, news_id, brightness, eye_openness, movement, energy_score,
                 gaze_score, attention_score, normalized_attention, face_detected, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id, news_id, brightness, eye_openness, movement, energy_score,
                    gaze_score, attention_score, normalized_attention, face_detected, attention_source,
                ),
            )
            stats = conn.execute(
                "SELECT impressions, clicks, likes, avg_time FROM category_stats WHERE category = ?",
                (category,),
            ).fetchone()
            impressions = int(stats["impressions"] if stats else 0) + 1
            clicks = int(stats["clicks"] if stats else 0) + int(click_val > 0)
            likes = int(stats["likes"] if stats else 0) + liked
            avg_time = ((float(stats["avg_time"] if stats else 0) * (impressions - 1)) + time_spent) / impressions
            log_denominator = max(math.log1p(impressions + 1), 1.0)
            trending_score = clamp(
                0.45 * (math.log1p(clicks) / log_denominator)
                + 0.25 * (math.log1p(likes) / log_denominator)
                + 0.15 * min(avg_time / 20.0, 1.0)
                + 0.15 * attention_score
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO category_stats
                (category, impressions, clicks, likes, avg_time, trending_score, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (category, impressions, clicks, likes, avg_time, trending_score),
            )
            current_user = conn.execute(
                "SELECT attention_score, interaction_score, exploration_signal FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            old_attention = float(current_user["attention_score"]) if current_user else attention_score
            old_interaction = float(current_user["interaction_score"]) if current_user else interaction_score
            old_exploration = float(current_user["exploration_signal"] or 0.2) if current_user else 0.2
            smoothed_attention = clamp(0.35 * old_attention + 0.65 * attention_score)
            smoothed_interaction = clamp(0.35 * old_interaction + 0.65 * interaction_score)
            exploration_delta = -0.02 if (liked and time_spent > 6) else 0.02 if not liked else 0.0
            new_exploration = clamp(old_exploration + exploration_delta)
            conn.execute(
                """
                UPDATE users
                SET attention_score = ?, interaction_score = ?, recent_activity = ?,
                    exploration_signal = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (
                    smoothed_attention,
                    smoothed_interaction,
                    clamp((smoothed_interaction + smoothed_attention) / 2),
                    new_exploration,
                    user_id,
                ),
            )
            pos = conn.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM user_memory WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]
            conn.execute(
                """
                INSERT OR IGNORE INTO user_memory(user_id, position, news_id, category)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, pos, news_id, category),
            )
            conn.execute(
                """
                DELETE FROM user_memory
                WHERE user_id = ? AND position <= (
                    SELECT COALESCE(MAX(position), 0) - 100 FROM user_memory WHERE user_id = ?
                )
                """,
                (user_id, user_id),
            )

        next_state = self.build_state_from_row(user_row, category, all_prefs, state_overrides)
        loss = agent.observe(state, category, reward, next_state, done=False)
        logger.info(
            "feedback user=%s news=%s category=%s reward=%.3f final_score=%.3f q=%.3f loss=%s",
            user_id, news_id, category, reward, final_score, q_value, loss,
        )
        return {
            "user_id": user_id,
            "news_id": news_id,
            "category": category,
            "reward": reward,
            "interaction_score": interaction_score,
            "attention_score": attention_score,
            "brightness": brightness,
            "eye_openness": eye_openness,
            "movement": movement,
            "energy_score": energy_score,
            "gaze_score": gaze_score,
            "normalized_attention": normalized_attention,
            "loss": loss,
            "blocked": dislikes >= 2,
            "message": "feedback applied and model updated",
        }

    def update_model(self, user_id: str) -> dict[str, Any]:
        agent = self._agent(user_id)
        loss = agent.train_step()
        agent.save()
        return {"user_id": user_id, "step": agent.step, "epsilon": agent.epsilon, "loss": loss}

    @staticmethod
    def _metric(payload: dict[str, Any], key: str, default: float, low: float, high: float) -> float:
        try:
            value = float(payload.get(key, default))
        except (TypeError, ValueError):
            value = default
        if not np.isfinite(value):
            value = default
        return max(low, min(high, value))
